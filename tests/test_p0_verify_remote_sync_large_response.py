# -*- coding: utf-8 -*-
"""CI-ENV-2026-09-19：verify_remote_sync.py 大响应被网络层截断的回归测试。

事故背景：P0（入库批次/有效期）经 API 通道推送后，收尾的
`verify_remote_sync.py` 抛 JSONDecodeError：

    Expecting property name enclosed in double quotes: line 10256 column 7

排查结论：**不是推送漏推**，而是沙箱网络层对单次 HTTP 响应有约 416KB 的
静默截断上限。实测 `git/trees/{sha}?recursive=1` 在 1461 文件（响应 465KB）
的仓库上必然被切断在 425984 字节处、正好切在 JSON 字符串中间，导致
`json.loads` 永远失败 —— 即该脚本在此环境"永远无法通过校验"，
把一次真实成功的推送误判成失败。

危害：这类"假红"会掩盖真红（真正漏推时反倒没人信），与脚本自身
docstring 里 CI-ENV-2026-09-11 事故的初衷背道而驰。

修复：识别到响应触顶/解析失败时改走 Range 分段拼接（HTTP 206 不受该上限
约束），且分段路径不做静默降级——任何异常一律显式抛出，避免"校验没跑成
却报成功"。
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "verify_remote_sync.py")


@pytest.fixture(scope="module")
def sync_mod():
    """把脚本当模块加载（脚本名不是合法包路径，需用 spec 显式加载）。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_vrs_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_verify_remote_sync_has_chunked_fetch():
    """分段取回函数必须存在（缺了就说明修复被回退，大仓库必红）。"""
    src = open(SCRIPT, encoding="utf-8").read()
    tree = ast.parse(src)
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "_curl_get_chunked" in names, (
        "verify_remote_sync.py 缺少 _curl_get_chunked："
        "大 tree 响应会被网络层截断，校验必然 JSONDecodeError"
    )


def test_verify_remote_sync_chunk_threshold_below_network_limit():
    """分段阈值必须低于实测截断点 425984B，否则仍会把半截 JSON 交给 loads。"""
    src = open(SCRIPT, encoding="utf-8").read()
    tree = ast.parse(src)
    limits = [
        n.value.value for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name) and t.id == "_RESPONSE_SIZE_LIMIT"
        and isinstance(n.value, ast.Constant)
    ]
    assert limits, "未找到 _RESPONSE_SIZE_LIMIT 常量"
    assert limits[0] < 425984, (
        f"_RESPONSE_SIZE_LIMIT={limits[0]} 未低于实测截断点 425984B，"
        "触顶响应仍会被当成完整 JSON 解析"
    )


def test_verify_remote_sync_chunked_fetch_parses_large_body(sync_mod, tmp_path, monkeypatch):
    """分段路径能把超长响应拼成合法 JSON（用假 curl 造 2 段 206 + 末段）。"""
    payload = '{"tree":[' + ",".join(
        '{"path":"f%04d.py","mode":"100644","type":"blob","sha":"%040d"}' % (i, i)
        for i in range(6000)
    ) + '],"truncated":false}'
    body = payload.encode()
    assert len(body) > sync_mod._CHUNK_SIZE, "用例载荷必须超过单段长度，否则测不到分段"

    chunk = sync_mod._CHUNK_SIZE
    calls: list[str] = []

    class FakeProc:
        def __init__(self, out: bytes):
            self.stdout = out

    def fake_run(cmd, capture_output=True, **kw):
        # 找出本次请求的 Range 起点
        rng = [c for c in cmd if c.startswith("Range: bytes=")]
        assert rng, "分段路径必须带 Range 头"
        start = int(rng[0].split("=")[1].split("-")[0])
        calls.append(rng[0])
        piece = body[start:start + chunk]
        code = "206" if len(piece) == chunk else "206"
        return FakeProc(piece + b"\n" + code.encode())

    monkeypatch.setattr(sync_mod.subprocess, "run", fake_run)
    got = sync_mod._curl_get_chunked("/repos/o/r/git/trees/abc?recursive=1", "t", "1.2.3.4")

    assert got["truncated"] is False
    assert len(got["tree"]) == 6000, "分段拼接后条目数应与原始响应一致"
    assert len(calls) >= 2, "超长响应必须分多段取回"


def test_verify_remote_sync_no_silent_success_on_bad_json(sync_mod, monkeypatch):
    """响应既触顶又拼不出合法 JSON 时必须报错，不能返回空 dict 冒充成功。

    这是本次事故的核心防线：校验脚本"没跑成"却回报成功，比直接报错更危险。
    """
    class FakeProc:
        stdout = b"this-is-not-json{broken\n206"

    monkeypatch.setattr(sync_mod.subprocess, "run",
                        lambda *a, **kw: FakeProc())
    with pytest.raises(RuntimeError):
        sync_mod._curl_get_chunked("/repos/o/r/git/trees/abc?recursive=1", "t", "1.2.3.4")


def test_verify_remote_sync_local_tree_matches_git_ls_tree():
    """本地 tree 采集口径必须与 git ls-tree -r HEAD 一致（防口径漂移）。"""
    out = subprocess.run(
        ["git", "-C", REPO_ROOT, "-c", "core.quotepath=false", "ls-tree", "-r", "HEAD"],
        capture_output=True, text=True, check=True).stdout
    expected = sum(1 for line in out.splitlines() if line.strip())
    assert expected > 0, "本地仓库应有文件"

    import importlib.util

    spec = importlib.util.spec_from_file_location("_vrs_local_probe", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    got = mod.local_tree()
    assert len(got) == expected, (
        f"local_tree() 采到 {len(got)} 项，git ls-tree 有 {expected} 项，口径漂移"
    )

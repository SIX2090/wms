#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""远端/本地 tree 同步校验（CI-ENV-2026-09-11 防呆）。

背景事故：2026-09-11 API 通道推送漏掉一个本地提交（native_api import 修复），
远端带着坏代码跑了 15 轮红 CI，而本地全绿——"测试红了不知道是谁的锅"。
本脚本对本地 HEAD 与远端 main 做逐文件 blob sha 对比，任何漏推/内容漂移都会暴露。

用法：
    GH_TOKEN=xxx python3 scripts/verify_remote_sync.py
    GH_TOKEN=xxx python3 scripts/verify_remote_sync.py --repo SIX2090/wms

退出码：0 = 完全同步；1 = 存在差异或 API 失败。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# CI-ENV-2026-09-12：与 api_push.py 同源问题——本沙箱里 Python 侧到
# api.github.com 的 TLS 握手会被掐断（改 /etc/hosts 指向同一 IP 也无效），
# 而 curl --resolve 指定 IP 稳定可用。故优先 curl + 多 IP 轮换，
# 失败/无 curl 时退回 urllib 重试。
CURL_IPS = ["140.82.112.6", "20.205.243.168", "140.82.112.5", "140.82.113.5"]

# CI-ENV-2026-09-19：git/trees/{sha}?recursive=1 在大仓库上（1465 文件、约
# 467KB）取回会失败，且**失败形态取决于是否带 token**——两种路径的成因不同，
# 必须分别处理：
#
#   ① 匿名（无 Authorization）：沙箱网络层把单次响应静默截断在约 416KB
#      （实测 425984B，正好切在 JSON 字符串中间）→ json.loads 必然报
#      "Expecting property name..."。此路径下 GitHub **认 Range**，返回
#      HTTP 206，可分段拼回完整响应。
#   ② 带 token：GitHub **忽略 Range，一律返回 HTTP 200 + 完整响应**
#      （实测 466980B 完整可解析，未截断）。此路径拿到 200 就已是全量，
#      直接解析即可。
#
# ⚠️ 曾经的错误修法（务必别改回去）：无脑按 _CHUNK_SIZE 循环发 Range 拼接。
#    它在①下碰巧能work，但在②下每段都收到同一份完整响应，拼接结果是把
#    全量 JSON 重复 N 遍 → 解析报 "Unterminated string"。即"修好一个路径、
#    弄坏另一个路径"。正确做法是**按响应码分流**：200 即全量、206 才拼接。
_CHUNK_SIZE = 200_000


def _curl_get_chunked(path: str, token: str, ip: str) -> dict | None:
    """取回可能超长的响应：按 HTTP 状态码分流处理 200（全量）/ 206（需拼接）。"""
    parts: list[bytes] = []
    offset = 0
    while True:
        proc = subprocess.run(
            ["curl", "-s", "--max-time", "120",
             "-H", "Authorization: Bearer " + token,
             "-H", "Accept: application/vnd.github+json",
             "-H", f"Range: bytes={offset}-{offset + _CHUNK_SIZE - 1}",
             "--resolve", f"api.github.com:443:{ip}",
             "-o", "-", "-w", "\n%{http_code}",
             "https://api.github.com" + path],
            capture_output=True)
        raw = proc.stdout
        if b"\n" not in raw:
            return None
        body, _, code = raw.rpartition(b"\n")
        code = code.decode().strip()
        if code == "0":
            return None
        if code not in ("200", "206"):
            raise RuntimeError(
                f"GitHub API {path} -> HTTP {code}: {body[:400].decode('utf-8', 'replace')}")
        parts.append(body)
        # 200：服务端忽略 Range，本次已是完整响应 → 立即停止（再循环会把全量重复拼接）
        if code == "200":
            break
        # 206：只拿到一段，短包即末段，否则继续取下一段
        if len(body) < _CHUNK_SIZE:
            break
        offset += _CHUNK_SIZE
    joined = b"".join(parts)
    if not joined.strip():
        return {}
    try:
        return json.loads(joined.decode("utf-8", "replace"))
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"GitHub API {path} 响应无法解析（共取回 {len(joined)}B、{len(parts)} 段）：{e}") from e


def _curl_get(path: str, token: str) -> dict | None:
    for ip in CURL_IPS:
        # recursive tree 是大响应端点，统一走按状态码分流的取回逻辑
        if "?recursive=1" in path:
            return _curl_get_chunked(path, token, ip)
        proc = subprocess.run(
            ["curl", "-s", "--max-time", "120", "-H", "Authorization: Bearer " + token,
             "-H", "Accept: application/vnd.github+json",
             "--resolve", f"api.github.com:443:{ip}",
             "-w", "\n%{http_code}",
             "https://api.github.com" + path],
            capture_output=True)
        raw = proc.stdout.decode("utf-8", "replace")
        if "\n" not in raw:
            print(f"  curl via {ip} 连接失败，换下一个 IP", file=sys.stderr)
            continue
        body, _, code = raw.rpartition("\n")
        code = code.strip()
        if code == "0":
            print(f"  curl via {ip} 连接失败（http 0），换下一个 IP", file=sys.stderr)
            continue
        if not code.startswith("2"):
            raise RuntimeError(f"GitHub API {path} -> HTTP {code}: {body[:400]}")
        try:
            return json.loads(body) if body.strip() else {}
        except json.JSONDecodeError as e:
            print(f"  curl via {ip} 响应解析失败（{len(body)}B），改走分段取回：{e}",
                  file=sys.stderr)
            return _curl_get_chunked(path, token, ip)
    return None


def req(path: str, token: str) -> dict:
    if shutil.which("curl"):
        got = _curl_get(path, token)
        if got is not None:
            return got
        raise RuntimeError(f"GitHub API 请求失败：候选 IP {CURL_IPS} 均被连接层掐断")
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            r = urllib.request.Request("https://api.github.com" + path)
            r.add_header("Authorization", "Bearer " + token)
            r.add_header("Accept", "application/vnd.github+json")
            with urllib.request.urlopen(r, timeout=120) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:  # noqa: BLE001 - 网络抖动重试
            last_err = e
            print(f"  retry {attempt + 1}/3: {e}", file=sys.stderr)
            time.sleep(2)
    raise RuntimeError(f"GitHub API 请求失败: {last_err}")


def local_tree() -> dict[str, tuple[str, str]]:
    """本地 HEAD 的 path -> (mode, blob sha)（core.quotepath=false 保中文路径原样）。"""
    out = subprocess.run(
        ["git", "-C", REPO_ROOT, "-c", "core.quotepath=false",
         "ls-tree", "-r", "HEAD"],
        capture_output=True, text=True, check=True).stdout
    tree: dict[str, tuple[str, str]] = {}
    for line in out.splitlines():
        meta, path = line.split("\t", 1)
        parts = meta.split()
        tree[path] = (parts[0], parts[2])
    return tree


def remote_tree(repo: str, token: str) -> tuple[str, dict[str, tuple[str, str]]]:
    head = req(f"/repos/{repo}/commits/main", token)["sha"]
    tree = req(f"/repos/{repo}/git/trees/{head}?recursive=1", token)
    if tree.get("truncated"):
        raise RuntimeError("远端 tree 被截断，无法完整校验")
    files = {e["path"]: (e["mode"], e["sha"])
             for e in tree["tree"] if e["type"] == "blob"}
    return head, files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("WMS_REPO", "SIX2090/wms"))
    args = ap.parse_args()
    token = os.environ.get("GH_TOKEN")
    if not token:
        print("缺少 GH_TOKEN 环境变量", file=sys.stderr)
        return 1

    local = local_tree()
    head, remote = remote_tree(args.repo, token)
    print(f"远端 HEAD: {head[:10]} | 本地文件: {len(local)} | 远端文件: {len(remote)}")

    missing_remote = sorted(set(local) - set(remote))
    missing_local = sorted(set(remote) - set(local))
    content_diff = sorted(
        p for p in set(local) & set(remote) if local[p][1] != remote[p][1])
    # mode 差异：内容一样但可执行位不同，git 视作不同对象（tree sha 也不同），
    # 且危害隐蔽——.githooks/pre-commit 丢 100755 会让钩子在 Linux/Mac 上
    # 静默不执行，防 BUG 规则形同虚设。历史 api_push.py 硬编码 100644 踩过。
    mode_diff = sorted(
        p for p in set(local) & set(remote) if local[p][0] != remote[p][0])

    ok = True
    if missing_remote:
        ok = False
        print(f"远端缺失 {len(missing_remote)} 个文件（本地有、远端无）——疑似漏推:")
        for p in missing_remote[:50]:
            print(f"  - {p}")
    if missing_local:
        ok = False
        print(f"远端多出 {len(missing_local)} 个文件（远端有、本地无）:")
        for p in missing_local[:50]:
            print(f"  + {p}")
    if content_diff:
        ok = False
        print(f"内容不一致 {len(content_diff)} 个文件:")
        for p in content_diff[:50]:
            print(f"  * {p}")
    if mode_diff:
        ok = False
        print(f"文件模式(mode)不一致 {len(mode_diff)} 个文件——可执行位丢失会让钩子/脚本无法直接运行:")
        for p in mode_diff[:50]:
            print(f"  ! {p}  本地={local[p][0]} 远端={remote[p][0]}")

    if ok:
        print("✓ 本地与远端 tree blob 级完全同步（含文件模式）")
        return 0
    print("✗ 推送同步校验失败——禁止认为'推完了'，逐个差异处理后重试",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

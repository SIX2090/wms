# -*- coding: utf-8 -*-
"""目录创建必须并发安全（AI-CI-GREEN-004）回归测试。

背景（真实 CI 故障，非推测）：
    CI 的 verify-and-smoke job 失败，失败详情（verify-failures artifact）显示

        ImportError while loading conftest 'tests/conftest.py'
        app/app.py:2873: in <module>
            os.makedirs(UPLOAD_FOLDER)
        E   FileExistsError: [Errno 17] File exists: '.../app/static/uploads'

    根因是 **TOCTOU 竞态**：`if not os.path.exists(d): os.makedirs(d)` 这种写法，
    在 CI 工作区（全新 checkout、目录不存在）下，verify_*.py 以 4 路并发各起一个
    进程导入 app.py，两个进程可能**同时**通过 exists 检查，随后一个建成、
    另一个抛 FileExistsError，把 conftest 导入直接打断。

    为什么本地复现不出来：开发机的 app/static/uploads 早就存在，竞态窗口为 0。
    所以这是一个**只在 CI 出现**的缺陷——正是「本地全绿、CI 必红」的典型成因。

    注：该竞态由 CI-PERF-2026-09-17（verify 改并发调度）引入暴露面，
    但它本身是 app 代码里长期存在的写法问题，故记在 AI-CI-GREEN-004 名下。

本测试锁定两件事：

T1. 全仓 `os.makedirs(...)` 调用必须都带 `exist_ok=True`。
    —— 这是消除 TOCTOU 竞态的标准做法；缺它就可能在并发导入/启动时踩雷。
T2. 不得出现 `if not os.path.exists(...): os.makedirs(...)` 这种
    「先检查后创建」的组合写法（即使补了别的地方，这种模式本身就是竞态）。
"""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 扫描范围：真正会被并发启动的入口代码。
# 不含 tests/ 本身（测试脚本多为单进程辅助，且 verify_* 里的临时目录无并发竞争），
# 也不含 docs/ 与构建产物。
SCAN_DIRS = ["app", "scripts"]
SKIP_PARTS = {"__pycache__", "node_modules", "migrations", "instance", "backups"}


def _iter_py_files():
    """遍历待扫描的 .py。

    用 os.walk + 顶层 prune，而不是 Path.rglob：rglob 会**先走进去再过滤**，
    而 app/ 下有 android-native-wms（Kotlin/Gradle 工程）、static/uploads、
    instance 等大盘子，实测会让本测试跑上百秒。prune 掉这些目录后降至毫秒级。
    """
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [x for x in dirnames if x not in SKIP_PARTS]
            for fn in filenames:
                if fn.endswith(".py"):
                    yield Path(dirpath) / fn


def _mask_by_positions(text: str) -> str:
    """按 token 位置把注释/字符串替换成空白，保持所有偏移不变。

    性能注意：必须**预计算行首偏移**。早先写成「每个 token 都 splitlines 一次、
    再 sum(len(x) for x in lines[:r-1]) 求偏移」，在 app.py（1.5MB / 3 万行）上
    退化成 O(n²)，实测单次扫描跑满 120s 不返回。改为前缀和数组后是毫秒级。
    """
    import io
    import tokenize

    chars = list(text)
    # 行首偏移前缀和：line_start[r] = 第 r 行（1-based）在 text 中的起始下标
    line_start = [0]
    for ln in text.splitlines(keepends=True):
        line_start.append(line_start[-1] + len(ln))
    total = len(text)

    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type not in (tokenize.COMMENT, tokenize.STRING):
                continue
            (srow, scol), (erow, ecol) = tok.start, tok.end
            for r in range(srow, erow + 1):
                if r >= len(line_start):
                    break
                a = scol if r == srow else 0
                b = ecol if r == erow else line_start[r] - line_start[r - 1]
                start = line_start[r - 1] + a
                for i in range(start, min(start + (b - a), total)):
                    if chars[i] != "\n":
                        chars[i] = " "
    except (tokenize.TokenError, IndentationError):
        return text
    return "".join(chars)


def _makedirs_calls(text: str):
    """产出 (行号, 参数字符串, 是否带 exist_ok) —— 用括号配对取完整调用。

    不能用 `re.compile(r"os\\.makedirs\\((.*?)\\)", re.S)`：非贪婪会在
    **第一个右括号**停下，于是 `os.makedirs(os.path.dirname(p), exist_ok=True)`
    被截成 `os.path.dirname(p`，exist_ok 看不到 → 误报。
    实测该 bug 一次报出 5 个假阳性（含本文件注释里的示例）。
    """
    needle = "os.makedirs("
    idx = 0
    while True:
        i = text.find(needle, idx)
        if i < 0:
            return
        j = i + len(needle)
        depth = 1
        while j < len(text) and depth:
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
            j += 1
        args = text[i + len(needle): j - 1]
        line_no = text[:i].count("\n") + 1
        yield line_no, args, "exist_ok" in args
        idx = j


def test_t1_every_makedirs_has_exist_ok():
    """T1：所有 os.makedirs 必须带 exist_ok=True（消除竞态的根治写法）。"""
    offenders = []
    for f in _iter_py_files():
        raw = f.read_text(encoding="utf-8", errors="replace")
        text = _mask_by_positions(raw)  # 抹掉注释与字符串里的示例代码
        for line_no, _args, has_ok in _makedirs_calls(text):
            if not has_ok:
                offenders.append(f"{f.relative_to(ROOT)}:{line_no}")
    assert not offenders, (
        "以下 os.makedirs 调用缺少 exist_ok=True，在并发启动/导入时会抛 "
        "FileExistsError（AI-CI-GREEN-004）：\n  " + "\n  ".join(offenders)
    )


def test_t2_no_check_then_create_pattern():
    """T2：不得再用 `if not os.path.exists(d): os.makedirs(d)` 的竞态组合。

    实现注意：**不要用正则去跨行匹配**。早先写成
        r"if\\s+not\\s+os\\.path\\.exists\\(...\\)\\s*:\\s*\\n(?P<body>(?:[ \\t]+.*\\n)*?)..."
    其中 `(?:[ \\t]+.*\\n)*?` 是嵌套量词，在 app.py 这种上万行文件上会**灾难性回溯**，
    实测直接把测试跑挂（90s+ 不返回、100% CPU）。改为逐行扫描：命中 `exists` 检查行后，
    向下看有限几行（跳过注释/空行/续行）是否紧跟同一路径的 makedirs。
    """
    import re as _re

    exists_re = _re.compile(r"if\s+not\s+os\.path\.exists\((?P<arg>[^)]*)\)\s*:")
    makedirs_re = _re.compile(r"os\.makedirs\((?P<arg>[^)]*)\)")

    offenders = []
    for f in _iter_py_files():
        text = _mask_by_positions(f.read_text(encoding="utf-8", errors="replace"))
        lines = text.splitlines()
        for i, line in enumerate(lines):
            m = exists_re.search(line)
            if not m:
                continue
            target = m.group("arg").strip()
            # 只往下看 5 行：真实的「检查后立即创建」必定紧邻，
            # 隔太远就不是同一个逻辑块，不该误判。
            for j in range(i + 1, min(i + 6, len(lines))):
                nxt = lines[j].strip()
                if not nxt:  # 空行
                    continue
                mm = makedirs_re.search(nxt)
                if mm and mm.group("arg").strip() == target:
                    offenders.append(f"{f.relative_to(ROOT)}:{j + 1}  ({target})")
                break  # 只看第一个非空行
    assert not offenders, (
        "以下位置使用了「先 os.path.exists 检查、再 os.makedirs 创建」的 TOCTOU "
        "竞态写法，应直接 `os.makedirs(path, exist_ok=True)`（AI-CI-GREEN-004）：\n  "
        + "\n  ".join(offenders)
    )


def test_t3_upload_folder_is_concurrency_safe():
    """T3：曾出事的那两处（UPLOAD_FOLDER / BACKUP_DIR）必须保持 exist_ok=True。"""
    src = (ROOT / "app" / "app.py").read_text(encoding="utf-8")
    code = _mask_by_positions(src)
    assert re.search(r"os\.makedirs\(UPLOAD_FOLDER,\s*exist_ok=True\)", code), (
        "app/app.py 的 UPLOAD_FOLDER 创建又变回了不安全写法——这正是 AI-CI-GREEN-004 "
        "CI 报错的原始位置"
    )
    assert re.search(r"os\.makedirs\(BACKUP_DIR,\s*exist_ok=True\)", code), (
        "app/app.py 的 BACKUP_DIR 创建缺少 exist_ok=True"
    )


def test_t4_scanner_self_check():
    """T4：自检——扫描器既要能认出真阳性，也不能被注释/字符串示例骗到。"""
    # 真阳性：裸调用
    assert [r for r in _makedirs_calls("os.makedirs(d)")] == [(1, "d", False)]
    # 真阴性：带 exist_ok
    assert [r for r in _makedirs_calls("os.makedirs(d, exist_ok=True)")] == [
        (1, "d, exist_ok=True", True)
    ]
    # 嵌套括号（旧正则就栽在这里）：必须看到外层的 exist_ok
    nested = "os.makedirs(os.path.dirname(p), exist_ok=True)"
    assert [ok for _, _, ok in _makedirs_calls(nested)] == [True], (
        "嵌套括号场景解析错误——这正是旧正则误报 5 处的原因"
    )
    # 注释里的示例不得被算作违规
    masked = _mask_by_positions("# 示例：os.makedirs(UPLOAD_FOLDER)\nx = 1\n")
    assert list(_makedirs_calls(masked)) == [], "注释中的示例代码被误判为真实调用"
    # 字符串里的示例同样不算
    masked2 = _mask_by_positions('msg = "用法：os.makedirs(d)"\n')
    assert list(_makedirs_calls(masked2)) == [], "字符串中的示例代码被误判为真实调用"


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL PASSED")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lint_no_raw_post_fetch.py
==========================

防回归扫描器：禁止在 ``app/static/js/`` 下裸调 ``fetch`` 发送非 GET 请求。

背景
----
之前在 ``app/static/js/app.js`` 中发现 5 处 ``fetch(url, {method: 'POST'})`` 调用
没有走 ``csrfFetch`` 统一封装，导致 CSRF 失败，物料批量删除不可用。
本脚本 + ``.githooks/pre-commit`` 钩子用于防止再有人犯同样的错。

规则
----
扫描 ``app/static/js/`` 下所有 ``.js`` 文件，匹配形如::

    fetch(url, { method: 'POST' })   # 或 PUT / DELETE / PATCH

的"裸调"调用。

白名单（即使匹配也不报错）：
1. ``app/static/js/app.js`` 顶部 30 行内的 ``if (typeof csrfFetch !== 'function')``
   回退定义块（含 ``csrfFetch`` 内部对 ``fetch`` 的 ``return``）。
2. ``csrfFetch`` 函数体内部的 ``return fetch(...)`` 调用（任意文件）。
3. 注释里的（行注释 ``//`` 与块注释 ``/* ... */`` 都会被剔除）。

用法
----
::

    python3 scripts/lint_no_raw_post_fetch.py            # 默认 --check
    python3 scripts/lint_no_raw_post_fetch.py --check    # 同上
    python3 scripts/lint_no_raw_post_fetch.py --help

退出码
------
* ``0``：未发现违规。
* ``1``：发现至少一处违规。
* ``2``：参数错误 / 文件无法读取。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

# 仓库根目录（脚本所在位置向上两级：scripts/ -> 仓库根）
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SCAN_DIR = REPO_ROOT / "app" / "static" / "js"

# 匹配 "裸调 fetch 发送非 GET 请求"：
#   fetch(url, { method: 'POST' ... })
# 说明：``[^)]*`` 排除右括号，能跨行匹配（无需 DOTALL），且已支持跨多行的
# options 对象；method 的大小写不敏感。
PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\bfetch\s*\([^)]*?method\s*:\s*[\'\"]?(POST|PUT|DELETE|PATCH)\b",
        re.IGNORECASE,
    ),
]

# ``app.js`` 顶部多少行属于 ``csrfFetch`` 回退定义块（白名单窗口）。
APPJS_FALLBACK_WINDOW = 30

# ---------------------------------------------------------------------------
# 注释剔除
# ---------------------------------------------------------------------------

# 块注释 /* ... */（跨行，DOTALL 开启）
_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
# 行注释 // ... （到换行为止）
_COMMENT_LINE = re.compile(r"//[^\n\r]*")


def strip_comments(text: str) -> str:
    """
    去掉 JS 注释（行注释 + 块注释），但**保持字符串长度不变**（用空格填充）。

    这样正则匹配拿到的偏移量仍然能映射回原文，用于计算行号与取源码片段。
    """
    text = _COMMENT_BLOCK.sub(lambda m: " " * len(m.group(0)), text)
    text = _COMMENT_LINE.sub(lambda m: " " * len(m.group(0)), text)
    return text


# ---------------------------------------------------------------------------
# csrfFetch 函数体定位
# ---------------------------------------------------------------------------

# 简单识别以下形式的 csrfFetch 定义（覆盖声明式 + 表达式式 + 箭头函数）：
#   function csrfFetch(url, options) { ... }
#   const csrfFetch = function (url, options) { ... };
#   const csrfFetch = (url, options) => { ... };
#   window.csrfFetch = function (...) { ... };
_CSRF_FN_DECL = re.compile(r"\bcsrfFetch\b")


def _skip_balanced(text: str, start: int, open_ch: str, close_ch: str) -> int:
    """
    从 ``start``（指向 ``open_ch``）开始向后扫描，返回与之匹配的 ``close_ch``
    之后的位置索引。若到文本末尾仍未闭合，返回 ``-1``。
    """
    if start >= len(text) or text[start] != open_ch:
        return -1
    depth = 0
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def _find_function_body(text: str, name_pos: int) -> "Tuple[int, int] | None":
    """
    给定 ``csrfFetch`` 标识符在 text 中的起始偏移 ``name_pos``，尝试找到
    其函数体（花括号 ``{...}``）的 ``(body_start, body_end)``，其中
    ``body_start`` 是 ``{`` 之后第一个字符，``body_end`` 是 ``}`` 索引（包含）。
    若判断为非函数定义或找不到匹配括号，返回 ``None``。
    """
    n = len(text)

    # 取前后文判断是否为函数定义
    before = text[max(0, name_pos - 12):name_pos]
    after = text[name_pos:name_pos + 64]

    is_decl = False
    # 情形 A：function csrfFetch( ... ) { ... }
    if re.search(r"\bfunction\s+$", before):
        is_decl = True
    # 情形 B：csrfFetch = function (...)  或  csrfFetch = (...) =>
    elif re.search(r"=\s*$", before) and re.match(
        r"\s*(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)", after
    ):
        is_decl = True
    if not is_decl:
        return None

    # 跳过参数列表：找下一个 (
    paren = text.find("(", name_pos)
    if paren == -1:
        return None
    after_paren = _skip_balanced(text, paren, "(", ")")
    if after_paren == -1:
        return None

    # 跳过空白
    i = after_paren
    while i < n and text[i] in " \t\r\n":
        i += 1

    # 情形：function () { ... }  或  () => { ... }
    if i < n and text[i] == "{":
        brace = i
    elif i + 1 < n and text[i] == "=" and text[i + 1] == ">":
        # 跳过 => 后的空白
        i += 2
        while i < n and text[i] in " \t\r\n":
            i += 1
        if i >= n or text[i] != "{":
            return None
        brace = i
    else:
        return None

    end = _skip_balanced(text, brace, "{", "}")
    if end == -1:
        return None
    body_end = end - 1  # 指向 '}'
    return (brace + 1, body_end)


def find_csrf_fetch_bodies(text: str) -> List[Tuple[int, int]]:
    """
    扫描 text，找出所有 ``csrfFetch`` 函数体的 ``(start, end)`` 区间。
    """
    bodies: List[Tuple[int, int]] = []
    for m in _CSRF_FN_DECL.finditer(text):
        body = _find_function_body(text, m.start())
        if body is not None:
            bodies.append(body)
    return bodies


def is_inside_csrf_fetch(pos: int, bodies: List[Tuple[int, int]]) -> bool:
    """位置 ``pos`` 是否落在任一 csrfFetch 函数体内。"""
    for s, e in bodies:
        if s <= pos <= e:
            return True
    return False


# ---------------------------------------------------------------------------
# 文件扫描
# ---------------------------------------------------------------------------

def line_number_at(text: str, pos: int) -> int:
    """``pos`` 之前（含 ``pos`` 之前）的换行数 + 1，即行号（从 1 开始）。"""
    return text.count("\n", 0, pos) + 1


def line_snippet(text: str, pos: int, max_len: int = 120) -> str:
    """取 ``pos`` 所在行的原文片段（已 ``strip``，过长截断）。"""
    line_start = text.rfind("\n", 0, pos) + 1
    line_end = text.find("\n", pos)
    if line_end == -1:
        line_end = len(text)
    snippet = text[line_start:line_end].strip()
    if len(snippet) > max_len:
        snippet = snippet[: max_len - 3] + "..."
    return snippet


def scan_file(
    file_path: Path, repo_root: Path
) -> List[Tuple[int, str, str]]:
    """
    扫描单个 ``.js`` 文件，返回违规列表，每项为 ``(行号, 片段, 相对路径)``。
    """
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # 兼容 GBK / Latin-1 等编码的极老文件
        text = file_path.read_text(encoding="utf-8", errors="replace")

    rel = str(file_path.relative_to(repo_root)).replace("\\", "/")

    # 先在原文上定位 csrfFetch 函数体（位置与 strip_comments 后一致）
    csrf_bodies = find_csrf_fetch_bodies(text)
    # 去除注释后再做正则匹配，避免注释中的示例代码被误判
    stripped = strip_comments(text)

    violations: List[Tuple[int, str, str]] = []
    for pattern in PATTERNS:
        for m in pattern.finditer(stripped):
            pos = m.start()
            ln = line_number_at(text, pos)

            # 例外 1：csrfFetch 函数体内部
            if is_inside_csrf_fetch(pos, csrf_bodies):
                continue
            # 例外 2：app.js 顶部 30 行回退定义块
            if (
                file_path.name == "app.js"
                and 1 <= ln <= APPJS_FALLBACK_WINDOW
            ):
                continue

            snippet = line_snippet(text, pos)
            violations.append((ln, snippet, rel))
    return violations


def scan_repo(repo_root: Path) -> List[Tuple[int, str, str]]:
    """扫描 ``app/static/js/`` 下所有 ``.js`` 文件，汇总违规。"""
    scan_dir = repo_root / "app" / "static" / "js"
    if not scan_dir.is_dir():
        return []
    violations: List[Tuple[int, str, str]] = []
    for js_path in sorted(scan_dir.glob("*.js")):
        violations.extend(scan_file(js_path, repo_root))
    return violations


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

HELP_TEXT = """\
禁止裸调非 GET fetch —— 防回归扫描器

扫描 app/static/js/ 下的 .js 文件，发现形如
    fetch(url, { method: 'POST' | 'PUT' | 'DELETE' | 'PATCH' })
的裸调调用并报错。

白名单：
  * csrfFetch 函数体内部的 return fetch(...)；
  * app/static/js/app.js 顶部 30 行的 csrfFetch 回退定义块；
  * JS 注释（// 与 /* ... */）。

退出码：0 = 通过，1 = 有违规，2 = 参数错误。
"""


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lint_no_raw_post_fetch.py",
        description=HELP_TEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        default=True,
        help="执行检查（默认行为，可省略）",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="仓库根目录（默认取脚本所在目录的上一级）",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root: Path = args.repo_root.resolve()

    if not args.check:
        # 当前只支持 --check 模式，保留扩展位
        print("✗ 当前仅支持 --check 模式", file=sys.stderr)
        return 2

    violations = scan_repo(repo_root)
    if not violations:
        print("✓ 未发现裸调非 GET fetch（app/static/js/ 扫描通过）")
        return 0

    print("✗ 禁止裸调非 GET fetch！请改用 csrfFetch(url, options)")
    for ln, snippet, rel in violations:
        print(f"{rel}:{ln}  ->  {snippet}")
    print(f"发现 {len(violations)} 处违规")
    return 1


if __name__ == "__main__":
    sys.exit(main())

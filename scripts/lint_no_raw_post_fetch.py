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
使用固定版本的纯 Python JavaScript 解析器检查完整语法树，识别例如::

    fetch(url, { method: 'POST' })   # 或 PUT / DELETE / PATCH

的"裸调"调用。业务代码应改走 ``WMS.api.get/post/put/delete(url, data)``
（``app/static/js/api.js`` 统一封装，自带 CSRF）。

F3.7（2026-10-12）起同时扫描 ``app/templates/`` 下 ``.html`` 的 ``<script>``
内联块，但**暂为 warn 模式**：违规只打印不计入退出码（观察期摸清存量，
再定棘轮基线转 strict；``--templates-strict`` 可提前按违规处理）。

白名单（即使匹配也不报错）：
1. AGENTS 规定的统一层 ``app/static/js/app.js``、``app/static/js/api.js``
   和 ``app/templates/base.html``。
2. 注释、字符串和正则字面量的内容不作为可执行调用。

业务文件不得通过定义名为 csrfFetch 的函数获得统一层例外。

嵌套表达式、模板插值、可选调用、已识别别名和动态方法均纳入检查；
不能证明为 GET 的 fetch options 拒绝通过。源码仅被解析，不执行。
第三方解析器的来源、许可证与资源限制见 vendor/README.md。

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
import subprocess
import sys
import runpy
from pathlib import Path
from typing import List, Tuple


# BUG-2026-10-17-010：中文 Windows 控制台（cp936/GBK）无法编码 ⚠/✓/✗，print 直接抛
# UnicodeEncodeError。pre-commit 以退出码判断结果，脚本崩溃会被误判成"发现违规"，
# 于是**任何提交都被拒**（实测：lint_no_raw_post_fetch.py:397 打印 ⚠ 崩溃）。
# 与 BUG-2026-10-17-006（check_ci_green）同一根因。修法：
#   _configure_stdio() —— stdout/stderr errors=replace 兜底，极端字符变 '?' 但不崩；
#   _glyph()          —— 编码不支持时主动降级为 ASCII 标记，输出仍可读。
def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(errors="replace")
        except (ValueError, OSError):
            pass


def _glyph(unicode_text: str, ascii_text: str) -> str:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        unicode_text.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return ascii_text
    return unicode_text

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

# 仓库根目录（脚本所在位置向上两级：scripts/ -> 仓库根）
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SCAN_DIR = REPO_ROOT / "app" / "static" / "js"
_fetch_positions = runpy.run_path(str(SCRIPT_DIR / "fetch_ast.py"))["positions"]

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
    file_path: Path, repo_root: Path, *, text: str | None = None
) -> List[Tuple[int, str, str]]:
    """
    扫描单个 ``.js`` 文件，返回违规列表，每项为 ``(行号, 片段, 相对路径)``。
    """
    if text is None:
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # 兼容 GBK / Latin-1 等编码的极老文件
            text = file_path.read_text(encoding="utf-8", errors="replace")

    rel = str(file_path.relative_to(repo_root)).replace("\\", "/")

    # 统一 API 封装层是 AGENTS 明确规定的例外；业务文件仍做完整语法分析。
    positions = _fetch_positions(text)
    if rel in {"app/static/js/api.js", "app/static/js/app.js"}:
        return []
    return sorted({(line_number_at(text, pos), line_snippet(text, pos), rel)
                   for pos in positions})


def scan_repo(repo_root: Path) -> List[Tuple[int, str, str]]:
    """扫描 ``app/static/js/`` 下所有 ``.js`` 文件，汇总违规。"""
    scan_dir = repo_root / "app" / "static" / "js"
    if not scan_dir.is_dir():
        return []
    violations: List[Tuple[int, str, str]] = []
    for js_path in sorted(scan_dir.rglob("*.js")):
        violations.extend(scan_file(js_path, repo_root))
    return violations


# ---------------------------------------------------------------------------
# F3.7：模板内联 <script> 扫描（warn 模式观察期）
# ---------------------------------------------------------------------------

# 提取无 src 的 <script>...</script> 块（内容，块起始偏移）
_SCRIPT_BLOCK = re.compile(
    r"<script(?![^>]*\bsrc\s*=)[^>]*>(.*?)</script\s*>",
    re.IGNORECASE | re.DOTALL,
)


def scan_template_file(
    file_path: Path, repo_root: Path, *, text: str | None = None
) -> List[Tuple[int, str, str]]:
    """扫描单个 ``.html`` 模板内联 <script> 块的裸调非 GET fetch。"""
    if text is None:
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = file_path.read_text(encoding="utf-8", errors="replace")

    rel = str(file_path.relative_to(repo_root)).replace("\\", "/")
    violations: List[Tuple[int, str, str]] = []
    from html.parser import HTMLParser

    class ScriptAttributes(HTMLParser):
        def __init__(self):
            super().__init__()
            self.attrs = []

        def handle_starttag(self, tag, attrs):
            if tag.lower() == 'script':
                self.attrs = attrs

    for block in _SCRIPT_BLOCK.finditer(text):
        body_text = block.group(1)
        base = block.start(1)
        attributes = ScriptAttributes()
        attributes.feed(text[block.start():base])
        types = [(value or '').strip().lower() for name, value in attributes.attrs
                 if name.lower() == 'type']
        if types == ['application/json']:
            continue
        try:
            positions = _fetch_positions(body_text)
        except RuntimeError:
            violations.append((line_number_at(text, base), '[无法解析模板脚本，请人工核对]', rel))
            continue
        if rel == 'app/templates/base.html':
            continue  # AGENTS 规定的全局 fetch/CSRF 统一封装层。
        violations.extend((line_number_at(text, base + pos), line_snippet(text, base + pos), rel)
                          for pos in positions)
    return sorted(set(violations))


def scan_templates(repo_root: Path) -> List[Tuple[int, str, str]]:
    """扫描 ``app/templates/`` 下所有 ``.html`` 模板的内联脚本。"""
    scan_dir = repo_root / "app" / "templates"
    if not scan_dir.is_dir():
        return []
    violations: List[Tuple[int, str, str]] = []
    for html_path in sorted(scan_dir.rglob("*.html")):
        violations.extend(scan_template_file(html_path, repo_root))
    return violations


def scan_staged(repo_root: Path) -> Tuple[List[Tuple[int, str, str]], List[Tuple[int, str, str]]]:
    """Scan the complete index snapshot, preserving the normal JS/template scope."""
    try:
        listing = subprocess.run(
            ["git", "ls-files", "--stage", "-z", "--", "app/static/js", "app/templates"],
            cwd=repo_root, capture_output=True, check=True,
        ).stdout
        selected = []
        for entry in listing.split(b"\0"):
            if not entry:
                continue
            metadata, raw_path = entry.split(b"\t", 1)
            mode, object_id, stage = metadata.split()
            path = raw_path.decode("utf-8", errors="strict")
            is_js = path.startswith("app/static/js/") and path.endswith(".js")
            is_template = path.startswith("app/templates/") and path.endswith(".html")
            if not (is_js or is_template):
                continue
            if stage != b"0" or mode not in (b"100644", b"100755"):
                raise ValueError("暂存文件存在冲突或不是普通文件")
            if not re.fullmatch(rb"[0-9a-f]{40}|[0-9a-f]{64}", object_id):
                raise ValueError("暂存对象标识无效")
            selected.append((path, object_id, is_js))
        if not selected:
            return [], []
        payload = b"".join(oid + b"\n" for _, oid, _ in selected)
        output = subprocess.run(["git", "cat-file", "--batch"], cwd=repo_root,
                                input=payload, capture_output=True, check=True).stdout
        js_violations, template_violations = [], []
        offset = 0
        for path, oid, is_js in selected:
            end = output.find(b"\n", offset)
            if end < 0:
                raise ValueError("暂存对象响应不完整")
            header = output[offset:end].split()
            if len(header) != 3 or header[0] != oid or header[1] != b"blob":
                raise ValueError("暂存对象响应无效")
            size = int(header[2])
            start, end = end + 1, end + 1 + size
            if size < 0 or end >= len(output) or output[end:end + 1] != b"\n":
                raise ValueError("暂存对象内容不完整")
            text = output[start:end].decode("utf-8", errors="replace")
            offset = end + 1
            file_path = repo_root / path
            if is_js:
                js_violations.extend(scan_file(file_path, repo_root, text=text))
            else:
                template_violations.extend(scan_template_file(file_path, repo_root, text=text))
        if offset != len(output):
            raise ValueError("暂存对象响应多出内容")
        return js_violations, template_violations
    except (OSError, subprocess.SubprocessError, UnicodeError, ValueError) as exc:
        raise RuntimeError("无法读取完整 Git 暂存快照") from exc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

HELP_TEXT = """\
禁止裸调非 GET fetch —— 防回归扫描器

扫描 app/static/js/ 下的 .js 文件，发现形如
    fetch(url, { method: 'POST' | 'PUT' | 'DELETE' | 'PATCH' })
的裸调调用并报错。

白名单：
  * app/static/js/app.js、app/static/js/api.js 与 app/templates/base.html 统一封装层；
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
    parser.add_argument(
        "--templates-strict",
        action="store_true",
        default=False,
        help="模板内联 JS 违规按失败处理（默认 warn 模式，只打印不影响退出码）",
    )
    parser.add_argument("--staged", action="store_true", help="扫描 Git 暂存快照")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    _configure_stdio()
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root: Path = args.repo_root.resolve()

    if not args.check:
        # 当前只支持 --check 模式，保留扩展位
        print(_glyph("✗", "[FAIL]") + " 当前仅支持 --check 模式", file=sys.stderr)
        return 2

    try:
        if args.staged:
            violations, tpl_violations = scan_staged(repo_root)
        else:
            violations = scan_repo(repo_root)
            tpl_violations = scan_templates(repo_root)
    except RuntimeError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 2

    if tpl_violations:
        # F3.7 观察期：模板违规 warn 模式（摸清存量后转 --templates-strict 棘轮）
        tag = _glyph("✗", "[FAIL]") if args.templates_strict else _glyph("⚠", "[WARN]")
        print(f"{tag} app/templates/ 内联 <script> 裸调非 GET fetch "
              f"{len(tpl_violations)} 处"
              + ("" if args.templates_strict else "（warn 模式观察期，不计入退出码）"))
        for ln, snippet, rel in tpl_violations[:50]:
            print(f"  {rel}:{ln}  ->  {snippet}")
        if len(tpl_violations) > 50:
            print(f"  ... 其余 {len(tpl_violations) - 50} 处省略")

    if not violations:
        print(_glyph("✓", "[OK]") + " 未发现裸调非 GET fetch（app/static/js/ 扫描通过）")
        if args.templates_strict and tpl_violations:
            print(f"发现 {len(tpl_violations)} 处模板违规（strict 模式）")
            return 1
        return 0

    print(_glyph("✗", "[FAIL]") + " 禁止裸调非 GET fetch！请改用 WMS.api.post/put/delete(url, data)"
          "（app/static/js/api.js 统一封装，自带 CSRF）")
    for ln, snippet, rel in violations:
        print(f"{rel}:{ln}  ->  {snippet}")
    print(f"发现 {len(violations)} 处违规")
    return 1


if __name__ == "__main__":
    sys.exit(main())

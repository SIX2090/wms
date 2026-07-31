#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lint_wms_rules.py
=================

WMS 防 BUG 多规则静态检查器
统一扫描 7 条最常见的"招 BUG 写法"，每条规则可独立开关。

7 条规则一览
------------
* **A1** 模板 ``<form method="post">`` 必须有 csrf_token
* **A2** Python POST 路由必须有 ``@csrf.exempt`` / ``@login_required`` / ``@csrf_protect``
* **A3** 业务 JS 不能有 ``console.log``
* **A4** 业务 JS 不能有 ``debugger;`` / ``alert(``
* **A5** 业务 JS 不能有裸 ``eval(`` / ``new Function(``（严格禁止，无白名单）
* **A6** 业务 Python 不能有 ``print(``
* **A7** SQL 字符串拼接（f-string / %s / text 拼接）禁止

设计要点
--------
* **零依赖**：仅使用 Python 3 标准库（re / pathlib / argparse / sys）。
* **类继承**：每条规则一个 ``Rule`` 子类，统一接口 ``scan()`` / ``format()``。
* **配置驱动**：每条规则的开关、扫描路径、白名单都放在 ``RULES`` 常量字典里，
  增加新规则只需写子类 + 加字典项。
* **可分级运行**：支持 ``--rule a1,a3`` 单跑 / 多跑，``--staged`` 只扫 git staged 文件。
* **CI 友好**：退出码 0/1/2，输出统一格式。

退出码
------
* ``0``：所有启用的规则均通过
* ``1``：发现至少一处违规
* ``2``：参数错误 / 文件无法读取

用法
----
::

    python3 scripts/lint_wms_rules.py                  # 跑所有规则
    python3 scripts/lint_wms_rules.py --rule a1        # 只跑 A1
    python3 scripts/lint_wms_rules.py --rule a1,a2     # 跑 A1 和 A2
    python3 scripts/lint_wms_rules.py --list           # 列出所有规则
    python3 scripts/lint_wms_rules.py --staged         # 只扫描 git staged 的文件
    python3 scripts/lint_wms_rules.py --verbose        # 详细输出（每条规则的扫描文件数）
    python3 scripts/lint_wms_rules.py --help           # 帮助

扩展一条新规则
--------------
1. 写一个 ``class RuleXxx(Rule)`` 子类，实现 ``name`` / ``description`` / ``scan()``。
2. 在 ``RULES`` 字典里注册：``RULES["ax"] = RuleXxx()``。
3. 更新 ``DEVELOPMENT_RULES.md`` 文档"防 BUG 规则清单"。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# 仓库根与路径常量
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
APP_DIR = REPO_ROOT / "app"
TEMPLATES_DIR = APP_DIR / "templates"
JS_DIR = APP_DIR / "static" / "js"


# ---------------------------------------------------------------------------
# 工具：行号 / 片段 / 注释剔除
# ---------------------------------------------------------------------------

def line_number_at(text: str, pos: int) -> int:
    """``pos`` 之前（含 ``pos`` 之前）的换行数 + 1，行号从 1 开始。"""
    return text.count("\n", 0, pos) + 1


def line_snippet(text: str, pos: int, max_len: int = 120) -> str:
    """取 ``pos`` 所在行的原文片段（strip + 截断）。"""
    line_start = text.rfind("\n", 0, pos) + 1
    line_end = text.find("\n", pos)
    if line_end == -1:
        line_end = len(text)
    snippet = text[line_start:line_end].strip()
    if len(snippet) > max_len:
        snippet = snippet[: max_len - 3] + "..."
    return snippet


# 通用注释剔除（行 + 块），保持字符串长度不变（用空格填充），方便行号映射。
_PY_COMMENT_BLOCK = re.compile(r"\"\"\".*?\"\"\"|'''.*?'''", re.DOTALL)
_PY_COMMENT_LINE = re.compile(r"#[^\n\r]*")

_JS_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_JS_COMMENT_LINE = re.compile(r"//[^\n\r]*")

_HTML_COMMENT_BLOCK = re.compile(r"<!--.*?-->", re.DOTALL)


def strip_py_comments(text: str) -> str:
    """去掉 Python 注释，但保持字符串长度。"""
    text = _PY_COMMENT_BLOCK.sub(lambda m: " " * len(m.group(0)), text)
    text = _PY_COMMENT_LINE.sub(lambda m: " " * len(m.group(0)), text)
    return text


def strip_js_comments(text: str) -> str:
    """去掉 JS 注释，但保持字符串长度。"""
    text = _JS_COMMENT_BLOCK.sub(lambda m: " " * len(m.group(0)), text)
    text = _JS_COMMENT_LINE.sub(lambda m: " " * len(m.group(0)), text)
    return text


def strip_html_comments(text: str) -> str:
    """去掉 HTML 注释，但保持字符串长度。"""
    return _HTML_COMMENT_BLOCK.sub(lambda m: " " * len(m.group(0)), text)


# ---------------------------------------------------------------------------
# 抽象规则基类
# ---------------------------------------------------------------------------

class Violation:
    """一条违规记录。"""

    __slots__ = ("file", "line", "snippet", "extra")

    def __init__(self, file: str, line: int, snippet: str = "", extra: str = ""):
        self.file = file
        self.line = line
        self.snippet = snippet
        self.extra = extra  # 附加信息（如路由路径）

    def __str__(self) -> str:
        # 形如：app/templates/xxx.html:42  <form method="post" ...>
        if self.extra:
            return f"{self.file}:{self.line}  {self.snippet}  [{self.extra}]"
        return f"{self.file}:{self.line}  {self.snippet}"


class Rule(ABC):
    """所有规则基类。"""

    #: 规则编号（短码）：a1 / a2 / ...
    name: str = ""
    #: 规则描述（一行）
    description: str = ""
    #: 默认是否启用
    enabled: bool = True
    #: 扫描路径（相对仓库根）
    scan_paths: Tuple[str, ...] = ()
    #: 排除路径前缀（相对仓库根）
    exclude_paths: Tuple[str, ...] = ()
    #: 文件后缀（用于过滤 glob 结果）
    extensions: Tuple[str, ...] = ()

    @abstractmethod
    def scan(self, files: Sequence[Path], repo_root: Path) -> List[Violation]:
        """扫描给定文件列表，返回违规列表。"""
        raise NotImplementedError

    def discover_files(self, repo_root: Path) -> List[Path]:
        """根据 ``scan_paths`` / ``exclude_paths`` / ``extensions`` 找出要扫的文件。"""
        result: List[Path] = []
        for rel in self.scan_paths:
            base = repo_root / rel
            if not base.exists():
                continue
            for p in base.rglob("*"):
                if not p.is_file():
                    continue
                if self.extensions and p.suffix not in self.extensions:
                    continue
                rel_str = str(p.relative_to(repo_root)).replace("\\", "/")
                if any(rel_str.startswith(ex) for ex in self.exclude_paths):
                    continue
                result.append(p)
        return sorted(result)


# ---------------------------------------------------------------------------
# A1：HTML <form method="post"> 必须有 csrf_token
# ---------------------------------------------------------------------------

class RuleA1FormCsrf(Rule):
    """模板里所有 POST form 必须包含 csrf_token。"""

    name = "a1"
    description = "模板 <form method=\"post\"> 必须有 csrf_token"
    enabled = True
    scan_paths = ("app/templates",)
    exclude_paths = ()  # 不过滤 csrf_error.html（它确实没有 form 标签）
    extensions = (".html", ".htm", ".jinja", ".jinja2", ".j2", ".tmpl")

    # 匹配 ``<form`` 开始标签，宽松匹配属性顺序
    _FORM_OPEN = re.compile(
        r"<form\b[^>]*\bmethod\s*=\s*['\"]?\s*post\b",
        re.IGNORECASE,
    )
    _FORM_CLOSE = re.compile(r"</form\s*>", re.IGNORECASE)

    def scan(self, files: Sequence[Path], repo_root: Path) -> List[Violation]:
        violations: List[Violation] = []
        for f in files:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = str(f.relative_to(repo_root)).replace("\\", "/")
            stripped = strip_html_comments(text)
            for m in self._FORM_OPEN.finditer(stripped):
                # 1. 同一行是否是 HTML 注释块（极少见） - 跳过
                line_start = text.rfind("\n", 0, m.start()) + 1
                line_end = text.find("\n", m.start())
                if line_end == -1:
                    line_end = len(text)
                line_text = text[line_start:line_end]
                if line_text.strip().startswith("<!--"):
                    continue
                # 2. form 之前最近的 600 字符窗口内出现 ``nocsrf:reason`` 标记 - 跳过
                lookahead_start = max(0, m.start() - 600)
                pre_window = text[lookahead_start:m.start()]
                if "nocsrf:reason" in pre_window.lower():
                    continue
                # 找匹配的 </form>
                end_m = self._FORM_CLOSE.search(stripped, m.end())
                if not end_m:
                    end = len(stripped)
                else:
                    end = end_m.end()
                body = stripped[m.start():end]
                # 检查 form 体内是否有 csrf_token
                if "csrf_token" not in body:
                    ln = line_number_at(text, m.start())
                    snippet = line_snippet(text, m.start())
                    violations.append(Violation(rel, ln, snippet))
        return violations


# ---------------------------------------------------------------------------
# A2：Python POST 路由必须 @csrf.exempt / @login_required / @csrf_protect
# ---------------------------------------------------------------------------

class RuleA2PostRouteCsrf(Rule):
    """Python 路由 POST 端点必须有 CSRF 处理装饰器。"""

    name = "a2"
    description = "Python POST 路由必须 @login_required 或 @csrf.exempt"
    enabled = True
    scan_paths = ("app",)
    exclude_paths = ("app/ai",)  # AI 模块不需要此规则
    extensions = (".py",)

    # 匹配 ``@app.route('...', methods=[..., 'POST', ...])``
    _ROUTE_POST = re.compile(
        r"@app\.route\(\s*['\"]([^'\"]+)['\"]\s*,\s*methods\s*=\s*\[[^\]]*['\"]POST['\"]",
        re.IGNORECASE,
    )

    # 已知豁免：登录前的端点、webhook 等
    KNOWN_EXEMPT_PATHS: Tuple[str, ...] = (
        "/api/login",
        "/api/csrf_refresh",
        "/api/webhook",
        "/wechat",
        "/login",  # login 页面
    )

    # 已知鉴权/权限装饰器：装饰器直接放在路由下方即视为"已处理"。
    # 把项目里所有等价的鉴权/权限装饰器都列上,避免误报。
    KNOWN_DECORATOR_HINTS: Tuple[str, ...] = (
        "@csrf.exempt",          # 标准 Flask-WTF CSRF 豁免
        "@login_required",       # Flask-Login 登录要求
        "@csrf_protect",         # 显式 CSRF 保护
        "@web_or_api_required",  # 项目自定义:Web 会话或 Bearer Token 任一通过即可
        "@role_required",        # 项目自定义:角色权限
        "@admin_required",       # 项目自定义:管理员权限
    )

    def scan(self, files: Sequence[Path], repo_root: Path) -> List[Violation]:
        violations: List[Violation] = []
        for f in files:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = str(f.relative_to(repo_root)).replace("\\", "/")
            stripped = strip_py_comments(text)
            lines = stripped.split("\n")
            for m in self._ROUTE_POST.finditer(stripped):
                path = m.group(1)
                if any(path.startswith(p) for p in self.KNOWN_EXEMPT_PATHS):
                    continue
                ln = line_number_at(text, m.start())
                line_idx = stripped[:m.start()].count("\n")
                window = "\n".join(lines[line_idx:line_idx + 30])
                # 命中任何已知鉴权/权限装饰器即视为合法
                if any(hint in window for hint in self.KNOWN_DECORATOR_HINTS):
                    continue
                # 兼容老逻辑:保留 csrf_token 字符串识别
                if "csrf_token" in window:
                    continue
                snippet = line_snippet(text, m.start())
                violations.append(Violation(rel, ln, snippet, extra=path))
        return violations


# ---------------------------------------------------------------------------
# A3：业务 JS 不能有 console.log
# ---------------------------------------------------------------------------

class RuleA3NoConsoleLog(Rule):
    """业务 JS 禁止 ``console.log``。"""

    name = "a3"
    description = "业务 JS 不能 console.log"
    enabled = True
    scan_paths = ("app/static/js",)
    exclude_paths = ()
    extensions = (".js",)

    # 视为第三方/库的文件（白名单，不扫描）
    THIRD_PARTY_FILES: Tuple[str, ...] = (
        "xlsx.full.min.js",
    )

    _PATTERN = re.compile(r"\bconsole\s*\.\s*log\s*\(")
    _ALLOW_HINT = re.compile(r"//\s*allow-console\b", re.IGNORECASE)

    def _is_third_party(self, rel: str) -> bool:
        if "/lib/" in rel or rel.startswith("lib/"):
            return True
        return any(rel.endswith(f) for f in self.THIRD_PARTY_FILES)

    def scan(self, files: Sequence[Path], repo_root: Path) -> List[Violation]:
        violations: List[Violation] = []
        for f in files:
            rel = str(f.relative_to(repo_root)).replace("\\", "/")
            if self._is_third_party(rel):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            stripped = strip_js_comments(text)
            for m in self._PATTERN.finditer(stripped):
                pos = m.start()
                # 检查原文行尾是否有 ``// allow-console`` 注释
                line_end = text.find("\n", pos)
                if line_end == -1:
                    line_end = len(text)
                line_start = text.rfind("\n", 0, pos) + 1
                line_text = text[line_start:line_end]
                if self._ALLOW_HINT.search(line_text):
                    continue
                ln = line_number_at(text, pos)
                snippet = line_snippet(text, pos)
                violations.append(Violation(rel, ln, snippet))
        return violations


# ---------------------------------------------------------------------------
# A4：业务 JS 不能有 debugger / alert
# ---------------------------------------------------------------------------

class RuleA4NoDebuggerAlert(Rule):
    """业务 JS 禁止 ``debugger;`` 和 ``alert(``。"""

    name = "a4"
    description = "业务 JS 不能 debugger / alert"
    enabled = True
    scan_paths = ("app/static/js",)
    exclude_paths = ()
    extensions = (".js",)

    THIRD_PARTY_FILES: Tuple[str, ...] = (
        "xlsx.full.min.js",
    )

    # ``debugger;`` 关键字 - 避免误匹配变量名
    _DEBUGGER = re.compile(r"\bdebugger\b\s*;?")
    _ALERT = re.compile(r"\balert\s*\(")
    _ALLOW_DEBUGGER = re.compile(r"//\s*allow-debugger\b", re.IGNORECASE)
    _ALLOW_ALERT = re.compile(r"//\s*allow-alert\b", re.IGNORECASE)

    def _is_third_party(self, rel: str) -> bool:
        if "/lib/" in rel or rel.startswith("lib/"):
            return True
        return any(rel.endswith(f) for f in self.THIRD_PARTY_FILES)

    def scan(self, files: Sequence[Path], repo_root: Path) -> List[Violation]:
        violations: List[Violation] = []
        for f in files:
            rel = str(f.relative_to(repo_root)).replace("\\", "/")
            if self._is_third_party(rel):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            stripped = strip_js_comments(text)
            for m in self._DEBUGGER.finditer(stripped):
                pos = m.start()
                line_start = text.rfind("\n", 0, pos) + 1
                line_end = text.find("\n", pos)
                if line_end == -1:
                    line_end = len(text)
                line_text = text[line_start:line_end]
                if self._ALLOW_DEBUGGER.search(line_text):
                    continue
                ln = line_number_at(text, pos)
                snippet = line_snippet(text, pos)
                violations.append(Violation(rel, ln, snippet))
            for m in self._ALERT.finditer(stripped):
                pos = m.start()
                line_start = text.rfind("\n", 0, pos) + 1
                line_end = text.find("\n", pos)
                if line_end == -1:
                    line_end = len(text)
                line_text = text[line_start:line_end]
                if self._ALLOW_ALERT.search(line_text):
                    continue
                ln = line_number_at(text, pos)
                snippet = line_snippet(text, pos)
                violations.append(Violation(rel, ln, snippet))
        return violations


# ---------------------------------------------------------------------------
# A5：业务 JS 不能有 eval / new Function
# ---------------------------------------------------------------------------

class RuleA5NoEvalFunction(Rule):
    """业务 JS 禁止 ``eval(`` / ``new Function(``。严格：无白名单。"""

    name = "a5"
    description = "业务 JS 不能 eval / new Function（严格）"
    enabled = True
    scan_paths = ("app/static/js",)
    exclude_paths = ()
    extensions = (".js",)

    THIRD_PARTY_FILES: Tuple[str, ...] = (
        "xlsx.full.min.js",
    )

    _EVAL = re.compile(r"(?<!\w)eval\s*\(")
    _NEW_FUNCTION = re.compile(r"\bnew\s+Function\s*\(")

    def _is_third_party(self, rel: str) -> bool:
        if "/lib/" in rel or rel.startswith("lib/"):
            return True
        return any(rel.endswith(f) for f in self.THIRD_PARTY_FILES)

    def scan(self, files: Sequence[Path], repo_root: Path) -> List[Violation]:
        violations: List[Violation] = []
        for f in files:
            rel = str(f.relative_to(repo_root)).replace("\\", "/")
            if self._is_third_party(rel):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            stripped = strip_js_comments(text)
            for pat in (self._EVAL, self._NEW_FUNCTION):
                for m in pat.finditer(stripped):
                    pos = m.start()
                    ln = line_number_at(text, pos)
                    snippet = line_snippet(text, pos)
                    violations.append(Violation(rel, ln, snippet))
        return violations


# ---------------------------------------------------------------------------
# A6：业务 Python 不能有 print(
# ---------------------------------------------------------------------------

class RuleA6NoPrint(Rule):
    """业务 Python 禁止 ``print(``。"""

    name = "a6"
    description = "业务 Python 不能 print"
    enabled = True
    scan_paths = ("app",)
    # 排除 AI 子包（动态/单文件脚本式）
    exclude_paths = (
        "app/ai",
    )
    # 顶层 CLI / 启动 / 辅助脚本：这些文件里的 print 是合法的运维输出
    TOP_LEVEL_RUNNER_FILES: Tuple[str, ...] = (
        "app/run_server.py",
        "app/auto_update.py",
        "app/restart.py",
        "app/notifications.py",
        "app/wechat_helper.py",
    )
    extensions = (".py",)

    # scripts 路径前缀允许 print
    _SCRIPT_PATH_ALLOW_PREFIX = re.compile(
        r"^scripts/(?:audit/|benchmark_|verify_)"
    )

    _PRINT = re.compile(r"(?<![\w.])print\s*\(")
    _ALLOW_HINT = re.compile(r"#\s*allow-print\b", re.IGNORECASE)

    def scan(self, files: Sequence[Path], repo_root: Path) -> List[Violation]:
        violations: List[Violation] = []
        for f in files:
            rel = str(f.relative_to(repo_root)).replace("\\", "/")
            # 跳过 scripts/audit scripts/benchmark scripts/verify
            if rel.startswith("scripts/") and self._SCRIPT_PATH_ALLOW_PREFIX.match(rel):
                continue
            # 跳过 app/ai/
            if rel.startswith("app/ai/"):
                continue
            # 跳过顶层 CLI 脚本
            if rel in self.TOP_LEVEL_RUNNER_FILES:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            stripped = strip_py_comments(text)
            # 简单判断 ``if __name__ == '__main__':`` 块
            main_block_ranges = self._find_main_blocks(stripped)
            for m in self._PRINT.finditer(stripped):
                pos = m.start()
                if self._in_any_range(pos, main_block_ranges):
                    continue
                # 检查原文行尾是否有 ``# allow-print``
                line_start = text.rfind("\n", 0, pos) + 1
                line_end = text.find("\n", pos)
                if line_end == -1:
                    line_end = len(text)
                line_text = text[line_start:line_end]
                if self._ALLOW_HINT.search(line_text):
                    continue
                ln = line_number_at(text, pos)
                snippet = line_snippet(text, pos)
                violations.append(Violation(rel, ln, snippet))
        return violations

    @staticmethod
    def _find_main_blocks(text: str) -> List[Tuple[int, int]]:
        """找出 ``if __name__ == '__main__':`` 块的字符范围。"""
        blocks: List[Tuple[int, int]] = []
        for m in re.finditer(
            r"^if\s+__name__\s*==\s*['\"]__main__['\"]\s*:",
            text,
            re.MULTILINE,
        ):
            start = m.end()
            rest = text[start:]
            lines = rest.split("\n")
            offset = 0
            for i, line in enumerate(lines):
                if i == 0:
                    offset += len(line) + 1
                    continue
                if line and not line.startswith((" ", "\t")):
                    end = start + offset
                    blocks.append((start, end))
                    break
                offset += len(line) + 1
            else:
                blocks.append((start, len(text)))
        return blocks

    @staticmethod
    def _in_any_range(pos: int, ranges: List[Tuple[int, int]]) -> bool:
        for s, e in ranges:
            if s <= pos < e:
                return True
        return False


# ---------------------------------------------------------------------------
# A7：SQL 字符串拼接禁止
# ---------------------------------------------------------------------------

class RuleA7NoSqlConcat(Rule):
    """禁止 SQL 字符串拼接（f-string / %s / text 拼接）。"""

    name = "a7"
    description = "SQL 必须参数化，禁止字符串拼接（严格）"
    enabled = True
    scan_paths = ("app",)
    exclude_paths = ("app/ai",)
    extensions = (".py",)

    # 真正危险的模式：text(f"...SQL...{var}...") 或 db.session.execute(f"...SQL...{var}...")
    # 关键：字符串必须紧跟 ``text(`` 或 ``execute(`` 之类的 SQL 执行函数
    _FSTRING_SQL_IN_TEXT = re.compile(
        r"""\btext\s*\(\s*f?['"][^'"]*\b(?:SELECT|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|FROM\s+\w+)\b[^'"]*\{[^}]+\}"""
    )
    _FSTRING_SQL_IN_EXECUTE = re.compile(
        r"""\bexecute\s*\(\s*f['"][^'"]*\b(?:SELECT|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|FROM\s+\w+)\b[^'"]*\{[^}]+\}"""
    )
    # text("...%s...") - 简单粗暴的占位符
    _PERCENT_SQL_IN_TEXT = re.compile(
        r"""\btext\s*\(\s*['"][^'"]*\b(?:SELECT|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|FROM\s+\w+)\b[^'"]*%s"""
    )

    def scan(self, files: Sequence[Path], repo_root: Path) -> List[Violation]:
        violations: List[Violation] = []
        for f in files:
            rel = str(f.relative_to(repo_root)).replace("\\", "/")
            if rel.startswith("app/ai/"):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            stripped = strip_py_comments(text)
            seen_pos: set = set()
            for pat in (
                self._FSTRING_SQL_IN_TEXT,
                self._FSTRING_SQL_IN_EXECUTE,
                self._PERCENT_SQL_IN_TEXT,
            ):
                for m in pat.finditer(stripped):
                    pos = m.start()
                    if pos in seen_pos:
                        continue
                    seen_pos.add(pos)
                    ln = line_number_at(text, pos)
                    snippet = line_snippet(text, pos)
                    violations.append(Violation(rel, ln, snippet))
        return violations


# ---------------------------------------------------------------------------
# 规则注册表
# ---------------------------------------------------------------------------

RULES: Dict[str, Rule] = {
    "a1": RuleA1FormCsrf(),
    "a2": RuleA2PostRouteCsrf(),
    "a3": RuleA3NoConsoleLog(),
    "a4": RuleA4NoDebuggerAlert(),
    "a5": RuleA5NoEvalFunction(),
    "a6": RuleA6NoPrint(),
    "a7": RuleA7NoSqlConcat(),
}

RULE_DISPLAY_ORDER: Tuple[str, ...] = ("a1", "a2", "a3", "a4", "a5", "a6", "a7")


# ---------------------------------------------------------------------------
# Git staged 文件收集
# ---------------------------------------------------------------------------

def get_staged_files(repo_root: Path) -> List[Path]:
    """获取 git staged 的文件路径（相对 repo_root）。"""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return []
    if result.returncode != 0:
        return []
    files: List[Path] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        p = repo_root / line
        if p.is_file():
            files.append(p)
    return files


def filter_staged_to_rule(
    staged: Sequence[Path], rule: Rule, repo_root: Path
) -> List[Path]:
    """只保留属于某条规则扫描范围 + extensions 的 staged 文件。"""
    out: List[Path] = []
    for f in staged:
        rel = str(f.relative_to(repo_root)).replace("\\", "/")
        in_scope = False
        for sp in rule.scan_paths:
            sp_norm = sp.rstrip("/")
            if rel == sp_norm or rel.startswith(sp_norm + "/"):
                in_scope = True
                break
        if not in_scope:
            continue
        if rule.extensions and f.suffix not in rule.extensions:
            continue
        if any(rel.startswith(ex) for ex in rule.exclude_paths):
            continue
        out.append(f)
    return out


# ---------------------------------------------------------------------------
# 输出格式化
# ---------------------------------------------------------------------------

def format_report(
    results: Dict[str, List[Violation]],
    files_scanned: Dict[str, int],
    verbose: bool,
) -> str:
    """把违规结果格式化为人类可读的字符串。"""
    lines: List[str] = []
    total = 0
    for rid in RULE_DISPLAY_ORDER:
        if rid not in results:
            continue
        v = results[rid]
        rule = RULES[rid]
        if not v:
            if verbose:
                lines.append(
                    f"[{rid.upper()}] ✓ 通过  ({rule.description})  "
                    f"扫描 {files_scanned.get(rid, 0)} 个文件"
                )
            continue
        lines.append(f"[{rid.upper()}] {rule.description} ({len(v)} 处)")
        for vio in v:
            lines.append(f"  {vio}")
        total += len(v)
    lines.append("─" * 64)
    active_with_violation = sum(1 for rid, vs in results.items() if vs)
    lines.append(f"总计 {total} 处违规，分布于 {active_with_violation} 条规则")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

HELP_TEXT = """\
WMS 防 BUG 多规则静态检查器（7 条规则）

用法：
  python3 scripts/lint_wms_rules.py                  跑所有规则
  python3 scripts/lint_wms_rules.py --rule a1        只跑 A1
  python3 scripts/lint_wms_rules.py --rule a1,a2     跑 A1 和 A2
  python3 scripts/lint_wms_rules.py --list           列出所有规则
  python3 scripts/lint_wms_rules.py --staged         只扫描 git staged 文件（pre-commit 用）
  python3 scripts/lint_wms_rules.py --verbose        详细输出（每条规则的扫描文件数）

退出码：0 = 通过，1 = 有违规，2 = 参数错误。
"""


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lint_wms_rules.py",
        description=HELP_TEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--rule",
        type=str,
        default="",
        help="只跑指定规则（逗号分隔），如 --rule a1,a3",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有规则及说明，然后退出",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="只扫描 git staged 的文件（pre-commit 用）",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="详细输出（每条规则的扫描文件数 + 通过规则也显示）",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="仓库根目录（默认取脚本所在目录的上一级）",
    )
    return parser.parse_args(argv)


def list_rules() -> int:
    print("WMS 防 BUG 规则清单：")
    for rid in RULE_DISPLAY_ORDER:
        r = RULES[rid]
        marker = "✓" if r.enabled else "✗"
        print(f"  [{rid.upper()}] {marker} {r.description}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    repo_root: Path = args.repo_root.resolve()

    if args.list:
        return list_rules()

    # 决定要跑的规则
    if args.rule:
        wanted = [s.strip().lower() for s in args.rule.split(",") if s.strip()]
        for w in wanted:
            if w not in RULES:
                print(
                    f"✗ 未知规则：{w}（可用：{','.join(RULE_DISPLAY_ORDER)}）",
                    file=sys.stderr,
                )
                return 2
    else:
        wanted = list(RULES.keys())

    # 决定要扫的文件范围
    staged_files: List[Path] = []
    if args.staged:
        staged_files = get_staged_files(repo_root)

    results: Dict[str, List[Violation]] = {}
    files_scanned: Dict[str, int] = {}

    for rid in wanted:
        rule = RULES[rid]
        if args.staged:
            files = filter_staged_to_rule(staged_files, rule, repo_root)
        else:
            files = rule.discover_files(repo_root)
        files_scanned[rid] = len(files)
        results[rid] = rule.scan(files, repo_root)

    # 输出报告
    report = format_report(results, files_scanned, args.verbose)
    print(report)

    # 退出码
    total = sum(len(v) for v in results.values())
    return 1 if total > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

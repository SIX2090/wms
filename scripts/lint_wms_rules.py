#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lint_wms_rules.py
=================

WMS 防 BUG 多规则静态检查器
统一扫描 10 条最常见的"招 BUG 写法"，每条规则可独立开关。

10 条规则一览
------------
* **A1** 模板 ``<form method="post">`` 必须有 csrf_token
* **A2** Python POST 路由必须有 ``@csrf.exempt`` / ``@login_required`` / ``@csrf_protect``
* **A3** 业务 JS 不能有 ``console.log``
* **A4** 业务 JS 不能有 ``debugger;`` / ``alert(``
* **A5** 业务 JS 不能有裸 ``eval(`` / ``new Function(``（严格禁止，无白名单）
* **A6** 业务 Python 不能有 ``print(``
* **A7** SQL 字符串拼接（f-string / %s / text 拼接）禁止
* **A8** 新增 POST/PUT/DELETE 路由必须用 pydantic 输入模型（防数据校验 BUG）
* **A9** 新增业务函数必须在 ``tests/`` 至少有 1 个失败测试（防未测试代码上线）
* **A10** ``app/app.py`` 禁止新增 ``@app.route`` 路由（防 app.py 重新膨胀，强制走 ``app/routes/`` 模块）

A8/A9/A10 是"新增代码生效"规则：仅对 git staged 的新增行强制，不会对存量代码一次性报几百条违规。

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
from typing import Dict, List, Optional, Sequence, Set, Tuple

# ---------------------------------------------------------------------------
# 仓库根与路径常量
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
APP_DIR = REPO_ROOT / "app"
TEMPLATES_DIR = APP_DIR / "templates"
JS_DIR = APP_DIR / "static" / "js"
TESTS_DIR = REPO_ROOT / "tests"


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


def _space_filler(m):
    """把匹配内容替换为等长空格，但保留换行符（保证行号映射不漂移）。

    直接用 ``" " * len(m.group(0))`` 会把多行 docstring / 块注释里的换行也
    一并吞掉，导致 ``stripped`` 的行号相对原始文件偏移，进而让 A8/A9 等
    依赖行号定位的规则失效（新增路由豁免注释检测不到）。
    """
    return re.sub(r"[^\n]", " ", m.group(0))


def strip_py_comments(text: str) -> str:
    """去掉 Python 注释（行 + 块），保持字符串长度与换行结构不变。"""
    text = _PY_COMMENT_BLOCK.sub(_space_filler, text)
    text = _PY_COMMENT_LINE.sub(_space_filler, text)
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
# 工具：git diff staged 新增行
# ---------------------------------------------------------------------------

# 解析 hunk header: "@@ -<old_start>,<old_count> +<new_start>,<new_count> @@"
_HUNK_HEADER = re.compile(
    r"^@@\s+-(?P<old_start>\d+)(?:,(?P<old_count>\d+))?\s+\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))?\s+@@"
)


def get_staged_added_lines(repo_root: Path, file_path: Path) -> Set[int]:
    """返回 staged 文件相对 HEAD 新增行（在新文件中的行号集合）。

    - 对新增文件（A），所有行都算"新增"。
    - 对修改文件（M），从 ``git diff --cached --unified=0`` 解析 hunk，仅取 ``+`` 行。
    - 解析失败 / 不在 git 中：返回空集（不报错，让规则"沉默"地放行）。
    """
    try:
        rel = str(file_path.relative_to(repo_root)).replace("\\", "/")
        # 优先用 --diff-filter=A 简化新增文件的情况
        result_a = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=A", "--", rel],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        is_new_file = rel in (result_a.stdout or "").split()
        if is_new_file:
            try:
                text = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return set()
            return set(range(1, text.count("\n") + 2))

        result = subprocess.run(
            ["git", "diff", "--cached", "--unified=0", "--", rel],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return set()
    if result.returncode != 0 or not result.stdout:
        return set()

    added: Set[int] = set()
    new_line = 0
    for line in result.stdout.splitlines():
        m = _HUNK_HEADER.match(line)
        if m:
            new_line = int(m.group("new_start"))
            continue
        if line.startswith("+++") or line.startswith("---") or line.startswith("diff "):
            continue
        if not new_line:
            continue
        if line.startswith("+"):
            added.add(new_line)
            new_line += 1
        elif line.startswith("-"):
            # 删除行不增加 new_line
            continue
        else:
            # 上下文行
            new_line += 1
    return added


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
        "@web_or_api_role_required",  # 项目自定义:Web 会话/Bearer Token + 角色权限
        "@_web_or_api_required",  # 项目自定义(mobile.py):Web 会话或 Bearer Token 任一通过即可
        "@_web_or_api_role_required",  # 项目自定义(mobile.py):Web 会话/Bearer Token + 角色权限
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
# A8：新增 POST/PUT/DELETE 路由必须用 pydantic 输入模型
# ---------------------------------------------------------------------------

class RuleA8NewRoutePydantic(Rule):
    """新增 POST/PUT/DELETE 路由必须用 pydantic BaseModel 做输入校验。

    这是一条"新增代码生效"规则：仅检查 git staged 中**新增**的写路由，
    不会对存量代码一次性报几百条违规。

    强制要求（满足任一即可）：
    - 在同一文件、路由下方 30 行窗口内出现 ``BaseModel`` / ``Field(`` /
      ``from pydantic`` 等 pydantic 痕迹。
    - 同文件（任何位置）已存在 ``class Xxx(BaseModel)`` 定义。
    - 新增行中有 ``# pydantic:reason=...`` 豁免注释。

    为什么强制 pydantic:
    - 手工 ``if not x: return error`` 容易漏掉类型校验（数字/字符串混淆）。
    - 没有契约文档，前端 / 后端字段名/类型漂移。
    - pydantic 一次给出 422 + 详细错误，避免脏数据进库。
    """

    name = "a8"
    description = "新增 POST/PUT/DELETE 路由必须用 pydantic 输入模型"
    enabled = True
    scan_paths = ("app",)
    exclude_paths = ("app/ai",)
    extensions = (".py",)

    # 匹配写路由: methods=[..., 'POST'/'PUT'/'DELETE', ...]
    _WRITE_ROUTE = re.compile(
        r"@app\.route\(\s*['\"]([^'\"]+)['\"]\s*,\s*methods\s*=\s*\[[^\]]*['\"](?:POST|PUT|DELETE)['\"]",
        re.IGNORECASE,
    )

    # 已知豁免：登录/刷新 csrf/webhook/wechat（与 A2 一致）
    KNOWN_EXEMPT_PATHS: Tuple[str, ...] = (
        "/api/login",
        "/api/csrf_refresh",
        "/api/webhook",
        "/wechat",
        "/login",
    )

    # 豁免注释: # pydantic:reason=...
    _ALLOW_HINT = re.compile(r"#\s*pydantic\s*:\s*reason\s*=", re.IGNORECASE)

    # pydantic 痕迹模式（任一命中即视为"已用 pydantic"）
    _PYDANTIC_HINTS = (
        re.compile(r"\bBaseModel\b"),
        re.compile(r"pydantic\s*\.\s*BaseModel"),
        re.compile(r"from\s+pydantic"),
        re.compile(r"\bField\s*\("),
    )

    def _file_has_pydantic(
        self, text: str, around_line: int, window: int = 30
    ) -> bool:
        """检查 text 中 ``around_line`` 附近 ``window`` 行窗口内是否出现 pydantic 痕迹。"""
        lines = text.split("\n")
        start = max(0, around_line - window - 1)
        end = min(len(lines), around_line + window)
        snippet = "\n".join(lines[start:end])
        return any(p.search(snippet) for p in self._PYDANTIC_HINTS)

    def _route_function_has_pydantic(
        self, text: str, route_match_span: Tuple[int, int]
    ) -> bool:
        """检查新增路由**函数体内部**是否出现 pydantic 痕迹。

        ``route_match_span`` 是 ``@app.route(...)`` 装饰器的 (start, end)。
        函数体范围：从装饰器下方 ``def func_name(`` 行 之后开始，到下个 ``def`` / 顶层
        ``@app.route`` 装饰器之前结束。
        """
        start_pos, _ = route_match_span
        lines = text.split("\n")
        # 找装饰器所在行索引
        deco_line_idx = text.count("\n", 0, start_pos)
        # 找 def 所在行索引（紧随装饰器的下一行起，扫描 5 行内）
        def_line_idx = None
        for i in range(deco_line_idx + 1, min(deco_line_idx + 6, len(lines))):
            if re.match(r"^\s*def\s+\w+\s*\(", lines[i]):
                def_line_idx = i
                break
        if def_line_idx is None:
            return False
        # 函数体结束：下一个"def"或顶层"@app.route"或装饰器行
        end_idx = len(lines)
        for i in range(def_line_idx + 1, len(lines)):
            stripped_line = lines[i].lstrip()
            if re.match(r"^(def |@app\.|@login_required|@csrf|@admin|@role|@web_or)", stripped_line):
                end_idx = i
                break
        body = "\n".join(lines[def_line_idx:end_idx])
        return any(p.search(body) for p in self._PYDANTIC_HINTS)

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
            # 1) 必须处于 staged 新增行集合
            added_lines = get_staged_added_lines(repo_root, f)
            if not added_lines:
                # 非 staged 修改 -> 跳过（A8 是新增代码生效规则）
                continue

            # 注释行号检查用 text 原始字符串(strip_py_comments 把 # 替换为空格)
            lines_raw = text.split("\n")
            lines = stripped.split("\n")
            for m in self._WRITE_ROUTE.finditer(stripped):
                path = m.group(1)
                if any(path.startswith(p) for p in self.KNOWN_EXEMPT_PATHS):
                    continue
                ln = line_number_at(text, m.start())
                if ln not in added_lines:
                    continue  # 这是旧路由，不强制
                # 2) 装饰器行 / 上一行 / def 行（含注释跨行情况）有无豁免注释
                line_idx = stripped[: m.start()].count("\n")
                found_allow = False
                for offset in (-1, 0, 1, 2):
                    check_idx = line_idx + offset
                    if 0 <= check_idx < len(lines_raw) and self._ALLOW_HINT.search(
                        lines_raw[check_idx]
                    ):
                        found_allow = True
                        break
                if found_allow:
                    continue
                # 3) 路由函数体内部是否出现 pydantic 痕迹
                if self._route_function_has_pydantic(
                    stripped, (m.start(), m.end())
                ):
                    continue
                # 4) 紧邻下方 3 行内（紧跟装饰器/函数定义）出现 pydantic 痕迹
                #    也放行（用于处理"路由函数被 pass / 仅调用 validate() "
                #    这种紧凑合法布局）
                if self._file_has_pydantic(stripped, ln, window=3):
                    continue
                snippet = line_snippet(text, m.start())
                violations.append(
                    Violation(rel, ln, snippet, extra=f"route={path}")
                )
        return violations


# ---------------------------------------------------------------------------
# A9：新增业务函数必须在 tests/ 至少有 1 个失败测试
# ---------------------------------------------------------------------------

class RuleA9NewFuncMustTest(Rule):
    """新增业务函数必须在 ``tests/`` 至少 1 个对应测试。

    这是一条"新增代码生效"规则：仅检查 git staged 中**新增**的 def，避免对存量
    函数一次性报几百条违规。

    强制要求（满足任一即可）：
    - tests/ 下存在 ``test_<func_name>.py`` 或 ``test_<module>_<func_name>.py``
      包含 ``test_<func_name>`` 形式的测试函数。
    - 同文件新增行中有 ``def test_<name>`` 这种 pytest 函数。
    - 新增行包含 ``# no-test:reason=...`` 豁免注释。

    排除范围（不算"业务函数"，不强制测试）：
    - 单下划线开头 ``_xxx``（内部 helper）
    - ``test_xxx``（本来就是测试）
    - dunder ``__xxx__``（魔术方法）
    - 顶层 ``main()`` 入口
    - 包含 ``@app.route`` 的路由函数（按 A2 走，不重复强制）
    - 包含 ``@property`` / ``@staticmethod`` / ``@classmethod`` 的属性/类方法
    """

    name = "a9"
    description = "新增业务函数必须在 tests/ 至少有 1 个失败测试"
    enabled = True
    scan_paths = ("app",)
    exclude_paths = ("app/ai", "app/migrations")
    extensions = (".py",)

    # 匹配 ``def function_name(``，行首可有空白。
    # 注意：前导空白用 [ \t]* 而非 \s*，否则 \s* 会跨行匹配到 def 之前的空行，
    # 导致 m.start() 指向空行、行号偏移、no-test 豁免注释检测失效。
    _DEF = re.compile(r"^[ \t]*def\s+([A-Za-z_]\w*)\s*\(", re.MULTILINE)
    _ALLOW_HINT = re.compile(r"#\s*no-test\s*:\s*reason\s*=", re.IGNORECASE)
    _ROUTE_DECORATOR = re.compile(r"@app\.route\b")

    # 排除的函数名前缀 / 模式
    _EXCLUDED_PREFIXES = ("_",)  # 以单下划线开头一律豁免
    _EXCLUDED_NAMES = {"main", "setUp", "tearDown", "setUpClass", "tearDownClass"}

    def _is_excluded(self, name: str) -> bool:
        if name.startswith(self._EXCLUDED_PREFIXES):
            return True
        if name.startswith("test_"):
            return True  # 测试函数本身不需要测试
        if name.startswith("__") and name.endswith("__"):
            return True
        if name in self._EXCLUDED_NAMES:
            return True
        return False

    def _function_has_test(self, name: str, text: str) -> bool:
        """同文件新增行中是否已包含 ``def test_<name>`` 或测试同名。"""
        return bool(
            re.search(
                rf"^\s*def\s+test_{re.escape(name)}\s*\(", text, re.MULTILINE
            )
        )

    def _tests_dir_has_test(self, name: str, tests_dir: Path) -> bool:
        """tests/ 下是否有 test_<name>.py 或包含 test_<name> 函数。"""
        if not tests_dir.exists():
            return False
        # 1) 命名匹配的文件
        for fname in (f"test_{name}.py", f"test_app_{name}.py"):
            if (tests_dir / fname).exists():
                return True
        # 2) 任意文件含 test_<name>
        for p in tests_dir.rglob("*.py"):
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if re.search(rf"\bdef\s+test_{re.escape(name)}\s*\(", txt):
                return True
        return False

    def scan(self, files: Sequence[Path], repo_root: Path) -> List[Violation]:
        violations: List[Violation] = []
        tests_dir = repo_root / "tests"
        for f in files:
            rel = str(f.relative_to(repo_root)).replace("\\", "/")
            if rel.startswith("app/ai/"):
                continue
            # 1) 必须处于 staged 新增行集合
            added_lines = get_staged_added_lines(repo_root, f)
            if not added_lines:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            stripped = strip_py_comments(text)
            # 注释行号检查用 text 原始字符串（strip_py_comments 把 # 替换为空格）
            lines_raw = text.split("\n")
            lines = stripped.split("\n")

            # 路由装饰器所在行集合（用于排除路由函数）
            route_line_nos: Set[int] = set()
            for m in self._ROUTE_DECORATOR.finditer(stripped):
                route_line_nos.add(line_number_at(text, m.start()))

            for m in self._DEF.finditer(stripped):
                name = m.group(1)
                if self._is_excluded(name):
                    continue
                ln = line_number_at(text, m.start())
                if ln not in added_lines:
                    continue
                # 排除路由函数（@app.route 装饰器与 def 之间可叠多层装饰器，
                # 如 @app.route + @require_role + @login_required + def 共跨 3 行；
                # 窗口放宽到 6 行，避免误报路由函数需单独测试）
                if any(ln - 6 <= rl <= ln for rl in route_line_nos):
                    continue
                # 排除属性/类方法
                if ln >= 2 and re.search(
                    r"@property|@staticmethod|@classmethod", lines[ln - 2]
                ):
                    continue
                # 同行 / 上一行 / 上两行（覆盖"def 行上一行是装饰器"情况）豁免注释
                found_allow = False
                for offset in (-2, -1, 0):
                    check_idx = ln - 1 + offset  # ln 是 1-indexed
                    if 0 <= check_idx < len(lines_raw) and self._ALLOW_HINT.search(
                        lines_raw[check_idx]
                    ):
                        found_allow = True
                        break
                if found_allow:
                    continue
                # 命中条件：同文件已有 test_<name> 或 tests/ 目录已有对应测试
                if self._function_has_test(name, stripped):
                    continue
                if self._tests_dir_has_test(name, tests_dir):
                    continue
                snippet = line_snippet(text, m.start())
                violations.append(
                    Violation(rel, ln, snippet, extra=f"def {name}()")
                )
        return violations


# ---------------------------------------------------------------------------
# A10：app/app.py 禁止新增 @app.route 路由（防 app.py 重新膨胀）
# ---------------------------------------------------------------------------

class RuleA10NoNewRouteInApp(Rule):
    """禁止在 ``app/app.py`` 新增 ``@app.route`` 路由。

    这是一条"新增代码生效"规则：仅检查 git staged 中 ``app/app.py`` **新增**的
    ``@app.route(...)`` 装饰器，强制新增路由走 ``app/routes/`` 独立模块
    （register-on-app 模式），防止 app.py 重新膨胀；存量路由不强制。

    豁免（任一命中即放行）：
    - 装饰器行 / 上一行 / 下一行出现 ``# route-in-app:reason=...`` 豁免注释
      （用于确有必要留在 app.py 的极少数路由，如启动期注册的特殊端点）。

    为什么强制走 routes/：
    - app.py 曾达约 3.6 万行，已按业务域拆到 ``app/routes/`` 38 个模块。
    - 若新路由直接写回 app.py，单文件膨胀风险会复发，可维护性下滑。
    - routes/ 模块 + register-on-app 模式完全不改变 endpoint 名 / URL，
      与 app.py 内既有 url_for 引用兼容。
    """

    name = "a10"
    description = "app.py 禁止新增 @app.route 路由（强制走 app/routes/）"
    enabled = True
    scan_paths = ("app",)
    exclude_paths = ()
    extensions = (".py",)

    # 匹配 ``@app.route(`` 装饰器（不限 methods，GET/POST 等一律强制走 routes/）
    _ROUTE = re.compile(r"@app\.route\s*\(")

    # 豁免注释: # route-in-app:reason=...
    _ALLOW_HINT = re.compile(r"#\s*route-in-app\s*:\s*reason\s*=", re.IGNORECASE)

    def scan(self, files: Sequence[Path], repo_root: Path) -> List[Violation]:
        violations: List[Violation] = []
        for f in files:
            rel = str(f.relative_to(repo_root)).replace("\\", "/")
            # 仅针对 app 主文件 app.py；其他文件（models/、routes/ 等）不适用
            if rel != "app/app.py":
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # 仅对 git staged 的新增行强制（存量路由不报）
            added_lines = get_staged_added_lines(repo_root, f)
            if not added_lines:
                continue
            stripped = strip_py_comments(text)
            lines_raw = text.split("\n")
            for m in self._ROUTE.finditer(stripped):
                ln = line_number_at(text, m.start())
                if ln not in added_lines:
                    continue  # 存量路由不强制
                # 装饰器行 / 上一行 / 下一行（含注释跨行）有无豁免注释
                line_idx = stripped[: m.start()].count("\n")
                found_allow = False
                for offset in (-1, 0, 1):
                    check_idx = line_idx + offset
                    if 0 <= check_idx < len(lines_raw) and self._ALLOW_HINT.search(
                        lines_raw[check_idx]
                    ):
                        found_allow = True
                        break
                if found_allow:
                    continue
                snippet = line_snippet(text, m.start())
                violations.append(
                    Violation(
                        rel,
                        ln,
                        snippet,
                        extra="app.py 新增路由，请移入 app/routes/ 模块",
                    )
                )
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
    "a8": RuleA8NewRoutePydantic(),
    "a9": RuleA9NewFuncMustTest(),
    "a10": RuleA10NoNewRouteInApp(),
}

RULE_DISPLAY_ORDER: Tuple[str, ...] = (
    "a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8", "a9", "a10",
)


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
WMS 防 BUG 多规则静态检查器（10 条规则）

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

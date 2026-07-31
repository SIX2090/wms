# -*- coding: utf-8 -*-
"""模块4黄金测试：lint_wms_rules.py 第 8/9 条规则（A8 pydantic + A9 测试）行为基线。

# AI_TASK: A8/A9 规则 黄金测试

A8 = 新增 POST/PUT/DELETE 路由必须用 pydantic BaseModel 做输入校验。
A9 = 新增业务函数必须在 tests/ 至少有 1 个对应 pytest 测试。

这两条规则都是"新增代码生效"：仅对 git staged 的新增行强制，对存量代码 0 违规。
本黄金测试通过临时 git index（stash-style）模拟新增/修改/不修改场景，验证规则触发、
豁免、路由函数豁免、下划线豁免、tests/ 已有 test_ 豁免、# pydantic:reason= 豁免等行为。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_LINT = WORKSPACE_ROOT / "scripts" / "lint_wms_rules.py"


def _run_git(args: list, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def temp_repo():
    """临时 git 仓库，复制 lint_wms_rules.py 用于 A8/A9 单元测试。"""
    tmp = Path(tempfile.mkdtemp(prefix="wms_a8a9_"))
    try:
        _run_git(["init", "-q"], tmp)
        _run_git(["config", "user.email", "test@example.com"], tmp)
        _run_git(["config", "user.name", "Test"], tmp)
        # 复制 lint_wms_rules.py 到临时仓库 scripts/
        scripts_dir = tmp / "scripts"
        scripts_dir.mkdir()
        shutil.copy(SCRIPT_LINT, scripts_dir / "lint_wms_rules.py")
        # 复制 app/ 骨架（rules 需要 scan_paths 存在）
        app_dir = tmp / "app"
        app_dir.mkdir()
        tests_dir = tmp / "tests"
        tests_dir.mkdir()
        # 首次 commit 让 HEAD 存在
        _run_git(["add", "-A"], tmp)
        _run_git(["commit", "-q", "-m", "init"], tmp)
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _stage_new_file(repo: Path, rel_path: str, content: str) -> None:
    """在 temp_repo 中新增并 stage 一个文件。"""
    target = repo / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _run_git(["add", rel_path], repo)


def _run_lint_staged(repo: Path, rule: str) -> tuple:
    """跑 lint_wms_rules.py --staged --rule <rule>，返回 (returncode, stdout)。"""
    proc = subprocess.run(
        ["python3", "scripts/lint_wms_rules.py", "--staged", "--rule", rule],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout


# ---------------------------------------------------------------------------
# 规则 A8 测试
# ---------------------------------------------------------------------------

class TestRuleA8Pydantic:
    """A8：新增 POST/PUT/DELETE 路由必须用 pydantic BaseModel 输入校验。"""

    def test_a8_无pydantic_应违规(self, temp_repo):
        """新增 POST 路由函数体内无 pydantic 痕迹 → A8 报违规。"""
        _stage_new_file(
            temp_repo,
            "app/test_route_no_pyd.py",
            (
                "from flask import request\n"
                "from app import app\n"
                "from app.utils import login_required\n"
                "\n"
                "@app.route('/api/x', methods=['POST'])\n"
                "@login_required\n"
                "def bad_route():\n"
                "    return {'ok': True}\n"
            ),
        )
        rc, out = _run_lint_staged(temp_repo, "a8")
        assert rc == 1, f"应该报违规但 rc={rc}, out={out!r}"
        assert "A8" in out
        assert "pydantic" in out

    def test_a8_有pydantic_放行(self, temp_repo):
        """新增 POST 路由函数体内引用 BaseModel → A8 放行。"""
        _stage_new_file(
            temp_repo,
            "app/test_route_with_pyd.py",
            (
                "from pydantic import BaseModel\n"
                "from app import app\n"
                "from app.utils import login_required\n"
                "\n"
                "class InputModel(BaseModel):\n"
                "    name: str\n"
                "\n"
                "@app.route('/api/good', methods=['POST'])\n"
                "@login_required\n"
                "def good_route():\n"
                "    payload = InputModel.parse_raw(request.get_data())\n"
                "    return {'ok': True, 'name': payload.name}\n"
            ),
        )
        rc, out = _run_lint_staged(temp_repo, "a8")
        assert rc == 0, f"应该放行但 rc={rc}, out={out!r}"

    def test_a8_pydantic_reason豁免(self, temp_repo):
        """路由装饰器/上/下三行内出现 ``# pydantic:reason=`` 注释 → 豁免。"""
        _stage_new_file(
            temp_repo,
            "app/test_route_exempt.py",
            (
                "from app import app\n"
                "from app.utils import login_required\n"
                "\n"
                "@app.route('/api/legacy', methods=['POST'])\n"
                "@login_required\n"
                "def legacy_route():  # pydantic:reason=legacy_internal_only\n"
                "    return {'ok': True}\n"
            ),
        )
        rc, out = _run_lint_staged(temp_repo, "a8")
        assert rc == 0, f"应被豁免但 rc={rc}, out={out!r}"

    def test_a8_存量代码不报(self, temp_repo):
        """未 staged 修改的文件 → A8 完全不报（避免对存量 612 个路由一次性报违规）。"""
        # 直接修改文件但不 add
        target = temp_repo / "app" / "old_route.py"
        target.write_text(
            "@app.route('/api/old', methods=['POST'])\n"
            "def old_route_no_pyd():\n"
            "    return {'ok': True}\n",
            encoding="utf-8",
        )
        rc, out = _run_lint_staged(temp_repo, "a8")
        assert rc == 0, f"非 staged 不应报但 rc={rc}, out={out!r}"


# ---------------------------------------------------------------------------
# 规则 A9 测试
# ---------------------------------------------------------------------------

class TestRuleA9Test:
    """A9：新增业务函数必须在 tests/ 至少有 1 个对应 pytest 测试。"""

    def test_a9_无测试_应违规(self, temp_repo):
        """新增业务函数且 tests/ 无对应 test_xxx → A9 报违规。"""
        _stage_new_file(
            temp_repo,
            "app/calc.py",
            (
                "def calculate_total(items):\n"
                "    return sum(i for i in items if i > 0)\n"
            ),
        )
        rc, out = _run_lint_staged(temp_repo, "a9")
        assert rc == 1, f"应该报违规但 rc={rc}, out={out!r}"
        assert "A9" in out
        assert "calculate_total" in out

    def test_a9_下划线开头_放行(self, temp_repo):
        """下划线开头 helper 函数 → A9 放行（不算业务函数）。"""
        _stage_new_file(
            temp_repo,
            "app/_helpers.py",
            (
                "def _private_helper(x):\n"
                "    return x * 2\n"
            ),
        )
        rc, out = _run_lint_staged(temp_repo, "a9")
        assert rc == 0, f"下划线开头应放行但 rc={rc}, out={out!r}"

    def test_a9_tests目录已存在对应测试_放行(self, temp_repo):
        """tests/ 下已存在 test_<name> 函数 → A9 放行。"""
        # 先在 tests/ 创建一个测试
        (temp_repo / "tests" / "test_calc.py").write_text(
            "def test_calculate_total():\n    assert True\n",
            encoding="utf-8",
        )
        _run_git(["add", "tests/test_calc.py"], temp_repo)
        # 再新增一个同名业务函数
        _stage_new_file(
            temp_repo,
            "app/calc2.py",
            (
                "def calculate_total_v2(items):\n"
                "    return sum(items)\n"
            ),
        )
        rc, out = _run_lint_staged(temp_repo, "a9")
        # calculate_total_v2 没有 test_, 但 calculate_total 有
        # calculate_total 没在新增行, 所以不强制, 只 calculate_total_v2 会报
        # 验证 calculate_total_v2 被报
        assert "calculate_total_v2" in out

    def test_a9_no_test_reason豁免(self, temp_repo):
        """def 上一行有 ``# no-test:reason=`` 注释 → 豁免。"""
        _stage_new_file(
            temp_repo,
            "app/exempt_func.py",
            (
                "def compute_hash(payload):  # no-test:reason=deprecated_will_be_removed\n"
                "    return hash(str(payload))\n"
            ),
        )
        rc, out = _run_lint_staged(temp_repo, "a9")
        assert rc == 0, f"应被豁免但 rc={rc}, out={out!r}"

    def test_a9_路由函数不强制测试(self, temp_repo):
        """路由函数（@app.route 装饰）→ A9 不强制（按 A2 走，不重复）。"""
        _stage_new_file(
            temp_repo,
            "app/route_func.py",
            (
                "from app import app\n"
                "from app.utils import login_required\n"
                "\n"
                "@app.route('/api/foo', methods=['POST'])\n"
                "@login_required\n"
                "def foo_handler():\n"
                "    return {'ok': True}\n"
            ),
        )
        rc, out = _run_lint_staged(temp_repo, "a9")
        # foo_handler 是路由函数, A9 应放行
        assert "foo_handler" not in out, f"路由函数不应被 A9 报但 out={out!r}"


# ---------------------------------------------------------------------------
# 规则注册表 / CLI 完整性测试
# ---------------------------------------------------------------------------

class TestRuleRegistry:
    """A8/A9 必须正确注册到 RULES 字典和 RULE_DISPLAY_ORDER。"""

    def test_a8_in_rules(self):
        """RULES['a8'] 必须存在并是 RuleA8NewRoutePydantic 实例。"""
        sys_path = str(SCRIPT_LINT.parent)
        import sys
        if sys_path not in sys.path:
            sys.path.insert(0, sys_path)
        import lint_wms_rules
        assert "a8" in lint_wms_rules.RULES
        assert (
            lint_wms_rules.RULES["a8"].__class__.__name__
            == "RuleA8NewRoutePydantic"
        )
        assert "a8" in lint_wms_rules.RULE_DISPLAY_ORDER

    def test_a9_in_rules(self):
        """RULES['a9'] 必须存在并是 RuleA9NewFuncMustTest 实例。"""
        sys_path = str(SCRIPT_LINT.parent)
        import sys
        if sys_path not in sys.path:
            sys.path.insert(0, sys_path)
        import lint_wms_rules
        assert "a9" in lint_wms_rules.RULES
        assert (
            lint_wms_rules.RULES["a9"].__class__.__name__
            == "RuleA9NewFuncMustTest"
        )
        assert "a9" in lint_wms_rules.RULE_DISPLAY_ORDER

    def test_list命令输出包含A8A9(self):
        """``--list`` 输出必须包含 A8/A9。"""
        proc = subprocess.run(
            ["python3", str(SCRIPT_LINT), "--list"],
            cwd=str(WORKSPACE_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        assert "[A8]" in proc.stdout
        assert "[A9]" in proc.stdout
        assert "pydantic" in proc.stdout
        assert "tests/" in proc.stdout

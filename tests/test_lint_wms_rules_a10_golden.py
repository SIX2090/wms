# -*- coding: utf-8 -*-
"""A10 规则黄金测试：lint_wms_rules.py 第 10 条规则（A10 app.py 防膨胀）。

# AI_TASK: A10 规则 黄金测试

A10 = ``app/app.py`` 禁止新增 ``@app.route`` 路由，强制走 ``app/routes/`` 模块。

这条规则是"新增代码生效"：仅对 git staged 中 ``app/app.py`` 的新增行强制，
对存量路由 0 违规。本黄金测试通过临时 git 仓库模拟新增路由 / 豁免注释 /
存量路由三种场景，验证规则触发与豁免行为。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
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
    """临时 git 仓库，复制 lint_wms_rules.py 用于 A10 单元测试。"""
    tmp = Path(tempfile.mkdtemp(prefix="wms_a10_"))
    try:
        _run_git(["init", "-q"], tmp)
        _run_git(["config", "user.email", "test@example.com"], tmp)
        _run_git(["config", "user.name", "Test"], tmp)
        scripts_dir = tmp / "scripts"
        scripts_dir.mkdir()
        shutil.copy(SCRIPT_LINT, scripts_dir / "lint_wms_rules.py")
        app_dir = tmp / "app"
        app_dir.mkdir()
        tests_dir = tmp / "tests"
        tests_dir.mkdir()
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
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "scripts/lint_wms_rules.py", "--staged", "--rule", rule],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    return proc.returncode, proc.stdout


class TestRuleA10NoNewRouteInApp:
    """A10：app/app.py 禁止新增 @app.route 路由。"""

    def test_a10_新增GET路由_应违规(self, temp_repo):
        """新增 app/app.py 含 @app.route（GET）→ A10 报违规。"""
        _stage_new_file(
            temp_repo,
            "app/app.py",
            (
                "from flask import Flask\n"
                "app = Flask(__name__)\n"
                "\n"
                "@app.route('/legacy')\n"
                "def legacy():\n"
                "    return {'ok': True}\n"
            ),
        )
        rc, out = _run_lint_staged(temp_repo, "a10")
        assert rc == 1, f"应该报违规但 rc={rc}, out={out!r}"
        assert "A10" in out
        assert "app/routes/" in out

    def test_a10_豁免注释放行(self, temp_repo):
        """装饰器上一行有 ``# route-in-app:reason=`` 注释 → A10 放行。"""
        _stage_new_file(
            temp_repo,
            "app/app.py",
            (
                "from flask import Flask\n"
                "app = Flask(__name__)\n"
                "\n"
                "# route-in-app:reason=legacy_entrypoint_must_stay_in_app\n"
                "@app.route('/legacy')\n"
                "def legacy():\n"
                "    return {'ok': True}\n"
            ),
        )
        rc, out = _run_lint_staged(temp_repo, "a10")
        assert rc == 0, f"应被豁免但 rc={rc}, out={out!r}"

    def test_a10_存量路由不报(self, temp_repo):
        """app/app.py 已提交（存量路由），staged 修改不含新路由 → 不报。"""
        app_py = temp_repo / "app" / "app.py"
        app_py.write_text(
            "@app.route('/legacy')\ndeg_dummy = 1\ndef legacy():\n    return {'ok': True}\n",
            encoding="utf-8",
        )
        _run_git(["add", "app/app.py"], temp_repo)
        _run_git(["commit", "-q", "-m", "add app.py"], temp_repo)
        # staged 修改：仅追加注释/空行，不含新 @app.route
        app_py.write_text(
            "@app.route('/legacy')\ndeg_dummy = 1\ndef legacy():\n    return {'ok': True}\n\n# helper comment\n",
            encoding="utf-8",
        )
        _run_git(["add", "app/app.py"], temp_repo)
        rc, out = _run_lint_staged(temp_repo, "a10")
        assert rc == 0, f"存量路由不应报但 rc={rc}, out={out!r}"

    def test_a10_非app_py文件不适用(self, temp_repo):
        """routes/ 下新增路由（@app.route）→ A10 不报（本就允许走 routes/）。"""
        _stage_new_file(
            temp_repo,
            "app/routes/foo.py",
            (
                "def register_foo_routes(app):\n"
                "    @app.route('/foo')\n"
                "    def foo():\n"
                "        return {'ok': True}\n"
            ),
        )
        rc, out = _run_lint_staged(temp_repo, "a10")
        assert rc == 0, f"routes/ 路由不应被 A10 报但 rc={rc}, out={out!r}"


class TestRuleA10Registry:
    """A10 必须正确注册到 RULES 字典和 RULE_DISPLAY_ORDER。"""

    def test_a10_in_rules(self):
        """RULES['a10'] 必须存在并是 RuleA10NoNewRouteInApp 实例。"""
        sys_path = str(SCRIPT_LINT.parent)
        if sys_path not in sys.path:
            sys.path.insert(0, sys_path)
        import lint_wms_rules
        assert "a10" in lint_wms_rules.RULES
        assert (
            lint_wms_rules.RULES["a10"].__class__.__name__
            == "RuleA10NoNewRouteInApp"
        )
        assert "a10" in lint_wms_rules.RULE_DISPLAY_ORDER

    def test_list命令输出包含A10(self):
        """``--list`` 输出必须包含 A10。"""
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_LINT), "--list"],
            cwd=str(WORKSPACE_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )
        assert proc.returncode == 0
        assert "[A10]" in proc.stdout
        assert "app/routes/" in proc.stdout
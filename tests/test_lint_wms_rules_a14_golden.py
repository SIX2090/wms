# -*- coding: utf-8 -*-
"""A14 规则黄金测试：CI/验证脚本以 production 导入 app 必须显式放行生产硬门禁（R6 机械化）。

A14 是 R6（同根因必须排查所有消费点）的机械化，实证 BUG-2026-09-20-004：
生产 Cookie 硬门禁引入后只给 tests/conftest.py 补 opt-in，漏排查 scripts/
下同样以 production 导入 app 的消费点，致 main 上 WMS CI 与 AI Verification 变红。

规则要点：仅对 staged 的 scripts/*.py 强制（存量不一次性报违规）；
切 testing 环境 / 不导入 app / 行尾 `# allow-no-optin` 均放行。
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

VERIFY_NO_OPTIN = """\
import sys
sys.path.insert(0, 'app')


def test_page():
    from app import app
    with app.test_client() as c:
        assert c.get('/x').status_code in (200, 302)
"""

VERIFY_WITH_OPTIN = """\
import os
import sys
sys.path.insert(0, 'app')
os.environ.setdefault('WMS_ALLOW_INSECURE_COOKIE', '1')


def test_page():
    from app import app
    with app.test_client() as c:
        assert c.get('/x').status_code in (200, 302)
"""

VERIFY_TESTING = """\
import os
import sys
sys.path.insert(0, 'app')
os.environ['FLASK_ENV'] = 'testing'


def test_page():
    from app import app
    assert app is not None
"""

VERIFY_NO_APP_IMPORT = """\
import re


def test_pattern():
    assert re.match('a', 'a')
"""


def _run_git(args: list, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args, cwd=str(cwd),
        capture_output=True, text=True, check=False,
    )


@pytest.fixture
def temp_repo():
    """临时 git 仓库：复制 lint 脚本 + 建 scripts/ 目录。"""
    tmp = Path(tempfile.mkdtemp(prefix="wms_a14_"))
    try:
        _run_git(["init", "-q"], tmp)
        _run_git(["config", "user.email", "test@example.com"], tmp)
        _run_git(["config", "user.name", "Test"], tmp)
        scripts_dir = tmp / "scripts"
        scripts_dir.mkdir()
        shutil.copy(SCRIPT_LINT, scripts_dir / "lint_wms_rules.py")
        (tmp / "README.md").write_text("# seed\n", encoding="utf-8")
        _run_git(["add", "-A"], tmp)
        _run_git(["commit", "-q", "-m", "init"], tmp)
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _stage_verify(repo: Path, content: str, name: str = "verify_fake.py") -> None:
    p = repo / "scripts" / name
    p.write_text(content, encoding="utf-8")
    _run_git(["add", f"scripts/{name}"], repo)


def _run_lint_staged(repo: Path) -> tuple:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "scripts/lint_wms_rules.py", "--staged", "--rule", "a14"],
        cwd=str(repo), capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env, check=False,
    )
    return proc.returncode, proc.stdout


def test_a14_flags_script_without_optin(temp_repo):
    """以 production 导入 app 且无 opt-in → 拦截（BUG-2026-09-20-004 复现场景）。"""
    _stage_verify(temp_repo, VERIFY_NO_OPTIN)
    code, out = _run_lint_staged(temp_repo)
    assert code == 1, out
    assert "verify_fake.py" in out
    assert "WMS_ALLOW_INSECURE_COOKIE" in out


def test_a14_passes_script_with_optin(temp_repo):
    """显式设置 opt-in → 放行。"""
    _stage_verify(temp_repo, VERIFY_WITH_OPTIN)
    code, out = _run_lint_staged(temp_repo)
    assert code == 0, out


def test_a14_passes_testing_env_script(temp_repo):
    """切到 testing 环境 → 不走生产门禁，放行。"""
    _stage_verify(temp_repo, VERIFY_TESTING)
    code, out = _run_lint_staged(temp_repo)
    assert code == 0, out


def test_a14_ignores_script_without_app_import(temp_repo):
    """不导入 app 的脚本 → 放行。"""
    _stage_verify(temp_repo, VERIFY_NO_APP_IMPORT)
    code, out = _run_lint_staged(temp_repo)
    assert code == 0, out


def test_a14_ignores_non_import_edits_on_existing_script(temp_repo):
    """存量脚本本次只改空行/注释（staged 新增行无 app 引用）→ 不触发，避免误报。"""
    p = temp_repo / "scripts" / "verify_legacy.py"
    p.write_text(VERIFY_NO_OPTIN, encoding="utf-8")
    _run_git(["add", "scripts/verify_legacy.py"], temp_repo)
    _run_git(["commit", "-q", "-m", "add legacy"], temp_repo)

    # 仅插入空行与注释，不新增 app 引用行
    p.write_text(
        "# 本次仅调整排版\n" + VERIFY_NO_OPTIN.replace("import sys", "import sys\n"),
        encoding="utf-8",
    )
    _run_git(["add", "scripts/verify_legacy.py"], temp_repo)
    code, out = _run_lint_staged(temp_repo)
    assert code == 0, out


def test_a14_flags_newly_added_import_line_on_existing_script(temp_repo):
    """存量脚本本次新增了 app 引用行 → 触发（新增代码生效）。"""
    p = temp_repo / "scripts" / "verify_legacy2.py"
    p.write_text("import re\n\n\ndef test_x():\n    assert re.match('a', 'a')\n", encoding="utf-8")
    _run_git(["add", "scripts/verify_legacy2.py"], temp_repo)
    _run_git(["commit", "-q", "-m", "add legacy2"], temp_repo)

    # 新增一段引入 app 的代码，且全脚本无 opt-in
    p.write_text(
        "import re\n\n\ndef test_x():\n    assert re.match('a', 'a')\n\n\n"
        "def test_app_import():\n    from app import app\n    assert app is not None\n",
        encoding="utf-8",
    )
    _run_git(["add", "scripts/verify_legacy2.py"], temp_repo)
    code, out = _run_lint_staged(temp_repo)
    assert code == 1, out
    assert "verify_legacy2.py" in out

# -*- coding: utf-8 -*-
"""BUG-2026-09-20-004 回归：BUG-2026-09-19-003 生产 Cookie 硬门禁漏排查 CI/验证脚本消费点。

根因：硬门禁引入后只给 tests/conftest.py 补了 WMS_ALLOW_INSECURE_COOKIE=1，
未排查「以 production 启动服务 / 导入 app」的非 pytest 消费点，导致
    - scripts/run_smoke_in_ci.py（FLASK_ENV=production 启服务）被拒启动 → WMS CI 红
    - scripts/verify_ai_business_quality_dashboard.py 等 verify 脚本导入 app 失败 → AI Verification 红

本测试锁定「CI 侧脚本必须显式 opt-in」契约，防止新增消费点时再次漏排查（R6）。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

# CI 中会以 production 启动服务 / 导入 app 的消费点清单
CI_CONSUMERS = [
    "run_smoke_in_ci.py",
    "verify_ai_business_quality_dashboard.py",
    "verify_ai_purchase_workbench_page.py",
    "verify_ai_warehouse_workbench_page.py",
    "verify_ai_provider_evaluation.py",
]


def _read(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def test_ci_consumers_exist():
    """A9 对应测试：清单内脚本必须存在，避免改名后断言空转。"""
    for name in CI_CONSUMERS:
        assert (SCRIPTS / name).exists(), f"scripts/{name} 不存在，请同步更新本测试清单"


@pytest.mark.parametrize("name", CI_CONSUMERS)
def test_ci_consumer_sets_insufficient_cookie_optin(name: str):
    """每个 CI 侧消费点都必须显式设置 WMS_ALLOW_INSECURE_COOKIE。"""
    src = _read(name)
    assert "WMS_ALLOW_INSECURE_COOKIE" in src, (
        f"scripts/{name} 缺 WMS_ALLOW_INSECURE_COOKIE 显式放行："
        "production 环境下导入 app 会被 BUG-2026-09-19-003 硬门禁拒绝（BUG-2026-09-20-004 复现）"
    )


def test_smoke_script_sets_env_in_start_server():
    """冒烟脚本必须把 opt-in 注入子进程 env（而非仅写在注释里）。"""
    src = _read("run_smoke_in_ci.py")
    assert re.search(
        r'env\["WMS_ALLOW_INSECURE_COOKIE"\]\s*=\s*"1"', src
    ), "run_smoke_in_ci.py 必须在 start_server() 的 env 中注入 WMS_ALLOW_INSECURE_COOKIE=1"
    assert 'env["FLASK_ENV"] = "production"' in src, (
        "冒烟脚本以 production 启动服务这一前提已变，请复核本测试"
    )


def test_guard_reproduces_without_optin(monkeypatch):
    """缺省 opt-in 时门禁必须复现（证明测的是真约束，不是空断言）。"""
    from config import validate_production_security_config

    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    monkeypatch.delenv("WMS_ALLOW_INSECURE_COOKIE", raising=False)
    monkeypatch.setenv("FLASK_ENV", "production")
    with pytest.raises(RuntimeError, match="SESSION_COOKIE_SECURE"):
        validate_production_security_config("production")


def test_guard_passes_with_optin(monkeypatch):
    """CI 脚本注入的 opt-in 值必须真能放行门禁。"""
    from config import validate_production_security_config

    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    monkeypatch.setenv("WMS_ALLOW_INSECURE_COOKIE", "1")
    assert validate_production_security_config("production") is None

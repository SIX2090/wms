from __future__ import annotations

import pytest

from config import ProductionConfig, validate_production_security_config


def test_validate_production_security_config(monkeypatch):
    """A9 对应测试：生产环境禁止通过环境变量关闭 CSRF。"""
    monkeypatch.setenv("WMS_ALLOW_INSECURE_COOKIE", "1")
    monkeypatch.setenv("WMS_DISABLE_CSRF", "1")
    with pytest.raises(RuntimeError, match="CSRF"):
        validate_production_security_config()
    monkeypatch.delenv("WMS_DISABLE_CSRF", raising=False)
    assert validate_production_security_config() is None


def test_production_csrf_is_enabled_without_disable_flag(monkeypatch):
    monkeypatch.setenv("WMS_ALLOW_INSECURE_COOKIE", "1")
    monkeypatch.delenv("WMS_DISABLE_CSRF", raising=False)
    validate_production_security_config()
    assert ProductionConfig.WTF_CSRF_ENABLED is True


@pytest.mark.parametrize("value", ["1", "true", "yes"])
def test_production_rejects_csrf_disable_flag(monkeypatch, value):
    monkeypatch.setenv("WMS_ALLOW_INSECURE_COOKIE", "1")
    monkeypatch.setenv("WMS_DISABLE_CSRF", value)
    with pytest.raises(RuntimeError, match="CSRF"):
        validate_production_security_config()


def test_non_production_config_does_not_use_production_guard(monkeypatch):
    monkeypatch.setenv("WMS_DISABLE_CSRF", "1")
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    monkeypatch.delenv("WMS_ALLOW_INSECURE_COOKIE", raising=False)
    validate_production_security_config(environment="testing")


# ---------- BUG-2026-09-19-003：生产会话 Cookie 安全硬门禁 ----------


def test_production_rejects_insecure_session_cookie_without_optin(monkeypatch):
    """生产既未开 SESSION_COOKIE_SECURE 也未显式放行时，阻止启动。"""
    monkeypatch.delenv("WMS_DISABLE_CSRF", raising=False)
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    monkeypatch.delenv("WMS_ALLOW_INSECURE_COOKIE", raising=False)
    with pytest.raises(RuntimeError, match="SESSION_COOKIE_SECURE"):
        validate_production_security_config()


@pytest.mark.parametrize("value", ["1", "true", "yes"])
def test_production_allows_insecure_cookie_with_explicit_optin(monkeypatch, value):
    """显式 WMS_ALLOW_INSECURE_COOKIE=1（受信内网 HTTP）放行启动。"""
    monkeypatch.delenv("WMS_DISABLE_CSRF", raising=False)
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    monkeypatch.setenv("WMS_ALLOW_INSECURE_COOKIE", value)
    assert validate_production_security_config() is None


@pytest.mark.parametrize("value", ["1", "true", "yes"])
def test_production_allows_secure_cookie_without_optin(monkeypatch, value):
    """SESSION_COOKIE_SECURE=true（HTTPS 部署）无需显式放行。"""
    monkeypatch.delenv("WMS_DISABLE_CSRF", raising=False)
    monkeypatch.setenv("SESSION_COOKIE_SECURE", value)
    monkeypatch.delenv("WMS_ALLOW_INSECURE_COOKIE", raising=False)
    assert validate_production_security_config() is None


def test_non_production_skips_insecure_cookie_guard(monkeypatch):
    """非生产环境不受会话 Cookie 门禁约束。"""
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    monkeypatch.delenv("WMS_ALLOW_INSECURE_COOKIE", raising=False)
    validate_production_security_config(environment="development")
    validate_production_security_config(environment="testing")

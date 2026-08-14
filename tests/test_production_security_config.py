from __future__ import annotations

import pytest

from config import ProductionConfig, validate_production_security_config


def test_validate_production_security_config(monkeypatch):
    """A9 对应测试：生产环境禁止通过环境变量关闭 CSRF。"""
    monkeypatch.setenv("WMS_DISABLE_CSRF", "1")
    with pytest.raises(RuntimeError, match="CSRF"):
        validate_production_security_config()
    monkeypatch.delenv("WMS_DISABLE_CSRF", raising=False)
    assert validate_production_security_config() is None


def test_production_csrf_is_enabled_without_disable_flag(monkeypatch):
    monkeypatch.delenv("WMS_DISABLE_CSRF", raising=False)
    validate_production_security_config()
    assert ProductionConfig.WTF_CSRF_ENABLED is True


@pytest.mark.parametrize("value", ["1", "true", "yes"])
def test_production_rejects_csrf_disable_flag(monkeypatch, value):
    monkeypatch.setenv("WMS_DISABLE_CSRF", value)
    with pytest.raises(RuntimeError, match="CSRF"):
        validate_production_security_config()


def test_non_production_config_does_not_use_production_guard(monkeypatch):
    monkeypatch.setenv("WMS_DISABLE_CSRF", "1")
    validate_production_security_config(environment="testing")

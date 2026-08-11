# -*- coding: utf-8 -*-
"""
BUG-2026-08-11-012 回归测试：助手健康检查 30s 进程内缓存。

根因：
- `wechat_share_page` 每次渲染都调用 `_wechat_share_get_helper_health`，
  内部同步 `requests.get(health_url, timeout=1.5)`；助手离线时每次打开
  分享页都被卡住约 1.5s，连续刷新/多标签打开体验很差。

修复：
- 模块级 `_WECHAT_SHARE_HEALTH_CACHE`：按 health_url 缓存结果 30s，
  30s 内重复调用直接命中缓存，不再发起 HTTP 请求；
- 地址未配置时同步清空缓存，避免换配置后命中旧地址结果。

验收点：
T1. 30s 内连续两次调用只发起 1 次 HTTP 请求，第二次命中缓存。
T2. 超过 30s 后缓存过期，重新发起 HTTP 请求。
T3. 更换 helper_url 后旧缓存不命中，按新地址重新请求。
T4. 未配置 helper_url 时不发请求，且已有缓存被清空。
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402

app_module.app.config["TESTING"] = True


def _make_config(**overrides):
    defaults = dict(helper_url="http://127.0.0.1:8765/send")
    defaults.update(overrides)
    return types.SimpleNamespace(**defaults)


class _FakeResponse:
    ok = True
    status_code = 200

    def json(self):
        return {
            "status": "ok",
            "wechat_window_found": True,
            "poll_enabled": False,
            "wms_base_url": "http://127.0.0.1:8080",
            "poll_interval": 30,
        }


def _reset_cache():
    app_module._WECHAT_SHARE_HEALTH_CACHE.update({"url": "", "at": None, "health": None})


def _freeze_time(monkeypatch, frozen_now):
    """把 app 模块里的 datetime 换成 now() 固定为 frozen_now 的子类。"""

    class _FrozenDatetime(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen_now

    monkeypatch.setattr(app_module, "datetime", _FrozenDatetime)
    return _FrozenDatetime


def _real_datetime():
    return dt.datetime


class TestHelperHealthCache:
    def test_t1_second_call_within_30s_hits_cache(self, monkeypatch):
        """T1：30s 内第二次调用命中缓存，requests.get 仅调用 1 次。"""
        _reset_cache()
        calls = []
        monkeypatch.setattr("requests.get", lambda url, timeout=None: calls.append(url) or _FakeResponse())
        with app_module.app.app_context():
            first = app_module._wechat_share_get_helper_health(_make_config())
            second = app_module._wechat_share_get_helper_health(_make_config())
        assert first["online"] is True
        assert second["online"] is True
        assert len(calls) == 1, f"30s 内应只请求 1 次，实际 {len(calls)} 次"

    def test_t2_cache_expires_after_30s(self, monkeypatch):
        """T2：超过 30s 缓存过期，重新发起请求。"""
        _reset_cache()
        calls = []
        monkeypatch.setattr("requests.get", lambda url, timeout=None: calls.append(url) or _FakeResponse())
        t0 = dt.datetime(2026, 8, 11, 12, 0, 0)
        frozen = _freeze_time(monkeypatch, t0)
        try:
            with app_module.app.app_context():
                app_module._wechat_share_get_helper_health(_make_config())
            # 推进 31 秒
            class _LaterDatetime(dt.datetime):
                @classmethod
                def now(cls, tz=None):
                    return t0 + dt.timedelta(seconds=31)

            monkeypatch.setattr(app_module, "datetime", _LaterDatetime)
            with app_module.app.app_context():
                app_module._wechat_share_get_helper_health(_make_config())
        finally:
            monkeypatch.setattr(app_module, "datetime", _real_datetime())
        assert len(calls) == 2, f"超过 30s 应重新请求，实际 {len(calls)} 次"

    def test_t3_url_change_bypasses_cache(self, monkeypatch):
        """T3：更换 helper_url 后旧缓存不命中。"""
        _reset_cache()
        calls = []
        monkeypatch.setattr("requests.get", lambda url, timeout=None: calls.append(url) or _FakeResponse())
        with app_module.app.app_context():
            app_module._wechat_share_get_helper_health(_make_config())
            app_module._wechat_share_get_helper_health(
                _make_config(helper_url="http://localhost:8765/send")
            )
        assert calls == [
            "http://127.0.0.1:8765/health",
            "http://localhost:8765/health",
        ], calls

    def test_t4_unconfigured_clears_cache_and_skips_request(self, monkeypatch):
        """T4：未配置地址时不发请求，且已有缓存被清空。"""
        _reset_cache()
        calls = []
        monkeypatch.setattr("requests.get", lambda url, timeout=None: calls.append(url) or _FakeResponse())
        with app_module.app.app_context():
            app_module._wechat_share_get_helper_health(_make_config())
            assert len(calls) == 1
            health = app_module._wechat_share_get_helper_health(_make_config(helper_url=""))
        assert health["configured"] is False
        assert "未配置" in health["message"]
        assert len(calls) == 1, "未配置不得发起请求"
        assert app_module._WECHAT_SHARE_HEALTH_CACHE["health"] is None, "缓存应被清空"
        _reset_cache()

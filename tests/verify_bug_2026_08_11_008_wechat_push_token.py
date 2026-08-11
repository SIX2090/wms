# -*- coding: utf-8 -*-
"""
BUG-2026-08-11-008 回归测试：微信分享直推模式缺少 helper token 导致一律 403。

根因：
- `_wechat_share_send_image` POST 到助手 `/send` 时未携带 `X-Wechat-Helper-Token`，
  而助手端 `_check_auth` 强制校验该 token（未配置也拒绝）→ 默认配置下直推必 403。
- 同时 helper_url 可配置成任意外网地址，token 一旦携带会明文泄露给第三方主机。

修复：
- 直推请求携带 `X-Wechat-Helper-Token: app.config['WECHAT_HELPER_TOKEN']`；
- 新增 `_wechat_share_helper_url_allowed`：helper_url 仅允许 http(s) + 本机回环
  （127.0.0.1 / localhost / ::1），发送前与保存配置时均校验；
- token 未配置时直推直接拒绝并提示，不发请求。

验收点：
T1. 直推请求携带正确的 token header，且合法回环地址正常发出请求。
T2. 非回环地址被拒绝（sent=False，消息含"回环"），且未发起任何 HTTP 请求。
T3. token 未配置时拒绝直推，且未发起任何 HTTP 请求。
T4. 保存配置路由拒绝非回环 helper_url，接受合法回环地址。
"""
from __future__ import annotations

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
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False
app_module.app.config["WECHAT_HELPER_TOKEN"] = "test-helper-token-008"


def _make_config(**overrides):
    defaults = dict(
        helper_url="http://127.0.0.1:8765/send",
        sender_name="",
        sender_wechat_id="",
        receiver_name="张三",
        receiver_wechat_id="",
        receiver_search_key="张三",
        receiver_type="person",
        auto_send=False,
    )
    defaults.update(overrides)
    return types.SimpleNamespace(**defaults)


def _make_image(tmp_path):
    image_path = tmp_path / "share.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nfake-png-bytes")
    return str(image_path)


class _FakeResponse:
    ok = True
    status_code = 200

    def json(self):
        return {"status": "sent", "msg": "已发送给：张三"}


class TestDirectPushToken:
    def test_t1_push_carries_helper_token(self, tmp_path, monkeypatch):
        """T1：直推请求携带 X-Wechat-Helper-Token，且状态映射为 sent。"""
        captured = {}
        # 同进程跑多个 verify 文件时，其它文件的模块级 config 赋值会覆盖本文件的
        # 模块级 token；测试内用 monkeypatch.setitem 固定，保证用例间相互隔离。
        monkeypatch.setitem(app_module.app.config, "WECHAT_HELPER_TOKEN", "test-helper-token-008")

        def fake_post(url, data=None, files=None, headers=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers or {}
            captured["data"] = data or {}
            return _FakeResponse()

        monkeypatch.setattr("requests.post", fake_post)
        with app_module.app.app_context():
            status, code, message = app_module._wechat_share_send_image(
                _make_config(), _make_image(tmp_path)
            )
        assert status == "sent", message
        assert captured["url"] == "http://127.0.0.1:8765/send"
        assert captured["headers"].get("X-Wechat-Helper-Token") == "test-helper-token-008"

    def test_t2_non_loopback_url_rejected(self, tmp_path, monkeypatch):
        """T2：非回环地址被拒绝且不发请求。"""
        calls = []
        monkeypatch.setattr("requests.post", lambda *a, **kw: calls.append(a))
        with app_module.app.app_context():
            status, code, message = app_module._wechat_share_send_image(
                _make_config(helper_url="http://evil.example.com/send"),
                _make_image(tmp_path),
            )
        assert status == "failed"
        assert code == "invalid_helper_url"
        assert "回环" in message
        assert calls == [], "非回环地址不得发起 HTTP 请求"

    def test_t3_missing_token_rejected(self, tmp_path, monkeypatch):
        """T3：WECHAT_HELPER_TOKEN 未配置时拒绝直推且不发请求。"""
        calls = []
        monkeypatch.setattr("requests.post", lambda *a, **kw: calls.append(a))
        with app_module.app.app_context():
            old = app_module.app.config.get("WECHAT_HELPER_TOKEN")
            app_module.app.config["WECHAT_HELPER_TOKEN"] = ""
            try:
                status, code, message = app_module._wechat_share_send_image(
                    _make_config(), _make_image(tmp_path)
                )
            finally:
                app_module.app.config["WECHAT_HELPER_TOKEN"] = old
        assert status == "failed"
        assert code == "token_not_configured"
        assert "TOKEN" in message.upper() or "token" in message
        assert calls == []

    def test_t4_save_route_validates_helper_url(self):
        """T4：保存配置拒绝非回环地址、接受合法回环地址。"""
        from werkzeug.security import generate_password_hash
        from app import User

        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            db.session.add(User(
                username="admin",
                password_hash=generate_password_hash("admin"),
                role="admin",
                must_change_password=False,
            ))
            db.session.commit()

        client = app_module.app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"})

        bad = client.post("/wechat_share/save", data={
            "share_time": "15:30",
            "receiver_name": "张三",
            "helper_url": "http://192.168.1.100:8765/send",
        })
        assert bad.get_json()["status"] == "error"
        assert "回环" in bad.get_json()["msg"]

        good = client.post("/wechat_share/save", data={
            "share_time": "15:30",
            "receiver_name": "张三",
            "helper_url": "http://127.0.0.1:8765/send",
        })
        assert good.get_json()["status"] == "success", good.get_json()

        with app_module.app.app_context():
            from app import WechatShareConfig
            cfg = WechatShareConfig.query.first()
            assert cfg.helper_url == "http://127.0.0.1:8765/send"


class TestHelperUrlAllowed:
    """_wechat_share_helper_url_allowed 的单元行为。"""

    def test_loopback_accepted(self):
        with app_module.app.app_context():
            for url in ("http://127.0.0.1:8765/send", "http://localhost:8765/send",
                        "https://127.0.0.1:8765/send", "http://[::1]:8765/send"):
                assert app_module._wechat_share_helper_url_allowed(url), url

    def test_rejected_values(self):
        with app_module.app.app_context():
            for url in ("", "ftp://127.0.0.1/send", "http://0.0.0.0:8765/send",
                        "http://192.168.0.2/send", "http://wechat.internal.lan/send",
                        "not-a-url"):
                assert not app_module._wechat_share_helper_url_allowed(url), url

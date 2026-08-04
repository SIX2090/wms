# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：微信分享（wechat_share）域路由迁移到 routes/wechat_share.py。

采用 register-on-app 模式（register_wechat_share_routes(app)），endpoint 名保持不变
（wechat_share_page/save_wechat_share_config/run_wechat_share_now/
resend_wechat_share_log/clear_wechat_share_logs/download_wechat_share_log_image），
URL 路径不变。

验收点：
S1. 6 个 endpoint 已注册，仍是原始 endpoint 名，不存在 wechat_share.xxx 重复。
S2. URL 路径保持不变。
S3. 分享配置页可渲染（200）。
S4. 保存配置：分享时间格式非法被拒；缺少接收人被拒；合法保存成功。
S5. 清理记录：仅允许清理 failed/skipped，其他状态被拒。
S6. 立即执行可调用（返回 success 或含 msg 的 error 信封）。
"""
from __future__ import annotations

import os
import sys
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

WECHAT_ENDPOINTS = [
    "wechat_share_page",
    "save_wechat_share_config",
    "run_wechat_share_now",
    "resend_wechat_share_log",
    "clear_wechat_share_logs",
    "download_wechat_share_log_image",
]


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    return app_module.app.test_client()


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


class TestWechatShareRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
        return _make_client()

    def test_endpoints_and_urls(self):
        """S1/S2：6 个 endpoint 注册、URL 不变、无前缀重复。"""
        with app_module.app.app_context():
            for ep in WECHAT_ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
            for ep in WECHAT_ENDPOINTS:
                assert f"wechat_share.{ep}" not in app_module.app.view_functions, f"wechat_share.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("wechat_share_page") == "/wechat_share"
                assert url_for("save_wechat_share_config") == "/wechat_share/save"
                assert url_for("run_wechat_share_now") == "/wechat_share/run_now"
                assert url_for("resend_wechat_share_log", log_id=1) == "/wechat_share/log/1/resend"
                assert url_for("clear_wechat_share_logs") == "/wechat_share/logs/clear"
                assert url_for("download_wechat_share_log_image", log_id=1) == "/wechat_share/log/1/image"

    def test_wechat_share_page(self):
        """S3：分享配置页可渲染。"""
        client = self._setup()
        _login(client)
        resp = client.get("/wechat_share")
        assert resp.status_code == 200
        assert "微信" in resp.get_data(as_text=True)

    def test_save_config(self):
        """S4：时间格式非法/缺接收人被拒；合法保存成功。"""
        client = self._setup()
        _login(client)
        # 时间格式非法
        r1 = client.post("/wechat_share/save", data={"share_time": "25:99", "receiver_name": "张三"})
        assert r1.get_json()["status"] == "error"
        # 缺少接收人
        r2 = client.post("/wechat_share/save", data={"share_time": "15:30"})
        assert r2.get_json()["status"] == "error"
        # 合法保存
        r3 = client.post("/wechat_share/save", data={
            "share_time": "16:00",
            "receiver_name": "张三",
            "receiver_wechat_id": "wx_zhangsan",
            "enabled": "1",
        })
        assert r3.get_json()["status"] == "success", r3.get_json()
        with app_module.app.app_context():
            from app import WechatShareConfig
            cfg = WechatShareConfig.query.first()
            assert cfg is not None
            assert cfg.receiver_name == "张三"
            assert cfg.share_time == "16:00"

    def test_clear_logs(self):
        """S5：仅允许清理 failed/skipped。"""
        client = self._setup()
        _login(client)
        r1 = client.post("/wechat_share/logs/clear", data={"status": "sent"})
        assert r1.get_json()["status"] == "error"
        r2 = client.post("/wechat_share/logs/clear", data={"status": "failed"})
        assert r2.get_json()["status"] == "success", r2.get_json()

    def test_run_now(self):
        """S6：立即执行返回标准信封。"""
        client = self._setup()
        _login(client)
        resp = client.post("/wechat_share/run_now", data={"force": "1"})
        data = resp.get_json()
        assert data is not None
        assert "status" in data
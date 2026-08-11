# -*- coding: utf-8 -*-
"""
BUG-2026-08-11-014 回归测试：重发微信分享冻结使用历史接收人。

根因：
- `resend_wechat_share_log` 直接用当前配置 `config.receiver_*` 直推；
  分享记录列表"接收人"列展示的却是分享时冻结的 `log.receiver_*`，
  配置中途修改后点重发，实际收件人与页面展示不一致，悄悄发错人。

修复：
- 重发时若日志存在冻结接收人（receiver_name/receiver_wechat_id），
  构造发送快照覆盖接收人字段（search key 取冻结值），
  并在 message 标注"按历史接收人重发"；无冻结接收人时回退当前配置。

验收点：
T1. 日志有冻结接收人时，直推使用历史接收人而非当前配置接收人。
T2. 日志无冻结接收人时，回退使用当前配置接收人。
T3. 使用冻结接收人时 message 标注"按历史接收人 张三 重发"。
"""
from __future__ import annotations

import datetime as dt
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
from app import WechatShareConfig, WechatShareLog, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _login_admin(client):
    from werkzeug.security import generate_password_hash
    from app import User

    db.session.add(User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    ))
    db.session.commit()
    client.post("/login", data={"username": "admin", "password": "admin"})


def _seed(tmp_path, receiver_name, receiver_wechat_id):
    """建配置（当前接收人=当前李四）+ 一条带图片的分享日志，返回 log。"""
    config = WechatShareConfig(
        sender_name="",
        sender_wechat_id="",
        receiver_name="当前李四",
        receiver_wechat_id="",
        receiver_search_key="当前李四",
        receiver_type="person",
        share_time="15:30",
        share_in_order=True,
        immediate_on_complete=False,
        enabled=True,
        auto_send=False,
        helper_url="http://127.0.0.1:8765/send",
        updated_at=dt.datetime.now(),
    )
    db.session.add(config)
    db.session.flush()
    image_path = tmp_path / "20260811_153000_RK20260811-0001.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    log = WechatShareLog(
        config_id=config.id,
        module_key="in_order",
        order_id=1,
        order_no="RK20260811-0001",
        share_date=dt.date.today(),
        trigger_type="manual",
        status="failed",
        message="原发送失败",
        image_path=str(image_path),
        image_size=15,
        receiver_name=receiver_name,
        receiver_wechat_id=receiver_wechat_id,
    )
    db.session.add(log)
    db.session.commit()
    return log


class TestResendFrozenReceiver:
    def _resend(self, tmp_path, monkeypatch, receiver_name, receiver_wechat_id):
        monkeypatch.setattr(app_module, "_wechat_share_output_dir", lambda: str(tmp_path))
        captured = {}

        def fake_send(config, image_path):
            captured["receiver_name"] = config.receiver_name
            captured["receiver_wechat_id"] = config.receiver_wechat_id
            captured["receiver_search_key"] = config.receiver_search_key
            return "sent", "ok", "已发送"

        monkeypatch.setattr(app_module, "_wechat_share_send_image", fake_send)
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            log = _seed(tmp_path, receiver_name, receiver_wechat_id)
            log_id = log.id
            client = app_module.app.test_client()
            _login_admin(client)
            response = client.post(f"/wechat_share/log/{log_id}/resend")
        return response, captured

    def test_t1_resend_uses_frozen_receiver(self, tmp_path, monkeypatch):
        """T1：直推使用冻结接收人 张三，而非当前配置 当前李四。"""
        response, captured = self._resend(tmp_path, monkeypatch, "张三", "")
        assert response.get_json()["status"] == "success"
        assert captured["receiver_name"] == "张三"
        assert captured["receiver_search_key"] == "张三"

    def test_t2_resend_falls_back_to_config_when_no_frozen(self, tmp_path, monkeypatch):
        """T2：无冻结接收人时回退当前配置接收人。"""
        response, captured = self._resend(tmp_path, monkeypatch, "", "")
        assert response.get_json()["status"] == "success"
        assert captured["receiver_name"] == "当前李四"

    def test_t3_message_marks_frozen_receiver(self, tmp_path, monkeypatch):
        """T3：使用冻结接收人时 message 标注提示。"""
        response, _captured = self._resend(tmp_path, monkeypatch, "张三", "")
        payload = response.get_json()
        assert payload["status"] == "success"
        assert "按历史接收人 张三 重发" in payload["msg"]

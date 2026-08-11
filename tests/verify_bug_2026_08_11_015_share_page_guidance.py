# -*- coding: utf-8 -*-
"""
BUG-2026-08-11-015 回归测试：微信分享页界面引导补充。

背景：
- 用户不清楚「直推」与「轮询」两种发送模式的区别，pending 记录为何堆积；
- auto_send（自动点击发送）无任何风险提示，消息发出无法撤回；
- 待发送记录没有消化路径引导。

修复（纯模板改动 app/templates/wechat_share.html）：
1. 助手地址字段下增加发送模式说明（直推 / 轮询 / 回环地址限制）；
2. auto_send 勾选时显示警示条（无人工确认、无法撤回），未勾选时默认隐藏，
   并由 JS change 监听实时切换；
3. 存在 pending 记录时状态卡片显示消化引导，并按助手在线/轮询状态给出提示。

验收点：
T1. 页面包含模式引导文案（直推 / 轮询 / WMS_WECHAT_HELPER_POLL）。
T2. auto_send 关闭时风险提示存在但默认隐藏；开启时不带 display:none。
T3. 无 pending 记录时不显示消化引导；有 pending 时显示引导文案。
T4. pending 存在且助手在线但未开轮询时，提示"不会被自动消费"。
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

_FAKE_HEALTH_ONLINE_NO_POLL = {
    "configured": True,
    "online": True,
    "wechat_window_found": True,
    "poll_enabled": False,
    "wms_base_url": "",
    "poll_interval": "",
    "message": "助手在线",
}


def _setup_db():
    from werkzeug.security import generate_password_hash
    from app import User

    db.drop_all()
    db.create_all()
    db.session.add(User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    ))
    db.session.commit()


def _client():
    client = app_module.app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"})
    return client


def _render(client, monkeypatch, health=None):
    """渲染分享页：固定健康检查结果，避免真实 HTTP 请求。"""
    monkeypatch.setattr(
        app_module, "_wechat_share_get_helper_health",
        lambda config: dict(health or _FAKE_HEALTH_ONLINE_NO_POLL),
    )
    response = client.get("/wechat_share")
    assert response.status_code == 200
    return response.get_data(as_text=True)


class TestSharePageGuidance:
    def test_t1_mode_guidance_present(self, monkeypatch):
        """T1：模式引导文案存在（直推 / 轮询 / 回环限制）。"""
        with app_module.app.app_context():
            _setup_db()
        html = _render(_client(), monkeypatch)
        assert "直推" in html
        assert "轮询" in html
        assert "WMS_WECHAT_HELPER_POLL=1" in html
        assert "127.0.0.1" in html

    def test_t2_auto_send_risk_hint_visibility(self, monkeypatch):
        """T2：auto_send 关闭时警示默认隐藏，开启时可见。"""
        from app import WechatShareConfig

        with app_module.app.app_context():
            _setup_db()
        # 默认配置 auto_send=False → 警示条存在但隐藏
        html = _render(_client(), monkeypatch)
        assert "无法撤回" in html
        assert 'id="autoSendRiskHint" style="display:none"' in html
        assert "autoSendRiskHint" in html  # JS 联动引用存在

        with app_module.app.app_context():
            config = WechatShareConfig.query.first()
            config.auto_send = True
            db.session.commit()
        html = _render(_client(), monkeypatch)
        assert "无法撤回" in html
        assert 'id="autoSendRiskHint" style="display:none"' not in html

    def test_t3_pending_guidance_only_when_pending(self, monkeypatch):
        """T3：无 pending 不显示引导；有 pending 时显示消化方式。"""
        from app import WechatShareLog
        import datetime as dt

        with app_module.app.app_context():
            _setup_db()
        html = _render(_client(), monkeypatch)
        assert "图片已生成但尚未进入微信" not in html

        with app_module.app.app_context():
            db.session.add(WechatShareLog(
                module_key="in_order",
                order_id=0,
                status="pending",
                message="助手未配置，图片已生成待发送",
                share_date=dt.date.today(),
                created_at=dt.datetime.now(),
            ))
            db.session.commit()
        html = _render(_client(), monkeypatch)
        assert "图片已生成但尚未进入微信" in html
        assert "重发" in html

    def test_t4_pending_with_online_no_poll_helper(self, monkeypatch):
        """T4：pending + 助手在线但未开轮询 → 提示不会被自动消费。"""
        from app import WechatShareLog
        import datetime as dt

        with app_module.app.app_context():
            _setup_db()
            db.session.add(WechatShareLog(
                module_key="in_order",
                order_id=0,
                status="pending",
                message="待发送",
                share_date=dt.date.today(),
                created_at=dt.datetime.now(),
            ))
            db.session.commit()
        html = _render(_client(), monkeypatch)
        assert "待发送记录不会被自动消费" in html

        # 助手离线 → 提示先启动助手
        offline = dict(_FAKE_HEALTH_ONLINE_NO_POLL, online=False, message="助手不可用")
        html = _render(_client(), monkeypatch, health=offline)
        assert "请先启动本机微信发送助手" in html

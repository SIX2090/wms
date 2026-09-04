# -*- coding: utf-8 -*-
"""微信分享总开关回归（2026-09-04 业务诉求：暂时不用微信分享时一键整体停用）。

总开关 = 系统设置 wechat_share_enabled（默认 '1'=开）。关闭后：
- 定时每日分享（run_due_wechat_share_jobs）直接跳过；
- run_wechat_share_for_today 任意触发（含手动）拒绝发送并提示总开关已关闭；
- 入库单完成异步直推（_async_wechat_share_on_complete）跳过；
- 页面顶部提供「微信分享总开关」勾选，保存即生效（/wechat_share/save）。

覆盖：
T1. 默认开启（无设置行时为开，兼容存量）
T2. 关闭/再开启切换生效（设置 0→False，1→True）
T3. 总开关关闭时 run_wechat_share_for_today（含手动）返回 skipped 提示
T4. 总开关关闭时 run_due_wechat_share_jobs 直接返回不产生新日志
T5. 保存页面总开关：取消勾选保存后页面显示已停用且系统设置落 0
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

_ctx = app_module.app.app_context()

import pytest as _pytest  # noqa: E402


@_pytest.fixture(autouse=True, scope="module")
def _release_app_ctx_after_module():
    _ctx.push()
    yield
    try:
        _ctx.pop()
    except Exception:
        pass


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
    db.session.commit()


def _login(client):
    r = client.post("/login", data={"username": "admin", "password": "admin"})
    assert r.status_code in (302, 303)


def test_master_enabled_default_true():
    """T1: 无设置行时总开关默认开启（兼容存量部署，避免静默停用）。"""
    _reset_db()
    assert app_module._wechat_share_master_enabled() is True


def test_master_enabled_toggles_with_setting():
    """T2: 系统设置 0/1 切换总开关。"""
    _reset_db()
    from app import set_system_setting
    set_system_setting("wechat_share_enabled", "0")
    db.session.commit()
    assert app_module._wechat_share_master_enabled() is False
    set_system_setting("wechat_share_enabled", "1")
    db.session.commit()
    assert app_module._wechat_share_master_enabled() is True


def test_run_for_today_skipped_when_master_off():
    """T3: 总开关关闭时任何触发（含手动）都拒绝发送并提示。"""
    _reset_db()
    from app import set_system_setting
    set_system_setting("wechat_share_enabled", "0")
    db.session.commit()
    result = app_module.run_wechat_share_for_today(trigger_type="manual")
    assert result["status"] == "skipped"
    assert "总开关已关闭" in result["msg"]


def test_scheduler_noop_when_master_off():
    """T4: 总开关关闭时每分钟定时入口直接返回，不产生分享日志。"""
    _reset_db()
    from app import WechatShareLog, set_system_setting
    # 预置一条 enabled=True 的配置，即便到点也不得执行
    from app import WechatShareConfig
    db.session.add(WechatShareConfig(
        receiver_name="测试接收人", receiver_wechat_id="wxid_test",
        share_time="15:30", enabled=True, share_in_order=True))
    db.session.commit()
    set_system_setting("wechat_share_enabled", "0")
    db.session.commit()
    before = WechatShareLog.query.count()
    app_module.run_due_wechat_share_jobs()
    assert WechatShareLog.query.count() == before, "总开关关闭时定时任务不得产生任何日志/分享"


def test_save_toggles_master_and_page_shows_badge():
    """T5: 页面取消勾选「微信分享总开关」保存 → 设置落 0 且页面显示已停用。"""
    _reset_db()
    _seed_admin()
    client = app_module.app.test_client()
    _login(client)

    # 保存表单：总开关未勾选（absent）、其余填必填
    r = client.post("/wechat_share/save", data={
        "share_time": "15:30",
        "receiver_type": "person",
        "receiver_name": "测试接收人",
        "receiver_wechat_id": "wxid_test",
        "helper_url": "http://127.0.0.1:8765/send",
        "share_in_order": "1",
    })
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["status"] == "success", r.get_json()
    assert app_module._wechat_share_master_enabled() is False

    html = client.get("/wechat_share").get_data(as_text=True)
    assert "已停用" in html, "总开关关闭后页面应显示已停用"
    assert "微信分享总开关" in html
    # 再勾选保存 → 恢复开启
    r2 = client.post("/wechat_share/save", data={
        "master_enabled": "1",
        "share_time": "15:30",
        "receiver_type": "person",
        "receiver_name": "测试接收人",
        "receiver_wechat_id": "wxid_test",
        "helper_url": "http://127.0.0.1:8765/send",
        "share_in_order": "1",
    })
    assert r2.status_code == 200 and r2.get_json()["status"] == "success"
    assert app_module._wechat_share_master_enabled() is True

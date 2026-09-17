# -*- coding: utf-8 -*-
"""AI-CI-GREEN-005-F03 回归：库存预警页 `/alert` 必须有可达入口。

背景：`/alert`（`app/routes/inventory_alert.py:60`）是**唯一**能看到 danger 档
（低于安全库存 = 低于 max(reorder_point, min_stock)）的页面，四张统计卡 + 状态
筛选 + 批量设阈值都在这里。但全仓搜索 `templates/`、`static/js/`、任何 `url_for`
都找不到指向它的链接 —— 只能手敲 URL 才能进，等于白做。

本测试把「入口可达」钉死，防止它再次退化成孤儿页：

T1. 源码级：除 alert.html 自身外，至少 1 个模板含指向 /alert 的链接。
T2. 路由级：总开关开启时 GET /alert 返回 200，且页面出现「库存预警」。
T3. 开关行为：总开关关闭时 GET /alert 重定向到物料档案（而非 500/空白）。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import db, User  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

TEMPLATE_DIR = APP_DIR / "templates"
# alert.html 自己的「清除筛选」按钮也指向 /alert，不能算入口
ALERT_LINK_RE = re.compile(r'href="/alert(?:\?[^"]*)?"|url_for\(\s*[\'"]alert_list[\'"]')


def _inbound_link_files():
    hits = []
    for f in sorted(TEMPLATE_DIR.glob("*.html")):
        if f.name == "alert.html":
            continue
        if ALERT_LINK_RE.search(f.read_text(encoding="utf-8")):
            hits.append(f.name)
    return hits


def _login_client():
    from werkzeug.security import generate_password_hash

    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(
                username="admin",
                password_hash=generate_password_hash("admin"),
                role="admin",
                must_change_password=False,
            ))
        db.session.commit()

    client = app_module.app.test_client()
    client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )
    return client


def test_t1_alert_has_inbound_menu_link():
    """T1：至少有一个非 alert.html 的模板链接到 /alert。"""
    hits = _inbound_link_files()
    assert hits, (
        "没有任何模板链接到 /alert —— 它又变成只能手敲 URL 的孤儿页了。"
        "入口应加在 base.html 的库存管理菜单与 material.html 的工具条。"
    )


def test_t2_alert_page_renders_when_enabled():
    """T2：开关开启时 /alert 正常渲染。"""
    client = _login_client()
    with app_module.app.app_context():
        app_module.set_system_setting("inventory_alert_enabled", "1")
        db.session.commit()

    resp = client.get("/alert")
    assert resp.status_code == 200, f"/alert -> {resp.status_code}"
    body = resp.get_data(as_text=True)
    assert "库存预警" in body, "预警页缺少标题「库存预警」"
    assert "低于最低库存" in body and "低于安全库存" in body, (
        "预警页应同时呈现 low（低于最低库存）与 danger（低于安全库存）两档"
    )


def test_t3_alert_redirects_when_switch_off():
    """T3：开关关闭时 /alert 重定向到物料档案（保持既有降级行为）。"""
    client = _login_client()
    with app_module.app.app_context():
        app_module.set_system_setting("inventory_alert_enabled", "0")
        db.session.commit()

    resp = client.get("/alert")
    assert resp.status_code == 302, f"开关关闭时 /alert 应重定向，实际 {resp.status_code}"
    assert "/material" in (resp.headers.get("Location") or ""), (
        f"开关关闭时 /alert 应跳物料档案，实际跳 {resp.headers.get('Location')}"
    )

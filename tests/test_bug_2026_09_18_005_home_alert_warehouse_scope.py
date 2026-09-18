# -*- coding: utf-8 -*-
"""BUG-2026-09-18-005 回归：电脑端首页「库存预警物料」计数支持按仓查看。

背景（两端口径分裂的残留）：手机端首页 dashboard 早已能切仓库（BUG-2026-09-10-010），
电脑端 /alert 页也在 BUG-2026-09-18-004 加了仓库维度，唯独**电脑端首页**那张
「库存预警物料」卡片仍只按全局 `Material.stock` 计数——多仓下 A 仓已缺货、但 A+B
加总还够时，首页卡片显示 0，掩盖本仓预警。

修复：index() 的 low_stock 新增可选仓库维度——
  - 默认（不传 alert_warehouse_id）= 全部仓库（全局 _material_low_stock_filter，行为零变化）；
  - 选定仓库：按 get_warehouse_stock_quantities 仓库级判定（与手机端首页、电脑端 /alert 一致）；
  - 无效仓库 id 回退全局；
  - 预警卡片内嵌仓库选择器并明示当前判定口径。

本测试构造「全局 normal、A 仓 danger、B 仓 normal」的物料，用预警计数（A=1、其余=0）
+ 口径文案做确定性断言。
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime
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
from app import db, User, Material  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


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
        app_module.set_system_setting("inventory_alert_enabled", "1")
        db.session.commit()

    client = app_module.app.test_client()
    client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )
    return client


def _seed_scene():
    """物料：全局 material.stock=130（全局 normal）；A 仓 30（danger）；B 仓 100（normal）。"""
    from app import Warehouse, StockTransaction
    with app_module.app.app_context():
        wh_a = Warehouse(code="WHA", name="A仓", status="active", is_default=True)
        wh_b = Warehouse(code="WHB", name="B仓", status="active")
        db.session.add_all([wh_a, wh_b])
        db.session.commit()
        m = Material(code="MHOME001", name="物料MHOME001", stock=130, min_stock=10, reorder_point=50)
        db.session.add(m)
        db.session.commit()
        for wh, qty in [(wh_a, 30), (wh_b, 100)]:
            db.session.add(StockTransaction(
                material_id=m.id, transaction_type="in", quantity=qty,
                location=wh.name, warehouse_id=wh.id, created_at=datetime.now()))
        db.session.commit()
        return wh_a.id, wh_b.id


def _get(client, url):
    resp = client.get(url)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
    return resp.get_data(as_text=True)


def _alert_count(html):
    m = re.search(r'库存预警物料</div>\s*<div class="value">(\d+)', html)
    assert m, "首页找不到「库存预警物料」卡片的计数"
    return int(m.group(1))


def test_default_global_scope_preserved():
    """T1：默认（不传 alert_warehouse_id）保持全局口径——物料全局 normal，预警数=0。"""
    client = _login_client()
    _seed_scene()
    html = _get(client, "/")
    assert "全部仓库（全局）" in html, "预警卡片必须有「全部仓库（全局）」默认项"
    assert "按全部仓库全局判定" in html, "默认口径说明应为全局"
    assert _alert_count(html) == 0, "物料全局 130>安全库存50 为 normal，全局预警数应为 0"


def test_warehouse_scope_counts_alert():
    """T2：选定 A 仓 → 按仓库级判定，物料（A仓30<=安全库存50）计入预警数=1。"""
    client = _login_client()
    wh_a, _ = _seed_scene()
    html = _get(client, f"/?alert_warehouse_id={wh_a}")
    assert "按「A仓」仓库级判定" in html, "口径说明应为 A 仓仓库级"
    assert _alert_count(html) == 1, "物料在 A 仓 30<=安全库存50 为 danger，A 仓预警数应为 1"


def test_other_warehouse_scope_normal():
    """T3：选定 B 仓 → 物料（B仓100>安全库存50）为 normal，预警数=0。"""
    client = _login_client()
    _, wh_b = _seed_scene()
    html = _get(client, f"/?alert_warehouse_id={wh_b}")
    assert "按「B仓」仓库级判定" in html
    assert _alert_count(html) == 0, "物料在 B 仓 100>安全库存50 为 normal，B 仓预警数应为 0"


def test_invalid_warehouse_falls_back_to_global():
    """T4：无效仓库 id 回退全局口径（不报错、不空白）。"""
    client = _login_client()
    _seed_scene()
    html = _get(client, "/?alert_warehouse_id=99999")
    assert "按全部仓库全局判定" in html, "无效仓库 id 应回退全局口径"
    assert _alert_count(html) == 0, "回退全局后物料仍为 normal，预警数应为 0"

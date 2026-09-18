# -*- coding: utf-8 -*-
"""BUG-2026-09-18-004 回归：/alert 预警页新增可选仓库维度，对齐手机端口径。

背景（两端口径分裂）：电脑端 /alert 页与首页一律按**全局** `Material.stock` 判定，
手机端（/api/mobile/alert/list 等）按**当前仓库** `get_warehouse_stock_quantities()`
判定。多仓库环境下同一物料两端结论可能相反，且两端都没有任何口径说明，用户困惑。

修复：/alert 新增可选仓库维度——
  - 默认「全部仓库（全局）」：保持原总览口径（material.stock），行为零变化；
  - 选定仓库：按该仓仓库级库存判定（get_warehouse_stock_quantities），与手机端一致；
  - 无效仓库 id 回退全局；
  - 页面明示当前判定口径（消除两端困惑）。

本测试用 status=danger 过滤做确定性断言：构造一个「全局正常、A 仓 danger、B 仓
正常」的物料，验证三种口径各归其位。
"""
from __future__ import annotations

import os
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
    """MALERT001：全局 material.stock=130（全局 normal）；A 仓 30（danger）；B 仓 100（normal）。"""
    from app import Warehouse, StockTransaction
    with app_module.app.app_context():
        wh_a = Warehouse(code="WHA", name="A仓", status="active", is_default=True)
        wh_b = Warehouse(code="WHB", name="B仓", status="active")
        db.session.add_all([wh_a, wh_b])
        db.session.commit()
        m = Material(code="MALERT001", name="物料MALERT001", stock=130, min_stock=10, reorder_point=50)
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


def test_default_global_scope_preserved():
    """T1：默认（不传 warehouse_id）保持全局口径——MALERT001 全局 normal，不出现在 danger 列表。"""
    client = _login_client()
    _seed_scene()
    html = _get(client, "/alert?status=danger")
    assert "全部仓库（全局）" in html, "筛选器必须有「全部仓库（全局）」默认项"
    assert "按全部仓库全局总量判定" in html, "默认口径说明应为全局总量"
    assert "MALERT001" not in html, "MALERT001 全局 130>安全库存50 为 normal，不应出现在 danger 列表"


def test_warehouse_scope_uses_warehouse_level_stock():
    """T2：选定 A 仓 → 按仓库级判定，MALERT001（A仓30<=安全库存50）显示为 danger。"""
    client = _login_client()
    wh_a, _ = _seed_scene()
    html = _get(client, f"/alert?status=danger&warehouse_id={wh_a}")
    assert "按仓库「A仓」仓库级库存判定" in html, "口径说明应为 A 仓仓库级"
    assert "MALERT001" in html, "MALERT001 在 A 仓 30<=安全库存50 应为 danger，必须出现"
    assert "低于安全库存" in html, "MALERT001 应以「低于安全库存」(danger 档) 呈现"


def test_other_warehouse_scope_normal():
    """T3：选定 B 仓 → MALERT001（B仓100>安全库存50）为 normal，不出现在 danger 列表。"""
    client = _login_client()
    _, wh_b = _seed_scene()
    html = _get(client, f"/alert?status=danger&warehouse_id={wh_b}")
    assert "按仓库「B仓」仓库级库存判定" in html
    assert "MALERT001" not in html, "MALERT001 在 B 仓 100>安全库存50 为 normal，不应出现在 danger 列表"


def test_invalid_warehouse_falls_back_to_global():
    """T4：无效仓库 id 回退全局口径（不报错、不空白）。"""
    client = _login_client()
    _seed_scene()
    html = _get(client, "/alert?status=danger&warehouse_id=99999")
    assert "按全部仓库全局总量判定" in html, "无效仓库 id 应回退全局口径"
    assert "MALERT001" not in html, "回退全局后 MALERT001 仍为 normal，不应出现"

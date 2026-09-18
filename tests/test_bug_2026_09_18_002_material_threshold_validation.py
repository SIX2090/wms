# -*- coding: utf-8 -*-
"""BUG-2026-09-18-002 回归：单物料新增/编辑的「安全库存 < 最低库存」写入门禁。

背景（R6 同根因）：「安全库存(reorder_point) 不得小于最低库存(min_stock)」这条
不变量此前只在两处生效——批量设置（routes/inventory_alert.py，显式冲突拒绝）与
Excel 导入（routes/material.py，clamp 提到 min）；而**单物料新增与编辑**两条手写
路径毫无校验，可写入 reorder_point < min_stock 的脏数据。后果：safety_stock =
max(reorder_point, min_stock) 退化为 min_stock，用户填的安全库存被静默吞掉、
danger 档（低于安全库存）消失，且四条写入路径三种行为。

修复：新增/编辑统一走 `_resolve_alert_thresholds()`——
  - 显式把安全库存填得比最低库存低（>0 且 <min）→ 400「安全库存不能低于最低库存」；
  - 安全库存未填（=0）但设了最低库存 → 自动提到最低库存（与导入/批量同口径）。

本测试钉死该口径（与批量设置页一致的纯后端校验，前端不加重复 JS 防漂移）。
"""
from __future__ import annotations

import os
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


def _get_material(code):
    with app_module.app.app_context():
        m = Material.query.filter_by(code=code).first()
        if not m:
            return None
        return {'min_stock': m.min_stock, 'reorder_point': m.reorder_point}


def test_add_rejects_explicit_safety_below_min():
    """T1：新增显式填 安全库存(30) < 最低库存(50) → 400，物料不落库。"""
    client = _login_client()
    resp = client.post("/material/add", data={
        "code": "T-ADD-REJ", "name": "拒绝样例",
        "min_stock": "50", "safety_stock": "30",
    })
    assert resp.status_code == 400, resp.get_data(as_text=True)
    body = resp.get_json()
    assert "安全库存不能低于最低库存" in (body.get("msg") or "")
    assert _get_material("T-ADD-REJ") is None, "被拒绝的物料不应写入数据库"


def test_add_blank_safety_auto_bumps_to_min():
    """T2：新增只填最低库存(50)、安全库存留 0 → 成功且 reorder_point 自动提到 50。"""
    client = _login_client()
    resp = client.post("/material/add", data={
        "code": "T-ADD-BUMP", "name": "自动提升样例",
        "min_stock": "50", "safety_stock": "0",
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    row = _get_material("T-ADD-BUMP")
    assert row is not None
    assert row["min_stock"] == 50
    assert row["reorder_point"] == 50, "安全库存未填时应自动提到最低库存（与导入/批量同口径）"


def test_add_safety_above_min_ok():
    """T3：新增 安全库存(80) >= 最低库存(50) → 成功且原值保留。"""
    client = _login_client()
    resp = client.post("/material/add", data={
        "code": "T-ADD-OK", "name": "正常样例",
        "min_stock": "50", "safety_stock": "80",
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    row = _get_material("T-ADD-OK")
    assert row["min_stock"] == 50 and row["reorder_point"] == 80


def _seed_material(code, min_stock=10, reorder_point=50):
    with app_module.app.app_context():
        m = Material(code=code, name=f"物料{code}", stock=0,
                     min_stock=min_stock, reorder_point=reorder_point)
        db.session.add(m)
        db.session.commit()
        return m.id


def test_edit_rejects_explicit_safety_below_min():
    """T4：编辑把 最低库存提到 80 而安全库存仍 50（显式 <min）→ 400 且原值不变。"""
    client = _login_client()
    mid = _seed_material("T-EDIT-REJ", min_stock=10, reorder_point=50)
    resp = client.post(f"/material/edit/{mid}", data={
        "code": "T-EDIT-REJ", "name": "编辑拒绝",
        "min_stock": "80", "reorder_point": "50",
    })
    assert resp.status_code == 400, resp.get_data(as_text=True)
    body = resp.get_json()
    assert "安全库存不能低于最低库存" in (body.get("msg") or "")
    row = _get_material("T-EDIT-REJ")
    assert row["min_stock"] == 10 and row["reorder_point"] == 50, "被拒绝的编辑不应改动原值"


def test_edit_blank_safety_auto_bumps_to_min():
    """T5：编辑只设最低库存(50)、安全库存留 0 → 成功且 reorder_point 自动提到 50。"""
    client = _login_client()
    mid = _seed_material("T-EDIT-BUMP", min_stock=0, reorder_point=0)
    resp = client.post(f"/material/edit/{mid}", data={
        "code": "T-EDIT-BUMP", "name": "编辑提升",
        "min_stock": "50", "reorder_point": "0",
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    row = _get_material("T-EDIT-BUMP")
    assert row["min_stock"] == 50 and row["reorder_point"] == 50

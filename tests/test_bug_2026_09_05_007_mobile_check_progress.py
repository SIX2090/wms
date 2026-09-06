# -*- coding: utf-8 -*-
"""BUG-2026-09-05-007 / FEATURE-2026-09-05-003 回归：手机端盘点进度与待盘清单。

问题：手机盘点只拿手机时看不到"这张单还剩哪些没盘"——漏盘核对只能回
PC 详情页；多人分区盘点时尤其容易漏。

修复：
- `_list_pending_check_orders` 增加 counted_count（已盘行数），选单下拉
  直接展示「已盘 X/Y」；
- 新增 GET /mobile/api/check_orders/<id>/items：返回进度（total/counted）
  与明细清单（未盘在前）。**盲盘设计**：不下发各行 system_stock——盘点人
  看到账面会照着填；已盘行回传实盘与盘点人/时间供自查，未盘行只给物料
  识别信息（actual_stock=null）；
- mobile_scan.html 选单后显示进度条与待盘清单（前 30 项+折叠），扫码
  提交成功与撤销后自动刷新。

覆盖：
T1. 选单列表返回 counted_count（已盘/总数）
T2. items 接口：进度计数正确、未盘行 actual=null 且无 system_stock 字段、
    已盘行带实盘/盘点人/时间
T3. 未盘行排在已盘行之前
T4. 盘点单不存在 → 404
T5. 手机扫码盘一行后：items counted+1，新加行 counted=True
T6. 模板契约：进度面板/刷新函数/提交后刷新/撤销后刷新/选项带进度
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
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


def _seed_scene():
    """A仓；物料 M001/M002/M003；盘点单 CK-T：M001 已盘(张三, 8)、M002/M003 未盘。"""
    from werkzeug.security import generate_password_hash
    from app import (InventoryCheck, InventoryCheckItem, Material,
                     StockTransaction, User, Warehouse)
    db.drop_all()
    db.create_all()
    admin = User(username="admin", password_hash=generate_password_hash("admin"),
                 role="admin", must_change_password=False)
    zhangsan = User(username="zhangsan", password_hash=generate_password_hash("x"),
                    role="warehouse", must_change_password=False)
    wh = Warehouse(code="WA", name="A仓", status="active", is_default=True)
    db.session.add_all([admin, zhangsan, wh])
    db.session.commit()
    mats = {}
    for code, qty in [("M001", 10.0), ("M002", 20.0), ("M003", 30.0)]:
        m = Material(code=code, name=f"物料{code}", spec=f"规格{code}", stock=qty)
        db.session.add(m)
        db.session.flush()
        db.session.add(StockTransaction(
            material_id=m.id, transaction_type="in", quantity=qty,
            location=wh.name, warehouse_id=wh.id, created_at=datetime.now()))
        mats[code] = m
    db.session.commit()
    check = InventoryCheck(check_no="CK-T-001", warehouse="A仓",
                           status="pending", operator_id=admin.id)
    db.session.add(check)
    db.session.flush()
    db.session.add_all([
        InventoryCheckItem(inventory_check_id=check.id, material_id=mats["M001"].id,
                           system_stock=10, actual_stock=8, difference=-2,
                           counted_by=zhangsan.id,
                           counted_at=datetime(2026, 9, 5, 10, 0)),
        InventoryCheckItem(inventory_check_id=check.id, material_id=mats["M002"].id,
                           system_stock=20, actual_stock=20, difference=0),
        InventoryCheckItem(inventory_check_id=check.id, material_id=mats["M003"].id,
                           system_stock=30, actual_stock=30, difference=0),
    ])
    db.session.commit()
    return check, mats


def _client():
    c = app_module.app.test_client()
    r = c.post("/login", data={"username": "admin", "password": "admin"})
    assert r.status_code in (302, 303), r.get_data(as_text=True)
    return c


def _bearer(client):
    r = client.post("/api/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, r.get_data(as_text=True)
    return {"Authorization": f"Bearer {r.get_json()['data']['token']}"}


# T1 ───────────────────────────────────────────────────────────────
def test_t1_orders_list_has_counted_count():
    check, _m = _seed_scene()
    client = _client()
    r = client.get("/mobile/api/check_orders?warehouse=A仓")
    assert r.status_code == 200, r.get_data(as_text=True)
    orders = r.get_json()["data"]["orders"]
    assert len(orders) == 1
    o = orders[0]
    assert o["item_count"] == 3
    assert o["counted_count"] == 1


# T2 ───────────────────────────────────────────────────────────────
def test_t2_items_progress_and_blind_count():
    check, _m = _seed_scene()
    client = _client()
    r = client.get(f"/mobile/api/check_orders/{check.id}/items")
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()["data"]
    assert d["check_no"] == "CK-T-001"
    assert d["total"] == 3 and d["counted"] == 1
    by_code = {it["code"]: it for it in d["items"]}
    # 盲盘：任何行都不下发账面数
    for it in d["items"]:
        assert "system_stock" not in it
    # 未盘行：只给识别信息，actual 为 null
    assert by_code["M002"]["counted"] is False
    assert by_code["M002"]["actual_stock"] is None
    assert by_code["M002"]["spec"] == "规格M002"
    # 已盘行：带实盘/盘点人/时间供自查
    m1 = by_code["M001"]
    assert m1["counted"] is True
    assert m1["actual_stock"] == 8.0
    assert m1["counted_by"] == "zhangsan"
    assert m1["counted_at"] == "09-05 10:00"


# T3 ───────────────────────────────────────────────────────────────
def test_t3_pending_items_sorted_first():
    check, _m = _seed_scene()
    client = _client()
    d = client.get(f"/mobile/api/check_orders/{check.id}/items").get_json()["data"]
    counted_flags = [it["counted"] for it in d["items"]]
    assert counted_flags == sorted(counted_flags)  # False(未盘) 全在 True 前
    assert d["items"][0]["counted"] is False
    assert d["items"][-1]["counted"] is True


# T4 ───────────────────────────────────────────────────────────────
def test_t4_items_not_found_404():
    _seed_scene()
    client = _client()
    r = client.get("/mobile/api/check_orders/999999/items")
    assert r.status_code == 404


# T5 ───────────────────────────────────────────────────────────────
def test_t5_scan_updates_progress():
    check, mats = _seed_scene()
    client = _client()
    h = _bearer(client)
    before = client.get(f"/mobile/api/check_orders/{check.id}/items").get_json()["data"]
    assert before["counted"] == 1
    # 手机盘 M002（清单内未盘行）
    r = client.post("/mobile/api/scan_submit", headers=h, json={
        "mode": "check", "code": "M002", "warehouse": "A仓",
        "actual_stock": 19, "check_id": check.id,
    })
    assert r.status_code == 200, r.get_data(as_text=True)
    after = client.get(f"/mobile/api/check_orders/{check.id}/items").get_json()["data"]
    assert after["counted"] == 2 and after["total"] == 3
    m2 = {it["code"]: it for it in after["items"]}["M002"]
    assert m2["counted"] is True
    assert m2["actual_stock"] == 19.0
    assert m2["counted_by"] == "admin"
    # 手机盘清单外物料 M-NEW → 自动加行且 total+1
    from app import Material
    new_m = Material(code="M-NEW", name="清单外物料", stock=0)
    db.session.add(new_m)
    db.session.commit()
    r2 = client.post("/mobile/api/scan_submit", headers=h, json={
        "mode": "check", "code": "M-NEW", "warehouse": "A仓",
        "actual_stock": 5, "check_id": check.id,
    })
    assert r2.status_code == 200, r2.get_data(as_text=True)
    # 手机新增行同样带盘点归属（否则前端会把刚盘过的行显示成"未盘"）；M003 仍未盘
    final = client.get(f"/mobile/api/check_orders/{check.id}/items").get_json()["data"]
    assert final["total"] == 4 and final["counted"] == 3
    codes = [it["code"] for it in final["items"]]
    assert "M-NEW" in codes
    new_row = {it["code"]: it for it in final["items"]}["M-NEW"]
    assert new_row["counted"] is True
    assert new_row["actual_stock"] == 5.0


# T6 ───────────────────────────────────────────────────────────────
def test_t6_template_contract():
    tpl = (ROOT / "app" / "templates" / "mobile_scan.html").read_text(encoding="utf-8")
    assert 'id="checkProgressBox"' in tpl
    assert 'id="checkProgressText"' in tpl
    assert 'id="checkItemsList"' in tpl
    assert "function refreshCheckProgress()" in tpl
    assert "/mobile/api/check_orders/" in tpl and "+ '/items'" in tpl
    # 提交成功与撤销后都刷新
    assert "if (mode === 'check') refreshCheckProgress();" in tpl
    assert "refreshCheckProgress();" in tpl
    # 选单下拉选项带进度
    assert "o.counted_count" in tpl and "o.item_count" in tpl
    # 盲盘提示注释（防后续误把账面数加回清单）
    assert "盲盘" in tpl

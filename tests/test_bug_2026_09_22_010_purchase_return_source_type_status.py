# -*- coding: utf-8 -*-
"""BUG-2026-09-22-010 回归：采购退货来源解析必须限定「已完成的采购入库单」。

根因：选源接口 `/api/purchase_in_order/selectable` 明确只返回
`business_type == '采购入库' AND status == 'completed'` 的入库单，
但**保存路径另有两条解析通道，都绕开了这个过滤**：

① 新增（`add_out_order`）：按 `source_in_order_id`（`db.session.get`）
   或 `source_in_order_no`（裸 `filter_by(order_no=...)`）解析；
② 编辑（`POST /out_order/<id>/update`）：按 `source_in_order_no` 裸 `filter_by(order_no=...)` 解析。

于是用户在前端手填一个单号即可击穿接口层过滤：
- 传**非采购入库类型**（销售退货入库 / 其他入库 / 采购退货出库自身）的单号：
  `仅采购退货出库单可关联采购入库来源` 的类型防线被绕过，污染按
  `source_in_order_item_id` 聚合的防超退口径；
- 传**未完成**的采购入库草稿：退货锚定在尚未真实入库的货上，库存账实分叉。

覆盖：
- T1 新增时传非采购入库类型单号 → 被拒（msg 指明不是已完成的采购入库单）；
- T2 新增时传未完成采购入库单号 → 被拒；
- T3 新增时传已完成的采购入库单号 → 放行（防误伤），来源正确落库；
- T4 编辑时传未完成采购入库单号 → 被拒，单头来源不被改写；
- T5 编辑时传已完成的采购入库单号 → 放行（防误伤）。
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
os.environ.setdefault("WMS_ALLOW_INSECURE_COOKIE", "1")

import datetime  # noqa: E402

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import InOrder, InOrderItem, Material, MaterialCategory, OutOrder, \
    OutOrderItem, Supplier, Unit, User, Warehouse, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_base():
    db.session.add(User(username="warehouse", password_hash=generate_password_hash("admin"),
                        role="warehouse", must_change_password=False))
    wh = Warehouse(name="来源限定仓", code="WSRC2", status="active", is_default=True)
    supplier = Supplier(code="S01", name="退货供应商")
    unit = Unit(code="GE", name="个")
    cat = MaterialCategory(code="WJ", name="五金")
    db.session.add_all([wh, supplier, unit, cat])
    db.session.flush()
    material = Material(code="M-SRCLIM", name="来源限定测试件", spec="T1", stock=50,
                        min_stock=0, price=3.0, unit_id=unit.id, category_id=cat.id)
    db.session.add(material)
    db.session.commit()
    return {"wh": wh, "supplier": supplier, "material": material}


def _seed_stock(material, warehouse, quantity):
    from app.services.warehouse_stock_service import apply_stock_delta
    with app_module.app.test_request_context():
        ok, err = apply_stock_delta(
            material, quantity, transaction_type="opening_in",
            reference_type="test_seed", reference_id=0,
            warehouse=warehouse.name, location="")
    assert ok, f"造库存失败：{err}"
    db.session.flush()


def _make_in_order(material, warehouse, order_no, business_type, status, quantity=10):
    """指定业务类型与状态的入库单 + 一行明细，返回 (in_order_id, in_order_item_id)。"""
    order = InOrder(order_no=order_no, date=datetime.date.today(),
                    business_type=business_type, supplier_id=1, status=status,
                    warehouse=warehouse.name)
    db.session.add(order)
    db.session.flush()
    ii = InOrderItem(in_order_id=order.id, material_id=material.id,
                     quantity=quantity, price=3.0, amount=quantity * 3.0)
    db.session.add(ii)
    db.session.commit()
    return order.id, ii.id


def _make_return_draft(material, warehouse, in_order_id, in_order_no, ii_id, quantity=2):
    order = OutOrder(order_no="PR-SRCLIM-1", date=datetime.date.today(),
                     business_type="采购退货出库", customer="退货供应商",
                     warehouse=warehouse.name, status="pending",
                     source_in_order_id=in_order_id, source_in_order_no=in_order_no)
    db.session.add(order)
    db.session.flush()
    db.session.add(OutOrderItem(out_order_id=order.id, material_id=material.id,
                                source_in_order_item_id=ii_id, quantity=quantity,
                                price=3.0, amount=quantity * 3.0))
    db.session.commit()
    return order.id


def _make_client(role="warehouse"):
    with app_module.app.app_context():
        if not User.query.filter_by(username=role).first():
            db.session.add(User(username=role, password_hash=generate_password_hash("admin"),
                                role=role, must_change_password=False))
            db.session.commit()
    client = app_module.app.test_client()
    client.post("/login", data={"username": role, "password": "admin"},
                content_type="application/x-www-form-urlencoded")
    return client


def _add_payload(warehouse_name, source_no=None, source_id=None, ii_id=None):
    payload = {
        "order_no": "PR-SRCLIM-NEW",
        "business_type": "采购退货出库",
        "date": "2026-09-22",
        "warehouse": warehouse_name,
        "customer": "退货供应商",
        "items": [{"code": "M-SRCLIM", "quantity": 2, "price": 3.0,
                   **({"source_in_order_item_id": ii_id} if ii_id else {})}],
    }
    if source_no is not None:
        payload["source_in_order_no"] = source_no
    if source_id is not None:
        payload["source_in_order_id"] = source_id
    return payload


def test_t1_add_rejects_wrong_business_type():
    """T1：新增时传非采购入库类型（其他入库）的单号必须被拒。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh"], 50)
        _, ii_id = _make_in_order(seed["material"], seed["wh"], "IN-WRONG-TYPE",
                                  "其他入库", "completed")
        seed_data.update(wh_name=seed["wh"].name, ii_id=ii_id)

    client = _make_client()
    payload = _add_payload(seed_data["wh_name"], source_no="IN-WRONG-TYPE",
                           ii_id=seed_data["ii_id"])
    resp = client.post("/out_order/add", json=payload)
    assert resp.status_code == 400, resp.get_data(as_text=True)[:300]
    data = resp.get_json()
    assert data["status"] == "error", f"非采购入库类型必须被拒，实际 {data}"
    assert "不是已完成的采购入库单" in data.get("msg", ""), data


def test_t2_add_rejects_incomplete_in_order():
    """T2：新增时传未完成（pending）的采购入库单号必须被拒。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh"], 50)
        _, ii_id = _make_in_order(seed["material"], seed["wh"], "IN-NOT-DONE",
                                  "采购入库", "pending")
        seed_data.update(wh_name=seed["wh"].name, ii_id=ii_id)

    client = _make_client()
    payload = _add_payload(seed_data["wh_name"], source_no="IN-NOT-DONE",
                           ii_id=seed_data["ii_id"])
    resp = client.post("/out_order/add", json=payload)
    assert resp.status_code == 400, resp.get_data(as_text=True)[:300]
    data = resp.get_json()
    assert data["status"] == "error", f"未完成入库单必须被拒，实际 {data}"
    assert "不是已完成的采购入库单" in data.get("msg", ""), data


def test_t3_add_accepts_completed_purchase_in_order():
    """T3：新增时传已完成的采购入库单号正常放行，来源正确落库（防误伤）。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh"], 50)
        in_order_id, ii_id = _make_in_order(seed["material"], seed["wh"], "IN-OK-1",
                                            "采购入库", "completed")
        seed_data.update(wh_name=seed["wh"].name, ii_id=ii_id,
                         in_order_id=in_order_id)

    client = _make_client()
    payload = _add_payload(seed_data["wh_name"], source_no="IN-OK-1",
                           ii_id=seed_data["ii_id"])
    resp = client.post("/out_order/add", json=payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
    data = resp.get_json()
    assert data["status"] == "success", f"合格的来源必须放行，实际 {data}"

    with app_module.app.app_context():
        order = db.session.get(OutOrder, data["id"])
        assert order.source_in_order_id == seed_data["in_order_id"], "来源 id 必须落库"
        assert order.source_in_order_no == "IN-OK-1", "来源单号必须回填"


def test_t4_edit_rejects_incomplete_in_order():
    """T4：编辑时传未完成的采购入库单号被拒，单头来源不被改写。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh"], 50)
        good_id, good_ii = _make_in_order(seed["material"], seed["wh"], "IN-EDIT-OK",
                                          "采购入库", "completed")
        _make_in_order(seed["material"], seed["wh"], "IN-EDIT-BAD", "采购入库", "pending")
        draft_id = _make_return_draft(seed["material"], seed["wh"], good_id,
                                      "IN-EDIT-OK", good_ii)
        seed_data.update(draft_id=draft_id, good_id=good_id)

    client = _make_client()
    resp = client.post(f"/out_order/{seed_data['draft_id']}/update",
                       json={"date": datetime.date.today().strftime("%Y-%m-%d"), "source_in_order_no": "IN-EDIT-BAD"})
    assert resp.status_code == 400, resp.get_data(as_text=True)[:300]
    data = resp.get_json()
    assert data["status"] == "error", f"编辑时未完成入库单必须被拒，实际 {data}"
    assert "不是已完成的采购入库单" in data.get("msg", ""), data

    with app_module.app.app_context():
        order = db.session.get(OutOrder, seed_data["draft_id"])
        assert order.source_in_order_id == seed_data["good_id"], "被拒后来源不得被改写"


def test_t5_edit_accepts_completed_purchase_in_order():
    """T5：编辑时传已完成的采购入库单号放行（防误伤）。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh"], 50)
        first_id, first_ii = _make_in_order(seed["material"], seed["wh"], "IN-E-1",
                                            "采购入库", "completed", quantity=5)
        second_id, second_ii = _make_in_order(seed["material"], seed["wh"], "IN-E-2",
                                              "采购入库", "completed", quantity=8)
        draft_id = _make_return_draft(seed["material"], seed["wh"], first_id,
                                      "IN-E-1", first_ii)
        seed_data.update(draft_id=draft_id, second_id=second_id)

    client = _make_client()
    resp = client.post(f"/out_order/{seed_data['draft_id']}/update",
                       json={"date": datetime.date.today().strftime("%Y-%m-%d"), "source_in_order_no": "IN-E-2"})
    assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
    data = resp.get_json()
    assert data["status"] == "success", f"合格来源改绑必须放行，实际 {data}"

    with app_module.app.app_context():
        order = db.session.get(OutOrder, seed_data["draft_id"])
        assert order.source_in_order_id == seed_data["second_id"], "来源应改绑到 IN-E-2"
        assert order.source_in_order_no == "IN-E-2"

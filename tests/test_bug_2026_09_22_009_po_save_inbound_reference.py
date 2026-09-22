# -*- coding: utf-8 -*-
"""BUG-2026-09-22-009 回归：已被入库单引用的采购订单不得编辑保存（重建明细）。

根因：`save_purchase_order` 编辑路径的守卫只有 `order.status != 'pending'`，
随后**无条件整批删除旧明细再按页面重建**：

    for existing_item in list(order.items):
        db.session.delete(existing_item)

而 `InOrderItem.source_purchase_order_item_id` 正是指向这些明细的外键。
删除路径（`delete_purchase_order`）早有 PUR-AUDIT-002 的两层引用保护
（表头 `InOrder.source_purchase_order_id` + 行级 `InOrderItem.source_purchase_order_item_id`），
**保存路径漏配**——于是「打开已下推入库的采购单编辑页、只改个备注、保存」
就会把已入库单的来源明细删掉重建，来源断链、采购执行进度（received_quantity）
失真，重则触发外键约束导致保存半途失败。

覆盖：
- T1 表头级引用（单来源下推入库）：保存被拒，明细未被删除、数量不变；
- T2 行级引用（多来源选单入库，表头 source_purchase_order_id 为空）：
     保存同样被拒（只查表头会漏掉的场景）；
- T3 无任何引用的 pending 采购单：保存正常放行（防误伤），明细按提交重建。
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
from app import InOrder, InOrderItem, Material, MaterialCategory, PurchaseOrder, \
    PurchaseOrderItem, Supplier, Unit, User, Warehouse, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_base():
    db.session.add(User(username="purchase", password_hash=generate_password_hash("admin"),
                        role="purchase", must_change_password=False))
    wh = Warehouse(name="采购编辑仓", code="WPOE", status="active", is_default=True)
    supplier = Supplier(code="S01", name="采购供应商")
    unit = Unit(code="GE", name="个")
    cat = MaterialCategory(code="WJ", name="五金")
    db.session.add_all([wh, supplier, unit, cat])
    db.session.flush()
    material = Material(code="M-POE", name="采购编辑测试件", spec="T1", stock=0,
                        min_stock=0, price=7.0, unit_id=unit.id, category_id=cat.id)
    db.session.add(material)
    db.session.commit()
    return {"wh": wh, "supplier": supplier, "material": material}


def _make_pending_po(material, quantity=10):
    """待入库采购单 + 一行明细，返回 (po_id, poi_id)。"""
    po = PurchaseOrder(order_no="PO-EDIT-1", supplier_id=1, status="pending",
                       date=datetime.date.today())
    db.session.add(po)
    db.session.flush()
    poi = PurchaseOrderItem(purchase_order_id=po.id, material_id=material.id,
                            quantity=quantity, price=7.0, amount=quantity * 7.0,
                            received_quantity=0)
    db.session.add(poi)
    db.session.commit()
    return po.id, poi.id


def _link_in_order_header(po_id, material, warehouse, quantity=3):
    """表头级引用：单来源下推入库（source_purchase_order_id 有值）。"""
    order = InOrder(order_no="IN-POE-HDR", date=datetime.date.today(),
                    business_type="采购入库", supplier_id=1, status="pending",
                    warehouse=warehouse.name, source_purchase_order_id=po_id)
    db.session.add(order)
    db.session.flush()
    db.session.add(InOrderItem(in_order_id=order.id, material_id=material.id,
                               quantity=quantity, price=7.0, amount=quantity * 7.0))
    db.session.commit()
    return order.id


def _link_in_order_item_level(poi_id, material, warehouse, quantity=3):
    """行级引用：多来源选单入库（表头 source_purchase_order_id 为 None）。"""
    order = InOrder(order_no="IN-POE-ITEM", date=datetime.date.today(),
                    business_type="采购入库", supplier_id=1, status="pending",
                    warehouse=warehouse.name, source_purchase_order_id=None)
    db.session.add(order)
    db.session.flush()
    db.session.add(InOrderItem(in_order_id=order.id, material_id=material.id,
                               source_purchase_order_item_id=poi_id,
                               quantity=quantity, price=7.0, amount=quantity * 7.0))
    db.session.commit()
    return order.id


def _make_client(role="purchase"):
    with app_module.app.app_context():
        if not User.query.filter_by(username=role).first():
            db.session.add(User(username=role, password_hash=generate_password_hash("admin"),
                                role=role, must_change_password=False))
            db.session.commit()
    client = app_module.app.test_client()
    client.post("/login", data={"username": role, "password": "admin"},
                content_type="application/x-www-form-urlencoded")
    return client


def _save_payload(po_id, material, quantity=10, remark="改个备注"):
    """模拟用户在编辑页保存：原明细 + 新备注（只改表头字段）。"""
    return {
        "order_id": po_id,
        "order_no": "PO-EDIT-1",
        "date": datetime.date.today().strftime("%Y-%m-%d"),
        "supplier_id": 1,
        "remark": remark,
        "items": [{"material_id": material.id, "material_code": material.code,
                   "quantity": quantity, "price": 7.0}],
    }


def test_t1_header_level_reference_blocks_save():
    """T1：表头级引用的采购单保存被拒，原明细完好。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        po_id, poi_id = _make_pending_po(seed["material"], quantity=10)
        in_order_id = _link_in_order_header(po_id, seed["material"], seed["wh"])
        seed_data.update(po_id=po_id, poi_id=poi_id, in_order_id=in_order_id,
                         material_id=seed["material"].id)

    client = _make_client()
    seed_material = None
    with app_module.app.app_context():
        seed_material = db.session.get(Material, seed_data["material_id"])
        payload = _save_payload(seed_data["po_id"], seed_material)
        material_code = seed_material.code

    resp = client.post("/purchase_order/save", json=payload)
    assert resp.status_code == 400, resp.get_data(as_text=True)[:300]
    data = resp.get_json()
    assert data["status"] == "error", f"有下游入库引用时保存必须被拒，实际 {data}"
    assert "已有下游入库单" in data.get("msg", ""), data

    with app_module.app.app_context():
        poi = db.session.get(PurchaseOrderItem, seed_data["poi_id"])
        assert poi is not None, "被拒后原明细不得被删除"
        assert poi.quantity == 10, f"被拒后数量必须保持 10，实际 {poi.quantity}"
        # 下游入库明细的来源外键仍完好
        in_item = InOrderItem.query.filter_by(in_order_id=seed_data["in_order_id"]).first()
        assert in_item is not None, "下游入库明细不得受损"


def test_t2_item_level_reference_blocks_save():
    """T2：纯行级引用（表头 source_purchase_order_id 为 None）同样拦截。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        po_id, poi_id = _make_pending_po(seed["material"], quantity=10)
        in_order_id = _link_in_order_item_level(poi_id, seed["material"], seed["wh"])
        seed_data.update(po_id=po_id, poi_id=poi_id, in_order_id=in_order_id,
                         material_id=seed["material"].id)

    client = _make_client()
    with app_module.app.app_context():
        material = db.session.get(Material, seed_data["material_id"])
        payload = _save_payload(seed_data["po_id"], material)

    resp = client.post("/purchase_order/save", json=payload)
    assert resp.status_code == 400, resp.get_data(as_text=True)[:300]
    data = resp.get_json()
    assert data["status"] == "error", \
        f"仅行级引用也必须拦截（只查表头会漏），实际 {data}"
    assert "已有下游入库单" in data.get("msg", ""), data

    with app_module.app.app_context():
        poi = db.session.get(PurchaseOrderItem, seed_data["poi_id"])
        assert poi is not None and poi.quantity == 10, "原明细必须完好"
        in_item = InOrderItem.query.filter_by(in_order_id=seed_data["in_order_id"]).first()
        assert in_item.source_purchase_order_item_id == seed_data["poi_id"], \
            "下游行级来源外键必须仍指向原明细"


def test_t3_no_reference_allows_save():
    """T3：无任何下游引用的 pending 采购单正常保存（防误伤）。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        po_id, poi_id = _make_pending_po(seed["material"], quantity=10)
        seed_data.update(po_id=po_id, material_id=seed["material"].id)

    client = _make_client()
    with app_module.app.app_context():
        material = db.session.get(Material, seed_data["material_id"])
        payload = _save_payload(seed_data["po_id"], material, quantity=12,
                                remark="正常改量改备注")

    resp = client.post("/purchase_order/save", json=payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
    data = resp.get_json()
    assert data["status"] == "success", f"无引用时保存必须放行，实际 {data}"

    with app_module.app.app_context():
        items = PurchaseOrderItem.query.filter_by(purchase_order_id=seed_data["po_id"]).all()
        assert len(items) == 1, f"明细应重建为 1 行，实际 {len(items)}"
        assert items[0].quantity == 12, f"数量应更新为 12，实际 {items[0].quantity}"
        po = db.session.get(PurchaseOrder, seed_data["po_id"])
        assert po.remark == "正常改量改备注", "备注应更新"

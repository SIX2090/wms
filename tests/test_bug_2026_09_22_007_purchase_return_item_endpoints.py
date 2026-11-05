# -*- coding: utf-8 -*-
"""BUG-2026-09-22-007 回归：采购退货出库明细接口必须守住来源与限额。

根因：采购退货出库的防超退设计是「有来源明细逐行计限、无来源行跳过」
（P1-7），但两个明细级接口都能造出无来源行 / 改大数量，绕过保存时校验：

① `POST /out_order/<id>/item/add`（单行裸加）只收 物料+数量，产出的行
   **没有 source_in_order_item_id** → 防超退闸整行跳过 → 该行可无限退货；
② `POST /out_order/item/update`（明细表内联改量 / ExcelTable autoSave）
   只校验「数量 > 0」就落库，草稿保存后把有来源行数量改大即可超退。

两者叠加使 P1-7 的整单真闸只剩完成时兜底，而批量完成此前正是第二个
后门（BUG-2026-09-22-005）。本 BUG 补齐接口层：①采购退货模式拒绝裸加；
②改量时按 validate_purchase_return_quantity 同口径复校。

覆盖：
- T1 采购退货单调 item/add 被拒（不再能造无来源行）；
- T2 采购退货单把有来源行数量改大超限被拒，数量不变；
- T3 限额内的改量正常放行（防误伤）；
- T4 非采购退货单（领料单）的 item/add 与改量不受影响（防误伤）。
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
from app import Department, InOrder, InOrderItem, Material, MaterialCategory, \
    OutOrder, OutOrderItem, Supplier, Unit, User, Warehouse, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_base():
    db.session.add(User(username="warehouse", password_hash=generate_password_hash("admin"),
                        role="warehouse", must_change_password=False))
    wh = Warehouse(name="明细接口仓", code="WHIT", status="active", is_default=True)
    supplier = Supplier(code="S01", name="退货供应商")
    unit = Unit(code="GE", name="个")
    cat = MaterialCategory(code="WJ", name="五金")
    db.session.add_all([wh, supplier, unit, cat])
    db.session.flush()
    material = Material(code="M-ITEM", name="明细接口测试件", spec="T1", stock=100,
                        min_stock=0, price=3.0, unit_id=unit.id, category_id=cat.id)
    db.session.add(material)
    db.session.commit()
    return {"wh": wh, "supplier": supplier, "material": material}


def _make_in_order(material, warehouse, quantity):
    order = InOrder(order_no="IN-ITEM-1", date=datetime.date.today(),
                    business_type="采购入库", supplier_id=1, status="completed",
                    warehouse=warehouse.name)
    db.session.add(order)
    db.session.flush()
    ii = InOrderItem(in_order_id=order.id, material_id=material.id,
                     quantity=quantity, price=3.0, amount=quantity * 3.0)
    db.session.add(ii)
    db.session.commit()
    return order.id, ii.id


def _make_return_draft(material, warehouse, in_order_id, ii_id, quantity):
    order = OutOrder(order_no="PR-ITEM-1", date=datetime.date.today(),
                     business_type="采购退货出库", customer="退货供应商",
                     warehouse=warehouse.name, status="pending",
                     source_in_order_id=in_order_id)
    db.session.add(order)
    db.session.flush()
    item = OutOrderItem(out_order_id=order.id, material_id=material.id,
                        source_in_order_item_id=ii_id, quantity=quantity,
                        price=3.0, amount=quantity * 3.0)
    db.session.add(item)
    db.session.commit()
    return order.id, item.id


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


def test_t1_item_add_rejected_for_purchase_return():
    """T1：采购退货单不得经 item/add 造无来源行（否则防超退闸整行跳过）。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        in_order_id, ii_id = _make_in_order(seed["material"], seed["wh"], 10)
        order_id, _ = _make_return_draft(seed["material"], seed["wh"],
                                         in_order_id, ii_id, 2)
        seed_data.update(order_id=order_id, material_code=seed["material"].code)

    client = _make_client()
    resp = client.post(f"/out_order/{seed_data['order_id']}/item/add",
                       data={"material_code": seed_data["material_code"], "quantity": 100})
    data = resp.get_json()
    assert data["status"] == "error", f"采购退货单必须拒绝裸加明细，实际 {data}"
    assert "来源采购入库行" in data.get("msg", ""), data

    with app_module.app.app_context():
        count = OutOrderItem.query.filter_by(out_order_id=seed_data["order_id"]).count()
        assert count == 1, f"不得新增无来源行，实际 {count} 行"


def test_t2_item_update_over_limit_rejected():
    """T2：有来源行改大数量超限必须被拒，且数量保持原值。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        in_order_id, ii_id = _make_in_order(seed["material"], seed["wh"], 10)
        order_id, item_id = _make_return_draft(seed["material"], seed["wh"],
                                               in_order_id, ii_id, 2)
        seed_data.update(item_id=item_id, material_code=seed["material"].code)

    client = _make_client()
    resp = client.post("/out_order/item/update",
                       data={"id": seed_data["item_id"], "code": seed_data["material_code"],
                             "quantity": 11, "price": 3.0})
    data = resp.get_json()
    assert data["status"] == "error", f"超限改量必须被拒，实际 {data}"
    assert "可退数量 10.00" in data.get("msg", ""), data

    with app_module.app.app_context():
        item = db.session.get(OutOrderItem, seed_data["item_id"])
        assert item.quantity == 2, f"被拒后数量必须保持 2，实际 {item.quantity}"


def test_t3_item_update_within_limit_allowed():
    """T3：限额内的改量正常放行（防误伤）。入库 10、当前 2 → 改成 6 应成功。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        in_order_id, ii_id = _make_in_order(seed["material"], seed["wh"], 10)
        order_id, item_id = _make_return_draft(seed["material"], seed["wh"],
                                               in_order_id, ii_id, 2)
        seed_data.update(item_id=item_id, material_code=seed["material"].code)

    client = _make_client()
    resp = client.post("/out_order/item/update",
                       data={"id": seed_data["item_id"], "code": seed_data["material_code"],
                             "quantity": 6, "price": 3.0})
    data = resp.get_json()
    assert data["status"] == "success", f"限额内改量必须放行，实际 {data}"

    with app_module.app.app_context():
        item = db.session.get(OutOrderItem, seed_data["item_id"])
        assert item.quantity == 6 and item.amount == 18.0, \
            f"数量/金额必须更新，实际 {item.quantity}/{item.amount}"


def test_t4_non_purchase_return_unaffected():
    """T4：非采购退货单（领料单）的 item/add 与改量不受本次改动影响。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        dept = Department(code="D01", name="生产部", status="active")
        db.session.add(dept)
        db.session.flush()
        order = OutOrder(order_no="OUT-ITEM-1", date=datetime.date.today(),
                         business_type="领料单", department_id=dept.id,
                         warehouse=seed["wh"].name, status="pending")
        db.session.add(order)
        db.session.commit()
        seed_data.update(order_id=order.id, material_code=seed["material"].code)

    client = _make_client()
    # 领料单裸加明细：应成功
    resp = client.post(f"/out_order/{seed_data['order_id']}/item/add",
                       data={"material_code": seed_data["material_code"], "quantity": 5})
    data = resp.get_json()
    assert data["status"] == "success", f"领料单裸加明细必须放行，实际 {data}"
    item_id = data["item_id"]

    # 领料单改量：无来源也应成功（不受采购退货闸影响）
    resp = client.post("/out_order/item/update",
                       data={"id": item_id, "code": seed_data["material_code"],
                             "quantity": 8, "price": 3.0})
    data = resp.get_json()
    assert data["status"] == "success", f"领料单改量必须放行，实际 {data}"

    with app_module.app.app_context():
        item = db.session.get(OutOrderItem, item_id)
        assert item.quantity == 8, f"领料单数量必须更新为 8，实际 {item.quantity}"

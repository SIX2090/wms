#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproduce material deletion when referenced by PurchaseOrderItem / SalesOrderItem."""
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

import app as app_module  # noqa: E402
from app import (AIMaterialAlias, AIDocumentItem, Material, MaterialCategory,  # noqa: E402
                 PurchaseOrder, PurchaseOrderItem, SalesOrder, SalesOrderItem,
                 Supplier, Unit, User, Warehouse, Customer, Contract, db)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _login(client):
    page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    token = m.group(1) if m else ""
    client.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token})


def _reset():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()


def _seed():
    from werkzeug.security import generate_password_hash
    with app_module.app.app_context():
        unit = Unit(name="个", code="PCS")
        cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
        sup = Supplier(code="SUP001", name="供应商")
        wh = Warehouse(code="WH01", name="主仓")
        user = User(username="admin", password_hash=generate_password_hash("admin"), role="admin", must_change_password=False)
        db.session.add_all([unit, cat, sup, wh, user])
        db.session.commit()
        u, c, s, w = unit, cat, sup, wh
        return {"unit": u, "cat": c, "sup": s, "wh": w, "user": user}


def _new_material(code, name):
    with app_module.app.app_context():
        from app import Material
        mat = Material(code=code, name=name, spec="S1", category_id=1, unit_id=1, supplier_id=1, stock=0, price=10, min_stock=0)
        db.session.add(mat)
        db.session.commit()
        return mat.id


def _delete(mat_id):
    client = app_module.app.test_client()
    _login(client)
    resp = client.post("/material/delete", json={"ids": [mat_id]})
    print(f"status_code={resp.status_code} body={resp.get_json()}")
    with app_module.app.app_context():
        still = db.session.get(Material, mat_id)
        print(f"  material still exists: {still is not None}")


def main():
    _reset()
    seeds = _seed()

    # Case 1: material referenced by PurchaseOrderItem
    with app_module.app.app_context():
        from app import Contract
        cus = Customer(code="C001", name="客户")
        db.session.add(cus)
        db.session.commit()
        po = PurchaseOrder(order_no="PO-001", supplier_id=1, status="pending", total_amount=0)
        db.session.add(po)
        db.session.commit()
        mat_id = _new_material("M-PO", "被采购订单引用")
        po_item = PurchaseOrderItem(purchase_order_id=po.id, material_id=mat_id, quantity=5, price=2, amount=10)
        db.session.add(po_item)
        db.session.commit()
    print("=== 删除被 PurchaseOrderItem 引用的物料 ===")
    _delete(mat_id)

    # Case 2: material referenced by SalesOrderItem
    with app_module.app.app_context():
        from app import Contract
        co = Contract(contract_no="CT-001", project_name="工程")
        db.session.add(co)
        db.session.commit()
        so = SalesOrder(order_no="SO-001", customer_id=1, status="pending", total_amount=0)
        db.session.add(so)
        db.session.commit()
        mat_id2 = _new_material("M-SO", "被销售订单引用")
        so_item = SalesOrderItem(sales_order_id=so.id, material_id=mat_id2, quantity=3, price=5, amount=15)
        db.session.add(so_item)
        db.session.commit()
    print("=== 删除被 SalesOrderItem 引用的物料 ===")
    _delete(mat_id2)

    # Case 3: unreferenced material
    mat_id3 = _new_material("M-FREE", "无引用")
    print("=== 删除无引用的物料 ===")
    _delete(mat_id3)


if __name__ == "__main__":
    main()
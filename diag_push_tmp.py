# -*- coding: utf-8 -*-
"""临时诊断：实测 下推领料单 (POST /in_order/<id>/push) 耗时，定位10秒卡顿。"""
from __future__ import annotations
import os, sys, time, re
from pathlib import Path
ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("app", str(APP_DIR / "app.py"))
app_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(app_module)
sys.modules["app"] = app_module
print("DEBUG app file:", getattr(app_module, "__file__", None))
from app import (Department, InOrder, InOrderItem, Material, Unit, Warehouse, db)  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def reset():
    db.drop_all(); db.create_all()

def seed():
    from werkzeug.security import generate_password_hash
    from app import User
    unit = Unit(code="U1", name="个")
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    dept = Department(code="D001", name="生产部", status="active")
    user = User(username="admin", password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False)
    mats = [Material(code=f"M{i:03d}", name=f"物料{i}", spec=f"S{i}", stock=100, price=10) for i in range(1, 26)]
    db.session.add_all([unit, wh, dept, user, *mats]); db.session.commit()
    return user, mats, dept

def completed_in_order(mats):
    order = InOrder(order_no="IN-PUSH-001", business_type="采购入库", status="completed", warehouse="仓库A", total_amount=0)
    db.session.add(order); db.session.flush()
    for m in mats:
        db.session.add(InOrderItem(in_order_id=order.id, material_id=m.id, quantity=10, price=10, amount=100))
    db.session.commit()
    return order.id

def login(client):
    return client.post("/login", data={"username": "admin", "password": "admin"},
                       content_type="application/x-www-form-urlencoded")

def main():
    with app_module.app.app_context():
        reset(); user, mats, dept = seed()
        oid = completed_in_order(mats)
        client = app_module.app.test_client()
        login(client)
        from app import InOrder
        order = InOrder.query.get(oid)
        items = [{"source_item_id": it.id, "quantity": 5} for it in order.items[:5]]
        payload = {"target_type": "requisition", "request_id": "diag-1",
                   "department_id": dept.id, "picker": "张三", "purpose": "",
                   "customer_id": "", "reason": "", "items": items}
        t0 = time.perf_counter()
        r = client.get(f"/in_order/{oid}/push")
        t_get = time.perf_counter() - t0
        print(f"GET /in_order/{oid}/push 耗时: {t_get*1000:.0f} ms, http={r.status_code}")
        t0 = time.perf_counter()
        r = client.post(f"/in_order/{oid}/push", json=payload)
        t_post = time.perf_counter() - t0
        print(f"POST /in_order/{oid}/push 耗时: {t_post*1000:.0f} ms, http={r.status_code}, resp={r.get_json()}")
        if r.status_code == 200 and r.get_json().get("status") == "success":
            tid = r.get_json()["id"]
            t0 = time.perf_counter()
            r2 = client.get(f"/out_order/{tid}")
            t_detail = time.perf_counter() - t0
            print(f"GET /out_order/{tid} 耗时: {t_detail*1000:.0f} ms, http={r2.status_code}")

if __name__ == "__main__":
    main()
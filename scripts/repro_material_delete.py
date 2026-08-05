#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproduce material deletion to find why '物料无法删除'."""
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
from app import db, User, Material, MaterialCategory, Unit, Supplier  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def main():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        from werkzeug.security import generate_password_hash
        unit = Unit(name="个", code="PCS")
        cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
        sup = Supplier(code="SUP001", name="测试供应商")
        user = User(username="admin", password_hash=generate_password_hash("admin"), role="admin", must_change_password=False)
        mat = Material(code="DEL-001", name="待删除物料", spec="S1", category=cat, unit=unit, supplier=sup, stock=0, price=10, min_stock=0, max_stock=9999, reorder_point=0)
        db.session.add_all([unit, cat, sup, user, mat])
        db.session.commit()
        mat_id = mat.id

    client = app_module.app.test_client()
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token})

    print("=== POST /material/delete (JSON) ===")
    resp = client.post("/material/delete", json={"ids": [mat_id]})
    print(f"status_code={resp.status_code}")
    print(f"body={resp.get_json()}")
    with app_module.app.app_context():
        still = db.session.get(Material, mat_id)
        print(f"material still exists: {still is not None}")

    # try form data
    print("=== POST /material/delete (FORM) ===")
    resp2 = client.post("/material/delete", data={"ids": repr([mat_id])})
    print(f"status_code={resp2.status_code}")
    print(f"body={resp2.get_json()}")


if __name__ == "__main__":
    main()
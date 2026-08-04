# -*- coding: utf-8 -*-
"""
BUG-2026-08-04-009 回归测试：新增物料带初始库存时补审计流水

原 Bug：
  add_material 创建物料时直接写 `material.stock = initial_stock`，
  但不在 stock_transaction 表记录一条 opening 流水，导致库存台账/月报
  无法追溯该初始库存的来源。

修复：
  物料创建并提交后，若 initial_stock > 0，追加一条 StockTransaction
  （transaction_type='opening'，reference_type='opening_stock'），
  与期初库存调整语义一致。

测试：
  T1. 新增物料初始库存 > 0 → 生成一条 opening 流水
  T2. 新增物料初始库存 = 0 → 不生成流水
  T3. 初始库存流水的数量/类型/物料正确
"""
from __future__ import annotations

import os
import sys
import re
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
from app import db, User, Material, StockTransaction, Warehouse  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    db.session.add(user)
    db.session.commit()


def _login(client):
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post("/login", data={
        "username": "admin", "password": "admin", "csrf_token": token})


class TestBug20260804009AddMaterialStockAudit:
    """新增物料带初始库存必须补审计流水。"""

    def test_T1_initial_stock_creates_opening_transaction(self):
        """新增物料初始库存 = 100 → 生成一条 opening 流水。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            client = app_module.app.test_client()
            _login(client)
            resp = client.post("/material/add", data={
                "code": "M001",
                "name": "轴承",
                "spec": "6204",
                "brand": "",
                "price": "10",
                "stock": "100",
            })
            assert resp.status_code == 200, resp.get_data(as_text=True)
            data = resp.get_json()
            assert data["status"] == "success", data
            mat = Material.query.filter_by(code="M001").first()
            assert mat is not None
            assert mat.stock == 100
            txns = StockTransaction.query.filter_by(material_id=mat.id).all()
            assert len(txns) == 1, "应生成一条审计流水"
            assert txns[0].transaction_type == "opening"
            assert txns[0].reference_type == "opening_stock"
            assert txns[0].quantity == 100

    def test_T2_zero_initial_stock_no_transaction(self):
        """新增物料初始库存 = 0 → 不生成流水。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            client = app_module.app.test_client()
            _login(client)
            resp = client.post("/material/add", data={
                "code": "M001",
                "name": "轴承",
                "spec": "6204",
                "brand": "",
                "price": "10",
                "stock": "0",
            })
            assert resp.status_code == 200, resp.get_data(as_text=True)
            data = resp.get_json()
            assert data["status"] == "success", data
            mat = Material.query.filter_by(code="M001").first()
            assert mat is not None
            txns = StockTransaction.query.filter_by(material_id=mat.id).all()
            assert len(txns) == 0, "初始库存为 0 时不应生成流水"

    def test_T3_quantity_and_type_correct(self):
        """初始库存流水的数量/类型/物料正确。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            client = app_module.app.test_client()
            _login(client)
            resp = client.post("/material/add", data={
                "code": "M002",
                "name": "螺母",
                "spec": "M8",
                "brand": "",
                "price": "5",
                "stock": "500",
            })
            assert resp.status_code == 200, resp.get_data(as_text=True)
            data = resp.get_json()
            assert data["status"] == "success", data
            mat = Material.query.filter_by(code="M002").first()
            assert mat is not None
            txn = StockTransaction.query.filter_by(material_id=mat.id).first()
            assert txn is not None
            assert txn.transaction_type == "opening"
            assert txn.material_id == mat.id
            assert txn.quantity == 500
            assert txn.reference_type == "opening_stock"
            assert txn.reference_id == mat.id
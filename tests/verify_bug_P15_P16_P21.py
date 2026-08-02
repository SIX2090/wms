"""P1-5 回归测试
- P1-5：采购入库单允许手工新增/保存/完成，不强制关联采购订单
"""
from __future__ import annotations

import os
import sys
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
from app import (  # noqa: E402
    Warehouse, User, Material, MaterialCategory, Unit, Supplier,
    InOrder, InOrderItem, db,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_common():
    unit = Unit(name="个", code="PCS")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    sup = Supplier(code="SUP001", name="测试供应商")
    wh_a = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    wh_b = Warehouse(code="WHB", name="仓库B", is_default=False, status="active")
    from werkzeug.security import generate_password_hash
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    mat = Material(
        code="M001", name="测试物料", spec="S1",
        category=cat, unit=unit, supplier=sup,
        stock=0, price=10, min_stock=0, max_stock=9999, reorder_point=0,
    )
    db.session.add_all([unit, cat, sup, wh_a, wh_b, user, mat])
    db.session.commit()
    return {
        "unit": unit, "cat": cat, "sup": sup,
        "wh_a": wh_a, "wh_b": wh_b,
        "user": user, "mat": mat,
    }


def _make_client():
    import re
    client = app_module.app.test_client()
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post(
        "/login",
        data={"username": "admin", "password": "admin", "csrf_token": token},
    )
    return client


# ---------------------------------------------------------------------------
# P1-5
# ---------------------------------------------------------------------------
class TestBugP15PurchaseInOptionalPurchaseOrder:
    def test_A_save_purchase_in_without_purchase_order(self):
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed_common()
            client = _make_client()
            resp = client.post("/in_order/add", json={
                "business_type": "采购入库",
                "supplier_id": seeds["sup"].id,
                "warehouse": seeds["wh_a"].name,
                "items": [{"code": "M001", "quantity": 5, "price": 10}],
            })
            body = resp.get_json()
            assert resp.status_code == 200, body
            assert body["status"] == "success", (
                f"采购入库手工保存失败，P1-5要求允许不关联采购订单：{body}"
            )
            assert body.get("id")
            order = InOrder.query.get(body["id"])
            assert order.source_purchase_order_id is None
            items = list(order.items)
            assert len(items) == 1
            assert items[0].source_purchase_order_item_id is None

    def test_B_complete_purchase_in_without_purchase_order(self):
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed_common()
            client = _make_client()
            resp = client.post("/in_order/add", json={
                "business_type": "采购入库",
                "supplier_id": seeds["sup"].id,
                "warehouse": seeds["wh_a"].name,
                "items": [{"code": "M001", "quantity": 3, "price": 10}],
            })
            order_id = resp.get_json()["id"]
            resp2 = client.post(f"/in_order/{order_id}/complete")
            body = resp2.get_json()
            assert resp2.status_code == 200, body
            assert body["status"] == "success", (
                f"手工采购入库被阻断，P1-5要求可直接完成入库：{body}"
            )
            mat = Material.query.filter_by(code="M001").first()
            assert (mat.stock or 0) >= 3

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
    InOrder, InOrderItem, PurchaseOrder, PurchaseOrderItem,
    SubcontractOrder, SubcontractItem, ProductionRequisition,
    ProductionRequisitionItem, db,
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


# ---------------------------------------------------------------------------
# P1-6
# ---------------------------------------------------------------------------
class TestBugP16CompletedInOrderCannotDeleteDirectly:
    def test_A_delete_completed_order_returns_409(self):
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed_common()
            client = _make_client()
            resp = client.post("/in_order/add", json={
                "business_type": "采购入库",
                "supplier_id": seeds["sup"].id,
                "warehouse": seeds["wh_a"].name,
                "items": [{"code": "M001", "quantity": 7, "price": 10}],
            })
            order_id = resp.get_json()["id"]
            client.post(f"/in_order/{order_id}/complete")

            delete_resp = client.post(f"/in_order/{order_id}/delete")
            assert delete_resp.status_code == 409, (
                f"已完成入库单被直接删除！P1-6要求必须先反提交：{delete_resp.get_json()}"
            )
            msg = (delete_resp.get_json() or {}).get("msg", "")
            assert "反提交" in msg or "草稿" in msg, msg
            assert InOrder.query.get(order_id) is not None

    def test_B_revert_then_delete_succeeds(self):
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed_common()
            client = _make_client()
            resp = client.post("/in_order/add", json={
                "business_type": "产品入库",
                "warehouse": seeds["wh_a"].name,
                "items": [{"code": "M001", "quantity": 2, "price": 10}],
            })
            order_id = resp.get_json()["id"]
            client.post(f"/in_order/{order_id}/complete")
            rev = client.post(f"/in_order/{order_id}/revert")
            assert rev.get_json()["status"] == "success", rev.get_json()
            d = client.post(f"/in_order/{order_id}/delete")
            assert d.get_json()["status"] == "success", d.get_json()
            assert InOrder.query.get(order_id) is None

    def test_C_batch_delete_blocks_completed(self):
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed_common()
            client = _make_client()
            r1 = client.post("/in_order/add", json={
                "business_type": "产品入库", "warehouse": seeds["wh_a"].name,
                "items": [{"code": "M001", "quantity": 1, "price": 10}]
            })
            id_pending = r1.get_json()["id"]
            r2 = client.post("/in_order/add", json={
                "business_type": "产品入库", "warehouse": seeds["wh_a"].name,
                "items": [{"code": "M001", "quantity": 1, "price": 10}]
            })
            id_done = r2.get_json()["id"]
            client.post(f"/in_order/{id_done}/complete")

            r = client.post("/in_order/batch_delete",
                            json={"ids": [id_pending, id_done]})
            body = r.get_json() or {}
            msg = body.get("msg", "")
            assert "已完成" in msg or "不能删除" in msg, (
                f"批量删除未挡住已完成单，P1-6要求：{body}"
            )
            assert InOrder.query.get(id_done) is not None

    def test_D_batch_delete_po_update_failure_warns(self, monkeypatch):
        """P1-1：批量删除后统一更新采购订单状态失败时，返回 po_update_failed=True
        且 msg 提示人工核对，不再静默返回 success。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed_common()
            from datetime import date as _date
            # 构造一张来源采购订单（草稿状态，received_quantity=5）
            po = PurchaseOrder(
                order_no="PO-P11", date=_date.today(), supplier_id=seeds["sup"].id,
                status="pending", total_amount=100,
            )
            db.session.add(po)
            db.session.flush()
            po_item = PurchaseOrderItem(
                purchase_order_id=po.id, material_id=seeds["mat"].id,
                quantity=10, received_quantity=5, price=10, amount=100,
            )
            db.session.add(po_item)
            db.session.flush()
            # 直接在 DB 构造一张来源该采购订单的草稿入库单（可删除）
            io = InOrder(
                order_no="IN-P11", date=_date.today(), supplier_id=seeds["sup"].id,
                business_type="采购入库", warehouse=seeds["wh_a"].name,
                source_purchase_order_id=po.id, status="pending",
                operator_id=seeds["user"].id, total_amount=20,
            )
            db.session.add(io)
            db.session.flush()
            # 关键：InOrderItem 关联 source_purchase_order_item_id，使批量删除时
            # affected_purchase_order_ids 非空，触发统一 update_purchase_order_status
            db.session.add(InOrderItem(
                in_order_id=io.id, material_id=seeds["mat"].id,
                source_purchase_order_item_id=po_item.id,
                quantity=2, price=10, amount=20,
            ))
            db.session.commit()
            order_id = io.id

            # mock update_purchase_order_status 抛异常，模拟 PO 状态更新失败
            def _boom(_po):
                raise RuntimeError("模拟采购订单状态更新失败")
            monkeypatch.setattr(app_module, "update_purchase_order_status", _boom)

            client = _make_client()
            r = client.post("/in_order/batch_delete", json={"ids": [order_id]})
            body = r.get_json() or {}
            assert body.get("status") == "success", body
            assert body.get("deleted") == 1, body
            assert body.get("po_update_failed") is True, (
                f"PO 状态更新失败时未返回 po_update_failed=True：{body}"
            )
            assert "采购订单状态更新失败" in body.get("msg", ""), (
                f"msg 未提示采购订单状态更新失败：{body}"
            )

    def test_E_batch_delete_po_update_ok_no_warn(self):
        """P1-1：正常路径下（PO 状态更新成功）po_update_failed=False。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed_common()
            client = _make_client()
            resp = client.post("/in_order/add", json={
                "business_type": "产品入库", "warehouse": seeds["wh_a"].name,
                "items": [{"code": "M001", "quantity": 2, "price": 10}],
            })
            order_id = resp.get_json()["id"]
            r = client.post("/in_order/batch_delete", json={"ids": [order_id]})
            body = r.get_json() or {}
            assert body.get("status") == "success", body
            assert body.get("deleted") == 1, body
            assert body.get("po_update_failed") is False, (
                f"正常路径下 po_update_failed 应为 False：{body}"
            )


# ---------------------------------------------------------------------------
# P2-1：subcontract / requisition / purchase_* 业务报表仓库必填守卫
# ---------------------------------------------------------------------------
class TestBugP21BizReportWarehouseGuard:
    def _seed_without_warehouse(self):
        """无仓库配置环境：不创建任何 Warehouse。"""
        with app_module.app.app_context():
            _reset_db()
            unit = Unit(name="个", code="PCS")
            cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
            sup = Supplier(code="SUP001", name="测试供应商")
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
            db.session.add_all([unit, cat, sup, user, mat])
            db.session.commit()
            return {"mat": mat, "sup": sup}

    def _seed_biz_orders(self):
        """在当前会话中造委外单 / 领料单 / 采购订单各一条，验证"有数据仍被守卫拦截"。"""
        from datetime import date as _date
        with app_module.app.app_context():
            mat = Material.query.filter_by(code="M001").first()
            sup = Supplier.query.filter_by(code="SUP001").first()
            if PurchaseOrder.query.count() == 0:
                po = PurchaseOrder(
                    order_no="PO-001", date=_date.today(), supplier_id=sup.id,
                    status="pending", total_amount=100,
                )
                db.session.add(po)
                db.session.flush()
                db.session.add(PurchaseOrderItem(
                    purchase_order_id=po.id, material_id=mat.id,
                    quantity=10, received_quantity=0, price=10, amount=100,
                ))
            if SubcontractOrder.query.count() == 0:
                sc = SubcontractOrder(
                    order_no="SC-001", date=_date.today(), supplier_id=sup.id,
                    status="pending", total_amount=50,
                )
                db.session.add(sc)
                db.session.flush()
                db.session.add(SubcontractItem(
                    subcontract_order_id=sc.id, material_id=mat.id, quantity=5,
                ))
            if ProductionRequisition.query.count() == 0:
                # BUG-2026-08-05-008：工单领料单已有 warehouse 列并参与报表仓库过滤，
                # 种子数据需带上当前默认仓库名，否则会被仓库过滤排除
                _default_wh = Warehouse.query.filter_by(is_default=True, status="active").first()
                pr = ProductionRequisition(
                    req_no="REQ-001", date=_date.today(),
                    purpose="测试领料", status="pending",
                    warehouse=_default_wh.name if _default_wh else None,
                )
                db.session.add(pr)
                db.session.flush()
                db.session.add(ProductionRequisitionItem(
                    requisition_id=pr.id, material_id=mat.id, quantity=3,
                ))
            db.session.commit()

    def test_A_no_warehouse_no_default_returns_empty(self):
        """无仓库参数 + 无默认仓库 → 三个业务报表返回空数据（守卫生效）。"""
        self._seed_without_warehouse()
        client = _make_client()
        for report_type in ('purchase_order_execution', 'subcontract', 'requisition'):
            resp = client.get(f"/report/api/{report_type}")
            body = resp.get_json() or {}
            assert resp.status_code == 200, (report_type, body)
            assert body.get("status") == "success", (report_type, body)
            assert body.get("data") == [], (
                f"{report_type} 无仓库时未返回空，违反 AGENTS.md 仓库必填：{body}"
            )
            assert body.get("total", 0) == 0, (report_type, body)

    def test_B_default_warehouse_auto_used_returns_rows(self):
        """有默认仓库且未显式传仓库 → 自动带入默认仓，报表返回数据（不误伤）。"""
        with app_module.app.app_context():
            _reset_db()
            # 建默认仓库
            wh = Warehouse(code="WHD", name="默认仓", is_default=True, status="active")
            unit = Unit(name="个", code="PCS")
            cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
            sup = Supplier(code="SUP001", name="测试供应商")
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
            db.session.add_all([wh, unit, cat, sup, user, mat])
            db.session.commit()
        self._seed_biz_orders()
        client = _make_client()
        for report_type in ('purchase_order_execution', 'subcontract', 'requisition'):
            resp = client.get(f"/report/api/{report_type}")
            body = resp.get_json() or {}
            assert resp.status_code == 200, (report_type, body)
            assert body.get("status") == "success", (report_type, body)
            assert body.get("data") != [], (
                f"{report_type} 有默认仓时不应被守卫拦截（自动带入默认仓）：{body}"
            )

    def test_C_explicit_warehouse_param_returns_rows(self):
        """显式传 warehouse_id → 报表正常返回数据（指定仓 PO 行可见）。"""
        with app_module.app.app_context():
            _reset_db()
            wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
            unit = Unit(name="个", code="PCS")
            cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
            sup = Supplier(code="SUP001", name="测试供应商")
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
            db.session.add_all([wh, unit, cat, sup, user, mat])
            db.session.commit()
            wh_id = wh.id
        self._seed_biz_orders()
        client = _make_client()
        for report_type in ('purchase_order_execution', 'subcontract', 'requisition'):
            resp = client.get(f"/report/api/{report_type}?warehouse_id={wh_id}")
            body = resp.get_json() or {}
            assert resp.status_code == 200, (report_type, body)
            assert body.get("status") == "success", (report_type, body)
            assert body.get("data") != [], (
                f"{report_type} 显式指定仓库时应返回数据：{body}"
            )

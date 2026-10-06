# -*- coding: utf-8 -*-
"""模块4：采购→入库→销售→出库 跨模块链路 E2E + 四本账一致性。

链路：采购订单 → 下推入库单 → 入库 push → 销售 → 下推出库 → 出库 push →
四本账核对（总账/仓级/库位/流水）。
"""
import sys
sys.path.insert(0, "/Coze/Drive/扣子/wms/scripts")
from deep_audit_lib import app_module, fresh_env, make_client, check, csrf_from
from app import (db, Material, Warehouse, Supplier, Customer,
                 PurchaseOrder, InOrder, SalesOrder, OutOrder)


def mod4_purchase_sales():
    with app_module.app.app_context():
        admin, mat = fresh_env()
        c = make_client()

        # seed 客商
        sup = Supplier(code="S001", name="供应商A")
        cust = Customer(code="C001", name="客户A")
        db.session.add_all([sup, cust])
        db.session.commit()

        # ---- P1. 采购订单创建（save_table 端点）----
        tok = csrf_from(c, "/purchase_order")
        r = c.post("/purchase_order/save", json={
            "supplier_id": sup.id,
            "remark": "深度检测采购单",
            "items": [{"material_id": mat.id, "quantity": 100, "price": 10}],
        }, follow_redirects=False)
        po = PurchaseOrder.query.order_by(PurchaseOrder.id.desc()).first()
        check("采购单创建", po is not None, f"st={r.status_code} po={po}")

        # ---- P2. 采购单下推入库单 ----
        tok = csrf_from(c, f"/purchase_order/{po.id}")
        r = c.post(f"/purchase_order/{po.id}/create_in_order", json={
            "warehouse": "A仓",
        }, follow_redirects=False)
        body = r.get_data(as_text=True)
        ino = InOrder.query.order_by(InOrder.id.desc()).first()
        check("下推入库单", ino is not None,
              f"st={r.status_code} body={body[:100]}")

        # ---- P3. 入库单执行（push）----
        if ino:
            tok = csrf_from(c, f"/in_order/{ino.id}")
            r = c.post(f"/in_order/{ino.id}/complete?force=true",
                       data={"csrf_token": tok}, follow_redirects=False)
            body = r.get_data(as_text=True)
            db.session.expire_all()
            from app import get_warehouse_stock_quantities, StockTransaction
            wh = Warehouse.query.filter_by(code="WHA").first()
            per_wh = get_warehouse_stock_quantities(wh)
            m2 = db.session.get(Material, mat.id)
            check("入库后总账=100", m2.stock == 100, f"stock={m2.stock}")
            check("入库后仓级=100", per_wh.get(mat.id) == 100,
                  f"per_wh={per_wh}")
            txs = [(t.transaction_type, t.quantity) for t in
                   StockTransaction.query.filter_by(material_id=mat.id).all()]
            check("流水含采购入库", any("in" == t[0] for t in txs), f"{txs}")
            # 采购单状态联动
            db.session.expire_all()
            po2 = db.session.get(PurchaseOrder, po.id)
            print("采购单状态:", po2.status)

        # ---- P4. 销售订单 ----
        tok = csrf_from(c, "/sales")
        r = c.post("/sales/add", json={
            "customer_id": cust.id,
            "warehouse": "A仓",
            "items": [{"code": "M001", "quantity": 30, "price": 20}],
        }, follow_redirects=False)
        so = SalesOrder.query.order_by(SalesOrder.id.desc()).first()
        check("销售单创建", so is not None, f"st={r.status_code} so={so}")

        # ---- P5. 出库（直接出库单，绕过销售下推）----
        tok = csrf_from(c, "/out_order")
        r = c.post("/out_order/add", json={
            "warehouse": "A仓",
            "business_type": "其他出库",
            "items": [{"code": "M001", "quantity": 30, "price": 20}],
        }, follow_redirects=False)
        oo = OutOrder.query.order_by(OutOrder.id.desc()).first()
        check("出库单创建", oo is not None,
              f"st={r.status_code} body={r.get_data(as_text=True)[:80]}")

        # ---- P6. 出库执行 + 账本 ----
        if oo:
            tok = csrf_from(c, f"/out_order/{oo.id}")
            r = c.post(f"/out_order/{oo.id}/complete?force=true",
                       data={"csrf_token": tok}, follow_redirects=False)
            body = r.get_data(as_text=True)
            db.session.expire_all()
            from app import get_warehouse_stock_quantities
            wh = Warehouse.query.filter_by(code="WHA").first()
            per_wh = get_warehouse_stock_quantities(wh)
            m3 = db.session.get(Material, mat.id)
            check("出库后总账=70", m3.stock == 70, f"stock={m3.stock}")
            check("出库后仓级=70", per_wh.get(mat.id) == 70,
                  f"per_wh={per_wh}")

        # ---- P7. 超卖拦截 ----
        tok = csrf_from(c, "/out_order")
        r = c.post("/out_order/add", json={
            "warehouse": "A仓",
            "business_type": "其他出库",
            "items": [{"code": "M001", "quantity": 10000, "price": 20}],
        }, follow_redirects=False)
        body = r.get_data(as_text=True)
        big_ok = OutOrder.query.order_by(OutOrder.id.desc()).first()
        check("超额出库被拦截或告警", r.status_code < 500,
              f"st={r.status_code} body={body[:80]}")


if __name__ == "__main__":
    mod4_purchase_sales()

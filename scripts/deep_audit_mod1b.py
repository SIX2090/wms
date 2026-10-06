# -*- coding: utf-8 -*-
"""模块1补：盘点（check）全链路 E2E + 盘点差异账本一致性。

真实端点序列：/check/add → /check/<id>/add_item（material_id，非 code）
→ /check/save_table 录实盘（若需要）→ /check/<id>/complete（JSON force=1）。
"""
import sys
sys.path.insert(0, "/Coze/Drive/扣子/wms/scripts")
from deep_audit_lib import app_module, fresh_env, stock_in, make_client, check, csrf_from
from app import db, Material, Warehouse


def mod1_check():
    with app_module.app.app_context():
        admin, mat = fresh_env()
        c = make_client()
        stock_in(admin, mat, 50, "A仓")   # 账面 50
        tok = csrf_from(c, "/check")
        r = c.post("/check/add", data={
            "csrf_token": tok,
            "warehouse": "A仓",
            "remark": "深度检测盘点",
        }, follow_redirects=False)
        check("盘点单创建", r.status_code in (200, 302), f"st={r.status_code}")
        from app import InventoryCheck, InventoryCheckItem
        ck = InventoryCheck.query.order_by(InventoryCheck.id.desc()).first()
        check("盘点单存在", ck is not None, f"ck={ck}")
        if not ck:
            return
        # 添加明细（material_id）
        tok = csrf_from(c, f"/check/{ck.id}")
        r = c.post(f"/check/{ck.id}/add_item", data={
            "csrf_token": tok,
            "material_id": str(mat.id),
        }, follow_redirects=False)
        check("盘点明细录入", r.status_code in (200, 302), f"st={r.status_code} body={r.get_data(as_text=True)[:80]}")
        # 录实盘 45（差异 -5）
        item = InventoryCheckItem.query.filter_by(
            inventory_check_id=ck.id, material_id=mat.id).first()
        check("明细行存在", item is not None, f"item={item}")
        if not item:
            return
        r = c.post(f"/check/{ck.id}/item/{item.id}", data={
            "csrf_token": tok,
            "actual_stock": "45",
        }, follow_redirects=False)
        check("实盘录入", r.status_code in (200, 302), f"st={r.status_code} body={r.get_data(as_text=True)[:80]}")
        db.session.expire_all()
        item = db.session.get(InventoryCheckItem, item.id)
        if item.actual_stock != 45:
            # 兜底：save_table 批量保存
            r = c.post("/check/save_table", json={
                "check_id": ck.id,
                "rows": [{"item_id": item.id, "actual_stock": 45}],
            }, follow_redirects=False)
            db.session.expire_all()
            item = db.session.get(InventoryCheckItem, item.id)
        check("实盘=45", item.actual_stock == 45,
              f"actual={item.actual_stock} diff={item.difference}")
        # 完成（未盘拦截：本行已盘，直接 force 保险）
        r = c.post(f"/check/{ck.id}/complete", json={"force": True},
                   follow_redirects=False)
        check("盘点完成", r.status_code in (200, 302), f"st={r.status_code} body={r.get_data(as_text=True)[:80]}")
        import json as _json
        resp = {}
        try:
            resp = r.get_json() or {}
        except Exception:
            pass
        adj_ids = resp.get("adjustment_ids") or []
        print("调整草稿:", adj_ids)
        if adj_ids:
            from app import AdjustmentOrder, AdjustmentOrderItem
            for aid in adj_ids:
                adj = db.session.get(AdjustmentOrder, aid)
                items = AdjustmentOrderItem.query.filter_by(adjustment_order_id=aid).all()
                print("草稿明细:", adj.adjustment_no, adj.adjustment_type,
                      [(i.material_id, i.quantity) for i in items])
                tok2 = csrf_from(c, "/adjustment")
                ra = c.post(f"/adjustment/{aid}/complete", data={"csrf_token": tok2},
                            follow_redirects=False)
                check(f"调整单 {adj.adjustment_no} 审核", ra.status_code in (200, 302),
                      f"st={ra.status_code} body={ra.get_data(as_text=True)[:80]}")
        db.session.expire_all()
        m2 = db.session.get(Material, mat.id)
        from app import StockTransaction, get_warehouse_stock_quantities
        wh = Warehouse.query.filter_by(code="WHA").first()
        per_wh = get_warehouse_stock_quantities(wh)
        types = [(t.transaction_type, t.quantity) for t in
                 StockTransaction.query.filter_by(material_id=mat.id).all()]
        check("盘点后总账=45", m2.stock == 45, f"stock={m2.stock}")
        check("盘点后仓级=45", per_wh.get(mat.id) == 45, f"per_wh={per_wh}")
        print("流水:", types)
        # 重复完成拒绝
        r = c.post(f"/check/{ck.id}/complete", json={"force": True},
                   follow_redirects=False)
        db.session.expire_all()
        m3 = db.session.get(Material, mat.id)
        check("重复完成不改账", m3.stock == 45, f"stock={m3.stock} st={r.status_code}")


if __name__ == "__main__":
    mod1_check()

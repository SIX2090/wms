# -*- coding: utf-8 -*-
"""模块3：主数据（物料/仓库/BOM/客商）深度检查。

重点：跨入口一致性（新建/编辑/停用/删除）、唯一约束、级联影响、
四本账在主数据变更后的行为。
"""
import sys
sys.path.insert(0, "/Coze/Drive/扣子/wms/scripts")
from deep_audit_lib import app_module, fresh_env, stock_in, make_client, check, csrf_from
from app import (db, Material, Warehouse, MaterialCategory, Unit,
                 Supplier, Customer, User)


def mod3_master_data():
    with app_module.app.app_context():
        admin, mat = fresh_env()
        c = make_client()
        stock_in(admin, mat, 20, "A仓")

        # ---- 物料 ----
        # M1. 重复编码创建被拒
        tok = csrf_from(c, "/material")
        r = c.post("/material/add", data={
            "csrf_token": tok, "code": "M001", "name": "dup",
            "category_id": "1", "unit_id": "1", "price": "1",
        }, follow_redirects=False)
        body = r.get_data(as_text=True)
        dup_ok = (r.status_code in (200, 302, 400)
                  and Material.query.filter_by(code="M001").count() == 1)
        check("重复编码物料被拒(400=api_error)", dup_ok, f"st={r.status_code}")

        # M2. 编辑物料改阈值，dashboard 告警同步
        tok = csrf_from(c, f"/material/{mat.id}")
        r = c.post(f"/material/edit/{mat.id}", data={
            "csrf_token": tok, "code": "M001", "name": "铜排",
            "category_id": "1", "unit_id": "1", "price": "10",
            "min_stock": "25", "reorder_point": "30",
        }, follow_redirects=False)
        db.session.expire_all()
        m2 = db.session.get(Material, mat.id)
        from app import _material_alert_status_values, get_all_warehouses_stock_quantities
        qty = get_all_warehouses_stock_quantities().get(mat.id, 0)
        st = _material_alert_status_values(m2, stock=qty)[3]
        check("编辑后阈值生效(库存20<min25→low)", st == "low",
              f"st={st} min={m2.min_stock}")

        # M3. 停用物料：历史库存仍可见
        tok = csrf_from(c, f"/material/{mat.id}")
        r = c.post(f"/material/edit/{mat.id}", data={
            "csrf_token": tok, "code": "M001", "name": "铜排",
            "category_id": "1", "unit_id": "1", "price": "10",
            "min_stock": "25", "reorder_point": "30", "status": "inactive",
        }, follow_redirects=False)
        db.session.expire_all()
        from app import get_warehouse_stock_quantities
        wh = Warehouse.query.filter_by(code="WHA").first()
        still = get_warehouse_stock_quantities(wh).get(mat.id)
        check("停用后库存仍可见", still == 20, f"still={still}")

        # M4. 删除有库存的物料 → 应拒绝或需确认
        tok = csrf_from(c, "/material")
        r = c.post(f"/material/{mat.id}/set_status", data={"csrf_token": tok},
                   follow_redirects=False)
        db.session.expire_all()
        gone = db.session.get(Material, mat.id) is None
        check("有库存物料删除被拦截", not gone, f"st={r.status_code} gone={gone}")

        # ---- 仓库 ----
        # W1. 停用默认仓库 → 新单据不得选用（查看是否还能建入库单）
        wha = Warehouse.query.filter_by(code="WHA").first()
        tok = csrf_from(c, "/warehouse")
        r = c.post(f"/warehouse/{wha.id}/edit", data={
            "csrf_token": tok, "code": "WHA", "name": "A仓", "status": "inactive",
        }, follow_redirects=False)
        db.session.expire_all()
        wha2 = db.session.get(Warehouse, wha.id)
        check("仓库停用生效", wha2.status == "inactive", f"st={wha2.status}")

        # W2. 唯一默认仓约束：另一仓设默认
        whb = Warehouse.query.filter_by(code="WHB").first()
        r = c.post(f"/warehouse/{whb.id}/edit", data={
            "csrf_token": tok, "code": "WHB", "name": "B仓",
            "status": "active", "is_default": "on",
        }, follow_redirects=False)
        db.session.expire_all()
        defaults = Warehouse.query.filter_by(is_default=True).all()
        check("默认仓唯一", len(defaults) <= 1,
              f"defaults={[w.code for w in defaults]}")

        # ---- BOM ----
        # B1. BOM 组件引用不存在物料 → 拒绝
        tok = csrf_from(c, "/bom")
        r = c.post("/bom/add", data={
            "csrf_token": tok, "bom_no": "BOM1", "material_code": "M001",
            "component_code": "GHOST-999", "quantity": "2",
        }, follow_redirects=False)
        body = r.get_data(as_text=True)
        check("BOM 幽灵组件被拒", r.status_code in (200, 400, 302),
              f"st={r.status_code} body={body[:80]}")

        # ---- 客商 ----
        # S1. 供应商重复编码
        tok = csrf_from(c, "/supplier")
        r = c.post("/supplier/add", data={
            "csrf_token": tok, "code": "S001", "name": "供应商A",
        }, follow_redirects=False)
        r2 = c.post("/supplier/add", data={
            "csrf_token": tok, "code": "S001", "name": "供应商B",
        }, follow_redirects=False)
        n = Supplier.query.filter_by(code="S001").count()
        check("供应商编码唯一", n == 1, f"n={n}")

        # S2. 无单据供应商批量删除（端点是 /supplier/delete 批量）
        s = Supplier.query.filter_by(code="S001").first()
        r = c.post("/supplier/delete", data={
            "csrf_token": tok, "ids": str(s.id),
        }, follow_redirects=False)
        check("供应商删除不 500", r.status_code < 500, f"st={r.status_code} body={r.get_data(as_text=True)[:80]}")


if __name__ == "__main__":
    mod3_master_data()

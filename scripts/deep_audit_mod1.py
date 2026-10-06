# -*- coding: utf-8 -*-
"""模块1：库存核心链路深度检测——转库/调整/盘点 全链路 E2E + 四本账一致性。"""
import sys
sys.path.insert(0, "/Coze/Drive/扣子/wms/scripts")
from deep_audit_lib import (app_module, fresh_env, stock_in, make_client,
                             check, get_json, csrf_from as _csrf)
from app import (Warehouse, StockTransaction, Material, db,
                 get_warehouse_stock_quantities, get_all_warehouses_stock_quantities)
import json


def mod1_transfer():
    """转库全链路：create → item add → complete → 四本账。"""
    with app_module.app.app_context():
        admin, mat = fresh_env()
        c = make_client()
        stock_in(admin, mat, 50, "A仓")
        wa = Warehouse.query.filter_by(code="WHA").first()
        wb = Warehouse.query.filter_by(code="WHB").first()

        # 1) 创建调拨单
        token = _csrf(c, "/transfer")
        r = c.post("/transfer/add", data={
            "csrf_token": token,
            "from_warehouse": "A仓", "to_warehouse": "B仓",
        })
        st, body = r.status_code, r.get_data(as_text=True)
        try:
            j = json.loads(body)
        except Exception:
            j = {}
        print("transfer/add:", st, j.get("msg", body[:80]))
        tid = j.get("id")
        if not tid:
            check("调拨单创建", False, body[:120]); return

        # 2) 加明细 30
        r2 = c.post(f"/transfer/{tid}/item/add", data={
            "csrf_token": token,
            "material_code": "M001", "quantity": 30, "price": 10,
        })
        try:
            j2 = json.loads(r2.get_data(as_text=True))
        except Exception:
            j2 = {}
        print("item/add:", r2.status_code, j2.get("msg", ""))

        # 3) complete
        r3 = c.post(f"/transfer/{tid}/complete", data={"csrf_token": token})
        try:
            j3 = json.loads(r3.get_data(as_text=True))
        except Exception:
            j3 = {}
        print("complete:", r3.status_code, j3.get("msg", ""))

        # 4) 四本账
        qA = get_warehouse_stock_quantities(wa).get(mat.id, 0)
        qB = get_warehouse_stock_quantities(wb).get(mat.id, 0)
        allq = get_all_warehouses_stock_quantities().get(mat.id, 0)
        check("转库后 A=20", qA == 20, f"A={qA}")
        check("转库后 B=30", qB == 30, f"B={qB}")
        check("转库后 all=50", allq == 50, f"all={allq}")
        check("转库后 material.stock=50", (mat.stock or 0) == 50, f"stock={mat.stock}")

        # 5) 重复 complete 拒绝
        r4 = c.post(f"/transfer/{tid}/complete", data={"csrf_token": token})
        j4 = json.loads(r4.get_data(as_text=True))
        check("重复完成被拒", j4.get("status") != "success", str(j4)[:80])


def mod1_adjustment():
    """调整单全链路：create → complete。"""
    with app_module.app.app_context():
        admin, mat = fresh_env()
        c = make_client()
        stock_in(admin, mat, 50, "A仓")
        wa = Warehouse.query.filter_by(code="WHA").first()

        token = _csrf(c, "/adjustment")
        r = c.post("/adjustment/add", data={
            "csrf_token": token,
            "adjustment_type": "loss", "warehouse": "A仓", "remark": "损耗测试",
            "material_id": mat.id, "quantity": 5,
        })
        try:
            j = json.loads(r.get_data(as_text=True))
        except Exception:
            j = {}
        print("adjustment/add:", r.status_code, j.get("msg", r.get_data(as_text=True)[:80]))
        aid = j.get("id")
        if not aid:
            check("调整单创建", False, str(j)[:120]); return
        r2 = c.post(f"/adjustment/{aid}/complete", data={"csrf_token": token})
        print("adjustment complete:", r2.status_code, r2.get_data(as_text=True)[:100])
        qA = get_warehouse_stock_quantities(wa).get(mat.id, 0)
        print("A now:", qA)


if __name__ == "__main__":
    mod1_transfer()
    mod1_adjustment()

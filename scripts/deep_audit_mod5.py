# -*- coding: utf-8 -*-
"""模块5：手机端 API 全接口健康扫描（GET 类全部 + POST 代表性）。

目标：每个接口 200/合法错误（400/401/404），抓 500 和静默异常。
"""
import sys
sys.path.insert(0, "/Coze/Drive/扣子/wms/scripts")
from deep_audit_lib import (app_module, fresh_env, stock_in, make_client,
                             check, get_json)
from app import Material, db, Warehouse, InOrder, InOrderItem, OutOrder, OutOrderItem
from datetime import date


GET_ENDPOINTS = [
    "/api/mobile/stocktake/check_orders",
    "/api/mobile/dashboard",
    "/api/mobile/dashboard?warehouse_id=all",
    "/api/mobile/location/options?warehouse=WHA",
    "/api/mobile/stock/query",
    "/api/mobile/stock/query?keyword=M001",
    "/api/mobile/alert/list",
    "/api/mobile/in_order/list",
    "/api/mobile/out_order/list",
    "/api/mobile/contracts",
    "/api/mobile/report/daily_detail",
    "/api/mobile/report/stock_daily",
    "/api/mobile/report/in_out_detail",
    "/api/mobile/report/stock_ledger",
    "/api/mobile/profile",
    "/api/warehouses",
    "/api/departments",
    "/api/mobile/suppliers",
    "/api/employees",
    "/api/categories",
    "/api/units",
    "/api/suppliers",
    "/api/customers",
    "/api/ai/v2/tools/inventory/health",
    "/api/ai/v2/tools/inventory/material?keyword=M001",
    "/api/ai/v2/tools/inventory/low-stock",
    "/api/ai/v2/tools/inventory/value",
]


def mod5_scan():
    with app_module.app.app_context():
        admin, mat = fresh_env()
        c = make_client()
        stock_in(admin, mat, 30, "A仓")

        fails = []
        for ep in GET_ENDPOINTS:
            r = c.get(ep)
            body = r.get_data(as_text=True)[:60].replace("\n", " ")
            if r.status_code >= 500:
                print(f"[HTTP {r.status_code}] {ep} — {body}")
                fails.append((ep, r.status_code, body))
            elif r.status_code == 200:
                print(f"[200] {ep}")
            else:
                print(f"[{r.status_code}] {ep} — {body}")
        check("无 5xx", not fails, str(fails)[:200])

        # 未登录访问应 401/302，不是 500
        anon = app_module.app.test_client()
        r = anon.get("/api/mobile/dashboard")
        check("未登录 dashboard 非 500", r.status_code < 500, f"{r.status_code}")
        r = anon.get("/api/mobile/alert/list")
        check("未登录 alert/list 非 500", r.status_code < 500, f"{r.status_code}")
        r = anon.get("/api/warehouses")
        check("未登录 warehouses 非 500", r.status_code < 500, f"{r.status_code}")

        # 带真实单据的接口
        ino = InOrder(order_no="IN1", warehouse="A仓", status="pending",
                      operator_id=admin.id, date=date.today())
        db.session.add(ino); db.session.commit()
        it = InOrderItem(in_order_id=ino.id, material_id=mat.id,
                         quantity=10, price=10, amount=100)
        db.session.add(it); db.session.commit()
        r = c.get("/api/mobile/in_order/list")
        st, j = get_json(c, "/api/mobile/in_order/list")
        total = j.get("data", {}).get("total") if j else None
        check("in_order/list 见单", total == 1, f"total={total}")
        st, j = get_json(c, f"/api/mobile/in_order/{ino.id}")
        check("in_order detail", st == 200 and j is not None, f"st={st}")


if __name__ == "__main__":
    mod5_scan()

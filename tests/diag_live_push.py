# -*- coding: utf-8 -*-
"""临时诊断（用完即删）：对 LIVE DB 实测 下推领料单 全链路耗时，定位 10 秒卡顿。
创建一张大入库单并下推为领料草稿，测量各阶段耗时，最后清理测试数据。
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))

import app as app_module  # noqa: E402
from app import (DocumentPushLine, InOrder, InOrderItem, Material, OperationLog,
                 OutOrder, OutOrderItem, db)  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _login(client):
    return client.post("/login", data={"username": "admin", "password": "admin"},
                       content_type="application/x-www-form-urlencoded")


def _measure_push(item_count, client):
    """创建 item_count 行入库单并下推为领料草稿，返回各段耗时(dict)。"""
    from app import generate_order_no
    tag = f"DIAG{PYTHON_PID}"
    mats = Material.query.order_by(Material.id.asc()).limit(item_count).all()
    order = InOrder(order_no=f"IN-{tag}", business_type="采购入库",
                    status="completed", warehouse="仓库A", total_amount=0)
    db.session.add(order)
    db.session.flush()
    for m in mats:
        db.session.add(InOrderItem(in_order_id=order.id, material_id=m.id,
                                   quantity=10, price=10, amount=100))
    db.session.commit()
    oid = order.id
    items = [{"source_item_id": it.id, "quantity": 5} for it in order.items]
    payload = {"target_type": "requisition", "request_id": f"diag-{oid}",
               "department_id": None, "picker": "张三", "purpose": "",
               "customer_id": "", "reason": "", "items": items}
    t0 = time.perf_counter()
    r = client.post(f"/in_order/{oid}/push", json=payload)
    total = (time.perf_counter() - t0) * 1000
    body = r.get_json()
    tid = body.get("id") if body else None
    # 清理
    if tid:
        DocumentPushLine.query.filter_by(target_document_id=tid).delete()
        OperationLog.query.filter_by(target_id=tid, target_type="requisition").delete()
        OutOrderItem.query.filter_by(out_order_id=tid).delete()
        OutOrder.query.filter_by(id=tid).delete()
    InOrderItem.query.filter_by(in_order_id=oid).delete()
    InOrder.query.filter_by(id=oid).delete()
    db.session.commit()
    return {"items": item_count, "ms": round(total), "http": r.status_code,
            "msg": (body or {}).get("msg")}


if __name__ == "__main__":
    PYTHON_PID = os.getpid()
    with app_module.app.app_context():
        client = app_module.app.test_client()
        _login(client)
        print("物料总数:", Material.query.count())
        for n in (5, 20, 50, 100, 200):
            try:
                res = _measure_push(n, client)
                print(f"[DIAG] 下推 {res['items']:>3} 行 -> {res['ms']:>6} ms  http={res['http']}  {res['msg']}")
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
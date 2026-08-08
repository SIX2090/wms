# -*- coding: utf-8 -*-
"""临时诊断（用完即删）：测量下推流程相关 GET 页面耗时（LIVE DB）。"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))

import app as app_module  # noqa: E402
from app import InOrder, OutOrder, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _login(client):
    return client.post("/login", data={"username": "admin", "password": "admin"},
                       content_type="application/x-www-form-urlencoded")


def _t(client, url, label):
    t0 = time.perf_counter()
    r = client.get(url)
    ms = (time.perf_counter() - t0) * 1000
    print(f"[DIAG] {label:<28} {ms:>7.0f} ms  http={r.status_code}  url={url}")
    return ms


if __name__ == "__main__":
    with app_module.app.app_context():
        client = app_module.app.test_client()
        _login(client)
        big = InOrder.query.filter_by(order_no="IN-PUSH-BIG").first()
        in_items = big.items if big else []
        print(f"来源入库单 IN-PUSH-BIG id={big.id if big else None} 明细数={len(in_items)}")
        req = OutOrder.query.filter_by(business_type="领料单").order_by(OutOrder.id.desc()).first()
        print(f"领料单 id={req.id if req else None} order_no={req.order_no if req else None} 明细数={len(req.items) if req else 0}")
        _t(client, "/", "首页")
        _t(client, "/in_order", "入库单列表")
        if big:
            _t(client, f"/in_order/{big.id}", "来源入库单详情")
            _t(client, f"/in_order/{big.id}/push", "下推页面 GET")
        if req:
            _t(client, f"/out_order/{req.id}", "领料单详情")
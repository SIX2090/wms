# -*- coding: utf-8 -*-
"""临时诊断（用完即删）：HTTP 实测下推领料单全链路耗时（含 CSRF）。"""
import os
import re
import sys
import time
import uuid
from pathlib import Path

import requests  # noqa: E402

BASE = "http://127.0.0.1:8080"
s = requests.Session()

t0 = time.perf_counter()
r = s.get(BASE + "/login", timeout=60)
m = re.findall(r'name="(csrf_token)" value="([^"]+)"', r.text)
csrf = m[0][1]
r = s.post(BASE + "/login", data={"username": "admin", "password": "admin", "csrf_token": csrf},
           timeout=60, allow_redirects=False)
t_login = time.perf_counter() - t0
print(f"[LIVE] 登录 耗时 {t_login*1000:.0f} ms status={r.status_code}")

OID = 2

# GET 下推页
t0 = time.perf_counter()
r = s.get(BASE + f"/in_order/{OID}/push?target=requisition", timeout=60)
t_get = time.perf_counter() - t0
print(f"[LIVE] GET push页 耗时 {t_get*1000:.0f} ms http={r.status_code} len={len(r.text)}")

item_ids = [int(x) for x in re.findall(r"data-item-id=\"(\d+)\"", r.text)]
meta_csrf = re.findall(r'<meta name="csrf-token" content="([^"]+)"', r.text)
push_csrf = meta_csrf[0] if meta_csrf else csrf
print(f"[LIVE] item ids: {item_ids[:6]} push_csrf={push_csrf[:20]}...")

# POST 下推领料单
payload = {
    "target_type": "requisition",
    "request_id": "live-" + uuid.uuid4().hex[:8],
    "department_id": "", "picker": "张三", "purpose": "",
    "customer_id": "", "reason": "",
    "items": [{"source_item_id": item_ids[i], "quantity": 5} for i in range(len(item_ids))],
}
t0 = time.perf_counter()
r = s.post(BASE + f"/in_order/{OID}/push", json=payload, headers={"X-CSRFToken": push_csrf}, timeout=120)
t_post = time.perf_counter() - t0
print(f"[LIVE] POST下推 耗时 {t_post*1000:.0f} ms http={r.status_code} resp={r.text[:150]}")
if r.status_code == 200 and r.json().get("status") == "success":
    tid = r.json()["id"]
    t0 = time.perf_counter()
    r2 = s.get(BASE + f"/out_order/{tid}", timeout=60)
    t_detail = time.perf_counter() - t0
    print(f"[LIVE] GET领料单详情 耗时 {t_detail*1000:.0f} ms http={r2.status_code} len={len(r2.text)}")
    t0 = time.perf_counter()
    s.get(BASE + f"/out_order/{tid}", timeout=60)
    print(f"[LIVE] GET领料单详情(2nd) 耗时 {(time.perf_counter()-t0)*1000:.0f} ms")
# -*- coding: utf-8 -*-
"""临时诊断（用完即删）：复现完整 采购入库单 -> 完成 -> 下推领料单 流程并分步计时。"""
from __future__ import annotations
import re, time, uuid
import requests

BASE = "http://127.0.0.1:8080"
s = requests.Session()

def csrf_of(html):
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if m: return m.group(1)
    m = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
    return m.group(1) if m else None

def step(label, fn):
    t0 = time.perf_counter()
    r = fn()
    print(f"[{label}] {time.perf_counter()-t0:.3f}s http={getattr(r,'status_code',None)}")
    return r

# 1) login
step("login", lambda: s.get(BASE + "/login", timeout=30))
r = s.get(BASE + "/login", timeout=30)
s.post(BASE + "/login", data={"username":"admin","password":"admin","csrf_token":csrf_of(r.text)},
       timeout=30, allow_redirects=False)

# 2) get a material code
addp = step("get /in_order/add", lambda: s.get(BASE + "/in_order/add", timeout=30))
code = "M001"
csrf = csrf_of(addp.text)
h = {"Content-Type":"application/json","X-CSRFToken":csrf or ""}

# 3) create inbound draft
payload = {"business_type":"采购入库","supplier_id":"","date":"2026-08-08","warehouse":"","purpose":"flow-diag","remark":"",
           "items":[{"code":code,"quantity":1,"price":1.0}]}
r = step("POST create inbound", lambda: s.post(BASE + "/in_order/add", json=payload, headers=h, timeout=60))
oid = r.json().get("id")
print("   inbound id=", oid, r.json().get("msg"))

# 4) complete it
r = step("POST complete", lambda: s.post(f"{BASE}/in_order/{oid}/complete", headers=h, timeout=60))
print("   complete:", r.json().get("msg"))

# 5) GET push page
pp = step("GET push page", lambda: s.get(f"{BASE}/in_order/{oid}/push", timeout=60))
item_ids = [int(x) for x in re.findall(r'data-item-id="(\d+)"', pp.text)]
meta = re.findall(r'<meta name="csrf-token" content="([^"]+)"', pp.text)
ph = {"Content-Type":"application/json","X-CSRFToken":(meta[0] if meta else csrf)}
print("   push items:", item_ids)

# 6) POST push
push = {"target_type":"requisition","request_id":f"flow-{uuid.uuid4().hex[:8]}",
        "department_id":"","picker":"张三","purpose":"flow-diag","customer_id":"","reason":"",
        "items":[{"source_item_id":item_ids[0],"quantity":1}]}
r = step("POST push requisition", lambda: s.post(f"{BASE}/in_order/{oid}/push", json=push, headers=ph, timeout=120))
print("   push resp:", r.text[:200])
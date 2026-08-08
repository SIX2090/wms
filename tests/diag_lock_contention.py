# -*- coding: utf-8 -*-
"""临时诊断（用完即删）：复现 下推领料单 10 秒卡顿 = SQLite 写锁竞争。
持有一个写事务(BEGIN IMMEDIATE) 5 秒，同时实测 push POST 的阻塞时长。"""
from __future__ import annotations
import re, sqlite3, threading, time, uuid
import requests

BASE = "http://127.0.0.1:8080"
DB = "/workspace/app/instance/inventory.db"

# 找一张 已完成 的入库单用于下推
c = sqlite3.connect(DB)
oin = c.execute("SELECT id FROM in_order WHERE status='completed' ORDER BY id DESC LIMIT 1").fetchone()
c.close()
OID = oin[0] if oin else None
print(f"[LOCK] 使用入库单 id={OID}")
assert OID

# 1) 登录拿到 session + csrf
s = requests.Session()
r = s.get(BASE + "/login", timeout=30)
csrf = re.findall(r'name="csrf_token" value="([^"]+)"', r.text)[0]
s.post(BASE + "/login", data={"username": "admin", "password": "admin", "csrf_token": csrf},
       timeout=30, allow_redirects=False)

# 2) GET push 页拿明细 id 与 meta csrf
r = s.get(BASE + f"/in_order/{OID}/push?target=requisition", timeout=30)
item_ids = [int(x) for x in re.findall(r'data-item-id="(\d+)"', r.text)]
meta = re.findall(r'<meta name="csrf-token" content="([^"]+)"', r.text)
push_csrf = meta[0] if meta else csrf
print(f"[LOCK] 可选明细 {len(item_ids)} 行, csrf={push_csrf[:12]}...")

# 3) 后台线程：持有一个写事务 5 秒
def hold_write_lock(seconds):
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("BEGIN IMMEDIATE")
    print(f"[LOCK] 已持有写事务，持续 {seconds}s ...")
    time.sleep(seconds)
    conn.rollback()
    conn.close()
    print("[LOCK] 写事务已释放")
t = threading.Thread(target=hold_write_lock, args=(5,), daemon=True)
t.start()
time.sleep(0.5)  # 确保写锁已拿到

# 4) 实测 push POST 阻塞时长
payload = {
    "target_type": "requisition",
    "request_id": "lock-" + uuid.uuid4().hex[:8],
    "department_id": "", "picker": "张三", "purpose": "",
    "customer_id": "", "reason": "",
    "items": [{"source_item_id": item_ids[0], "quantity": 1}],
}
t0 = time.perf_counter()
try:
    r = s.post(BASE + f"/in_order/{OID}/push", json=payload,
               headers={"X-CSRFToken": push_csrf}, timeout=30)
    print(f"[LOCK] POST下推 在写锁竞争下耗时 {(time.perf_counter()-t0)*1000:.0f} ms http={r.status_code} resp={r.text[:120]}")
except Exception as e:
    print(f"[LOCK] POST 异常: {e}")
t.join()
# -*- coding: utf-8 -*-
import sys, io, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import os
os.chdir(r"c:\Users\Administrator\Desktop\wms\app")
sys.path.insert(0, r"c:\Users\Administrator\Desktop\wms\app")
from app import app

app.config["PROPAGATE_EXCEPTIONS"] = True
with app.test_client() as c:
    r = c.get("/login")
    import re
    csrf = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', r.data).group(1).decode()
    r = c.post("/login", data={"username": "admin", "password": "AAAA1234",
                               "usage_consent": "1", "login_mode": "admin", "csrf_token": csrf},
               follow_redirects=True)
    print("login status:", r.status_code)
    for p in ["/ai/inventory_health_live"]:
        try:
            r = c.get(p)
            print(f"{p} -> {r.status_code} len={len(r.data)}")
        except Exception:
            with open(r"c:\Users\Administrator\Desktop\wms\audit_screenshots\_tb_inventory.txt", "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
            print("traceback written")

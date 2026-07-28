# -*- coding: utf-8 -*-
import re, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
src = open(r"c:\Users\Administrator\Desktop\wms\app\app.py", encoding="utf-8").read()
routes = sorted(set(re.findall(r"""@app\.route\(\s*['"]([^'"]+)['"]""", src)))
print(f"total routes: {len(routes)}")
for r in routes:
    print(r)

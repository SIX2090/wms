# -*- coding: utf-8 -*-
"""库存核心规则(只读): 已完成入库单删除入口检查 + 入库新增页结构分析."""
import re, sys, urllib.request, urllib.parse, http.cookiejar, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BASE = "http://127.0.0.1:8080"
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
b = op.open(BASE + "/login").read().decode("utf-8", "ignore")
csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', b).group(1)
op.open(BASE + "/login", data=urllib.parse.urlencode(
    {"username": "admin", "password": "AAAA1234", "usage_consent": "1",
     "login_mode": "admin", "csrf_token": csrf}).encode())

st = op.open(BASE + "/in_order")
html = st.read().decode("utf-8", "ignore")

# 按表格行切分，找每行状态与按钮
rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
print(f"in_order 列表行数(含表头): {len(rows)}")
completed_rows, draft_rows = [], []
for r in rows:
    txt = re.sub(r"<[^>]+>", " ", r)
    txt = re.sub(r"\s+", " ", txt)
    has_del = ("删除" in r) or ("delete" in r.lower())
    has_unsubmit = "反提交" in r
    if "已完成" in txt or "已审核" in txt:
        completed_rows.append((txt[:80], has_del, has_unsubmit))
    elif "草稿" in txt:
        draft_rows.append((txt[:80], has_del))
print(f"已完成行: {len(completed_rows)}, 草稿行: {len(draft_rows)}")
for t, d, u in completed_rows[:5]:
    flag = "BUG! 已完成单显示删除按钮" if d else "OK 无删除按钮"
    print(f"  已完成单: {t}... 删除={d}({flag}) 反提交={u}")
for t, d in draft_rows[:3]:
    print(f"  草稿单: {t}... 删除={d}(草稿允许删除)")

# 新增页结构
b2 = op.open(BASE + "/in_order/add").read().decode("utf-8", "ignore")
fields = re.findall(r'<(?:input|select)[^>]*name="([^"]+)"', b2)
print("\nin_order/add 表单字段:", sorted(set(fields)))
must_po = "必须选择采购订单" in b2 or ("purchase_order" in b2 and "required" in b2.split("purchase_order")[0][-200:])
print("是否强制关联采购订单:", "是(违反规则)" if must_po else "否(可手工新增)")
print("页面含采购订单选择(可选):", "purchase_order" in b2)

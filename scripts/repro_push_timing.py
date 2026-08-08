#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Concurrency test: fire many concurrent push requests to reveal SQLite write-lock contention."""
import re, sys, time, uuid, threading
from html.parser import HTMLParser
import requests

BASE="http://127.0.0.1:8080"
class CsrfExtractor(HTMLParser):
    def __init__(self): super().__init__(); self.csrf_token=None
    def handle_starttag(self,tag,attrs):
        if tag.lower()=="input":
            d={k.lower():v for k,v in attrs}
            if d.get("name")=="csrf_token": self.csrf_token=d.get("value")
def get_csrf(html):
    m=re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"',html)
    if m: return m.group(1)
    p=CsrfExtractor(); p.feed(html); return p.csrf_token

def login(s):
    for pwd in ["Admin@123","admin","Admin123","123456","admin123"]:
        for k in list(s.cookies.keys()): del s.cookies[k]
        r=s.get(BASE+"/login",timeout=10); cs=get_csrf(r.text)
        r=s.post(BASE+"/login",data={"csrf_token":cs,"username":"admin","password":pwd},allow_redirects=False,timeout=10)
        if r.status_code in (302,303) and "/login" not in r.headers.get("Location","/login"):
            return True
    return False

# prepare ONE material code
prep=requests.Session(); login(prep)
addp=prep.get(BASE+"/in_order/add",timeout=15)
codes=re.findall(r'"code"\s*:\s*"([^"]+)"',addp.text)
code=codes[0]
csrf=get_csrf(addp.text)
headers={"Content-Type":"application/json"}
if csrf: headers["X-CSRFToken"]=csrf
print("material:",code)

results=[]
def worker(idx):
    s=requests.Session(); login(s)
    # create draft
    payload={"business_type":"采购入库","supplier_id":"","date":"2026-08-08","warehouse":"","purpose":"conc-repro","remark":"",
             "items":[{"code":code,"quantity":1,"price":1.0}]}
    r=s.post(BASE+"/in_order/add",json=payload,headers=headers,timeout=60)
    oid=r.json().get("id")
    rc=s.post(f"{BASE}/in_order/{oid}/complete",headers=headers,timeout=60)
    pp=s.get(f"{BASE}/in_order/{oid}/push",timeout=60)
    pcsrf=get_csrf(pp.text)
    item_ids=re.findall(r'data-item-id="(\d+)"',pp.text)
    ph={"Content-Type":"application/json"}
    if pcsrf: ph["X-CSRFToken"]=pcsrf
    push={"target_type":"requisition","request_id":f"conc-{uuid.uuid4()}","purpose":"conc",
          "department_id":"","picker":"","customer_id":"","reason":"",
          "items":[{"source_item_id":int(item_ids[0]),"quantity":1}]}
    t0=time.time()
    pr=s.post(f"{BASE}/in_order/{oid}/push",json=push,headers=ph,timeout=120)
    results.append((idx, time.time()-t0, pr.status_code))

N=20
threads=[threading.Thread(target=worker,args=(i,)) for i in range(N)]
t0=time.time()
for t in threads: t.start()
for t in threads: t.join()
total=time.time()-t0
lats=sorted(x[1] for x in results)
print(f"total wall={total:.3f}s for {N} concurrent pushes")
print(f"latencies: min={lats[0]:.3f} p50={lats[N//2]:.3f} p90={lats[int(N*0.9)]:.3f} max={lats[-1]:.3f}")
print("all 2xx:", all(x[2]==200 for x in results))
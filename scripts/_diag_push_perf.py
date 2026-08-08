#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断下推领料单 10 秒卡顿：登录后找一个可下推的已完成入库单，计时 push 请求。"""
import re
import sys
import time
import uuid
from html.parser import HTMLParser

import requests

BASE = "http://127.0.0.1:8080"
USERNAME = "admin"
PASSWORDS = ["Admin@123", "admin", "Admin123", "123456", "admin123"]


class CsrfExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.csrf_token = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "input":
            attr_dict = dict(attrs)
            if attr_dict.get("name", "").lower() == "csrf_token":
                self.csrf_token = attr_dict.get("value")


def get_csrf(html):
    p = CsrfExtractor()
    p.feed(html)
    return p.csrf_token


def login(s):
    r = s.get(f"{BASE}/login", timeout=10)
    if r.status_code != 200:
        return False
    csrf = get_csrf(r.text)
    if not csrf:
        return False
    r = s.post(f"{BASE}/login", data={"csrf_token": csrf, "username": USERNAME, "password": "admin"},
               allow_redirects=False, timeout=10)
    return r.status_code in (302, 303)


def main():
    s = requests.Session()
    if not login(s):
        print("LOGIN FAILED")
        return
    print("LOGIN OK")

    # 找已完成入库单列表
    r0 = time.perf_counter()
    resp = s.get(f"{BASE}/in_order?status=completed&per_page=50", timeout=30)
    print(f"GET /in_order?status=completed took {time.perf_counter()-r0:.2f}s code={resp.status_code}")
    html = resp.text

    # 提取入库单 id 和 order_no（从列表链接 /in_order/<id>）
    ids = []
    for m in re.finditer(r'href="(/in_order/(\d+))"', html):
        oid = int(m.group(2))
        if oid not in ids:
            ids.append(oid)
    print(f"found {len(ids)} in_order ids")

    # 也尝试从表格行提取 order_no 已完成的
    for oid in ids[:10]:
        # 先取下推页看是否可下推及明细
        r1 = time.perf_counter()
        pr = s.get(f"{BASE}/in_order/{oid}/push", timeout=30)
        dur1 = time.perf_counter() - r1
        if pr.status_code != 200:
            print(f"  order {oid} push page code={pr.status_code} dur={dur1:.2f}s")
            continue
        # 提取明细 source_item_id 与可下推数量
        item_ids = [int(x) for x in re.findall(r'data-source-item-id="(\d+)"', pr.text)]
        # 也试通用 id 提取
        if not item_ids:
            item_ids = [int(x) for x in re.findall(r'name="source_item_id" value="(\d+)"', pr.text)]
        qty_rows = re.findall(r'data-available="([\d.]+)"', pr.text)
        print(f"  order {oid} push page dur={dur1:.2f}s items={item_ids} avail={qty_rows[:3]}")
        if not item_ids:
            # 尝试从详情页拿明细
            det = s.get(f"{BASE}/in_order/{oid}", timeout=30)
            item_ids = [int(x) for x in re.findall(r'data-item-id="(\d+)"', det.text)]
            print(f"    detail items={item_ids}")
        if not item_ids:
            continue
        # 计时 push 请求（领料单）
        payload = {
            "target_type": "requisition",
            "request_id": f"diag-{uuid.uuid4().hex[:8]}",
            "items": [{"source_item_id": item_ids[0], "quantity": 1.0}],
        }
        csrf = get_csrf(s.get(f"{BASE}/in_order/{oid}", timeout=30).text)
        headers = {"Content-Type": "application/json", "X-CSRFToken": csrf or ""}
        r2 = time.perf_counter()
        ps = s.post(f"{BASE}/in_order/{oid}/push", json=payload, headers=headers, timeout=60)
        dur2 = time.perf_counter() - r2
        print(f"  >>> PUSH order {oid} took {dur2:.2f}s code={ps.status_code}")
        try:
            print("      resp:", ps.json().get("msg"))
        except Exception:
            print("      raw:", ps.text[:200])
        break


if __name__ == "__main__":
    main()
"""Verify BUG-005 backend rejection: empty in_order form rejected."""
import io
import re
import sys
import json
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar

BASE = "http://127.0.0.1:8080"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def get_csrf():
    r = opener.open(f"{BASE}/login")
    body = r.read().decode("utf-8", errors="ignore")
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', body)
    if not m:
        m = re.search(r'value="([^"]+)"[^>]*name="csrf_token"', body)
    return m.group(1) if m else None

def login(csrf):
    data = urllib.parse.urlencode({
        "username": "admin",
        "password": "AAAA1234",
        "usage_consent": "1",
        "login_mode": "admin",
        "csrf_token": csrf or "",
    }).encode()
    r = opener.open(f"{BASE}/login", data=data)
    return r.status, r.url

def get_in_order_csrf():
    r = opener.open(f"{BASE}/in_order/add")
    body = r.read().decode("utf-8", errors="ignore")
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', body)
    if not m:
        m = re.search(r'value="([^"]+)"[^>]*name="csrf_token"', body)
    return m.group(1) if m else None

csrf = get_csrf()
print("Login CSRF:", csrf[:15] + "..." if csrf else "NONE")
status, url = login(csrf)
print(f"Login: {status} -> {url}")

csrf = get_in_order_csrf()
print("in_order CSRF:", csrf[:15] + "..." if csrf else "NONE")

# Test 1: Empty form (no warehouse, no items_json)
empty_data = urllib.parse.urlencode({
    "csrf_token": csrf or "",
    "order_no": "IN26079999",  # arbitrary
}).encode()
req = urllib.request.Request(f"{BASE}/in_order/add", data=empty_data, method="POST")
try:
    r = opener.open(req)
    print(f"Empty form: {r.status} {r.read()[:200]}")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="ignore")
    print(f"Empty form HTTPError: {e.code}")
    # Look for JSON
    m = re.search(r'\{[^}]*"msg"[^}]*\}', body)
    print(f"  msg: {m.group(0) if m else body[:200]}")

# Test 2: warehouse but no items
data2 = urllib.parse.urlencode({
    "csrf_token": csrf or "",
    "order_no": "IN26079998",
    "warehouse": "MAIN",
}).encode()
req = urllib.request.Request(f"{BASE}/in_order/add", data=data2, method="POST")
try:
    r = opener.open(req)
    print(f"No items: {r.status} {r.read()[:200]}")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="ignore")
    m = re.search(r'\{[^}]*"msg"[^}]*\}', body)
    print(f"No items HTTPError: {e.code}")
    print(f"  msg: {m.group(0) if m else body[:200]}")

"""Verify BUG-004 backend rejection: admin self password reset blocked."""
import io
import json
import sys
import urllib.request
import urllib.parse
import http.cookiejar

BASE = "http://127.0.0.1:8080"
USER = "admin"
PWD = "AAAA1234"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# 1. Get login page + CSRF
r = opener.open(f"{BASE}/login")
csrf = None
for line in r.read().decode("utf-8", errors="ignore").splitlines():
    if "csrf_token" in line and "name=" in line:
        import re
        m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', line)
        if not m:
            m = re.search(r'value="([^"]+)"[^>]*name="csrf_token"', line)
        if m:
            csrf = m.group(1)
            break
if not csrf:
    # Try meta tag
    body = r.read().decode("utf-8", errors="ignore") if False else ""
    import re
    m = re.search(r'<meta name="csrf-token" content="([^"]+)"', body)
    if m: csrf = m.group(1)
print("CSRF token:", csrf[:20] + "..." if csrf else "NONE")

# 2. POST login
data = urllib.parse.urlencode({
    "username": USER,
    "password": PWD,
    "usage_consent": "1",
    "login_mode": "admin",
    "csrf_token": csrf or "",
}).encode()
r = opener.open(f"{BASE}/login", data=data)
print("Login:", r.status, r.url)

# 3. Get user list to find admin id
r = opener.open(f"{BASE}/user")
body = r.read().decode("utf-8", errors="ignore")
import re
# Find current user id and admin id
ids = re.findall(r'/user/\d+', body)
print("User URL ids:", set(ids))

# 4. Get current user id from /admin/console or via /me
r = opener.open(f"{BASE}/admin/console")
body = r.read().decode("utf-8", errors="ignore")
admin_id = None
m = re.search(r'admin\s*\(ID[:\s]*(\d+)\)', body)
if m:
    admin_id = int(m.group(1))
else:
    # fallback: any ID
    ids = re.findall(r'\b(\d{1,3})\b', body)
    if ids:
        admin_id = int(ids[0])
print("Admin user id (guess):", admin_id)

# 5. Re-fetch login page for fresh CSRF
r = opener.open(f"{BASE}/login")
body = r.read().decode("utf-8", errors="ignore")
m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', body)
if not m:
    m = re.search(r'value="([^"]+)"[^>]*name="csrf_token"', body)
csrf = m.group(1) if m else csrf
print("Fresh CSRF:", csrf[:20] + "..." if csrf else "NONE")

# 6. Try reset admin self (id=1 assumed)
reset_data = urllib.parse.urlencode({
    "user_id": str(admin_id or 1),
    "new_password": "Test123456",
    "csrf_token": csrf or "",
}).encode()
req = urllib.request.Request(f"{BASE}/user/reset_password", data=reset_data, method="POST")
try:
    r = opener.open(req)
    body = r.read().decode("utf-8", errors="ignore")
    print("Self reset status:", r.status)
    print("Response:", body[:300])
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="ignore")
    print("Self reset HTTPError:", e.code)
    print("Response:", body[:300])

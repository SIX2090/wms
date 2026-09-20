import re, time, requests

BASE = 'http://127.0.0.1:8080'
s = requests.Session()

def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)

# 1. GET login to obtain session + csrf token
r = s.get(f'{BASE}/login', timeout=30)
m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
if not m:
    m = re.search(r'csrf_token["\']?\s*[:=]\s*["\']([^"\']+)', r.text)
csrf = m.group(1) if m else None
log(f'GET /login status={r.status_code} csrf={"yes" if csrf else "NO"}')

# 2. POST login
t0 = time.time()
r = s.post(f'{BASE}/login', data={
    'username': 'admin', 'password': 'admin',
    'csrf_token': csrf or '', 'usage_consent': '1', 'login_mode': 'admin',
}, timeout=30, allow_redirects=True)
log(f'POST /login status={r.status_code} took={time.time()-t0:.3f}s')

# 3. New csrf from session (use in_order 3, item 501, available)
r2 = s.get(f'{BASE}/in_order/3/push?target=requisition', timeout=30)
m2 = re.search(r'<meta name="csrf-token" content="([^"]+)"', r2.text)
csrf2 = m2.group(1) if m2 else None
log(f'GET /in_order/3/push status={r2.status_code} csrf2={"yes" if csrf2 else "NO"}')

payload = {
    'target_type': 'requisition',
    'request_id': 'bench-' + str(int(time.time())),
    'department_id': '',
    'purpose': '',
    'picker': 'bench',
    'customer_id': '',
    'reason': '',
    'items': [{'source_item_id': 501, 'quantity': 1}],
}
t0 = time.time()
r = s.post(f'{BASE}/in_order/3/push', json=payload,
           headers={'X-CSRFToken': csrf2 or '', 'Content-Type': 'application/json'},
           timeout=60)
dt = time.time() - t0
log(f'POST /in_order/3/push status={r.status_code} took={dt:.3f}s body={r.text[:200]}')
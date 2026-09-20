import re, time, requests, sqlite3, threading

BASE = 'http://127.0.0.1:8080'
DB = '/workspace/app/instance/inventory.db'

# background: hold a sqlite write lock (BEGIN IMMEDIATE) for N sec
def hold_write_lock(seconds):
    conn = sqlite3.connect(DB, timeout=60)
    conn.execute('PRAGMA busy_timeout=60000')
    cur = conn.cursor()
    cur.execute('BEGIN IMMEDIATE')
    print('  [bg] write lock ACQUIRED', flush=True)
    time.sleep(seconds)
    cur.execute('CREATE TEMP TABLE _t_lock_holder(x)')  # keep txn alive
    conn.rollback()
    conn.close()
    print('  [bg] write lock RELEASED', flush=True)

# login once
s = requests.Session()
r = s.get(f'{BASE}/login', timeout=30)
m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
csrf = m.group(1) if m else None
s.post(f'{BASE}/login', data={'username':'admin','password':'admin','csrf_token':csrf or '','usage_consent':'1','login_mode':'admin'}, timeout=30)
r2 = s.get(f'{BASE}/in_order/4/push?target=requisition', timeout=30)
m2 = re.search(r'<meta name="csrf-token" content="([^"]+)"', r2.text)
csrf2 = m2.group(1) if m2 else None
# in_order 4 item 502 qty 3 pushed 1 => available 2
payload = {'target_type':'requisition','request_id':'bench-'+str(int(time.time())),'department_id':'','purpose':'','picker':'b','customer_id':'','reason':'','items':[{'source_item_id':502,'quantity':1}]}

# start holding lock for 8s
t = threading.Thread(target=hold_write_lock, args=(8,), daemon=True)
t.start()
time.sleep(1.5)  # ensure lock acquired

t0 = time.time()
r = s.post(f'{BASE}/in_order/4/push', json=payload, headers={'X-CSRFToken':csrf2 or '','Content-Type':'application/json'}, timeout=60)
dt = time.time() - t0
print(f'PUSH took={dt:.3f}s status={r.status_code} body={r.text[:120]}', flush=True)
t.join()
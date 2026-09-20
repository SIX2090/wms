import re, time, requests

BASE = 'http://127.0.0.1:8080'
s = requests.Session()
r = s.get(f'{BASE}/login', timeout=30)
csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text).group(1)
s.post(f'{BASE}/login', data={'username':'admin','password':'admin','csrf_token':csrf,'usage_consent':'1','login_mode':'admin'}, timeout=30)

def time_push(in_id, item_ids, label):
    r2 = s.get(f'{BASE}/in_order/{in_id}/push?target=requisition', timeout=30)
    csrf2 = re.search(r'<meta name="csrf-token" content="([^"]+)"', r2.text).group(1)
    items = [{'source_item_id': iid, 'quantity': 1} for iid in item_ids]
    payload = {'target_type':'requisition','request_id':'bench-'+str(int(time.time()))+label,'department_id':'','purpose':'','picker':'b','customer_id':'','reason':'','items':items}
    t0=time.time()
    r=s.post(f'{BASE}/in_order/{in_id}/push', json=payload, headers={'X-CSRFToken':csrf2,'Content-Type':'application/json'}, timeout=120)
    print(f'{label}: {time.time()-t0:.3f}s status={r.status_code} {r.text[:80]}', flush=True)

# in_order 1 has 25 items (1..25); in_order 2 has 500 items (26..525)
time_push(1, list(range(1,26)), 'in1(25 items)')
time_push(2, list(range(26,526)), 'in2(500 items)')
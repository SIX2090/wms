"""Test client render of key document pages (with login as admin)."""
import os
import sys
import runpy
from flask import Flask, url_for

os.environ.setdefault('WMS_BOOTSTRAP_PASSWORD', 'admin')
os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault('WMS_TEST_DB', 'sqlite:///:memory:')

sys.path.insert(0, '/workspace/app')

# Load app.py
app_globals = runpy.run_path('/workspace/app/app.py')
flask_app = None
for key, val in app_globals.items():
    if isinstance(val, Flask):
        flask_app = val
        break
if not flask_app:
    print("ERROR: No Flask app found")
    sys.exit(1)

flask_app.config['TESTING'] = True
flask_app.config['WTF_CSRF_ENABLED'] = False
client = flask_app.test_client()

# Step 1: Try to find a login route and login as admin
login_url = None
for rule in flask_app.url_map.iter_rules():
    if rule.endpoint and 'login' in rule.endpoint.lower():
        login_url = rule.rule
        break
print(f"Login URL: {login_url}")

# Try logging in via the login route
print("=== Login flow ===")
resp = client.get('/login', follow_redirects=False)
print(f"GET /login -> {resp.status_code}")
# Try POST
resp = client.post('/login', data={
    'username': 'admin',
    'password': 'admin',
}, follow_redirects=False)
print(f"POST /login -> {resp.status_code}")

# Step 2: Try to render key list pages
key_pages = [
    ('in_order', '/in_order'),
    ('out_order', '/out_order'),
    ('after_sale_out', '/after_sale_out'),
    ('transfer', '/transfer'),
    ('check', '/check'),
    ('adjustment', '/adjustment'),
    ('subcontract', '/subcontract'),
    ('subcontract_issue', '/subcontract_issue'),
    ('subcontract_receive', '/subcontract_receive'),
    ('report', '/report'),
]
print("\n=== Key page render test ===")
for name, url in key_pages:
    resp = client.get(url, follow_redirects=False)
    print(f"  {name:25s} GET {url:35s} -> {resp.status_code} (len={len(resp.data)})")

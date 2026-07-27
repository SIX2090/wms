"""Dynamic test for key document pages."""
import os
import sys
import runpy
from io import StringIO

# Set test env
os.environ.setdefault('WMS_BOOTSTRAP_PASSWORD', 'admin')
os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault('WMS_TEST_DB', 'sqlite:///:memory:')

# Load app.py with proper module path
sys.path.insert(0, '/workspace/app')

# Load app.py
app_globals = runpy.run_path('/workspace/app/app.py')

# Get app from globals
from flask import Flask
flask_app = None
for key, val in app_globals.items():
    if isinstance(val, Flask):
        flask_app = val
        break

if flask_app is None:
    print("ERROR: No Flask app found")
    sys.exit(1)

# Print registered routes summary
print("=== Registered routes (count by endpoint) ===")
endpoints = {}
for rule in flask_app.url_map.iter_rules():
    if rule.endpoint == 'static':
        continue
    name = rule.endpoint
    if name in endpoints:
        endpoints[name] += 1
    else:
        endpoints[name] = 1
print(f"Total unique endpoints: {len(endpoints)}")
print(f"Total routes (incl. multiple): {sum(endpoints.values())}")

# Print key doc-related routes
print("\n=== Key document routes ===")
key_prefixes = ['/in_order', '/out_order', '/after_sale_out', '/transfer', '/check', '/adjustment', '/subcontract', '/report', '/inventory']
for rule in sorted(flask_app.url_map.iter_rules(), key=lambda r: r.rule):
    if any(rule.rule.startswith(p) for p in key_prefixes):
        methods = ','.join(sorted([m for m in rule.methods if m not in ('HEAD', 'OPTIONS')]))
        print(f"  {methods:20s} {rule.rule}")

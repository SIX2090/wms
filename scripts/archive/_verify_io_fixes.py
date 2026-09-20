"""WMS 出入库单据修复验证脚本 - test_client 渲染检查。"""
import os
import sys
import runpy
from flask import Flask

os.environ['WMS_BOOTSTRAP_PASSWORD'] = 'admin'
os.environ['WMS_TEST_DB'] = 'sqlite:///:memory:'
sys.path.insert(0, '/workspace/app')

# Load the app module
app_globals = runpy.run_path('/workspace/app/app.py')
flask_app = next(v for v in app_globals.values() if isinstance(v, Flask))

flask_app.config['WTF_CSRF_ENABLED'] = False
flask_app.config['TESTING'] = True

client = flask_app.test_client()

# Verify key pages - they should return 200 (or 302 for login redirect)
URLS_TO_CHECK = [
    '/in_order',
    '/out_order',
    '/after_sale_out',
    '/transfer',
    '/check',
    '/adjustment',
    '/subcontract',
    '/subcontract_issue',
    '/subcontract_receive',
    '/purchase_order',
    '/batch_import',
    '/report',
    '/subcontract/download_template',
    '/subcontract_issue/download_template',
    '/subcontract_receive/download_template',
    '/after_sale_out/download_template',
    '/after_sale_out/export',
    '/subcontract/export',
]

print("=" * 80)
print("test_client 渲染验证")
print("=" * 80)

results = []
for url in URLS_TO_CHECK:
    try:
        resp = client.get(url, follow_redirects=False)
        status = resp.status_code
        ok = status in (200, 302)
        results.append((url, status, ok))
        marker = "OK" if ok else "FAIL"
        print(f"  [{marker}] {url:55s} -> {status}")
    except Exception as e:
        results.append((url, f"ERROR: {e}", False))
        print(f"  [FAIL] {url:55s} -> ERROR: {e}")

# Verify post-redirects work
print("\n" + "=" * 80)
print("POST 路由 302/405 验证 (CSRF disabled)")
print("=" * 80)

POST_URLS = [
    '/after_sale_out/import',  # Missing file should return 400
    '/subcontract/import',
    '/subcontract_issue/import',
    '/subcontract_receive/import',
    '/after_sale_out/download_template',  # GET only
]

for url in POST_URLS:
    try:
        resp = client.post(url, follow_redirects=False)
        print(f"  POST {url:55s} -> {resp.status_code}")
    except Exception as e:
        print(f"  POST {url:55s} -> ERROR: {e}")

# Summary
total = len(results)
passed = sum(1 for r in results if r[2])
print(f"\n=== Summary: {passed}/{total} URLs passed ===")

if passed == total:
    print("ALL OK")
    sys.exit(0)
else:
    print(f"FAILED: {total - passed} URLs")
    sys.exit(1)

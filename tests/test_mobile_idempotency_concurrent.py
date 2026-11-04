"""Concurrent HTTP handlers against a real isolated SQLite file."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_mobile_concurrent_receipts_and_stock(tmp_path):
    database = tmp_path / 'concurrent.sqlite'
    env = dict(os.environ, DATABASE_URL='sqlite:///' + database.as_posix(),
               FLASK_ENV='development', WMS_NO_DB_TOUCH='1', WMS_SKIP_AUTO_UPDATE='1',
               WMS_ALLOW_INSECURE_COOKIE='1', LOG_FILE=str(tmp_path / 'app.log'),
               PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    script = r'''
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
import sys
sys.path.insert(0, sys.argv[1])
import app as w
w.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
with w.app.app_context():
    assert w.db.engine.url.database == sys.argv[2]
    w.initialize_database(); w.db.create_all()
    user=w.User(username='concurrent',role='admin',password_hash='unused',must_change_password=False)
    w.db.session.add_all([user,w.Warehouse(code='A',name='A',status='active',is_default=True),w.Material(code='M',name='M',stock=0,price=0)])
    w.db.session.commit(); uid=user.id
def race(url, body):
    barrier=Barrier(4)
    def submit(i):
        c=w.app.test_client()
        with c.session_transaction() as s:s['_user_id']=str(uid);s['_fresh']=True
        barrier.wait()
        r=c.post(url,json=body)
        return r.status_code,r.json
    with ThreadPoolExecutor(max_workers=4) as pool:responses=list(pool.map(submit,range(4)))
    assert all(r[0]==200 for r in responses),responses
    assert all(r==responses[0] for r in responses),responses
    return responses[0][1]
with patch('routes.print_queue.enqueue_auto_print_job',return_value=None):
    race('/mobile/api/scan_submit',dict(mode='in',code='M',quantity=5,warehouse='A',request_id='in'))
    race('/mobile/api/scan_submit',dict(mode='out',code='M',quantity=2,warehouse='A',request_id='out'))
    draft=race('/mobile/api/scan_batch_draft',dict(mode='in',warehouse='A',request_id='batch',lines=[dict(material_code='M',quantity=3)]))
    race('/mobile/api/scan_draft_confirm/'+str(draft['data']['order_id']),dict(order_type='in',request_id='confirm'))
with w.app.app_context():
    assert w.InOrder.query.count()==2
    assert w.OutOrder.query.count()==1
    assert w.Material.query.one().stock==6
    assert w.StockTransaction.query.count()==3
    assert w.MobileApiRequest.query.count()==4
print('CONCURRENT_MOBILE_OK')
'''
    result = subprocess.run([sys.executable, '-c', script, str(ROOT / 'app'), database.as_posix()], env=env, capture_output=True, text=True, encoding='utf-8', timeout=80)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'CONCURRENT_MOBILE_OK' in result.stdout

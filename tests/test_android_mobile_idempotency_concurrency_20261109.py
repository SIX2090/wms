"""Real native Flask handlers and concurrent SQLite connections in an owned LPAC file."""
if __name__ == '__main__':
    raise SystemExit('安全阻断：请通过已核验隔离启动器的显式 pytest 清单运行本回归')

import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]

SCRIPT=r'''
import os,runpy,sys,sysconfig
from pathlib import Path
app_dir=Path(sys.argv[1]);database=Path(sys.argv[2])
guard=runpy.run_path(str(app_dir.parent/'scripts/verify_db_guard.py'))
guard['require_owned_test_profile']()
assert guard['validate_owned_test_file'](database)==database
assert database.stat().st_size==0
url='sqlite:///'+database.as_posix()
assert os.environ['DATABASE_URL']==os.environ['WMS_DATABASE_URI']==url
sys.path.insert(0,str(app_dir));sys.path.append(sysconfig.get_paths()['purelib'])
import app as w
from datetime import datetime,timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
w.app.config.update(TESTING=True,WTF_CSRF_ENABLED=False,DEBUG=False)
with w.app.app_context():
    assert os.path.normcase(os.path.abspath(w.db.engine.url.database))==os.path.normcase(str(database))
    w.db.create_all()
    user=w.User(username='owned-native-race',role='admin',status='normal',password_hash='unused-synthetic',must_change_password=False)
    a=w.Warehouse(code='A',name='合成并发甲仓',status='active',is_default=True)
    b=w.Warehouse(code='B',name='合成并发乙仓',status='active')
    mat=w.Material(code='RACE-M',name='合成并发物料',stock=10,price=1)
    w.db.session.add_all([user,a,b,mat]);w.db.session.flush();uid,aid,bid,mid=user.id,a.id,b.id,mat.id
    w.db.session.add(w.ApiToken(token=w.hash_access_token('owned-native-race-token'),user_id=uid,
        expires_at=datetime.now()+timedelta(days=3),last_used_at=datetime.now(),revoked=False))
    for wh in (a,b):
        w.db.session.add(w.LocationInventory(material_id=mid,warehouse_id=wh.id,location=wh.name,quantity=5))
        w.db.session.add(w.StockTransaction(material_id=mid,warehouse_id=wh.id,transaction_type='in',quantity=5))
    w.set_system_setting('auto_print_on_submit','0')
    w.set_system_setting('location_management_enabled','0')
    w.db.session.commit()

def race(path,payloads,keys):
    barrier=Barrier(4)
    def send(i):
        client=w.app.test_client()
        barrier.wait(timeout=15)
        result=client.post(path,json=payloads[i],headers={'Authorization':'Bearer owned-native-race-token','X-Idempotency-Key':keys[i]})
        return result.status_code,result.json
    with ThreadPoolExecutor(max_workers=4) as pool:
        replies=list(pool.map(send,range(4)))
    assert any(status==200 for status,_ in replies),replies
    assert all(status in (200,409,503) for status,_ in replies),replies
    # The fenced lease can answer 503 while another owner is active. Once all
    # owners returned, retry only those responses with their original content/key.
    for i,(status,_) in enumerate(replies):
        if status==503:
            result=w.app.test_client().post(path,json=payloads[i],headers={
                'Authorization':'Bearer owned-native-race-token','X-Idempotency-Key':keys[i]})
            replies[i]=(result.status_code,result.json)
    return replies

def same(path,body,key):
    replies=race(path,[body]*4,[key]*4)
    assert all(status==200 and data.get('success') is True for status,data in replies),replies
    assert all(reply==replies[0] for reply in replies),replies

body={'warehouse_code':'A','business_type':'其他入库','lines':[{'material_code':'RACE-M','quantity':2,'price':1}]}
same('/api/inbound',body,'same-in')
out={'warehouse_code':'A','lines':[{'material_code':'RACE-M','quantity':1,'price':1}]}
same('/api/outbound',out,'same-out')
same('/api/mobile/inbound_draft',body,'same-draft')
distinct=race('/api/inbound',[out]*4,['different-'+str(i) for i in range(4)])
assert all(status==200 for status,_ in distinct),distinct
assert len({data['data']['id'] for _,data in distinct})==4,distinct
one={'warehouse_code':'A','business_type':'其他入库','lines':[{'material_code':'RACE-M','quantity':1,'price':1}]}
two={'warehouse_code':'A','business_type':'其他入库','lines':[{'material_code':'RACE-M','quantity':2,'price':1}]}
mixed=race('/api/inbound',[one,two,one,two],['same-mixed']*4)
assert sorted(status for status,_ in mixed)==[200,200,409,409],mixed
winners=[data for status,data in mixed if status==200]
assert winners[0]==winners[1]
with w.app.app_context():
    winner=w.db.session.get(w.InOrder,winners[0]['data']['id'])
    added=winner.items[0].quantity
    assert w.InOrder.query.count()==7
    assert w.OutOrder.query.count()==1
    assert w.MobileApiRequest.query.count()==8
    assert w.StockTransaction.query.count()==9
    assert w.PrintJob.query.count()==0
    assert w.db.session.get(w.Material,mid).stock==15+added
    assert w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse,aid))[mid]==10+added
    assert w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse,bid))[mid]==5
    w.db.session.remove();w.db.engine.dispose()
print('NATIVE_CONCURRENT_OK')
'''


def test_native_concurrent_receipts_and_inventory_use_one_owned_file():
    guard=runpy.run_path(str(ROOT/'scripts/verify_db_guard.py'))
    profile=guard['require_owned_test_profile']()
    directory=profile/'Temp';directory.mkdir(exist_ok=True)
    descriptor,name=tempfile.mkstemp(prefix='native-concurrent-',suffix='.sqlite',dir=directory)
    os.close(descriptor)
    database=guard['validate_owned_test_file'](Path(name))
    assert database.stat().st_size==0
    url='sqlite:///'+database.as_posix()
    # TestingConfig forces an in-memory engine. This owned-file child verifies its exact URL
    # before creating any table, then explicitly enables Flask's test client behavior.
    env=dict(os.environ,DATABASE_URL=url,WMS_DATABASE_URI=url,FLASK_ENV='development',
        WMS_NO_DB_TOUCH='1',WMS_SKIP_AUTO_UPDATE='1',WMS_ALLOW_INSECURE_COOKIE='1',
        LOG_FILE=str(directory/'native-concurrent.log'),PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
    result=subprocess.run([sys.executable,'-I','-S','-B','-X','utf8','-c',SCRIPT,
        str(ROOT/'app'),str(database)],env=env,capture_output=True,text=True,encoding='utf-8',timeout=90)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'NATIVE_CONCURRENT_OK' in result.stdout

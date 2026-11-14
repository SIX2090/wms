"""Actual command HTTP: existing Linux proof, fresh owned memory and real routes."""
import ast
import math
import types
import unittest
from scripts.verify_db_guard import require_isolated_test_runtime
require_isolated_test_runtime()
import pytest  # noqa: E402
import app as w  # noqa: E402
from tests.document_revision_client import document_post  # noqa: E402
from tests.test_opening_reference_ownership_runtime_20261113 import source_scene  # noqa: E402,F401
from tests.test_purchase_reservation_runtime_20261114 import _RealModelNamespace, _txn  # noqa: E402
from tests.test_document_command_family_source_20261114 import CASES,PENDING_HELPERS,COMMANDS  # noqa: E402

SCENARIOS=[(mode,same) for mode in COMMANDS for same in (False,True)]
assert len(SCENARIOS)==18 and len(set(SCENARIOS))==18

def _http_command_call(self,mode,source,key):
    endpoint,pattern,model=COMMANDS[mode]
    path=pattern.replace('<int:id>',str(source.id)).replace('<int:bom_id>',str(source.id))
    payload={'warehouse':self.a.name,'warehouse_id':self.a.id} if mode=='bom' else {}
    self.http_paths.append(path)
    response=document_post(self.client,path,json=payload,headers={'X-Idempotency-Key':key,'X-Requested-With':'XMLHttpRequest'})
    assert response.is_json,(path,response.status_code,response.get_data(as_text=True)[:600])
    w.db.session.expire_all()
    return response.status_code,response.get_json()

def _specimen(source_scene):
    client,a,b=source_scene
    w.set_system_setting('location_management_enabled','0')
    w.set_system_setting('purchase_over_receive_control_mode','forbid')
    w.db.session.commit()
    specimen=unittest.TestCase()
    specimen.client=client;specimen.a=a;specimen.b=b
    specimen.user=w.User.query.filter_by(username='synthetic-sources').one()
    specimen.material=w.Material(code='SYN-COMMAND-M',name='合成幂等复制物料',stock=0,price=0)
    w.db.session.add(specimen.material);w.db.session.commit()
    specimen.http_paths=[]
    specimen.txn=types.MethodType(_txn,specimen)
    specimen.command_call=types.MethodType(_http_command_call,specimen)
    namespace={'ns':_RealModelNamespace(),'db':w.db,'math':math,'COMMANDS':COMMANDS,'observed':[]}
    helpers=[n for n in ast.parse(PENDING_HELPERS).body if isinstance(n,ast.FunctionDef) and n.name=='pending']
    helpers += [n for n in ast.parse(CASES).body if isinstance(n,ast.FunctionDef) and n.name in ('command_seed','command_replay','alias_product')]
    assert {n.name for n in helpers}=={'pending','command_seed','command_replay','alias_product'}
    exec(compile(ast.Module(body=helpers,type_ignores=[]),'<actual-command-http-fixtures>','exec'),namespace)
    for node in helpers:setattr(specimen,node.name,types.MethodType(namespace[node.name],specimen))
    assert specimen.command_call.__func__ is _http_command_call
    return specimen

@pytest.mark.parametrize('mode,same',SCENARIOS)
def test_real_command_response_loss_replays_and_new_key_creates(source_scene,mode,same):
    specimen=_specimen(source_scene)
    specimen.command_replay(mode,same)
    assert len(specimen.http_paths)==2

@pytest.mark.parametrize('same',(False,True))
def test_real_product_alias_preserves_existing_source_push_protocol(source_scene,same):
    specimen=_specimen(source_scene)
    specimen.alias_product(same)
    assert len(specimen.http_paths)==2

@pytest.mark.parametrize('failure',('recalculate','receipt'))
def test_real_sales_copy_failure_leaves_no_document_or_receipt(source_scene,monkeypatch,failure):
    specimen=_specimen(source_scene)
    source,target=specimen.command_seed('sales');before=target.query.count()
    original=[(r.id,r.quantity,r.price,r.amount) for r in source.items]
    def reject(*args,**kwargs):raise RuntimeError('owned synthetic '+failure+' failure')
    with monkeypatch.context() as local:
        if failure=='recalculate':local.setattr(w,'recalculate_sales_order',reject)
        else:local.setattr('routes.sales.stage_document_response',reject)
        response=specimen.command_call('sales',source,'same-failed-sales-intent')
    assert response[0]==500,response
    assert target.query.count()==before
    assert [(r.id,r.quantity,r.price,r.amount) for r in source.items]==original
    assert w.MobileApiRequest.query.count()==0
    response=specimen.command_call('sales',source,'same-failed-sales-intent')
    assert response[0]==200,response
    assert target.query.count()==before+1
    assert w.MobileApiRequest.query.count()==1
    assert specimen.material.stock==20
    assert len(specimen.http_paths)==2

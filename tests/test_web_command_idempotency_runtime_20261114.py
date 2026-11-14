"""Actual copy/selection/PO-push requests under the existing verified Linux broker."""
import ast
import copy
import json
import math
from pathlib import Path
import types
import unittest

from scripts.verify_db_guard import require_isolated_test_runtime

require_isolated_test_runtime()

import pytest  # noqa: E402
from sqlalchemy import event, text  # noqa: E402
import app as w  # noqa: E402
from services import document_edit_guard as actual_guard  # noqa: E402
from tests.document_revision_client import document_post  # noqa: E402
from tests.test_opening_reference_ownership_runtime_20261113 import source_scene  # noqa: E402,F401
from tests.test_purchase_reservation_runtime_20261114 import _RealModelNamespace, _txn  # noqa: E402
from tests.test_purchase_reservation_source_20261114 import HELPERS  # noqa: E402


class ActualNamespace(_RealModelNamespace):
    def __getitem__(self,key):
        if key in ('EDIT_ENDPOINTS','NEW_DOCUMENT_INTENTS'):
            return getattr(actual_guard,key)
        return super().__getitem__(key)


tree=ast.parse((Path(__file__).with_name('test_web_command_idempotency_source_20261114.py')).read_text(encoding='utf-8'))
cases=next(ast.literal_eval(node.value) for node in ast.walk(tree)
           if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant)
           and isinstance(node.value.value,str) and any(isinstance(t,ast.Name) and t.id=='cases' for t in node.targets))
functions={node.name:node for node in ast.parse(cases).body if isinstance(node,ast.FunctionDef) and node.name!='call_intent'}
SCENARIOS=tuple(sorted(name for name in functions if name.startswith('test_')))
assert len(SCENARIOS)==26 and len(set(SCENARIOS))==26


def _actual_http(self,mode,order,source,key,quantity=1.01,payload_extra=None):
    # This mutates only this test's synthetic actor; no real account credentials.
    self.user.role='admin'
    w.db.session.commit()
    with self.client.session_transaction() as session:
        session['_user_id'],session['_fresh']=str(self.user.id),True
    if mode=='copy':
        path=f'/in_order/{order.id}/copy';payload={}
    elif mode=='selection':
        path='/purchase_order/create_in_order_from_selection'
        payload={'warehouse':self.a.name,'items':[{'purchase_order_item_id':source.id,'quantity':quantity}]}
    elif mode=='push':
        path=f'/purchase_order/{source.purchase_order_id}/create_in_order'
        payload={'warehouse':self.a.name,'items':[{'item_id':source.id,'quantity':quantity}]}
    elif mode=='save':
        path='/in_order/add'
        payload={'business_type':'采购入库','warehouse':self.a.name,'location':'SAME',
                 'items':[{'code':self.material.code,'quantity':quantity,'price':0,'source_purchase_order_item_id':source.id}]}
    else:
        raise AssertionError('Unknown finite HTTP consumer: '+mode)
    if payload_extra is not None:
        payload.update(payload_extra)
    self.http_paths.append(path)
    response=document_post(self.client,path,json=payload,headers={'X-Idempotency-Key':key,'X-Requested-With':'XMLHttpRequest'})
    assert response.is_json,(path,response.status_code,response.get_data(as_text=True)[:500])
    w.db.session.expire_all()
    return response.status_code,response.get_json()


@pytest.mark.parametrize('location_on',[False,True],ids=['bin-off','bin-on'])
@pytest.mark.parametrize('case_name',SCENARIOS)
def test_real_web_command_idempotency(source_scene,location_on,case_name):
    client,a,b=source_scene
    w.set_system_setting('purchase_receipt_strict_order','1')
    w.set_system_setting('purchase_order_to_in_order_enabled','1')
    w.db.session.commit()
    specimen=unittest.TestCase()
    specimen.client=client;specimen.a=a;specimen.b=b
    specimen.user=w.User.query.filter_by(username='synthetic-sources').one()
    specimen.material=w.Material(code='SYN-COMMAND-REPLAY-M',name='合成命令物料',stock=0)
    w.db.session.add(specimen.material);w.db.session.commit()
    specimen.http_paths=[]
    specimen.txn=types.MethodType(_txn,specimen)
    specimen.call_intent=types.MethodType(_actual_http,specimen)
    namespace={'ns':ActualNamespace(),'db':w.db,'math':math,'event':event,'observed':[]}
    # The only reused code is data fixtures and assertions. Source call_intent
    # (which dispatches extracted functions) is deliberately never compiled.
    fixture=[n for n in ast.parse(HELPERS).body if isinstance(n,ast.FunctionDef) and n.name in ('pending','pending_state')]
    nodes=copy.deepcopy([*fixture,*functions.values()])
    for node in nodes:
        for call in ast.walk(node):
            if (isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute)
                    and isinstance(call.func.value,ast.Name) and call.func.value.id=='self'
                    and call.func.attr=='pending' and len(call.args)==3
                    and isinstance(call.args[2],ast.Constant) and call.args[2].value is False):
                call.args[2]=ast.Constant(value=location_on)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),
                 '<actual-web-command-http:'+case_name+'>','exec'),namespace)
    for node in nodes:
        setattr(specimen,node.name,types.MethodType(namespace[node.name],specimen))
    assert specimen.call_intent.__func__ is _actual_http
    getattr(specimen,case_name)()
    assert len(specimen.http_paths)>=2,'Every scenario must issue actual business POSTs'
    assert w.MobileApiRequest.query.filter_by(status_code=0).count()==0,'A failed command left an incomplete committed receipt'
    assert specimen.material.stock==20
    assert w.StockTransaction.query.count()==2,'Draft commands must not write inventory movements'
    assert all(not row[2] for row in w.db.session.execute(text('PRAGMA database_list')))

"""The shared 110 behavioral cases against real WMS HTTP in verified memory isolation.

Only fixture/assertion functions are shared with the source suite. No extracted
product function, synthetic Flask app, fake API response or app function patch is
used here. Every consumer dispatch below makes an actual Flask client request.
"""
from datetime import datetime
import ast
import math
import types
import unittest

from scripts.verify_db_guard import require_isolated_test_runtime

require_isolated_test_runtime()

import pytest  # noqa: E402
from sqlalchemy import event  # noqa: E402
import app as w  # noqa: E402
from tests.document_revision_client import document_post  # noqa: E402
from tests.test_opening_reference_ownership_runtime_20261113 import source_scene  # noqa: E402,F401
from tests.test_purchase_reservation_source_20261114 import DELETE, UPDATE, COUNTER, EXTRA, HELPERS  # noqa: E402


class _RealModelNamespace:
    """Expose real models; test config changes use the actual setting writer."""
    def __getitem__(self,key):
        return getattr(w,key)

    def __setitem__(self,key,value):
        if key=='location_management_enabled':
            setting='location_management_enabled'
            stored='1' if value() else '0'
        elif key=='purchase_over_receive_control_mode':
            setting='purchase_over_receive_control_mode'
            stored=value()
        else:
            raise AssertionError('Product functions cannot be patched: '+key)
        w.set_system_setting(setting,stored)
        w.db.session.commit()


def _scenarios():
    cases=[]
    for location_on in (False,True):
        suffix='_on' if location_on else '_off'
        for mode in ('single','alias','whole','batch'):
            for kind in ('line','counter','both','normal'):
                name=mode+'_'+kind+suffix
                cases.append((name,DELETE.format(name=name,mode=mode,kind=kind,location_on=location_on)))
        for strict_mode in ('forbid','allow'):
            name=strict_mode+suffix
            cases.append((name,UPDATE.format(name=name,strict_mode=strict_mode,location_on=location_on)))
        for mode in ('addrow','copy','core','selection','json_new','json_replace'):
            name=mode+suffix
            cases.append((name,COUNTER.format(name=name,mode=mode,location_on=location_on)))
        for mode in ('json_history_line','json_bad_source','json_bad_customer','json_bad_batch','json_bad_expiry',
            'json_shared_forbid','json_shared_replace_forbid','json_shared_allow','copy_shared_forbid','copy_shared_allow',
            'update_history_line','update_history_counter','update_metadata_history','update_header_total',
            'batch_mixed_forward','batch_mixed_reverse','batch_later_dml','core_unselected_history',
            'no_source_single','no_source_whole','no_source_batch','ulp_addrow','ulp_update','ulp_copy','reverted_whole','reverted_batch',
            'json_two_sources_success','json_two_sources_later_failure','copy_two_sources_success','metadata_zero_history','update_other_line_amount'):
            name=mode+suffix
            cases.append((name,EXTRA.format(name=name,mode=mode,location_on=location_on)))
    assert len(cases)==110 and len({name for name,_ in cases})==110
    return cases


SCENARIOS=_scenarios()


def _txn(self,warehouse_id,quantity,reference_type=None,reference_id=None):
    row=w.StockTransaction(material_id=self.material.id,warehouse_id=warehouse_id,quantity=quantity,
        transaction_type='in' if quantity>=0 else 'out',reference_type=reference_type,
        reference_id=reference_id,location='',created_at=datetime.now())
    w.db.session.add(row)
    w.db.session.flush()
    return row


def _http_call(self,mode,order,row,source,payload_override=None,form_override=None):
    data=None
    payload=None
    if mode=='single':
        path=f'/in_order/{order.id}/delete_item/{row.id}'
    elif mode=='alias':
        path=f'/in_order/{order.id}/item/{row.id}/delete'
    elif mode=='whole':
        path=f'/in_order/{order.id}/delete'
    elif mode=='batch':
        path='/in_order/batch_delete'
        payload={'ids':[order.id,str(order.id),order.id]}
    elif mode=='update':
        path='/in_order/item/update'
        data={'id':row.id,'quantity':2,'price':0,'remark':'new'}
    elif mode=='addrow':
        path=f'/in_order/{order.id}/item/add'
        data={'material_code':self.material.code,'quantity':1.01,'price':0,'source_purchase_order_item_id':source.id}
    elif mode=='copy':
        path=f'/in_order/{order.id}/copy'
    elif mode=='core':
        path=f'/purchase_order/{source.purchase_order_id}/create_in_order'
        payload={'warehouse':self.a.name,'items':[{'item_id':source.id,'quantity':1.01}]}
    elif mode=='selection':
        path='/purchase_order/create_in_order_from_selection'
        payload={'warehouse':self.a.name,'items':[{'purchase_order_item_id':source.id,'quantity':1.01}]}
    elif mode in ('json_new','json_replace'):
        path='/in_order/add'
        payload={'business_type':'采购入库','warehouse':self.a.name,'location':'SAME',
            'items':[{'code':self.material.code,'quantity':1.01,'price':0,'source_purchase_order_item_id':source.id}]}
        if mode=='json_replace':
            payload['order_id']=order.id
    else:
        raise AssertionError('Unknown real HTTP consumer: '+mode)
    if payload_override is not None:
        payload=payload_override
    if form_override is not None:
        data=form_override
    self.http_paths.append(path)
    options={'json':payload} if payload is not None else ({'data':data} if data is not None else {})
    response=document_post(self.client,path,**options)
    assert response.is_json,(path,response.status_code,response.get_data(as_text=True)[:600])
    return response.status_code,response.get_json()


@pytest.mark.parametrize('case_name,specification',SCENARIOS,ids=[name for name,_ in SCENARIOS])
def test_real_pending_reservation_consumer(source_scene,case_name,specification):
    client,a,b=source_scene
    # These are configuration values only, through existing real writers.
    w.set_system_setting('purchase_receipt_strict_order','1')
    w.set_system_setting('purchase_order_to_in_order_enabled','1')
    w.db.session.commit()
    specimen=unittest.TestCase()
    specimen.client=client
    specimen.a=a
    specimen.b=b
    specimen.user=w.User.query.filter_by(username='synthetic-sources').one()
    specimen.material=w.Material(code='SYN-RESERVATION-M',name='合成预留物料',stock=0)
    w.db.session.add(specimen.material)
    w.db.session.commit()
    specimen.http_paths=[]
    specimen.txn=types.MethodType(_txn,specimen)
    specimen.pending_call=types.MethodType(_http_call,specimen)
    namespace={'ns':_RealModelNamespace(),'db':w.db,'math':math,'event':event}
    # Reuse only model-fixture construction and assertions. The source version's
    # pending_call is excluded, so it cannot dispatch extracted product functions.
    helper_nodes=[node for node in ast.parse(HELPERS).body
                  if isinstance(node,ast.FunctionDef) and node.name!='pending_call']
    assert {node.name for node in helper_nodes}=={'pending','pending_state'}
    case_nodes=ast.parse(specification).body
    assert len(case_nodes)==1 and isinstance(case_nodes[0],ast.FunctionDef)
    exec(compile(ast.Module(body=[*helper_nodes,*case_nodes],type_ignores=[]),
        '<actual-WMS-reservation-http:'+case_name+'>','exec'),namespace)
    for node in helper_nodes:
        setattr(specimen,node.name,types.MethodType(namespace[node.name],specimen))
    assert specimen.pending_call.__func__ is _http_call
    namespace[case_nodes[0].name](specimen)
    assert specimen.http_paths,'Every collected case must really issue a business HTTP request'

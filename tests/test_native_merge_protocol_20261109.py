"""Merged native protocols, fresh LPAC synthetic memory only."""
import hashlib
import json

import pytest
from tests.test_money_route_synthetic_20261109 import money_case
from tests.test_native_atomic_receipts_20261109 import target, snapshot


@pytest.mark.parametrize('protocol', ['old_remote', 'old_local'])
@pytest.mark.parametrize('changed', [False, True])
def test_native_confirmed_receipts_from_both_protocols(money_case, protocol, changed):
    c=money_case;endpoint,body,headers=target(c,'inbound')
    content={'path':endpoint,'payload':{k:v for k,v in body.items() if k!='request_id'}}
    if protocol=='old_local':content.update(method='POST',query='')
    fingerprint=hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False,
        separators=(',',':')).encode('utf-8')).hexdigest()
    expected={'status':'success','success':True,'data':{'id':42}}
    original=json.dumps({'fingerprint':fingerprint,'response':expected},ensure_ascii=False)
    c.w.db.session.add(c.w.MobileApiRequest(user_id=c.ids['user'],endpoint='inbound',
        request_key=headers['X-Idempotency-Key'],status_code=200,response_json=original))
    c.w.db.session.commit();before=snapshot(c)
    if changed:body={**body,'remark':'new content'}
    response=c.client.post(endpoint,json=body,headers=headers)
    assert response.status_code==(409 if changed else 200),response.json
    if not changed:assert response.json==expected
    assert snapshot(c)==before
    assert c.w.MobileApiRequest.query.one().response_json==original


def test_native_request_query_is_part_of_the_content_identity(money_case):
    c=money_case;endpoint,body,headers=target(c,'inbound')
    first=c.client.post(endpoint+'?mode=one',json=body,headers=headers)
    assert first.status_code==200,first.json
    before=snapshot(c)
    changed=c.client.post(endpoint+'?mode=two',json=body,headers=headers)
    assert changed.status_code==409,changed.json
    assert snapshot(c)==before

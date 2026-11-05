"""Real rendered collectHeader -> requisition routes, using isolated SQLite only."""
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess

import pytest
import app as wms
from services.warehouse_stock_service import apply_stock_delta
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]


class Fields(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.values = {}
        self.select = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        name = attrs.get('name')
        if tag == 'input' and name:
            self.values[name] = attrs.get('value', '')
        if tag == 'select':
            self.select = name
            if name:self.values[name] = None
        if tag == 'option' and self.select:
            if self.values[self.select] is None or 'selected' in attrs:
                self.values[self.select] = attrs.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'select':self.select = None


def _header_source():
    text = (ROOT / 'app/templates/document_table_form.html').read_text(encoding='utf-8')
    return re.search(r'^function collectHeader\(\) \{[\s\S]*?^\}', text, re.M).group()


def header_from_page(client, path, changes=None):
    page = client.get(path)
    assert page.status_code == 200
    fields = Fields(page.get_data(as_text=True)).values
    for name, value in (changes or {}).items():
        assert name in fields, f'Actual form has no {name} control'
        fields[name] = value
    node = shutil.which('node')
    if not node:pytest.skip('Node.js required for actual collectHeader execution')
    source = _header_source()
    script = r'''
const vm=require('node:vm'),p=JSON.parse(process.argv[1]);
const ctx={docType:'requisition',document:{querySelector:selector=>{
const name=selector.match(/name="([^"]+)"/)[1];
return Object.hasOwn(p.fields,name)?{value:p.fields[name]}:null;
}}};vm.createContext(ctx);vm.runInContext(p.source,ctx);
process.stdout.write(JSON.stringify(ctx.collectHeader()));
'''
    result = subprocess.run([node, '--max-old-space-size=64', '-e', script,
                             json.dumps({'source':source,'fields':fields})],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.fixture
def scene(monkeypatch, request):
    enabled = getattr(request, 'param', True)
    monkeypatch.setitem(wms.app.config, 'TESTING', True)
    monkeypatch.setitem(wms.app.config, 'WTF_CSRF_ENABLED', False)
    with wms.app.app_context():
        assert str(wms.db.engine.url) == 'sqlite:///:memory:'
        wms.db.session.remove();wms.db.drop_all();wms.db.create_all()
        user = wms.User(username='u1-integration', role='production', status='normal',
                        password_hash=generate_password_hash('isolated-fixture'), must_change_password=False)
        unit = wms.Unit(code='U1-UNIT', name='个')
        a = wms.Warehouse(code='U1-A', name='U1仓A', status='active', is_default=True)
        b = wms.Warehouse(code='U1-B', name='U1仓B', status='active')
        wms.db.session.add_all([user,unit,a,b]);wms.db.session.flush()
        material = wms.Material(code='U1-M', name='U1物料', unit_id=unit.id, stock=0, price=2)
        wms.db.session.add(material);wms.db.session.flush()
        wms.set_system_setting('location_management_enabled', '1' if enabled else '0')
        wms.set_system_setting('allow_negative_stock', '0')
        with wms.app.test_request_context():
            from flask_login import login_user
            login_user(user)
            for warehouse, location, qty in [(a, 'Rack-1', 40), (a, 'Rack-2', 30), (b, 'Rack-1', 80)]:
                ok, msg = apply_stock_delta(material, qty, transaction_type='in',
                                           reference_type='u1-fixture', reference_id=1,
                                           warehouse=warehouse.name, location=location if enabled else warehouse.name)
                assert ok, msg
            wms.db.session.commit()
        client = wms.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user.id);session['_fresh'] = True
        try:
            yield client, a.id, b.id, material.id, unit.id
        finally:
            wms.db.session.remove();wms.db.drop_all()


def snapshot(mid):
    wms.db.session.expire_all()
    return (wms.db.session.get(wms.Material, mid).stock,
            [(r.warehouse_id,r.location,r.quantity) for r in wms.LocationInventory.query.order_by(wms.LocationInventory.id)],
            [(r.id,r.warehouse_id,r.quantity,r.reference_id) for r in wms.StockTransaction.query.order_by(wms.StockTransaction.id)])


def save(client, mid, uid, header, *, order_id='', order_no='U1-REQ', quantity=5):
    return client.post('/requisition/save_table', json={
        'order_id':order_id,'order_no':order_no,'date':'2026-10-23','header':header,
        'items':[{'material_id':mid,'quantity':quantity,'unit_id':uid}]
    })


def accepted(response):
    body = response.get_json()
    assert response.status_code == 200, body
    assert body['status'] == 'success', body
    return body


def test_real_header_saves_and_edit_roundtrips_location_without_stock_writes(scene):
    client,a,_,mid,uid = scene
    before = snapshot(mid)
    location = '货架A\'"<&>\\一'
    header = header_from_page(client, '/requisition/add', {'warehouse_id':str(a),'location':location})
    assert header['location'] == location
    rid = accepted(save(client,mid,uid,header))['id']
    assert wms.db.session.get(wms.ProductionRequisition,rid).location == location
    edited = header_from_page(client,f'/requisition/{rid}')
    assert edited['location'] == location
    accepted(save(client,mid,uid,edited,order_id=rid,quantity=6))
    wms.db.session.expire_all()
    assert wms.db.session.get(wms.ProductionRequisition,rid).location == location
    assert snapshot(mid) == before


def test_real_header_completion_isolates_warehouse_and_location_and_totals(scene):
    client,a,b,mid,uid = scene
    baseline = len(snapshot(mid)[2])
    for wid,no,qty in [(a,'U1-A-REQ',5),(b,'U1-B-REQ',7)]:
        header = header_from_page(client,'/requisition/add',{'warehouse_id':str(wid),'location':'Rack-1'})
        rid = accepted(save(client,mid,uid,header,order_no=no,quantity=qty))['id']
        accepted(client.post(f'/requisition/{rid}/complete'))
    total, locations, transactions = snapshot(mid)
    assert {(wid,loc):qty for wid,loc,qty in locations} == {(a,'Rack-1'):35,(a,'Rack-2'):30,(b,'Rack-1'):73}
    assert total == sum(qty for _,_,qty in locations) == 138
    assert len(transactions) == baseline + 2
    assert [row[1:] for row in transactions[-2:]] == [(a,-5,1),(b,-7,2)]
    assert wms.get_warehouse_stock_quantities(wms.db.session.get(wms.Warehouse,a))[mid] == 65
    assert wms.get_warehouse_stock_quantities(wms.db.session.get(wms.Warehouse,b))[mid] == 73


def test_enabled_blank_real_header_rejects_save_without_writes(scene):
    client,a,_,mid,uid = scene
    before = snapshot(mid)
    header = header_from_page(client,'/requisition/add',{'warehouse_id':str(a),'location':''})
    response = save(client,mid,uid,header)
    assert response.status_code == 400
    assert '库位' in response.get_json()['msg']
    assert wms.ProductionRequisition.query.count() == 0
    assert snapshot(mid) == before


def test_enabled_legacy_blank_location_complete_guard_preserves_ledgers(scene):
    client,a,_,mid,uid = scene
    order = wms.ProductionRequisition(req_no='U1-LEGACY',status='pending',warehouse=wms.db.session.get(wms.Warehouse,a).name,location=None)
    wms.db.session.add(order);wms.db.session.flush()
    wms.db.session.add(wms.ProductionRequisitionItem(requisition_id=order.id,material_id=mid,quantity=5,unit_id=uid))
    wms.db.session.commit();wms.db.session.refresh(order)
    assert order.location == ''  # ORM default: this is a historical blank, not persisted SQL NULL.
    rid=order.id;before=snapshot(mid)
    response=client.post(f'/requisition/{rid}/complete')
    assert response.status_code==400 and '库位' in response.get_json()['msg']
    assert wms.db.session.get(wms.ProductionRequisition,rid).status=='pending'
    assert snapshot(mid)==before


@pytest.mark.parametrize('scene',[False],indirect=True)
@pytest.mark.parametrize('legacy_location',[None,'历史库位'])
def test_disabled_real_header_preserves_legacy_location_and_empty_compatibility(scene,legacy_location):
    client,a,_,mid,uid=scene
    order=wms.ProductionRequisition(req_no='U1-DISABLED',status='pending',warehouse=wms.db.session.get(wms.Warehouse,a).name,location=legacy_location)
    wms.db.session.add(order);wms.db.session.flush()
    wms.db.session.add(wms.ProductionRequisitionItem(requisition_id=order.id,material_id=mid,quantity=5,unit_id=uid))
    wms.db.session.commit();wms.db.session.refresh(order)
    assert order.location == (legacy_location or '')
    rid=order.id
    header=header_from_page(client,f'/requisition/{rid}')
    assert header['location']==(legacy_location or '')
    before=snapshot(mid)
    accepted(save(client,mid,uid,header,order_id=rid,order_no='U1-DISABLED'))
    assert snapshot(mid)==before
    assert wms.db.session.get(wms.ProductionRequisition,rid).location==(legacy_location or '')
    if legacy_location is None:
        accepted(client.post(f'/requisition/{rid}/complete'))
        total,locations,transactions=snapshot(mid)
        # With location management off, stock is sourced from warehouse transactions.
        assert locations == []
        assert total == sum(row[2] for row in transactions) == 145
        assert wms.get_warehouse_stock_quantities(wms.db.session.get(wms.Warehouse,a))[mid] == 65
        assert len(transactions)==len(before[2])+1

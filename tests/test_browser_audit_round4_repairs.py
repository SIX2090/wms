"""2026-11-03 follow-up: isolated regression locks for browser findings."""
import io
import json
import subprocess
import shutil
from datetime import date
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from openpyxl import Workbook, load_workbook
import app as w
from tests.test_bug_2026_09_13_002_warehouse_deductions import scene

ROOT = Path(__file__).resolve().parents[1]


def test_contract_blockers_accept_messages_and_counts(scene):
    client, wh, _, material = scene
    contract = w.Contract(contract_no='REF-C', project_name='Referenced')
    w.db.session.add(contract); w.db.session.flush()
    w.db.session.add(w.InOrder(order_no='REF-IN', contract_id=contract.id, warehouse=wh.name))
    w.db.session.commit()
    response = client.post('/contract/delete', json={'ids': [contract.id]})
    assert response.status_code != 500
    assert w.db.session.get(w.Contract, contract.id) is not None
    assert '引用' in response.get_data(as_text=True) or '\\u5f15\\u7528' in response.get_data(as_text=True)
    assert w._format_delete_blockers([('单据', 2), ('空', 0)]) == '单据 2 条'


def test_purchase_return_numbers_reserve_both_models(scene):
    suffix = date.today().strftime('%y%m')
    w.db.session.add_all([
        w.PurchaseRequest(request_no=f'PR{suffix}0007', status='pending'),
        w.OutOrder(order_no=f'PR{suffix}0012', business_type='采购退货出库'),
        w.OutOrder(order_no=f'PR{suffix}0002', business_type='采购退货出库')])
    w.db.session.commit()
    assert w.generate_order_no('PR') == f'PR{suffix}0013'
    w.db.session.add(w.PurchaseRequest(request_no=f'PR{suffix}0020', status='pending'))
    w.db.session.commit()
    assert w.generate_order_no('PR') == f'PR{suffix}0021'


def test_workbench_pending_check_and_live_routes(scene):
    client, wh, _, material = scene
    check = w.InventoryCheck(check_no='CHECK-QUEUE', status='pending', warehouse=wh.name, date=date.today())
    inbound = w.InOrder(order_no='IN-QUEUE', status='pending', warehouse=wh.name)
    outbound = w.OutOrder(order_no='OUT-QUEUE', status='pending', warehouse=wh.name)
    w.db.session.add_all([check,inbound,outbound]); w.db.session.commit()
    count, items = w._ai_ww_query_inventory_check_pending()
    assert count == 1 and items[0]['title'] == 'CHECK-QUEUE'
    for loader in [w._ai_ww_query_today_inbound_pending,w._ai_ww_query_today_outbound_pending,w._ai_ww_query_inventory_check_pending,w._ai_ww_query_abnormal_stock]:
        for item in loader()[1]:
            assert client.get(item['jump_url']).status_code == 200, item['jump_url']
    data=client.get('/api/ai/warehouse_workbench').json
    def links(value):
        if isinstance(value,dict):
            for k,v in value.items():
                if k=='jump_url' and v: yield v
                else: yield from links(v)
        elif isinstance(value,list):
            for v in value: yield from links(v)
    for link in links(data):
        assert client.get(link).status_code in (200,302),link


@pytest.mark.parametrize('kind', ['purchase', 'sales'])
def test_adjacent_workbench_detail_and_all_links_exist(scene, kind):
    client, wh, _, material = scene
    supplier = w.Supplier(code='V-NAV', name='Vendor navigation')
    customer = w.Customer(code='C-NAV', name='Customer navigation')
    w.db.session.add_all([supplier, customer]); w.db.session.flush()
    w.db.session.add(w.PurchaseOrder(order_no='PO-NAV', supplier_id=supplier.id,
        status='pending', expected_date=date.today()))
    w.db.session.add(w.SalesOrder(order_no='SO-NAV', customer_id=customer.id,
        status='confirmed', shipment_status='pending', delivery_date=date.today()))
    w.db.session.commit()
    response = client.get(f'/api/ai/{kind}_followup_workbench')
    assert response.status_code == 200
    data = response.json['workbench']
    def links(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == 'jump_url' and item: yield item
                else: yield from links(item)
        elif isinstance(value, list):
            for item in value: yield from links(item)
    checked = list(links(data))
    assert any(link.startswith('/purchase_order/' if kind=='purchase' else '/sales/') for link in checked)
    for link in checked:
        assert client.get(link).status_code in (200, 302), link


@pytest.mark.parametrize('role,status', [('admin',200),('warehouse',200),
    ('purchase',403),('sales',403),('finance',403),('viewer',403)])
def test_processing_queue_role_boundary(scene, role, status):
    client, _, _, _ = scene
    w.User.query.one().role=role; w.db.session.commit()
    assert client.get('/ai/drafts', headers={'Accept':'application/json'}).status_code==status
    if role=='finance':
        denied=client.get('/ai/drafts')
        assert denied.status_code==302 and denied.headers['Location']=='/'


def test_processing_queue_pagination_escapes_text_and_omits_payload(scene):
    client, _, _, _ = scene
    user=w.User.query.one()
    for n in range(31):
        w.db.session.add(w.AIDraftIdempotency(user_id=user.id, capability='in_order_draft',
            idempotency_key=f'queue-{n}', draft_no=f'DRAFT-{n}', status='processing',
            source='<script>fixture</script>', request_snapshot='PRIVATE_FIXTURE_PAYLOAD'))
    w.db.session.commit()
    first=BeautifulSoup(client.get('/ai/drafts').data, 'html.parser')
    second=BeautifulSoup(client.get('/ai/drafts?page=2').data, 'html.parser')
    assert len(first.select('tbody tr'))==30 and len(second.select('tbody tr'))==1
    assert first.find('a', string='下一页')
    assert 'PRIVATE_FIXTURE_PAYLOAD' not in str(first)
    assert not first.select('tbody script')
    assert w.AIDraftIdempotency.query.filter_by(status='processing').count()==31


@pytest.mark.parametrize('quantity', [2, 0])
def test_outbound_import_rejects_empty_rows_without_inbound_party_rules(scene, quantity):
    client, wh, _, material = scene
    wb=Workbook(); ws=wb.active
    ws.append(['单据编号', '仓库', '物料编码', '数量', '客供'])
    ws.append(['OUT-IMPORT', wh.name, material.code, quantity, '是'])
    buf=io.BytesIO(); wb.save(buf); buf.seek(0)
    response=client.post('/import/out_order', data={'file':(buf,'out.xlsx')},
        headers={'X-Requested-With':'XMLHttpRequest'})
    assert response.status_code==200
    assert response.json['count']==(1 if quantity else 0)
    assert w.OutOrder.query.count()==(1 if quantity else 0)


@pytest.mark.parametrize('kind,party', [('其他入库','Client'),('采购入库','Vendor')])
@pytest.mark.parametrize('quantity', [2,0])
def test_combined_import_header_and_invalid_row_no_side_effects(scene,kind,party,quantity):
    client,wh,_,material=scene
    wb=Workbook();ws=wb.active
    ws.append(['单据编号','业务类型','供应商/客户','仓库','物料编码','数量'])
    ws.append(['IMPORT-COMBINED',kind,party,wh.name,material.code,quantity])
    buf=io.BytesIO();wb.save(buf);buf.seek(0)
    response=client.post('/import/in_order',data={'file':(buf,'orders.xlsx')},headers={'X-Requested-With':'XMLHttpRequest'})
    assert response.status_code==200,response.get_data(as_text=True)
    assert response.json['count']==(1 if quantity else 0),response.json
    assert w.Supplier.query.filter_by(name=party).count()==(1 if quantity and kind=='采购入库' else 0)
    assert w.Customer.query.filter_by(name=party).count()==(1 if quantity and kind=='其他入库' else 0)
    assert w.InOrder.query.count()==(1 if quantity else 0)


@pytest.mark.parametrize('path', ['/report/api/ledger?export=excel','/report/ledger/print_excel','/report/ledger/print_preview'])
def test_ledger_export_and_print_require_material(scene,path):
    client,wh,_,_=scene
    response=client.get(path+('&' if '?' in path else '?')+f'warehouse_id={wh.id}')
    assert response.status_code==400


def test_ledger_reversal_label_preserves_net_balance(scene):
    client,wh,_,material=scene
    order=w.InOrder(order_no='LEDGER',warehouse=wh.name)
    w.db.session.add(order);w.db.session.flush()
    for qty,kind in [(3,'in'),(-3,'revert_in'),(3,'in')]:
        w.db.session.add(w.StockTransaction(material_id=material.id,quantity=qty,transaction_type=kind,reference_type='in_order',reference_id=order.id,warehouse_id=wh.id,location=wh.name))
    w.db.session.commit()
    with w.app.test_request_context(f'/?warehouse_id={wh.id}&material_code={material.code}'):
        rows=w._collect_ledger_rows(w._build_report_filters())
    movements=[row for row in rows if row.get('reference_no')=='LEDGER']
    assert len(movements)==3
    assert len([row for row in movements if '反提交冲销' in row['reference_type']])==1
    assert movements[-1]['balance_quantity']==3


def test_mobile_confirm_prefers_configured_default_and_lookup_named(scene):
    client,wh,_,_=scene
    w.db.session.add(w.Warehouse(code='000',name='Other first',status='active'));w.db.session.commit()
    page=BeautifulSoup(client.get('/mobile/scan?mode=confirm').data,'html.parser')
    assert page.select_one('#confirmWarehouseSelect option[selected]')['value']==wh.name
    page=BeautifulSoup(client.get('/mobile/scan?mode=query').data,'html.parser')
    assert page.select_one('#lookupBtn').get('aria-label')=='查找物料'


def test_adjustment_detail_has_authorized_revert(scene):
    client,wh,_,_=scene
    order=w.AdjustmentOrder(adjustment_no='ADJ-DETAIL',status='completed',adjustment_type='surplus',warehouse=wh.name)
    w.db.session.add(order);w.db.session.commit()
    page=BeautifulSoup(client.get(f'/adjustment/{order.id}').data,'html.parser')
    assert page.select_one('[data-document-action="revertAdjustment"]')


@pytest.mark.parametrize('mode,model,kind', [('in',w.InOrder,'其他入库'),('out',w.OutOrder,'其他出库')])
def test_other_document_navigation_scope_and_edges(scene,mode,model,kind):
    client,wh,_,_=scene
    rows=[model(order_no=f'NAV{i}',warehouse=wh.name,business_type=kind if i%2==0 else 'IGNORE',status='pending') for i in range(5)]
    w.db.session.add_all(rows);w.db.session.commit()
    with w.app.test_request_context('/?embedded=1'):
        nav=w._other_order_navigation(mode,rows[2].id)
        assert nav['first']==nav['prev'] and nav['next']==nav['last']
        for link in nav.values():
            assert client.get(link).status_code==200
        first=w._other_order_navigation(mode,rows[0].id)
        assert first['first'] is None and first['prev'] is None


@pytest.mark.parametrize('bad', [False,True])
def test_page_setup_persists_workbook_and_rejects_invalid_atomically(tmp_path,bad):
    from print_fill import apply_print_template_grid, serialize_print_template_grid
    from routes.print_template_editor import PrintTemplateGridRequest
    path=tmp_path/'page.xlsx';wb=Workbook();wb.active['A1']='Keep';wb.save(path)
    cfg=dict(size='A5',orient='landscape',w=148,h=210,mt=9,mb=0,ml=3,mr=4,scale=90)
    if bad:cfg['mt']=-1
    before=path.read_bytes()
    if bad:
        with pytest.raises(ValueError):
            request=PrintTemplateGridRequest.model_validate({'sheets':[{'name':'Sheet','page_setup':cfg}]})
            apply_print_template_grid(path,[s.to_engine_payload() for s in request.sheets])
        assert path.read_bytes()==before
        return
    request=PrintTemplateGridRequest.model_validate({'sheets':[{'name':'Sheet','page_setup':cfg}]})
    output=apply_print_template_grid(path,[s.to_engine_payload() for s in request.sheets])
    path.write_bytes(output.read())
    wb=load_workbook(path);ws=wb.active
    assert ws['A1'].value=='Keep'
    assert ws.page_setup.orientation=='landscape' and str(ws.page_setup.paperSize)=='11'
    assert ws.page_setup.scale==90 and ws.page_margins.top==pytest.approx(9/25.4)
    assert serialize_print_template_grid(path)['sheets'][0]['page_setup']==cfg


@pytest.mark.parametrize('measure,expected', [('50mm',50),('5cm',50),('2in',50.8),('144pt',50.8)])
def test_millimetres(tmp_path, measure, expected):
    from print_fill import serialize_print_template_grid
    path=tmp_path/'custom.xlsx'; wb=Workbook(); ws=wb.active
    ws.page_setup.paperWidth=measure; ws.page_setup.paperHeight='10cm'; wb.save(path)
    setup=serialize_print_template_grid(path)['sheets'][0]['page_setup']
    assert setup['size']=='custom'
    assert setup['w']==pytest.approx(expected) and setup['h']==100


def test_page_setup_changes_only_requested_sheet(tmp_path):
    from print_fill import apply_print_template_grid, serialize_print_template_grid
    path=tmp_path/'two.xlsx'; wb=Workbook(); wb.active.title='First'
    wb.create_sheet('Second').page_setup.orientation='landscape'; wb.save(path)
    cfg=dict(size='custom',orient='portrait',w=130,h=220,mt=5,mb=5,ml=3,mr=3,scale=80)
    path.write_bytes(apply_print_template_grid(path,[{'name':'First','page_setup':cfg}]).read())
    sheets=serialize_print_template_grid(path)['sheets']
    assert sheets[0]['page_setup']==cfg
    assert sheets[1]['page_setup']['orient']=='landscape'
    assert sheets[1]['page_setup']['size']=='A4'


@pytest.mark.parametrize('scenario',['mobile-input','check-initial','batch-contract','batch-employee','frozen-stock','unknown-stock'])
def test_frontend_regressions(scenario):
    node=shutil.which('node')
    if not node:pytest.skip('Node required')
    result=subprocess.run([node,str(ROOT/'tests/browser_audit_round4.cjs'),scenario],capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stdout+result.stderr

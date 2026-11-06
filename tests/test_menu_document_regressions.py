"""Business context must survive menu, document, navigation and export transitions."""
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import io

from bs4 import BeautifulSoup
from openpyxl import load_workbook
import pytest
import app as w

APP_DIR=Path(w.__file__).resolve().parent
IN_TYPES=['采购入库','产品入库','其他入库','销售退货入库']
OUT_TYPES=['领料单','销售出库','其他出库','采购退货出库']
OUT_ALIASES=dict(zip(OUT_TYPES,['requisition','sale','other_out','purchase_return']))
IN_ALIASES=dict(zip(IN_TYPES,['purchase_in','product_in','other_in','sales_return']))

@pytest.fixture
def menu_documents(monkeypatch):
    monkeypatch.setitem(w.app.config,'TESTING',True)
    monkeypatch.setitem(w.app.config,'WTF_CSRF_ENABLED',False)
    with w.app.app_context():
        assert str(w.db.engine.url)=='sqlite:///:memory:'
        w.db.session.remove();w.db.drop_all();w.db.create_all()
        users={}
        for role in ['admin','warehouse','purchase','sales','finance','viewer']:
            user=w.User(username='menu-'+role,role=role,password_hash='unused',must_change_password=False)
            w.db.session.add(user);w.db.session.flush();users[role]=user.id
        warehouses=[w.Warehouse(code='MENU-A',name='菜单甲仓',status='active',is_default=True),
                    w.Warehouse(code='MENU-B',name='菜单乙仓',status='active')]
        unit=w.Unit(code='MENU-U',name='台');supplier=w.Supplier(code='MENU-S',name='菜单供应商')
        customer=w.Customer(code='MENU-C',name='菜单客户');department=w.Department(code='MENU-D',name='菜单领料部')
        w.db.session.add_all([*warehouses,unit,supplier,customer,department]);w.db.session.flush()
        material=w.Material(code='MENU-M',name='菜单物料',unit_id=unit.id,stock=0,price=5)
        w.db.session.add(material);w.db.session.flush()
        sales=w.SalesOrder(order_no='MENU-SALES',customer_id=customer.id,warehouse=warehouses[0].name,
                           warehouse_id=warehouses[0].id,status='confirmed')
        w.db.session.add(sales);w.db.session.flush()
        sales_item=w.SalesOrderItem(sales_order_id=sales.id,material_id=material.id,quantity=8,price=5)
        w.db.session.add(sales_item);w.db.session.flush()
        ids={'users':users,'warehouses':[x.id for x in warehouses],'in_order':{},'out_order':{},'sales':sales.id,
             'customer':customer.id,'department':department.id,'material':material.id}
        for kind,types,Model,Item,fk in [('in_order',IN_TYPES,w.InOrder,w.InOrderItem,'in_order_id'),
                                       ('out_order',OUT_TYPES,w.OutOrder,w.OutOrderItem,'out_order_id')]:
            for index,business in enumerate(types):
                ids[kind][business]=[]
                for wi,warehouse in enumerate(warehouses):
                    extra=dict(customer_id=customer.id,supplier_id=supplier.id) if kind=='in_order' else dict(customer=customer.name,department_id=department.id)
                    if business=='销售退货入库':extra.update(source_sales_order_id=sales.id,source_sales_order_no=sales.order_no,supplier_id=None)
                    if business=='销售出库':extra['source_sales_order_id']=sales.id
                    order=Model(order_no=f'MENU-{kind}-{index}-{wi}',date=date.today(),business_type=business,
                                status='pending',warehouse=warehouse.name,total_amount=10,operator_id=users['admin'],**extra)
                    w.db.session.add(order);w.db.session.flush()
                    line=Item(**{fk:order.id},material_id=material.id,quantity=2,price=5,amount=10,
                              contract_no='LINE-C',project_name='行工程')
                    if business=='销售退货入库':line.source_sales_order_item_id=sales_item.id
                    w.db.session.add(line);ids[kind][business].append(order.id)
                    if business=='销售出库' and wi==0:sales.shipment_order_no=order.order_no
        w.db.session.commit()
    def client(role='admin'):
        result=w.app.test_client()
        with result.session_transaction() as session:
            session['_user_id']=str(users[role]);session['_fresh']=True
        return result
    yield client,ids
    with w.app.app_context():w.db.session.remove()


def soup(response):
    assert response.status_code==200,response.get_data(as_text=True)[:300]
    return BeautifulSoup(response.get_data(as_text=True),'html.parser')

@pytest.mark.parametrize('parameter',['type','business_type'])
@pytest.mark.parametrize('warehouse_index',[0,1])
def test_sales_return_export_matches_selected_warehouse_and_type(menu_documents,parameter,warehouse_index):
    clients,ids=menu_documents;c=clients();wh=ids['warehouses'][warehouse_index]
    query={'warehouse_id':wh,parameter:'sales_return' if parameter=='type' else '销售退货入库'}
    listing=soup(c.get('/in_order',query_string=query))
    expected=[a.text for a in listing.select('#inOrderTable td[data-column-key="order_no"] a')]
    response=c.get('/in_order/export',query_string=query);assert response.status_code==200
    rows=list(load_workbook(io.BytesIO(response.data),data_only=True).active.values)[1:]
    assert [r[0] for r in rows]==expected and len(rows)==1
    assert {r[2] for r in rows}=={'销售退货入库'}
    with w.app.app_context():assert w.StockTransaction.query.count()==0 and w.Material.query.one().stock==0


def test_sales_return_report_filter_can_restore_the_requested_type(menu_documents):
    clients,ids=menu_documents;c=clients()
    page=soup(c.get('/report/view/in_detail',query_string={'business_type':'销售退货入库'}))
    options={o.get('value') for o in page.select('#business_type option')}
    assert set(IN_TYPES)|{''} == options
    data=c.get('/report/api/in_detail',query_string={'warehouse_id':ids['warehouses'][0],'business_type':'销售退货入库'}).json
    assert data['total']==1 and {r['business_type'] for r in data['data']}=={'销售退货入库'}


def test_sales_order_recent_outbound_link_reaches_the_same_sales_document(menu_documents):
    clients,ids=menu_documents;c=clients();page=soup(c.get('/sales/'+str(ids['sales'])))
    label=page.find('span',class_='info-label',string='最近出库草稿')
    link=label.parent.find('a');assert link
    target=soup(c.get(link['href']))
    assert '销售出库' in target.title.text
    assert f"/out_order/{ids['out_order']['销售出库'][0]}" in str(target) or urlsplit(link['href']).path==f"/out_order/{ids['out_order']['销售出库'][0]}"
    assert '暂无领料明细' not in target.get_text()

@pytest.mark.parametrize('kind,types',[('in_order',IN_TYPES),('out_order',OUT_TYPES)])
def test_document_navigation_stays_with_current_business_type(menu_documents,kind,types):
    clients,ids=menu_documents;c=clients()
    for business in types:
        expected=ids[kind][business];current=expected[-1]
        data=c.get('/api/document_navigation/'+kind,query_string={'current_id':current}).json
        assert data['status']=='success' and data['total']==len(expected)
        assert [x['id'] for x in data['list']]==expected
        assert data['next_id'] is None and data['prev_id']==expected[0]
        assert data['first_id']==expected[0] and data['last_id']==current

@pytest.mark.parametrize('kind,business',[('in_order','产品入库'),('in_order','销售退货入库'),('out_order','销售出库'),('out_order','采购退货出库')])
def test_new_document_finder_can_request_a_business_scope(menu_documents,kind,business):
    clients,ids=menu_documents
    data=clients().get('/api/document_navigation/'+kind,query_string={'business_type':business}).json
    assert data['total']==len(ids[kind][business])
    assert [x['id'] for x in data['list']]==ids[kind][business]

@pytest.mark.parametrize('business',OUT_TYPES)
def test_outbound_list_new_and_columns_match_business(menu_documents,business):
    clients,_=menu_documents;c=clients();page=soup(c.get('/out_order',query_string={'type':OUT_ALIASES[business]}))
    new=page.select_one('.wms-entry-toolbar a.btn-primary');assert new
    expected={'领料单':'新增领料单','销售出库':'新增销售出库','其他出库':'新增其他出库','采购退货出库':'新增采购退货出库'}[business]
    assert expected in new.text
    target=soup(c.get(new['href']));assert business in target.title.text
    field=target.select_one('[name="business_type"]')
    assert (field.find('option',selected=True)['value'] if field.name=='select' else field['value'])==business
    headings={x['data-column-key']:x.text.strip() for x in page.select('#outOrderTable th[data-column-key]')}
    party={'领料单':'领料部门','销售出库':'客户','其他出库':'客户/领用单位','采购退货出库':'退货供应商'}[business]
    assert party in headings['customer']

@pytest.mark.parametrize('business',OUT_TYPES[1:])
def test_outbound_clear_and_detail_return_preserve_business(menu_documents,business):
    clients,ids=menu_documents;c=clients();query={'type':OUT_ALIASES[business],'search':'MENU','embedded':'1'}
    page=soup(c.get('/out_order',query_string=query));clear=page.find('a',string='清除')
    target=soup(c.get(clear['href']));assert business in target.title.text
    detail=soup(c.get('/out_order/'+str(ids['out_order'][business][0]),query_string={'embedded':'1'}))
    back=next(a for a in detail.find_all('a') if a.get_text(strip=True)=='返回')
    target=soup(c.get(back['href']));assert business in target.title.text
    assert parse_qs(urlsplit(back['href']).query).get('embedded')==['1']


def test_all_inbound_list_title_and_return_source_match_real_documents(menu_documents):
    clients,ids=menu_documents;c=clients()
    page=soup(c.get('/in_order'));assert '全部入库' in page.title.text
    returns=soup(c.get('/in_order',query_string={'type':'sales_return'}))
    assert '来源销售订单' in returns.get_text()
    assert returns.select_one(f'#inOrderTable a[href="/sales/{ids["sales"]}"]')
    assert '来源采购单' not in returns.select_one('#inOrderTable').get_text()
    new=returns.select_one('.btn-primary[href*="/in_order/add"]');assert new and 'sales_return' in new['href']

@pytest.mark.parametrize('role,path',[('purchase','/purchase_request/add'),('purchase','/purchase_order/add'),('sales','/sales/add')])
def test_authorized_roles_have_working_business_menu_entries(menu_documents,role,path):
    clients,_=menu_documents;c=clients(role);page=soup(c.get('/'))
    primary=page.select_one('#appSidebar > ul.nav')
    assert primary.select_one(f'a[href="{path}"]')
    assert c.get(path).status_code==200

@pytest.mark.parametrize('role',['purchase','sales'])
def test_role_menus_do_not_expose_warehouse_only_creation(menu_documents,role):
    clients,_=menu_documents;page=soup(clients(role).get('/'))
    primary=page.select_one('#appSidebar > ul.nav')
    assert not primary.select_one('a[href="/in_order/add"]')
    assert not primary.select_one('a[href="/out_order/add?type=sale"]')


@pytest.mark.parametrize('role',['admin','warehouse','purchase','sales','finance','viewer'])
def test_home_creation_shortcuts_follow_existing_write_permissions(menu_documents,role):
    clients,_=menu_documents;c=clients(role)
    page=soup(c.get('/')).select_one('.dashboard-shell')
    for path,roles in [('/in_order/add',{'admin','warehouse'}),
                       ('/out_order/add',{'admin','warehouse'}),
                       ('/purchase_request/add',{'admin','purchase'})]:
        entries=page.select(f'a[href="{path}"]')
        assert bool(entries)==(role in roles),(role,path)
        if entries:assert c.get(path).status_code==200,(role,path)


def test_ai_read_menu_allowed_matches_existing_rollout_without_writing_audits(menu_documents,monkeypatch):
    clients,ids=menu_documents
    monkeypatch.setattr(w,'_ai_rollout_mode',lambda:'off')
    page=soup(clients('warehouse').get('/'));primary=page.select_one('#appSidebar > ul.nav')
    paths=['/ai/replenishment','/ai/replenishment_smart','/ai/inventory_health']
    assert not any(primary.select_one(f'a[href="{path}"]') for path in paths)
    monkeypatch.setattr(w,'_ai_rollout_mode',lambda:'all')
    page=soup(clients('warehouse').get('/'));primary=page.select_one('#appSidebar > ul.nav')
    assert all(primary.select_one(f'a[href="{path}"]') for path in paths)
    for path in paths:assert clients('warehouse').get(path).status_code==200
    monkeypatch.setattr(w,'_ai_global_enabled',lambda:False)
    page=soup(clients('warehouse').get('/'));primary=page.select_one('#appSidebar > ul.nav')
    assert not any(primary.select_one(f'a[href="{path}"]') for path in paths)

@pytest.mark.parametrize('kind,business,grid,field,search',[
    ('in_order','产品入库','产品入库','采购入库',''),
    ('in_order','销售退货入库',None,'销售退货入库','?type=sales_return'),
    ('out_order','销售出库','销售出库','领料单',''),
    ('out_order','采购退货出库',None,'采购退货出库','?type=purchase_return'),
])
def test_navigation_request_keeps_saved_or_new_form_business_type(kind,business,grid,field,search):
    import json,shutil,subprocess
    node=shutil.which('node')
    if not node:pytest.skip('Node.js required')
    source=(APP_DIR/'static/js/app.js').read_text(encoding='utf-8')
    functions=[]
    for name in ['withEmbeddedParam','preserveEmbeddedUrl','getDocumentBusinessType','getDocumentNavigationApiUrl','openAdd']:
        start=source.find('function '+name+'(')
        if start<0:continue
        end=source.find('\nfunction ',start+10)
        functions.append(source[start:end if end>=0 else None])
    data=json.dumps(dict(kind=kind,business=business,grid=grid,field=field,search=search),ensure_ascii=False)
    program=r'''const assert=require('node:assert/strict'),vm=require('node:vm');
const p=INPUT;
const grid=p.grid?{dataset:{businessType:p.grid},getAttribute:()=>p.grid}:null;
const field=p.field?{value:p.field}:null;
const document={body:{classList:{contains:()=>true}},getElementById:id=>id==='itemTable'?grid:null,querySelector:selector=>selector.includes('data-business-type')?grid:selector.includes('business_type')?field:null};
const opened=[];
const ctx={document,URL,URLSearchParams,encodeURIComponent,openUrl:url=>opened.push(url),getCurrentRecordId:()=>p.grid?'3':null,window:{location:{search:p.search,origin:'http://fixture'}}};
vm.createContext(ctx);vm.runInContext(SOURCE,ctx);
const url=new URL(ctx.getDocumentNavigationApiUrl({key:p.kind},'合同甲'),'http://fixture');
assert.equal(url.searchParams.get('business_type'),p.business);
assert.equal(url.searchParams.get('q'),'合同甲');
assert.equal(url.searchParams.get('current_id'),p.grid?'3':null);
ctx.openAdd({key:p.kind,addUrl:'/'+p.kind+'/add'});
const created=new URL(opened[0],'http://fixture');
assert.equal(created.searchParams.get('type'),({'产品入库':'product','销售退货入库':'sales_return','销售出库':'sale','采购退货出库':'purchase_return'})[p.business]);
assert.equal(created.searchParams.get('embedded'),'1');
'''.replace('INPUT',data).replace('SOURCE',json.dumps('\n'.join(functions)))
    result=subprocess.run([node,'-e',program],capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert result.returncode==0,result.stdout+result.stderr


def test_inbound_navigation_keeps_legacy_null_type_in_purchase_scope(menu_documents):
    clients,ids=menu_documents
    with w.app.app_context():
        order=w.InOrder(order_no='MENU-LEGACY-IN',business_type=None,warehouse='菜单甲仓',date=date.today())
        w.db.session.add(order);w.db.session.commit();oid=order.id
    result=clients().get('/api/document_navigation/in_order',query_string={'current_id':oid}).json
    assert {row['id'] for row in result['list']}==set(ids['in_order']['采购入库']+[oid])

@pytest.mark.parametrize('legacy',[None,'','Android扫码出库','生产出库'])
def test_outbound_navigation_keeps_legacy_requisition_types(menu_documents,legacy):
    clients,ids=menu_documents
    with w.app.app_context():
        order=w.OutOrder(order_no='MENU-LEGACY-OUT',business_type=legacy,warehouse='菜单甲仓',date=date.today())
        w.db.session.add(order);w.db.session.commit();oid=order.id
    result=clients().get('/api/document_navigation/out_order',query_string={'current_id':oid}).json
    assert {row['id'] for row in result['list']}==set(ids['out_order']['领料单']+[oid])


@pytest.mark.parametrize('kind,business',[('in_order','产品入库'),('out_order','销售出库')])
def test_navigation_current_document_cannot_be_switched_by_conflicting_type(menu_documents,kind,business):
    clients,ids=menu_documents
    response=clients().get('/api/document_navigation/'+kind,query_string={
        'current_id':ids[kind][business][0],'business_type':'采购入库' if kind=='in_order' else '领料单'})
    assert response.status_code==200
    assert {x['id'] for x in response.json['list']}==set(ids[kind][business])

@pytest.mark.parametrize('kind',['in_order','out_order'])
def test_navigation_rejects_unknown_explicit_business_type(menu_documents,kind):
    clients,_=menu_documents
    assert clients().get('/api/document_navigation/'+kind,query_string={'business_type':'unknown'}).status_code==400


def test_menu_permission_checks_do_not_write_access_audits(menu_documents,monkeypatch):
    clients,_=menu_documents;calls=[]
    monkeypatch.setattr(w,'_ai_rollout_mode',lambda:'off')
    monkeypatch.setattr(w,'_ai_record_capability_audit',lambda *args,**kwargs:calls.append('capability'))
    monkeypatch.setattr(w,'_ai_record_rollout_denied_audit',lambda *args,**kwargs:calls.append('rollout'))
    assert clients('warehouse').get('/').status_code==200
    assert calls==[]
    assert clients('warehouse').get('/ai/replenishment').status_code==302
    assert 'rollout' in calls and 'capability' in calls

@pytest.mark.parametrize('included',[False,True])
def test_ai_menu_respects_existing_user_allowlist(menu_documents,monkeypatch,included):
    clients,ids=menu_documents
    monkeypatch.setattr(w,'_ai_rollout_mode',lambda:'allowlist')
    monkeypatch.setattr(w,'_ai_allowed_user_ids',lambda:[ids['users']['warehouse']] if included else [])
    primary=soup(clients('warehouse').get('/')).select_one('#appSidebar > ul.nav')
    for path in ['/ai/replenishment','/ai/replenishment_smart','/ai/inventory_health']:
        assert bool(primary.select_one(f'a[href="{path}"]')) is included

@pytest.mark.parametrize('business',OUT_TYPES)
def test_outbound_list_new_page_saves_a_draft_of_the_same_type(menu_documents,business):
    clients,ids=menu_documents;c=clients()
    listing=soup(c.get('/out_order',query_string={'type':OUT_ALIASES[business]}))
    target=soup(c.get(listing.select_one('.wms-entry-toolbar a.btn-primary')['href']))
    type_field=target.select_one('[name="business_type"]')
    selected=type_field.find('option',selected=True)['value'] if type_field.name=='select' else type_field['value']
    payload=dict(order_id=None,business_type=selected,date=date.today().isoformat(),
        warehouse_id=ids['warehouses'][0],department_id=ids['department'],customer='菜单客户',
        items=[dict(material_id=ids['material'],material_code='MENU-M',quantity=1,price=5)])
    if business=='采购退货出库':
        with w.app.app_context():
            source=w.db.session.get(w.InOrder,ids['in_order']['采购入库'][0])
            source.status='completed'
            payload['source_in_order_id']=source.id
            payload['customer']=source.supplier.name
            payload['items'][0]['source_in_order_item_id']=source.items[0].id
            w.db.session.commit()
    result=c.post('/out_order/add',json=payload)
    assert result.status_code==200 and result.json['status']=='success',result.json
    oid=result.json.get('id') or result.json.get('order_id')
    with w.app.app_context():
        if not oid:oid=w.OutOrder.query.order_by(w.OutOrder.id.desc()).first().id
        saved=w.db.session.get(w.OutOrder,oid)
        assert (saved.business_type,saved.status)==(business,'pending')
        assert w.StockTransaction.query.count()==0 and w.Material.query.one().stock==0
    detail=soup(c.get(f'/out_order/{oid}'))
    title={'领料单':'领料单详情','销售出库':'销售出库单详情','其他出库':'其他出库单详情','采购退货出库':'采购退货单详情'}[business]
    assert detail.title.text==f'{title} - {saved.order_no}'

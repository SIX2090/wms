"""Every document uses the selected Excel file for browser preview, without business writes."""
from datetime import date,datetime
import io
from pathlib import Path
from urllib.parse import urlsplit,parse_qs

from bs4 import BeautifulSoup
from openpyxl import load_workbook
import pytest
from sqlalchemy import String,Integer,Float,Date,DateTime
import app as w

KINDS={
 'purchase_request':('PurchaseRequest','PurchaseRequestItem','purchase_request_id'),
 'purchase_order':('PurchaseOrder','PurchaseOrderItem','purchase_order_id'),
 'sales_order':('SalesOrder','SalesOrderItem','sales_order_id'),
 'after_sale_out':('AfterSaleOutOrder','AfterSaleOutOrderItem','after_sale_out_order_id'),
 'transfer':('TransferOrder','TransferOrderItem','transfer_order_id'),
 'check':('InventoryCheck','InventoryCheckItem','inventory_check_id'),
 'adjustment':('AdjustmentOrder','AdjustmentOrderItem','adjustment_order_id'),
 'requisition':('ProductionRequisition','ProductionRequisitionItem','requisition_id'),
 'subcontract':('SubcontractOrder','SubcontractItem','subcontract_order_id'),
 'subcontract_issue':('SubcontractIssue','SubcontractIssueItem','issue_id'),
 'subcontract_receive':('SubcontractReceive','SubcontractReceiveItem','receive_id'),
 'bom':('BOM','BOMItem','bom_id'),
 'opening_stock':('OpeningStockDoc','OpeningStock','doc_id'),
 'in_order':('InOrder','InOrderItem','in_order_id'),
 'out_order':('OutOrder','OutOrderItem','out_order_id')}


@pytest.fixture
def print_case(tmp_path,monkeypatch):
    monkeypatch.setitem(w.app.config,'TESTING',True);monkeypatch.setitem(w.app.config,'WTF_CSRF_ENABLED',False)
    monkeypatch.setattr(w.app,'static_folder',str(tmp_path))
    with w.app.app_context():
        assert str(w.db.engine.url)=='sqlite:///:memory:'
        w.db.session.remove();w.db.drop_all();w.db.create_all()
        w.db.session.add_all([w.User(id=1,username='print-test',role='admin',password_hash='unused',must_change_password=False),
            w.Unit(id=1,code='PRINT-U',name='台'),w.Warehouse(id=1,code='PRINT-A',name='打印甲仓',status='active',is_default=True),
            w.Warehouse(id=2,code='PRINT-B',name='打印乙仓',status='active'),
            w.Supplier(id=1,code='PRINT-S',name='打印供应商'),w.Customer(id=1,code='PRINT-C',name='打印客户'),
            w.Department(id=1,code='PRINT-D',name='打印领料部')]);w.db.session.flush()
        w.db.session.add(w.Material(id=1,code='PRINT-M',name='打印物料',spec='样例规格',unit_id=1,stock=0));w.db.session.flush()
        counter=0
        def create(name,**values):
            nonlocal counter
            counter+=1;model=getattr(w,name);columns={c.name:c for c in model.__table__.columns};data={}
            for c in columns.values():
                if c.nullable or c.default is not None or c.primary_key:continue
                if isinstance(c.type,DateTime):data[c.name]=datetime(2026,11,7)
                elif isinstance(c.type,Date):data[c.name]=date(2026,11,7)
                elif isinstance(c.type,Integer):data[c.name]=1
                elif isinstance(c.type,Float):data[c.name]=2
                elif isinstance(c.type,String):data[c.name]='PRINT-'+str(counter)
            data.update({k:v for k,v in values.items() if k in columns})
            item=model(**data);w.db.session.add(item);w.db.session.flush();return item
        docs={}
        source=create('SubcontractOrder',order_no='PRINT-SUB-SOURCE',supplier_id=1,warehouse='打印甲仓')
        for code,(model,item,fk) in KINDS.items():
            order=create(model,warehouse='打印甲仓',warehouse_id=1,from_warehouse='打印甲仓',to_warehouse='打印乙仓',
                supplier_id=1,customer_id=1,department_id=1,operator_id=1,subcontract_order_id=source.id,
                customer='打印客户',business_type='采购入库' if code=='in_order' else '领料单',
                adjustment_type='surplus',total_amount=10,total_cost=10)
            create(item,**{fk:order.id},material_id=1,unit_id=1,warehouse_id=1,quantity=2,price=5,amount=10,
                   estimated_price=5,estimated_amount=10,material_name='打印物料',contract_no='PRINT-C-01',
                   system_stock=0,actual_stock=2,difference=2)
            docs[code]=order.id
        w.db.session.commit()
    client=w.app.test_client()
    with client.session_transaction() as s:s['_user_id']='1';s['_fresh']=True
    yield client,docs,tmp_path
    with w.app.app_context():w.db.session.remove()


def prefix(code):return 'sales' if code=='sales_order' else code


@pytest.mark.parametrize('code',KINDS)
def test_register_document_print_routes(print_case,code):
    client,docs,_=print_case;base=f'/{prefix(code)}/{docs[code]}'
    options=client.get(base+'/print_options');assert options.status_code==200,options.get_data(as_text=True)
    dom=BeautifulSoup(options.data,'html.parser');form=dom.select_one('form[action$="/print_preview"]')
    assert form and form['method']=='get' and form['action']==base+'/print_preview'
    assert dom.select_one('#documentPrintTemplate[name="template_id"]')
    preview=client.get(form['action']);assert preview.status_code==200,preview.get_data(as_text=True)
    page=BeautifulSoup(preview.data,'html.parser')
    assert page.select_one('#documentPrintNow') and page.select('section.excel-page')
    assert '打印物料' in page.get_text() or 'PRINT-M' in page.get_text()
    file=client.get(base+'/print_excel');assert file.status_code==200 and 'spreadsheetml' in file.content_type
    assert load_workbook(io.BytesIO(file.data)).worksheets
    assert preview.cache_control.no_store
    with w.app.app_context():
        assert w.StockTransaction.query.count()==0 and w.db.session.get(w.Material,1).stock==0
        assert w.ExcelPrintTemplate.query.count()==0


def custom_template(static,code,name):
    from doc_print_excel import generate_builtin_template
    book=load_workbook(generate_builtin_template('purchase_order' if code in ('in_order','out_order') else code));book.active['A1']=name
    path=static/f'{name}.xlsx';book.save(path)
    with w.app.app_context():
        if code in ('in_order','out_order'):
            model=w.InOrderPrintTemplate if code=='in_order' else w.OutOrderPrintTemplate
            t=model(name=name,template_type='excel',excel_template_path='/static/'+path.name)
        else:
            t=w.ExcelPrintTemplate(name=name,target_type='document',target_code=code,template_type='excel',
                                  excel_template_path='/static/'+path.name)
        w.db.session.add(t);w.db.session.commit();return t.id,path


@pytest.mark.parametrize('code',KINDS)
def test_selected_template_matches_preview_and_download_and_does_not_set_default(print_case,code):
    client,docs,static=print_case
    a,path_a=custom_template(static,code,'模板甲');b,path_b=custom_template(static,code,'模板乙')
    unchanged={p:p.read_bytes() for p in (path_a,path_b)}
    base=f'/{prefix(code)}/{docs[code]}'
    for tid,name,absent in [(a,'模板甲','模板乙'),(b,'模板乙','模板甲')]:
        response=client.get(base+'/print_preview',query_string={'template_id':tid})
        assert response.status_code==200
        page=BeautifulSoup(response.data,'html.parser')
        assert name in page.select_one('.excel-page').get_text() and absent not in page.select_one('.excel-page').get_text()
        link=next(a['href'] for a in page.find_all('a') if '下载 Excel' in a.text)
        assert parse_qs(urlsplit(link).query)['template_id']==[str(tid)]
        file=client.get(link);assert load_workbook(io.BytesIO(file.data)).active['A1'].value==name
    assert all(p.read_bytes()==raw for p,raw in unchanged.items())
    with w.app.app_context():
        for model in (w.ExcelPrintTemplate,w.InOrderPrintTemplate,w.OutOrderPrintTemplate):
            assert not any(t.is_default for t in model.query.all())


@pytest.mark.parametrize('value',['-1','bad','999999','foreign','missing','formula'])
def test_invalid_template_never_prints_an_unrequested_fallback(print_case,value):
    client,docs,static=print_case
    if value in ('foreign','missing','formula'):
        tid,path=custom_template(static,'purchase_order' if value=='foreign' else 'purchase_request','错误模板')
        if value=='missing':path.unlink()
        if value=='formula':
            book=load_workbook(path);book.active['A3']='=1+1';book.save(path)
        value=str(tid)
    response=client.get(f'/purchase_request/{docs["purchase_request"]}/print_preview',query_string={'template_id':value})
    assert response.status_code==400
    dom=BeautifulSoup(response.data,'html.parser');assert dom.select_one('[role="alert"]')
    assert not dom.select_one('#documentPrintNow') and not dom.select('section.excel-page')


def test_print_preview_requires_login_and_existing_document(print_case):
    client,docs,_=print_case
    for path in [f'/purchase_request/{docs["purchase_request"]}/print_options',f'/purchase_request/{docs["purchase_request"]}/print_preview']:
        assert w.app.test_client().get(path).status_code==302
    assert client.get('/purchase_request/999999/print_preview').status_code==404


@pytest.mark.parametrize('code',KINDS)
def test_document_print_menu_has_one_consistent_entry_and_valid_targets(print_case,code):
    client,docs,_=print_case
    path=f'/{prefix(code)}/{docs[code]}' if code not in ('subcontract_issue','subcontract_receive') else '/'+code
    response=client.get(path);assert response.status_code==200
    dom=BeautifulSoup(response.data,'html.parser')
    menu=dom.select_one(f'[data-wms-document-print][data-document-code="{code}"][data-document-id="{docs[code]}"]')
    assert menu is not None,(code,path)
    assert menu['aria-label']=='打印' and menu['title']=='打印'
    assert menu.get_text(strip=True)==('' if code in ('subcontract_issue','subcontract_receive') else '打印')
    assert menu['href']==f'/{prefix(code)}/{docs[code]}/print_options'
    options=client.get(menu['href']);assert options.status_code==200
    page=BeautifulSoup(options.data,'html.parser')
    assert page.select_one('#documentTemplatePreview').get_text(strip=True)=='预览并打印'
    settings=next(a['href'] for a in page.find_all('a') if a.get_text(strip=True)=='模板设置')
    assert client.get(settings).status_code==200
    assert '普通打印' not in response.get_data(as_text=True)


@pytest.mark.parametrize('code',KINDS)
def test_every_document_print_menu_uses_the_same_template_flow(print_case,code):
    with w.app.app_context():
        html=w.app.jinja_env.get_template('_document_print_menu.html').module.document_print_menu(code,1)
    dom=BeautifulSoup(html,'html.parser')
    links=dom.find_all('a')
    assert len(links)==1 and links[0].get_text(strip=True)=='打印'
    assert links[0]['href']==f'/{prefix(code)}/1/print_options'
    assert not dom.find('button') and '普通打印' not in dom.get_text() and '网页打印' not in dom.get_text()


@pytest.mark.parametrize('code',KINDS)
def test_printing_does_not_issue_database_writes(print_case,code):
    from sqlalchemy import event
    client,docs,_=print_case
    base=f'/{prefix(code)}/{docs[code]}'
    def refuse_writes(connection,cursor,statement,parameters,context,executemany):
        assert statement.lstrip().split()[0].upper() not in {'INSERT','UPDATE','DELETE','CREATE','ALTER','DROP','REPLACE'},statement
    with w.app.app_context():
        engine=w.db.engine
        event.listen(engine,'before_cursor_execute',refuse_writes)
        try:
            for suffix in ('print_options','print_preview','print_file','print_excel'):
                response=client.get(base+'/'+suffix)
                assert response.status_code==200,response.get_data(as_text=True) if suffix not in ('print_excel','print_file') else code
        finally:event.remove(engine,'before_cursor_execute',refuse_writes)


@pytest.mark.parametrize('code',['bom','opening_stock','requisition'])
def test_print_heading_uses_the_actual_document_number(print_case,code):
    client,docs,_=print_case
    with w.app.app_context():
        order=w.db.session.get(getattr(w,KINDS[code][0]),docs[code])
        number=getattr(order,{'bom':'bom_no','opening_stock':'doc_no','requisition':'req_no'}[code])
    preview=client.get(f'/{code}/{docs[code]}/print_preview')
    assert preview.status_code==200 and '单号：'+number in preview.get_data(as_text=True)


def test_product_receipt_keeps_its_fixed_twenty_line_pages(print_case):
    client,docs,_=print_case
    with w.app.app_context():
        order=w.db.session.get(w.InOrder,docs['in_order']);order.business_type='产品入库'
        order.items[0].box_no='001-A'
        for i in range(24):
            w.db.session.add(w.InOrderItem(in_order_id=order.id,material_id=1,
                quantity=1,price=2,amount=2,box_no=f'CAB-{i:02}',contract_no='合同-保持文本'))
        w.db.session.commit()
    response=client.get(f'/in_order/{docs["in_order"]}/print_preview')
    assert response.status_code==200,response.get_data(as_text=True)
    dom=BeautifulSoup(response.data,'html.parser');pages=dom.select('section.excel-page')
    assert len(pages)==2
    assert '001-A' in pages[0].get_text() and 'CAB-23' in pages[1].get_text()
    assert 'CAB-23' not in pages[0].get_text()


def test_opening_stock_prints_only_the_selected_document_and_warehouse(print_case):
    client,docs,_=print_case
    with w.app.app_context():
        other=w.OpeningStockDoc(doc_no='QS-OTHER',warehouse_id=2);w.db.session.add(other);w.db.session.flush()
        w.db.session.add_all([w.OpeningStock(doc_id=other.id,material_id=1,warehouse_id=2,quantity=991),
                             w.OpeningStock(material_id=1,warehouse_id=None,quantity=888),
                             w.OpeningStock(doc_id=docs['opening_stock'],material_id=1,warehouse_id=None,
                                            quantity=3,price=2,amount=6)])
        w.db.session.commit()
    response=client.get(f'/opening_stock/{docs["opening_stock"]}/print_preview')
    assert response.status_code==200
    text=BeautifulSoup(response.data,'html.parser').select_one('.excel-page').get_text(' ',strip=True)
    assert '打印甲仓' in text and '打印乙仓' not in text and '991' not in text and '888' not in text
    output=client.get(f'/opening_stock/{docs["opening_stock"]}/print_file')
    sheet=load_workbook(io.BytesIO(output.data)).active
    rows=[r for r in sheet.iter_rows() if r[0].value=='PRINT-M']
    total=next(r for r in sheet.iter_rows() if r[0].value=='合计')
    assert len(rows)==2 and sum(float(r[6].value) for r in rows)==float(total[6].value)==5
    assert sum(float(r[8].value) for r in rows)==float(total[8].value)==16


@pytest.mark.parametrize('code',['purchase_order','in_order','out_order'])
def test_long_selected_template_expands_print_area_and_footer_without_losing_rows(print_case,code):
    from openpyxl import Workbook
    client,docs,static=print_case
    tid,path=custom_template(static,code,'长单模板')
    book=Workbook();s=book.active;s.append(['长单抬头']);s.append(['{item.material.code}','{item.quantity}'])
    s.merge_cells('A3:B3');s['A3']='结尾合计 {total_quantity}';s.print_area='A1:B3';book.save(path)
    with w.app.app_context():
        order=w.db.session.get(getattr(w,KINDS[code][0]),docs[code])
        for i in range(49):
            w.db.session.add(getattr(w,KINDS[code][1])(**{KINDS[code][2]:order.id},material_id=1,quantity=1,price=2,amount=2))
        w.db.session.commit()
    response=client.get(f'/{prefix(code)}/{docs[code]}/print_preview',query_string={'template_id':tid})
    assert response.status_code==200,response.get_data(as_text=True)
    dom=BeautifulSoup(response.data,'html.parser');text=dom.select('.excel-cell')
    assert sum(c.get_text(strip=True)=='PRINT-M' for c in text)==50
    assert sum('结尾合计' in c.get_text() for c in text)==1
    file_url=next(a['href'] for a in dom.find_all('a') if '下载 Excel' in a.get_text())
    wb=load_workbook(io.BytesIO(client.get(file_url).data));sheet=wb.active
    assert '52' in str(sheet.print_area)
    assert 'A52:B52' in {str(m) for m in sheet.merged_cells.ranges}


@pytest.mark.parametrize('kind',['in_order','out_order'])
@pytest.mark.parametrize('business_index',[0,1,2,3])
def test_each_inbound_and_outbound_business_uses_its_own_print_data(print_case,kind,business_index):
    client,docs,_=print_case
    types=['采购入库','产品入库','其他入库','销售退货入库'] if kind=='in_order' else ['领料单','销售出库','其他出库','采购退货出库']
    business=types[business_index]
    with w.app.app_context():
        order=w.db.session.get(w.InOrder if kind=='in_order' else w.OutOrder,docs[kind]);order.business_type=business
        w.db.session.commit()
    base=f'/{kind}/{docs[kind]}'
    page=client.get(base+'/print_preview');assert page.status_code==200,page.get_data(as_text=True)
    assert business.replace('单','') in page.get_data(as_text=True) or (business=='领料单' and '领料单' in page.get_data(as_text=True))
    web=client.get(base+'/print?format=html');assert web.status_code==200
    assert 'printTemplatePreviewLink' not in web.get_data(as_text=True)

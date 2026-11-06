"""Regression locks for the four document-detail follow-ups (business fields)."""
from datetime import date
from html import unescape
import io
import re

from openpyxl import load_workbook
import pytest
import app as w

from tests.test_detail_row_column_context_runtime import TableParser
from tests.test_document_edit_conflicts import revision
from tests.test_web_document_idempotency import receipt_case
from tests.test_product_receipt_sales_conversion import product_sale_case, convert, stocks


def material_table(html):
    tables = [TableParser(block) for block in re.findall(r'<table\b[\s\S]*?</table>',html)]
    return next(table for table in tables if any(cell['text'].strip()=='物料编码' for cell in table.headers))


@pytest.fixture
def sales_documents(receipt_case):
    client, _ = receipt_case
    with w.app.app_context():
        material = w.Material.query.one()
        unit = w.Unit(code='DETAIL-U',name='台'); customer = w.Customer(code='DETAIL-C',name='退货客户甲')
        w.db.session.add_all([unit,customer]); w.db.session.flush(); material.unit_id=unit.id
        warehouse = w.Warehouse.query.one()
        first=w.SalesOrder(order_no='SOURCE-SALE-A',date=date.today(),customer_id=customer.id,
            warehouse=warehouse.name,warehouse_id=warehouse.id,status='confirmed',
            contract_no='HEADER-C',project_name='表头工程',total_amount=35)
        second=w.SalesOrder(order_no='SOURCE-SALE-B',date=date.today(),customer_id=customer.id,
            warehouse=warehouse.name,status='confirmed')
        w.db.session.add_all([first,second]);w.db.session.flush()
        a=w.SalesOrderItem(sales_order_id=first.id,material_id=material.id,quantity=5,shipped_quantity=5,
            price=5,amount=25,contract_no='LINE-C-001',project_name='行工程甲')
        b=w.SalesOrderItem(sales_order_id=first.id,material_id=material.id,quantity=2,price=5,amount=10)
        c=w.SalesOrderItem(sales_order_id=second.id,material_id=material.id,quantity=5,shipped_quantity=5,price=2,amount=10)
        w.db.session.add_all([a,b,c]);w.db.session.commit()
        ids=dict(first=first.id,second=second.id,a=a.id,b=b.id,c=c.id,customer=customer.id,
                 warehouse=warehouse.id,material=material.id)
    return client,ids


def sales_return(ids,status='pending',mode='single'):
    with w.app.app_context():
        order=w.InOrder(order_no='RETURN-DETAIL',date=date.today(),business_type='销售退货入库',
            customer_id=ids['customer'],warehouse='重试仓',status=status,operator_id=1,
            source_sales_order_id=ids['first'] if mode=='single' else None,
            source_sales_order_no='SOURCE-SALE-A' if mode=='single' else ('HISTORIC-SALE' if mode=='historical' else None))
        w.db.session.add(order);w.db.session.flush()
        source_ids=[ids['a'],ids['c']] if mode=='multiple' else [ids['a'] if mode=='single' else None]
        for source_id in source_ids:
            w.db.session.add(w.InOrderItem(in_order_id=order.id,material_id=ids['material'],
                quantity=1,price=5,amount=5,source_sales_order_item_id=source_id))
        w.db.session.commit()
        return order.id


@pytest.mark.parametrize('status',['pending','completed'])
@pytest.mark.parametrize('mode',['single','multiple','historical','manual'])
def test_sales_return_detail_uses_customer_and_actual_sales_sources(sales_documents,status,mode):
    client,ids=sales_documents;oid=sales_return(ids,status,mode)
    response=client.get(f'/in_order/{oid}');assert response.status_code==200
    html=response.get_data(as_text=True);table=material_table(html)
    headings=[c['text'].strip() for c in table.headers]
    assert '原销售订单' in headings
    assert not {'来源采购单','采购数量','已下推','已入库','来源状态'} & set(headings)
    information=html[html.index('<!-- 单据信息 -->'):html.index('<!-- 工具栏 -->')]
    assert '退货客户' in information and '退货客户甲' in information
    assert '来源采购单' not in information and '供应商' not in information
    if mode in ('single','multiple'):
        assert f'/sales/{ids["first"]}' in html and 'SOURCE-SALE-A' in html
    if mode=='multiple':assert f'/sales/{ids["second"]}' in html and 'SOURCE-SALE-B' in html
    if mode=='historical':assert 'HISTORIC-SALE' in information
    if status=='pending':
        form=html[html.index('id="editHeaderForm"'):html.index('</form>',html.index('id="editHeaderForm"'))]
        assert re.search(r'<option[^>]*value="销售退货入库"[^>]*selected',form)
        assert 'name="customer_id"' in form
        assert re.search(r'href="/in_order/add\?type=sales_return(?:&amp;|&)',html)
    with w.app.app_context():assert w.StockTransaction.query.count()==0 and w.Material.query.one().stock==0


def test_sales_return_plain_and_builtin_excel_print_use_return_customer(sales_documents):
    client,ids=sales_documents;oid=sales_return(ids)
    html=client.get(f'/in_order/{oid}/print').get_data(as_text=True)
    assert '退货客户' in html and '退货客户甲' in html and 'SOURCE-SALE-A' in html
    assert '供应商：' not in html
    response=client.get(f'/in_order/{oid}/print_excel');assert response.status_code==200
    book=load_workbook(io.BytesIO(response.data));values=[str(c.value or '') for row in book.active for c in row]
    assert any('退货客户' in v and '退货客户甲' in v for v in values)


def test_sales_order_detail_and_print_preserve_line_contract_project(sales_documents):
    client,ids=sales_documents
    for path in [f'/sales/{ids["first"]}',f'/sales/{ids["first"]}/print']:
        response=client.get(path);assert response.status_code==200
        table=material_table(response.get_data(as_text=True))
        headings=[c['text'].strip() for c in table.headers]
        assert '合同编号' in headings and '工程名称' in headings
        contract,project=headings.index('合同编号'),headings.index('工程名称')
        rows=[r for r in table.rows if len(r['cells'])==len(headings)]
        assert [(r['cells'][contract]['text'].strip(),r['cells'][project]['text'].strip()) for r in rows[:2]]==[
            ('LINE-C-001','行工程甲'),('HEADER-C','表头工程')]


@pytest.mark.parametrize('path',['detail','print','preview','excel'])
def test_get_out_order_box_numbers_are_item_scoped_and_read_only(product_sale_case,path):
    client,source_id,_=product_sale_case
    result=convert(client,source_id);assert result.status_code==200
    oid=result.json['out_order_id']
    with w.app.app_context():before=stocks()
    route={'detail':f'/out_order/{oid}','print':f'/out_order/{oid}/print',
           'preview':f'/out_order/{oid}/preview_template','excel':f'/out_order/{oid}/print_excel'}[path]
    response=client.get(route);assert response.status_code==200
    if path=='excel':
        book=load_workbook(io.BytesIO(response.data));sheet=book.active
        assert '销售出库' in sheet.title
        headings=[c.value for c in sheet[3]];assert '箱体编号' in headings
        column=headings.index('箱体编号')+1
        assert [sheet.cell(row=r,column=column).value for r in [4,5]]==['001-A','002-B']
    else:
        html=response.json['content'] if path=='preview' else response.get_data(as_text=True)
        table=material_table(html);headings=[c['text'].strip() for c in table.headers]
        assert '箱体编号' in headings
        box=headings.index('箱体编号');rows=[r for r in table.rows if len(r['cells'])==len(headings)]
        assert [r['cells'][box]['text'].strip() for r in rows[:2]]==['001-A','002-B']
        if path!='detail':assert '销售出库单' in html and '领料部门' not in html
    with w.app.app_context():assert stocks()==before


def test_released_product_link_does_not_reuse_another_cabinets_number(product_sale_case):
    client,source_id,_=product_sale_case;oid=convert(client,source_id).json['out_order_id']
    with w.app.app_context():
        first=w.DocumentPushLine.query.filter_by(target_document_id=oid,target_document_type='sales_out').order_by(w.DocumentPushLine.id).first()
        first.status='released';w.db.session.commit()
    html=client.get(f'/out_order/{oid}').get_data(as_text=True);table=material_table(html)
    column=[c['text'].strip() for c in table.headers].index('箱体编号')
    rows=[r for r in table.rows if r['attrs'].get('data-id')]
    assert [r['cells'][column]['text'].strip() for r in rows]==['-','002-B']


def test_box_column_absent_on_unlinked_sales_and_requisition(receipt_case):
    client,_=receipt_case
    with w.app.app_context():
        orders=[]
        for business in ['销售出库','领料单']:
            order=w.OutOrder(order_no='NO-BOX-'+str(len(orders)),business_type=business,date=date.today(),warehouse='重试仓',status='pending')
            w.db.session.add(order);w.db.session.flush();orders.append(order.id)
        w.db.session.commit()
    for oid in orders:
        html=client.get(f'/out_order/{oid}').get_data(as_text=True)
        assert '箱体编号' not in [c['text'].strip() for c in material_table(html).headers]


def test_sales_return_header_update_keeps_type_customer_sources_and_stock(sales_documents):
    client,ids=sales_documents;oid=sales_return(ids,mode='multiple')
    response=client.post(f'/in_order/{oid}/update',json=dict(date=date.today().isoformat(),
        business_type='销售退货入库',customer_id=ids['customer'],warehouse_id=ids['warehouse'],
        contract_no='RETURN-C',project_name='退货工程',remark='修改备注'),
        headers={'X-WMS-Document-Revision':revision(client,f'/in_order/{oid}')})
    assert response.status_code==200 and response.json['status']=='success',response.json
    with w.app.app_context():
        order=w.db.session.get(w.InOrder,oid)
        assert (order.business_type,order.customer_id,order.supplier_id)==('销售退货入库',ids['customer'],None)
        assert [i.source_sales_order_item_id for i in order.items]==[ids['a'],ids['c']]
        assert (order.contract_no,order.project_name)==('RETURN-C','退货工程')
        assert w.StockTransaction.query.count()==0 and w.Material.query.one().stock==0


@pytest.mark.parametrize('fault',['wrong-document','wrong-material','orphan-item','blank-box'])
def test_get_out_order_box_numbers_rejects_invalid_source_identity(product_sale_case,fault):
    from services.document_detail import get_out_order_box_numbers
    client,source_id,_=product_sale_case;oid=convert(client,source_id).json['out_order_id']
    with w.app.app_context():
        before=stocks()
        order=w.db.session.get(w.OutOrder,oid)
        links=w.DocumentPushLine.query.filter_by(target_document_id=oid,target_document_type='sales_out').order_by(w.DocumentPushLine.id).all()
        link=links[0];target=link.target_item_id;source=w.db.session.get(w.InOrderItem,link.source_item_id)
        if fault=='wrong-document':link.source_document_id=source_id+999
        elif fault=='wrong-material':source.material_id=source.material_id+999
        elif fault=='orphan-item':link.source_item_id=source.id+999
        else:source.box_no=''
        w.db.session.flush()
        result=get_out_order_box_numbers(order)
        assert result.get(links[1].target_item_id)=='002-B'
        assert (target in result and result[target]=='') if fault=='blank-box' else target not in result
        assert stocks()==before
        w.db.session.rollback()


def test_get_out_order_box_numbers(product_sale_case):
    from services.document_detail import get_out_order_box_numbers
    from sqlalchemy import event
    client,source_id,_=product_sale_case;oid=convert(client,source_id).json['out_order_id']
    with w.app.app_context():
        order=w.db.session.get(w.OutOrder,oid);items=list(order.items);statements=[]
        def record(conn,cursor,statement,parameters,context,executemany):statements.append(statement)
        event.listen(w.db.engine,'before_cursor_execute',record)
        try:result=get_out_order_box_numbers(order)
        finally:event.remove(w.db.engine,'before_cursor_execute',record)
        assert result=={items[0].id:'001-A',items[1].id:'002-B'}
        assert len(statements)==1
        assert not w.db.session.dirty and not w.db.session.new


def test_product_sales_print_defaults_and_explicit_excel_box_placeholder(product_sale_case,tmp_path,monkeypatch):
    from openpyxl import Workbook
    import print_fill
    client,source_id,_=product_sale_case;oid=convert(client,source_id).json['out_order_id']
    template_path=tmp_path/'cabinet-template.xlsx';book=Workbook();sheet=book.active
    sheet.append(['箱体编号','物料编码']);sheet.append(['{item.box_no}','{item.material.code}']);book.save(template_path)
    monkeypatch.setattr(print_fill,'template_file_abspath',lambda *args:str(template_path))
    with w.app.app_context():
        source=w.db.session.get(w.InOrder,source_id);source.items[0].box_no='=001+A'
        template=w.OutOrderPrintTemplate(name='自定义箱体',template_type='excel',excel_template_path='/static/uploads/print_templates/cabinet-template.xlsx',is_default=True)
        w.db.session.add(template);w.db.session.commit();template_id=template.id;before=stocks()
    # A generic default does not hide the cabinet column; both HTML aliases retain it.
    for route in ['print','print_with_template','preview_template']:
        response=client.get(f'/out_order/{oid}/{route}');assert response.status_code==200
        html=response.json['content'] if route=='preview_template' else response.get_data(as_text=True)
        assert '箱体编号' in html and '=001+A' in html and '002-B' in html
    for suffix,column,first_row in [('',1,4),(f'?template_id={template_id}',1,2)]:
        response=client.get(f'/out_order/{oid}/print_excel{suffix}');assert response.status_code==200
        book=load_workbook(io.BytesIO(response.data));sheet=book.active
        assert sheet.cell(first_row,column).value=='=001+A'
        assert sheet.cell(first_row,column).data_type=='s'
        assert sheet.cell(first_row+1,column).value=='002-B'
    with w.app.app_context():
        assert stocks()==before
        assert 'box_no' not in w.OutOrderItem.__table__.columns


@pytest.mark.parametrize('mode',['multiple','historical','manual'])
def test_sales_return_print_sources_preserve_saved_history(sales_documents,mode):
    client,ids=sales_documents;oid=sales_return(ids,mode=mode)
    for route in ['print','print_with_template','preview_template']:
        response=client.get(f'/in_order/{oid}/{route}');assert response.status_code==200
        html=response.json['content'] if route=='preview_template' else response.get_data(as_text=True)
        assert '原销售订单' in html and '退货客户甲' in html and '供应商：' not in html
        for value in {'multiple':['SOURCE-SALE-A','SOURCE-SALE-B'],'historical':['HISTORIC-SALE'],'manual':[]}[mode]:assert value in html


def test_normal_sales_default_excel_preview_keeps_sales_title_customer_and_signature(receipt_case):
    client,_=receipt_case
    with w.app.app_context():
        order=w.OutOrder(order_no='SALE-PRINT-TYPE',business_type='销售出库',customer='销售客户乙',date=date.today(),warehouse='重试仓',status='pending')
        w.db.session.add_all([order,w.OutOrderPrintTemplate(name='通用出库默认',template_type='excel',excel_template_path='/not-a-real-template.xlsx',is_default=True)])
        w.db.session.commit();oid=order.id
    html=client.get(f'/out_order/{oid}/print').get_data(as_text=True)
    assert '销售出库单' in html and '客户：销售客户乙' in html and '收货：' in html
    assert '领料部门：' not in html and 'sig-cell">领料：' not in html


def test_multiple_active_boxes_for_one_target_are_distinct_and_stable(product_sale_case):
    from services.document_detail import get_out_order_box_numbers
    client,source_id,_=product_sale_case;oid=convert(client,source_id).json['out_order_id']
    with w.app.app_context():
        order=w.db.session.get(w.OutOrder,oid)
        links=w.DocumentPushLine.query.filter_by(target_document_id=oid,target_document_type='sales_out').order_by(w.DocumentPushLine.id).all()
        links[1].target_item_id=links[0].target_item_id;w.db.session.flush()
        assert get_out_order_box_numbers(order)=={links[0].target_item_id:'001-A、002-B'}
        w.db.session.rollback()

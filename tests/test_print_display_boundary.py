"""A08 correct behavior: immutable display facts, no object traversal or business writes."""
from datetime import date
from decimal import Decimal
import hashlib
import io
from types import SimpleNamespace as NS

from openpyxl import Workbook, load_workbook
import pytest
from sqlalchemy import event
import app as w
from print_fill import _Filler, apply_print_template_grid, validate_template_file
from tests.test_document_print_flow import KINDS, custom_template, prefix, print_case


def workbook_bytes(token):
    book=Workbook();book.active['A1']='Display boundary';book.active['A2']=token
    stream=io.BytesIO();book.save(stream);book.close();return stream.getvalue()


def test_resolve():
    from print_display import PrintFieldError, _project
    source=NS(code='001-A',quantity=0,spec=None,secret='must not be visible')
    view=_project(source,frozenset(['code','quantity','spec']))
    source.code='changed';source.quantity=9;source.spec='late update'
    assert view.resolve('code')=='001-A'
    assert view.resolve('quantity')==0 and view.resolve('spec') is None
    for path in ['secret','query.delete','__class__','material.password_hash']:
        with pytest.raises(PrintFieldError,match='占位符字段'):
            view.resolve(path)


@pytest.mark.parametrize('path',[
 'order.operator.password_hash','order.operator.api_tokens','order.operator.get_id',
 'order.query.delete','order.__class__','order._sa_instance_state',
 'order.unknown_display_field','item.material.query.delete','item.material.__dict__',
 'item.material.supplier.password_hash','item.unknown_display_field',
 'img_barcode:order.operator.password_hash','img_qrcode:item.material.__class__',
])
def test_validate_template_file_rejects_non_display_paths(path):
    message=validate_template_file(workbook_bytes('{'+path+'}'))
    assert message and '占位符' in message and path in message


@pytest.mark.parametrize('path',['order.operator.password_hash','order.query.delete','item.__class__','img_qrcode:item.unknown_display_field'])
def test_apply_print_template_grid_rejects_non_display_paths(tmp_path,path):
    template=tmp_path/'grid.xlsx';template.write_bytes(workbook_bytes('{order.order_no}'))
    before=template.read_bytes()
    with pytest.raises(ValueError,match='占位符'):
        apply_print_template_grid(str(template),[{'name':'Sheet','upserts':[[2,1,'{'+path+'}']]}])
    assert template.read_bytes()==before


def test_filler_never_calls_a_callable_even_under_a_valid_display_name():
    calls=[]
    def dangerous():calls.append(True);return 'must not run'
    with pytest.raises(ValueError,match='字段|占位符|调用'):
        filler=_Filler(NS(order_no=dangerous,total_amount=0),[],None)
        filler.order_value('order.order_no')
    assert not calls


def test_filler_freezes_approved_order_and_line_values_before_template_evaluation():
    supplier=NS(name='Original supplier');material=NS(code='M-001',name='Original material',unit=NS(name='台'))
    item=NS(material=material,quantity=2,price=Decimal('3.5'),amount=7,box_no='001-A')
    order=NS(order_no='ORIGINAL-001',supplier=supplier,total_amount=7,date=date(2026,11,8))
    filler=_Filler(order,[item],'2026-11-08')
    order.order_no='Changed';supplier.name='Changed';material.name='Changed';item.quantity=99
    assert filler.order_value('order.order_no')=='ORIGINAL-001'
    assert filler.order_value('order.supplier.name')=='Original supplier'
    assert filler.item_value('item.material.name',filler.items[0])=='Original material'
    assert filler.order_value('total_quantity')==2


@pytest.mark.parametrize('legacy,current,value',[
    ('supplier_name','supplier.name','Legacy supplier'),
    ('customer_name','customer.name','Legacy customer'),
    ('operator_name','operator.username','Legacy operator'),
])
def test_legacy_display_names_map_to_approved_current_facts(legacy,current,value):
    source=NS(total_amount=0,supplier=NS(name='Legacy supplier'),
              customer=NS(name='Legacy customer'),operator=NS(username='Legacy operator'))
    filler=_Filler(source,[],None)
    assert filler.order_value('order.'+legacy)==value
    assert filler.order_value('order.'+current)==value


@pytest.mark.parametrize('legacy,source_name',[
    ('supplier_name','supplier'),('customer_name','customer'),
])
def test_legacy_display_name_keeps_existing_text_party_fields(legacy,source_name):
    source=NS(total_amount=0,**{source_name:'Legacy text party'})
    assert _Filler(source,[],None).order_value('order.'+legacy)=='Legacy text party'


def test_display_attribute_compatibility_contains_only_frozen_approved_facts():
    source=NS(material=NS(code='M-001'),purchase_order=NS(order_no='PO-001'),
              received_quantity=4,quantity=10,price=2)
    row=_Filler(NS(total_amount=20),[source],None).items[0]
    source.material.code='CHANGED';source.purchase_order.order_no='CHANGED'
    source.received_quantity=999;source.quantity=999
    assert row.received_quantity==4 and row.quantity==10 and row.price==2
    assert row.material.code=='M-001' and row.purchase_order.order_no=='PO-001'
    for obj,name in [(row,'query'),(row.material,'query'),(row.purchase_order,'operator')]:
        with pytest.raises(AttributeError):getattr(obj,name)
    with pytest.raises(AttributeError):row.material.code='cannot write'


@pytest.mark.parametrize('token',['order.query.delete','order.operator.password_hash','item.material.query.delete'])
def test_filler_rejects_paths_even_when_a_supplied_object_has_them(token):
    calls=[]
    def remove():calls.append(True);return 1
    obj=NS(order_no='safe',total_amount=0,query=NS(delete=remove),operator=NS(username='public',password_hash='synthetic-only'))
    row=NS(quantity=1,material=NS(code='safe',query=NS(delete=remove)))
    with pytest.raises(ValueError,match='字段|占位符'):
        filler=_Filler(obj,[row],None)
        if token.startswith('item.'):filler.item_value(token,filler.items[0])
        else:filler.order_value(token)
    assert not calls


def test_filler_preserves_scalar_types_and_literal_cabinet_identifiers():
    filler=_Filler(NS(order_no='001-A',date=date(2026,11,8),total_amount=7),
                   [NS(quantity=2,box_no='=001-A',price=3.5,amount=7)],'2026-11-08')
    book=Workbook();sheet=book.active
    sheet.append(['{order.order_no}','{order.date}','{total_amount}'])
    sheet.append(['{item.box_no}','{item.quantity}','{item.price}'])
    filler.fill(sheet)
    assert sheet['A1'].value=='001-A' and sheet['B1'].value=='2026-11-08'
    assert sheet['C1'].value==7 and sheet['B2'].value==2 and sheet['C2'].value==3.5
    assert sheet['A2'].value=='=001-A' and sheet['A2'].data_type=='s'


@pytest.mark.parametrize('token',['item.unknown_display_field','img_qrcode:item.material.__class__'])
def test_empty_lines_cannot_silently_clear_an_invalid_placeholder(token):
    sheet=Workbook().active;sheet['A1']='{'+token+'}'
    with pytest.raises(ValueError,match='字段|占位符'):
        _Filler(NS(order_no='EMPTY',total_amount=0),[],None).fill(sheet)


def test_render_report_keeps_explicit_server_declared_flat_columns(tmp_path,monkeypatch):
    import doc_print_excel as dpe
    monkeypatch.setattr(dpe,'resolve_excel_template',lambda *a,**k:None)
    columns=[{'field':'approved_code','title':'服务端展示编码'},{'field':'quantity','title':'数量'}]
    result=dpe.render_report_excel_print('boundary-demo','合法报表',columns,
                [{'approved_code':'REPORT-001','quantity':3}],static_folder=str(tmp_path))
    book=load_workbook(result[0]);values=[cell.value for sheet in book for row in sheet for cell in row]
    assert 'REPORT-001' in values and 3 in values
    assert not any(isinstance(value,str) and '{item.' in value for value in values)
    book.close()


SCENARIOS=[(code,None) for code in KINDS if code not in ('in_order','out_order')]+[
 ('in_order',value) for value in ['采购入库','产品入库','其他入库','销售退货入库']]+[
 ('out_order',value) for value in ['领料单','销售出库','其他出库','采购退货出库']]
assert len(SCENARIOS)==21


def set_business(code,business,docs):
    if business:
        with w.app.app_context():
            w.db.session.get(w.InOrder if code=='in_order' else w.OutOrder,docs[code]).business_type=business
            w.db.session.commit()


def all_table_hashes():
    with w.app.app_context():
        result={}
        for table in w.db.metadata.sorted_tables:
            rows=sorted(repr(tuple(row)) for row in w.db.session.execute(table.select()))
            result[table.name]=hashlib.sha256(repr(rows).encode()).hexdigest()
        return result


@pytest.mark.parametrize('code,business',SCENARIOS)
def test_all_twenty_one_document_print_paths_preserve_all_business_tables(print_case,code,business):
    client,docs,_=print_case;set_business(code,business,docs)
    before=all_table_hashes();writes=[]
    def reject(connection,cursor,statement,parameters,context,executemany):
        first=statement.lstrip().split()[0].upper()
        if first in {'INSERT','UPDATE','DELETE','REPLACE','CREATE','DROP','ALTER'}:
            writes.append(statement);raise AssertionError('Printing must never issue a business write')
    with w.app.app_context():
        engine=w.db.engine;event.listen(engine,'before_cursor_execute',reject)
        try:
            for suffix in ['print_options','print_preview','print_file','print_excel']:
                response=client.get(f'/{prefix(code)}/{docs[code]}/{suffix}')
                assert response.status_code==200,(code,business,suffix,response.status_code)
        finally:event.remove(engine,'before_cursor_execute',reject)
    assert not writes and all_table_hashes()==before


@pytest.mark.parametrize('code',KINDS)
def test_saved_legacy_sensitive_template_is_explicitly_rejected_by_preview_and_download(print_case,code):
    client,docs,static=print_case
    tid,path=custom_template(static,code,'Legacy-sensitive-'+code)
    book=load_workbook(path);book.active['A1']='{order.operator.password_hash}';book.save(path);book.close()
    raw=path.read_bytes();before=all_table_hashes()
    for suffix in ['print_preview','print_file','print_excel']:
        response=client.get(f'/{prefix(code)}/{docs[code]}/{suffix}',query_string={'template_id':tid})
        assert response.status_code==400,(code,suffix,response.status_code)
        message=response.json.get('msg','') if response.is_json else response.get_data(as_text=True)
        assert '占位符' in message or '字段' in message
        assert 'order.operator.password_hash' in message
    assert path.read_bytes()==raw and all_table_hashes()==before

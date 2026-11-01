"""Field-level extraction guards; sample scores cannot hide a lost correct line."""
import json
from pathlib import Path

import pytest

from ai.documents.extractor import extract_from_text, extract_from_excel_table

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((ROOT/'samples/ai_documents').glob('*.json'))]
TEXT_SAMPLES = [s for s in SAMPLES if s.get('source_category') in ('wechat_text','excel') and s.get('source_text')]


@pytest.mark.parametrize('name', ['开关','开关电源','发电机','送风机','生成器','创建按钮','入库阀','出库闸'])
def test_material_names_are_not_command_prefixes(name):
    doc = extract_from_text(name + ' 20台')
    assert [(i.name,i.quantity,i.unit) for i in doc.lines] == [(name,20,'台')]
    assert doc.needs_confirmation and all(i.needs_confirmation for i in doc.lines)


@pytest.mark.parametrize('text,code,name,spec,quantity,unit', [
    ('SW-10A 开关 10A 250V 500个','SW-10A','开关','10A 250V',500,'个'),
    ('WIRE-2.5 导线 2.5mm² 100米','WIRE-2.5','导线','2.5mm²',100,'米'),
    ('A001 轴承 6204-2RS 2套','A001','轴承','6204-2RS',2,'套'),
    ('6204 轴承 6204-2RS 20套','6204','轴承','6204-2RS',20,'套'),
])
def test_identifier_spec_and_quantity_fields_remain_separate(text,code,name,spec,quantity,unit):
    doc = extract_from_text(text)
    assert len(doc.lines) == 1
    item = doc.lines[0]
    assert (item.code,item.name,item.spec,item.quantity,item.unit) == (code,name,spec,quantity,unit)


@pytest.mark.parametrize('text', ['A0012套','开关 -2台','开关 0台','开关 1000000001台'])
def test_no_guessing_ambiguous_codes_or_invalid_quantities(text):
    assert extract_from_text(text).lines == []


def test_explicit_sender_heading_is_not_lost_or_material_data():
    doc = extract_from_text('【鑫达五金】明天发货清单：\nSW-10A 开关 500个')
    assert doc.header.supplier == '鑫达五金'
    assert doc.header.document_type.value == 'in_order'
    assert [(i.code,i.name,i.quantity) for i in doc.lines] == [('SW-10A','开关',500)]


def test_placeholder_sender_is_not_a_real_supplier():
    assert extract_from_text('【供应商】明天发货清单：\nA001 轴承 2套').header.supplier == ''


def test_excel_header_is_not_an_inventory_line_and_line_numbers_are_contiguous():
    text='物料编码\t物料名称\t规格\t数量\t单位\nA001\t开关\t10A\t2\t个\n物料编码\t物料名称\t规格\t数量\t单位\nB002\t导线\t2.5mm²\t3\t米'
    doc=extract_from_excel_table(text)
    assert [(i.line_no,i.code,i.name,i.spec,i.quantity,i.unit) for i in doc.lines] == [(1,'A001','开关','10A',2,'个'),(2,'B002','导线','2.5mm²',3,'米')]


def test_headerless_excel_remains_supported():
    doc=extract_from_excel_table('A001\t开关\t10A\t2\t个')
    assert len(doc.lines)==1 and doc.lines[0].code=='A001' and doc.lines[0].quantity==2


def test_reaffirmation_does_not_add_a_third_copy_or_merge_two_real_lines():
    doc=extract_from_text('SW-10A 开关 500个\nSW-10A 开关 500个\n再确认一下 SW-10A 开关 500个')
    assert [(i.code,i.name,i.quantity) for i in doc.lines] == [('SW-10A','开关',500),('SW-10A','开关',500)]


def test_changed_reaffirmation_keeps_uncertain_alternative_for_human_review():
    doc=extract_from_text('SW-10A 开关 500个\n再确认一下 SW-10A 开关 600个')
    assert [i.quantity for i in doc.lines]==[500,600]
    assert doc.needs_confirmation and all(i.needs_confirmation for i in doc.lines)


@pytest.mark.parametrize('sample', TEXT_SAMPLES, ids=lambda s:s['sample_id'])
def test_all_43_explicit_quantity_sequences_match_without_scoring_other_fields(sample):
    doc=(extract_from_excel_table if sample['source_category']=='excel' else extract_from_text)(sample['source_text'])
    assert [i.quantity for i in doc.lines] == [i['quantity'] for i in sample['expected']['items']]


@pytest.mark.parametrize('sample', [s for s in TEXT_SAMPLES if s['expected'].get('supplier') and s['expected']['supplier'] in s['source_text']], ids=lambda s:s['sample_id'])
def test_suppliers_explicitly_present_in_source_are_preserved(sample):
    doc=(extract_from_excel_table if sample['source_category']=='excel' else extract_from_text)(sample['source_text'])
    assert doc.header.supplier==sample['expected']['supplier']


@pytest.mark.parametrize('sample', TEXT_SAMPLES, ids=lambda s:s['sample_id'])
def test_explicit_code_name_pairs_survive_and_are_not_quantity_digits(sample):
    doc=(extract_from_excel_table if sample['source_category']=='excel' else extract_from_text)(sample['source_text'])
    for expected in sample['expected']['items']:
        code,name=expected.get('code',''),expected.get('name','')
        text=sample['source_text']
        if code and name and (code+' '+name in text or code+'\t'+name+'\t' in text):
            assert any(i.code==code and i.name==name and i.quantity==expected['quantity'] for i in doc.lines), (sample['sample_id'],code,name)

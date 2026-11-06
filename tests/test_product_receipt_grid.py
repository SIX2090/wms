"""Execute the shipped TSV parser, including empty cells and quoted Excel data."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def _node(body):
    source = ROOT / 'app/static/js/product-receipt-grid.js'
    result = subprocess.run(['node', '-e', 'const grid=require(' + json.dumps(str(source)) + ');' + body],
                            capture_output=True, text=True, encoding='utf-8', check=True)
    return json.loads(result.stdout)


def test_product_clipboard_five_columns_row_and_column():
    result = _node(r'''
const keys=['material_code','box_no','material_name','spec','unit','quantity','price'];
process.stdout.write(JSON.stringify({
 block:grid.planPaste('A\t配电柜\t800*675*2345\t台\t1\r\nB\t配电柜\t800*675*2345\t台\t2\r\n',keys,'box_no'),
 column:grid.planPaste('A\r\nB\r\nC\r\n',keys,'box_no'),
 row:grid.planPaste('配电箱\t800*330*1090\t台\t3',keys,'material_name'),
 empty:grid.planPaste('\t配电柜\t\t台\t1',keys,'box_no')
}));
''')
    assert result['block'] == [dict(box_no='A', material_name='配电柜', spec='800*675*2345', unit='台', quantity='1'),
                               dict(box_no='B', material_name='配电柜', spec='800*675*2345', unit='台', quantity='2')]
    assert result['column'] == [dict(box_no='A'), dict(box_no='B'), dict(box_no='C')]
    assert result['row'] == [dict(material_name='配电箱', spec='800*330*1090', unit='台', quantity='3')]
    assert result['empty'][0]['box_no'] == '' and result['empty'][0]['spec'] == ''


def test_product_clipboard_roundtrip_multiline_quotes_leading_zero_and_headers():
    result = _node(r'''
const cells=[['001-A','配电"柜','一行\n二行','台','1'],['002','柜','带\t制表符','台','2']];
process.stdout.write(JSON.stringify({rows:grid.parseTsv(grid.toTsv(cells)),
 headers:grid.planPaste('箱体编号\t设备名称\t规格\t单位\t数量\n001\t配电柜\tX\t台\t1',['box_no'],'box_no')}));
''')
    assert result['rows'] == [['001-A', '配电"柜', '一行\n二行', '台', '1'], ['002', '柜', '带\t制表符', '台', '2']]
    assert result['headers'] == [dict(box_no='001', material_name='配电柜', spec='X', unit='台', quantity='1')]


def test_product_clipboard_rejects_invalid_block_before_any_mutation():
    result = _node(r'''
const cases=[['1\n-2',['quantity'],'quantity'], ['abc',['price'],'price'],
 ['1.234',['quantity'],'quantity'],['2026-02-31',['expiry_date'],'expiry_date'],
 ['a\tb',['box_no'],'box_no'],['"unclosed',['box_no'],'box_no'],
 [Array(1002).fill('a').join('\n'),['box_no'],'box_no']];
process.stdout.write(JSON.stringify(cases.map(args=>{try {grid.planPaste(...args);return false;}catch(e){return !!e.message;}})));
''')
    assert result == [True] * 7

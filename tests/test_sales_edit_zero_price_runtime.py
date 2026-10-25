"""Exercise real sales edit row creation and entry handlers without changing zero prices."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _block(source, marker):
    start = source.index(marker)
    opening = source.index('{', start)
    depth = 0
    for end in range(opening, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return source[start:end + 1]
    raise AssertionError(marker)


CASES = [
    ('load', 0, 0), ('load', '0', 0), ('load', '0.00', 0),
    ('load', '19.95', 19.95), ('load', 'missing', 125),
    ('load', None, 125), ('load', '', 125),
    ('copy', '0', 0), ('copy', '19.95', 19.95),
    ('template', '0', 0), ('template', '19.95', 19.95),
    ('template', 'missing', 125), ('template', None, 125),
    ('paste', '0', 0), ('paste', '19.95', 19.95), ('paste', '', 125),
    ('new', 'missing', 125), ('recent', 'missing', 125),
    ('change', '0', 0), ('change', '19.95', 19.95),
]


@pytest.mark.parametrize('entry,price,expected', CASES)
def test_sales_edit_preserves_explicit_prices_and_defaults_only_missing(entry, price, expected):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for actual sales edit entry handlers')
    source = (ROOT / 'app/templates/sales_order_edit.html').read_text(encoding='utf-8')
    functions = [
        'var unitName = function(', 'var findMaterial = function(',
        'function recalcRow(', 'function recalc(', 'function fillRow(',
        'function selectMaterial(', 'function addRow(', 'function renumber(',
        'function collect(', 'function ensureBlankRows(',
    ]
    script = '\n'.join(_block(source, marker) + ';' for marker in functions)
    for start, end in [
        ("document.getElementById('copyRowBtn').addEventListener", "document.getElementById('pasteBtn').addEventListener"),
        ("document.getElementById('pasteBtn').addEventListener", "document.addEventListener('click'"),
        ("document.getElementById('recentBtn').addEventListener", "document.getElementById('saveTemplateBtn').addEventListener"),
        ("document.getElementById('templateSelect').addEventListener", "document.getElementById('refreshMaterialsBtn').addEventListener"),
    ]:
        script += '\n' + source[source.index(start):source.index(end, source.index(start))]
    program = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const p=JSON.parse(fs.readFileSync(0,'utf8')),rows=[],totals={},buttons={},handlers={},storage={};
function element(value='') {
    let current=String(value);
    return {get value(){return current;},set value(v){current=String(v);},
        textContent:'',style:{},dataset:{},focus(){},select(){},
        addEventListener(){},querySelectorAll(){return [];}};
}
function makeRow() {
    const fields={},row={dataset:{},querySelector:s=>fields[s],
        querySelectorAll:s=>s==='input'?Object.values(fields).filter(x=>x.isInput):[],remove(){}};
    Object.defineProperty(row,'innerHTML',{set(html){
        for(const m of html.matchAll(/<(input|div|button|td)\b([^>]*)>/g)) {
            const classes=m[2].match(/class="([^"]*)"/);if(!classes)continue;
            const value=m[2].match(/\bvalue="([^"]*)"/),n=element(value?value[1]:'');
            n.isInput=m[1]==='input';for(const c of classes[1].split(' '))fields['.'+c]=n;
        }
    }});
    return row;
}
const body={appendChild:r=>rows.push(r),
    querySelectorAll:s=>s==='tr'?rows:s==='.row-no'?rows.map(r=>r.querySelector(s)):[],
    querySelector:s=>s==='tr .material-code'?rows[0]?.querySelector('.material-code'):
        s==='tr:last-child'?rows.at(-1):s==='tr'?rows[0]:null};
Object.defineProperty(body,'innerHTML',{set(v){assert.equal(v,'');rows.length=0;}});
const ctx={body,defaultTaxRate:0.13,activeDropdown:null,
    materials:[{code:'FREE',name:'Fixture material',spec:'M8',unit:'PCS',price:125},
        {code:'OTHER',name:'Other fixture',spec:'M10',unit:'PCS',price:300}],
    formFields:['customer_id'],SALES_RECENT_KEY:'recent',SALES_TEMPLATE_KEY:'templates',
    escAttr:v=>String(v),handleKeydown(){},showDropdown(){},
    localStorage:{getItem:k=>storage[k]??null},navigator:{clipboard:{readText:()=>Promise.resolve(p.clipboard)}},
    document:{createElement:()=>makeRow(),querySelector:()=>({value:'2'}),
        getElementById:id=>{
            if(id==='copyRowBtn'||id==='pasteBtn'||id==='recentBtn'||id==='templateSelect')
                return buttons[id]??=(Object.assign(element(),{addEventListener:(event,fn)=>handlers[id]=fn}));
            return totals[id]??=element();
        }},window:{}};
vm.createContext(ctx);vm.runInContext(p.script,ctx);
const item={code:'FREE',quantity:2,tax_rate:0,batch_no:'B1',remark:'fixture'};
if(p.price!=='missing')item.price=p.price;
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
    let row;
    if(p.entry==='load') row=ctx.addRow(item);
    if(p.entry==='copy') {
        // Set the entered price after creation so this independently exercises copy.
        row=ctx.addRow({...item,price:9});row.querySelector('.price').value=p.price;
        handlers.copyRowBtn();row=rows.at(-1);
    }
    if(p.entry==='template') {
        storage.templates=JSON.stringify([{items:[item]}]);buttons.templateSelect.value='0';
        handlers.templateSelect.call(buttons.templateSelect);row=rows[0];
    }
    if(p.entry==='paste') {
        row=ctx.addRow();handlers.pasteBtn();await flush();
    }
    if(p.entry==='new') {row=ctx.addRow({quantity:2});ctx.selectMaterial(row,'FREE');}
    if(p.entry==='recent') {
        row=ctx.addRow({quantity:2});storage.recent=JSON.stringify(['FREE']);handlers.recentBtn();
    }
    if(p.entry==='change') {
        row=ctx.addRow({...item,price:9});row.querySelector('.price').value=p.price;
        ctx.selectMaterial(row,'OTHER');
        assert.equal(row.querySelector('.material-code').value,'OTHER');
    }
    const result=ctx.collect(),actual=result.items.find(i=>i.code);
    assert(actual,'actual collect must include the material row');
    assert.equal(Number(row.querySelector('.price').value),p.expected,'visible explicit zero must survive row fill');
    assert.equal(Number(actual.price),p.expected,'actual collect payload must preserve the same price');
    const expectedRate=p.entry==='new'||p.entry==='recent'?0.13:0;
    assert.equal(Number(actual.tax_rate),expectedRate,'tax rate is unchanged');
    const quantity=Number(actual.quantity),total=quantity*p.expected;
    assert.equal(Number(row.querySelector('.included').textContent),total,'line amount uses preserved price');
    const populatedCount=p.entry==='copy'?2:1;
    assert.equal(Number(totals.totalIncluded.textContent),total*populatedCount,'totals include every populated row');
    assert.equal(Number(totals.totalUntaxed.textContent),Number((total/(1+expectedRate)).toFixed(2))*populatedCount);
    assert.equal(Number(totals.totalTax.textContent),Number((total-total/(1+expectedRate)).toFixed(2))*populatedCount);
    assert.equal(actual.batch_no,p.entry==='new'||p.entry==='recent'?'':'B1');
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    completed = subprocess.run([node, '-e', program], input=json.dumps({
        'script': script, 'entry': entry, 'price': price, 'expected': expected,
        'clipboard': 'FREE\t2\t' + (str(price) if price is not None else '') + '\t0\tB1',
    }), encoding='utf-8', capture_output=True, timeout=15)
    assert completed.returncode == 0, completed.stderr

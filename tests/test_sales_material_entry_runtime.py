"""Execute actual sales entry consumers, retaining history outside the choice cache."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from tests.test_sales_collection_boundary_runtime import _block

ROOT = Path(__file__).resolve().parents[1]
CASES = [(page, entry) for page in ['add', 'edit']
         for entry in ['exact', 'dropdown', 'recent', 'template', 'paste', 'bad_template']]
CASES.append(('edit', 'history'))


@pytest.mark.parametrize('page,entry', CASES)
def test_sales_tail_material_entries_and_history(page, entry):
    source = (ROOT / f'app/templates/sales_order_{page}.html').read_text(encoding='utf-8')
    markers = ['var unitName = function(', 'var findMaterial = function(',
               'function recalcRow(', 'function recalc(', 'function fillRow(',
               'function showDropdown(', 'function selectMaterial(', 'function addRow(',
               'function renumber(', 'function collect(', 'function ensureBlankRows(']
    script = '\n'.join(_block(source, marker) + ';' for marker in markers)
    if 'var formatStock = function(' in source:
        script += '\n' + _block(source, 'var formatStock = function(') + ';'
    for button in ['recentBtn', 'templateSelect', 'pasteBtn']:
        script += '\n' + _block(source, f"document.getElementById('{button}').addEventListener") + ');'
    program = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const p=JSON.parse(fs.readFileSync(0,'utf8')),rows=[],buttons={},handlers={},storage={},status={textContent:''};
function element(value='') {
 let current=String(value);
 const node={get value(){return current;},set value(v){current=String(v);},textContent:'',style:{},dataset:{},validity:{badInput:false},events:{},
   focus(){},select(){},addEventListener(e,fn){const before=this.events[e];this.events[e]=(...a)=>{if(before)before(...a);fn(...a);};},querySelectorAll(){return [];}};
 return node;
}
function makeRow(){
 const fields={},row={dataset:{},querySelector:s=>fields[s],
   querySelectorAll:s=>s==='input'?Object.values(fields).filter(x=>x.isInput):[],remove(){}};
 Object.defineProperty(row,'innerHTML',{set(html){
  for(const m of html.matchAll(/<(input|div|button|td)\b([^>]*)>/g)){
   const classes=m[2].match(/class="([^"]*)"/);if(!classes)continue;
   const value=m[2].match(/\bvalue="([^"]*)"/),n=element(value?value[1]:'');n.isInput=m[1]==='input';
   for(const c of classes[1].split(' '))fields['.'+c]=n;
  }
 }});return row;
}
const body={appendChild:r=>rows.push(r),querySelectorAll:s=>s==='tr'?rows:s==='.row-no'?rows.map(r=>r.querySelector(s)):[],
 querySelector:s=>s==='tr .material-code'?rows[0]?.querySelector('.material-code'):s==='tr:last-child'?rows.at(-1):s==='tr'?rows[0]:null};
Object.defineProperty(body,'innerHTML',{set(v){assert.equal(v,'');rows.length=0;}});
const tail={id:2005,code:'M2005',name:'后段物料',spec:'长规格',unit:{name:'PCS'},price:125};
const ctx={body,materials:[tail],defaultTaxRate:0.13,activeDropdown:null,activeIndex:-1,formFields:['customer_id'],
 SALES_RECENT_KEY:'recent',SALES_TEMPLATE_KEY:'templates',esc:v=>String(v),escAttr:v=>String(v),handleKeydown(){},
 localStorage:{getItem:k=>storage[k]??null},navigator:{clipboard:{readText:()=>Promise.resolve('M2005\t2\t0\t0\tB1')}},
 document:{createElement:makeRow,querySelector:()=>({value:'2'}),getElementById:id=>{
   if(id==='entryStatus')return status;
   return buttons[id]??=Object.assign(element(),{addEventListener:(e,fn)=>handlers[id]=fn});
 }},WMS:{positionDropdown(){}}};ctx.window=ctx;
vm.createContext(ctx);vm.runInContext(p.script,ctx);
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 let row=ctx.addRow();row.querySelector('.qty').value='2';row.querySelector('.price').value='0';row.querySelector('.tax-rate').value='0';
 if(p.entry==='exact'){row.querySelector('.material-code').value='m2005';row.querySelector('.material-code').events.input();}
 if(p.entry==='dropdown'){
  row.querySelector('.material-code').value='后段';ctx.showDropdown(row);
  assert(row.querySelector('.material-dropdown').innerHTML.includes('M2005'));ctx.selectMaterial(row,'M2005');
 }
 if(p.entry==='recent'){storage.recent=JSON.stringify(['OFF','M2005']);handlers.recentBtn();}
 if(p.entry==='template'){
  storage.templates=JSON.stringify([{items:[{code:'M2005',quantity:2,price:0,tax_rate:0,batch_no:'B1'}]}]);
  buttons.templateSelect.value='0';handlers.templateSelect.call(buttons.templateSelect);row=rows[0];
 }
 if(p.entry==='paste'){handlers.pasteBtn();await flush();await flush();}
 if(p.entry==='bad_template'){
  ctx.selectMaterial(row,'M2005');row.querySelector('.line-remark').value='must keep';
  const before=JSON.stringify(ctx.collect());
  storage.templates=JSON.stringify([{items:[{code:'OFF',quantity:9,price:8}]}]);
  buttons.templateSelect.value='0';handlers.templateSelect.call(buttons.templateSelect);
  assert.equal(JSON.stringify(ctx.collect()),before,'invalid template must not erase entered lines');
  assert(status.textContent.includes('停用'));return;
 }
 if(p.entry==='history'){
  const historical={code:'OFF',name:'历史停用料',spec:'旧规格',unit:{name:'个'},price:7};
  row=ctx.addRow({code:'OFF',quantity:4,price:0,tax_rate:0,material:historical});
  assert.equal(row.querySelector('.name').value,'历史停用料');assert.equal(row.querySelector('.unit').value,'个');
  row.querySelector('.material-code').events.input();assert.equal(row.querySelector('.name').value,'历史停用料');
  const fresh=ctx.addRow();ctx.selectMaterial(fresh,'OFF');assert.equal(fresh.querySelector('.material-code').value,'');
  assert.equal(row.querySelector('.price').value,'0');return;
 }
 assert.equal(row.querySelector('.material-code').value,'M2005','matched code must keep its actual archive spelling for save');
 assert.equal(row.querySelector('.name').value,'后段物料');assert.equal(row.querySelector('.spec').value,'长规格');
 assert.equal(row.querySelector('.unit').value,'PCS');assert.equal(Number(row.querySelector('.price').value),0);
 const chosen=ctx.collect().items.filter(x=>x.code);assert.equal(chosen.length,1);assert.equal(Number(chosen[0].quantity),2);
 assert.equal(Number(chosen[0].price),0);assert(!chosen.some(x=>x.code==='OFF'));
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''
    binary = shutil.which('node')
    assert binary, 'Node.js is required for actual sales entry consumers'
    result = subprocess.run([binary, '--max-old-space-size=64', '-e', program],
                            input=json.dumps(dict(page=page, entry=entry, script=script)),
                            capture_output=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr

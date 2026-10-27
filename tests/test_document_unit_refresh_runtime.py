"""Run the actual shared-form unit refresh and save collection with delayed HTTP."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from tests.test_in_order_material_search_runtime import function

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('kind', ['bom', 'transfer', 'check', 'requisition'])
@pytest.mark.parametrize('action', ['success', 'order', 'latest_error', 'stale_error', 'http',
                                  'business', 'shape', 'bad_row', 'duplicate', 'network', 'empty',
                                  'missing', 'selection', 'readonly', 'disabled', 'disable_pending',
                                  'detached', 'new_row', 'text', 'id_text', 'headers'])
def test_unit_refresh_preserves_row_selection_and_saved_unit(kind, action):
    source = (ROOT / 'app/templates/document_table_form.html').read_text(encoding='utf-8')
    app = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const calls=[],pending=[],notices=[];
const decode=s=>s.replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
class Select {
 constructor(value='1'){this._value=value;this.disabled=false;this.isConnected=true;this.options=[{value:'',text:'-'},{value:'1',text:'个'},{value:'2',text:'箱'}];this.markup='original';}
 get value(){return this._value;}set value(v){this._value=this.options.some(o=>o.value===String(v))?String(v):'';}
 get innerHTML(){return this.markup;}
 set innerHTML(html){this.markup=html;this.options=[...html.matchAll(/<option value="([^"]*)"([^>]*)>([\s\S]*?)<\/option>/g)].map(m=>({value:decode(m[1]),text:decode(m[3]),selected:m[2].includes('selected')}));this._value=(this.options.find(o=>o.selected)||this.options[0]||{value:''}).value;}
 appendChild(option){this.options.push(option);}
}
const selects=[new Select()],fields={'.material-code':{value:'M1',style:{}},'.unit-id':selects[0],'.line-qty':{value:'3',style:{}},'.line-price':{value:'0'},'.material-name':{value:'物料'},'.material-spec':{value:''},'.material-unit':{value:'个'},'.line-usage':{value:''},'.line-remark':{value:''},'.line-area':{value:'A'},'.system-stock':{value:'4'},'.actual-stock':{value:'3'},'.line-reason':{value:''}};
const row={dataset:{counted:'true'},querySelector:s=>fields[s]||null};
const ctx={FormData:class{},document:{querySelector:()=>null,querySelectorAll:s=>s==='.unit-id'?selects:s==='#docTableBody tr'?[row]:[]},
 fetch:(url,options={})=>{calls.push({url,options});return new Promise((resolve,reject)=>pending.push({resolve,reject}));},showToast:m=>notices.push(m),
 findMaterialByCode:()=>({id:1,code:'M1',name:'物料',unit:{id:1,name:'个'},price:5}),getMaterialUnitId:()=>1,getMaterialUnit:()=>'个'};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.helper,ctx);vm.runInContext(p.escape,ctx);
vm.runInContext('const units=[{id:1,name:"个"},{id:2,name:"箱"}];const readonly='+String(p.action==='readonly')+';const docType='+JSON.stringify(p.kind)+';const checkLocationRequired=false;',ctx);
vm.runInContext(p.options+'\n'+p.refresh+'\n'+p.collect,ctx);
const cache=vm.runInContext('units',ctx),before=selects[0].innerHTML,usual=[{id:1,name:'新个'},{id:2,name:'新箱'}];
const selected=()=>String(ctx.collectItems().items[0].unit_id);
const settle=async()=>{for(let i=0;i<7;i++)await new Promise(setImmediate);};
async function reply(index,data=usual,error=null){if(error==='network')pending[index].reject(Error('offline'));else pending[index].resolve({ok:error!=='http',status:error==='http'?503:200,json:()=>Promise.resolve(data)});await settle();}
(async()=>{
 if(p.action==='disabled')selects[0].disabled=true;
 ctx.refreshUnits();
 if(p.action==='readonly'){if(pending.length)await reply(0,[{id:3,name:'OTHER'}]);assert.equal(selects[0].innerHTML,before);assert.equal(calls.length,0,'readonly document must retain historical unit display');assert.equal(selected(),'1');return;}
 assert.equal(calls.length,1);assert.equal(calls[0].url,'/api/units');
 if(['order','latest_error','stale_error'].includes(p.action)){
  ctx.refreshUnits();await reply(1,usual,p.action==='latest_error'?'network':null);const beforeLate=selects[0].innerHTML;
  await reply(0,[{id:3,name:'OLD'}],p.action==='stale_error'?'network':null);
  assert.equal(selects[0].innerHTML,beforeLate,'obsolete success/error must not rerender row units');assert.equal(selected(),'1');
  assert.deepEqual(Array.from(cache,x=>x.name),p.action==='latest_error'?['个','箱']:['新个','新箱']);return;
 }
 if(['selection','empty','missing'].includes(p.action))selects[0].value='2';
 if(p.action==='disable_pending')selects[0].disabled=true;
 if(p.action==='detached')selects[0].isConnected=false;
 if(p.action==='new_row')selects.push(new Select('2'));
 let data=usual;
 if(p.action==='empty')data=[];
 if(p.action==='missing')data=[usual[0]];
 if(p.action==='business')data={status:'error',msg:'拒绝刷新'};
 if(p.action==='shape')data={items:usual};
 if(p.action==='bad_row')data=[{id:1}];
 if(p.action==='duplicate')data=[usual[0],usual[0]];
 if(p.action==='text')data=[{id:1,name:'个"<img src=x onerror=attack()>&'},usual[1]];
 if(p.action==='id_text')data=[{id:'3" onmouseover="attack()',name:'新单位'},...usual];
 await reply(0,data,p.action);
 if(['http','business','shape','bad_row','duplicate','network'].includes(p.action)){assert.deepEqual(Array.from(cache,x=>x.name),['个','箱']);assert.equal(selects[0].innerHTML,before);}
 if(['disabled','disable_pending','detached'].includes(p.action))assert.equal(selects[0].innerHTML,before,'disabled/disconnected rows must retain their options');
 if(['success','selection','new_row','text','id_text','headers'].includes(p.action))assert(selects[0].options.some(o=>o.value==='1'&&o.text===data.find(x=>x.id===1).name));
 assert.equal(selected(),['selection','empty','missing'].includes(p.action)?'2':'1','refresh must never change the unit sent by collectItems to the material default');
 if(p.action==='new_row')assert.equal(selects[1].value,'2');
 if(p.action==='text')assert(!selects[0].innerHTML.includes('<img'));
 if(p.action==='id_text'){assert(!selects[0].innerHTML.includes(' onmouseover="attack()'));assert(selects[0].options.some(o=>o.value==='3" onmouseover="attack()'));}
 assert.strictEqual(cache,vm.runInContext('units',ctx));assert.equal(notices.length,0);
 if(p.action==='headers')assert.equal(calls[0].options.headers['X-Requested-With'],'XMLHttpRequest');
})().then(()=>process.stdout.write('ok')).catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node, 'Node.js required for unit-refresh/save contract runtime tests'
    result = subprocess.run([node, '-e', program], input=json.dumps(dict(kind=kind, action=action,
        api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'),
        helper=(ROOT / 'app/static/js/list-cache.js').read_text(encoding='utf-8'),
        escape=function(app, 'escapeHtml'), options=function(source, 'unitOptions'),
        refresh=function(source, 'refreshUnits'), collect=function(source, 'collectItems'))),
        capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == 'ok', 'Runtime must finish all assertions'

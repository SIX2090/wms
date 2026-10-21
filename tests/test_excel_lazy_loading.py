"""Exercise the shared Excel component with lazy dependencies and real SheetJS."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["in_order_detail", "out_order_detail", "after_sale_out_detail", "purchase_request_detail", "subcontract_detail"]


@pytest.mark.parametrize("page", PAGES)
def test_detail_does_not_preload_sheetjs(page):
    source = (ROOT / f"app/templates/{page}.html").read_text(encoding="utf-8")
    assert "js/xlsx.full.min.js" not in source
    assert "js/excel-import-export.js" in source


@pytest.mark.parametrize("scenario", ["idle", "cached", "concurrent", "network", "missing", "server", "export", "template", "import", "import_failure", "import_stale", "real"])
def test_excel_dependency_runtime(scenario):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required")
    payload = {"source": (ROOT / "app/static/js/excel-import-export.js").read_text(encoding="utf-8"), "scenario": scenario, "library": str(ROOT / "app/static/js/xlsx.full.min.js")}
    script = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const p=JSON.parse(process.argv[1]);let scripts=[],removed=0,opened=[],writes=[],messages=[],reads=[],preview=[];
const headers=[{textContent:'code',querySelector:()=>null},{textContent:'quantity',querySelector:()=>null}];
const cells=[{textContent:'M001',querySelector:()=>null},{textContent:'2',querySelector:()=>null}];
const table={querySelectorAll:s=>s==='thead th'?headers:[{querySelector:()=>null,querySelectorAll:()=>cells}]};
const confirm={disabled:true};
const document={currentScript:{src:'https://wms.test/prefix/static/js/excel-import-export.js?v=test-1'},baseURI:'https://wms.test/prefix/doc/7',
 createElement:tag=>({tag,remove(){removed++;}}),head:{appendChild:s=>scripts.push(s)},
 getElementById:id=>id==='itemTable'?table:(id==='confirmImportBtn'?confirm:null)};
const api={utils:{json_to_sheet:rows=>({rows}),book_new:()=>({sheets:[]}),book_append_sheet:(b,s,n)=>b.sheets.push({s,n}),sheet_to_json:()=>[{code:'M001',quantity:2}]},
 read:()=>({SheetNames:['first'],Sheets:{first:{}}}),writeFile:(b,n)=>writes.push({b,n})};
class Reader{readAsArrayBuffer(file){reads.push(file.name);this.onload({target:{result:new ArrayBuffer(2)}});}}
const ctx={document,URL,Promise,FileReader:Reader,Uint8Array,ArrayBuffer,console,showToast:(m,t)=>messages.push({m,t}),open:(...x)=>opened.push(x)};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.source+';this.Component=ExcelImportExport;',ctx);
const C=ctx.Component;C.prototype.createButtons=()=>{};C.prototype.createImportModal=()=>{};
const component=new C({fileName:'audit',columns:[{label:'code',example:'M001'},{label:'quantity',example:2}]});
component.showPreview=x=>preview.push(x);
const flush=()=>new Promise(r=>setImmediate(r));
function loaded(){ctx.XLSX=api;scripts.at(-1).onload();}
(async()=>{
 assert.equal(scripts.length,0,'initialization must not load SheetJS');
 assert.equal(typeof C.loadXlsx,'function');
 if(p.scenario==='idle')return;
 if(p.scenario==='cached'){ctx.XLSX=api;assert.equal(await C.loadXlsx(),api);assert.equal(scripts.length,0);return;}
 if(p.scenario==='server'){component.options.exportUrl='/export/7';component.options.templateUrl='/template';component.exportToExcel();component.downloadTemplate();assert.equal(opened.length,2);assert.equal(scripts.length,0);return;}
 if(p.scenario==='concurrent'){const a=C.loadXlsx(),b=C.loadXlsx();assert.equal(a,b);assert.equal(scripts.length,1);loaded();assert.equal(await a,api);assert.equal(await b,api);await C.loadXlsx();assert.equal(scripts.length,1);return;}
 if(['network','missing'].includes(p.scenario)){const a=C.loadXlsx();const failure=assert.rejects(a);if(p.scenario==='network')scripts[0].onerror();else scripts[0].onload();await failure;assert.equal(removed,1);const b=C.loadXlsx();assert.equal(scripts.length,2);loaded();await b;return;}
 if(p.scenario==='export'){const work=component.clientExport();assert.equal(writes.length,0);assert.equal(scripts.length,1);loaded();await work;assert.equal(writes.length,1);assert.equal(writes[0].b.sheets[0].s.rows[0].code,'M001');}
 if(p.scenario==='template'){const work=component.generateTemplate();loaded();await work;assert.equal(writes.length,1);assert.equal(writes[0].b.sheets[0].s.rows[0].quantity,2);}
 if(p.scenario.startsWith('import')){
  const first={name:'first.xlsx'};const a=component.handleFileSelect({target:{files:[first]}});
  assert.equal(reads.length,0,'wait for dependency before reading');
  if(p.scenario==='import_failure'){scripts[0].onerror();await a;assert.equal(confirm.disabled,true);assert(messages.some(x=>x.t==='danger'));const b=component.handleFileSelect({target:{files:[first]}});assert.equal(scripts.length,2);loaded();await b;}
  else if(p.scenario==='import_stale'){const b=component.handleFileSelect({target:{files:[{name:'second.xlsx'}]}});loaded();await Promise.all([a,b]);assert.deepEqual(reads,['second.xlsx']);}
  else{loaded();await a;}
  assert.equal(preview.length,1);assert.equal(confirm.disabled,false);
 }
 if(p.scenario==='real'){
  const work=component.generateTemplate();vm.runInContext(fs.readFileSync(p.library,'utf8'),ctx);const real=ctx.XLSX;real.writeFile=(book,name)=>{const bytes=real.write(book,{type:'array',bookType:'xlsx'});const parsed=real.read(bytes,{type:'array'});writes.push({rows:real.utils.sheet_to_json(parsed.Sheets[parsed.SheetNames[0]])});};scripts[0].onload();await work;assert.equal(writes[0].rows[0].code,'M001');assert.equal(writes[0].rows[0].quantity,2);
 }
 assert.equal(scripts[0].src,'https://wms.test/prefix/static/js/xlsx.full.min.js?v=test-1','preserve deployment prefix and asset version');
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result = subprocess.run([node, "-e", script, json.dumps(payload)], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr

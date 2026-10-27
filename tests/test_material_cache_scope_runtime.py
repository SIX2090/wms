"""Warehouse changes must not restore stale stock or rewrite frozen counts."""
from pathlib import Path
import shutil
import subprocess


def test_material_cache_scope_switch_preserves_frozen_count():
    asset = Path(__file__).resolve().parents[1]/'app/static/js/material-cache.js'
    program = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const calls=[],pending=[],handlers={};
const field={value:'A',selectedOptions:[{textContent:'仓库 A'}],dataset:{},addEventListener:(name,fn)=>handlers[name]=fn};
const make=(frozen,counted)=>{const fields={'.material-stock':{value:'10'},'.system-stock':{value:'6'},'.actual-stock':{value:'5'},'.line-diff':{value:'-1'}};
 const row={dataset:{systemStockFrozen:String(frozen),counted:String(counted)},querySelector:s=>fields[s]};
 const code={value:'M1',closest:()=>row};return {fields,code};};
const frozen=make(true,true),fresh=make(false,false),target=[{id:1,code:'M1',name:'料',stock:10}];
const ctx={document:{querySelector:()=>field,querySelectorAll:s=>s==='.material-stock'?[frozen.fields[s],fresh.fields[s]]:[frozen.code,fresh.code]},
 WMS:{api:{getRaw:url=>{calls.push(url);return new Promise((resolve,reject)=>pending.push({resolve,reject}));}}},console};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
ctx.WMS.materialCache.bindWarehouse(target);const first=handlers.change();
field.value='B';field.selectedOptions=[{textContent:'仓库 B'}];const second=handlers.change();
const result=stock=>({status:'success',materials:[{id:1,code:'M1',name:'料',stock}],total:1,page:1,per_page:2000,pages:1});
(async()=>{pending[1].resolve(result(4));await second;pending[0].resolve(result(6));await first;
 assert(calls[0].includes('warehouse='+encodeURIComponent('仓库 A')));assert(calls[1].includes('warehouse='+encodeURIComponent('仓库 B')));
 assert.equal(target[0].stock,4);assert.equal(frozen.fields['.material-stock'].value,'4.00');
 assert.equal(frozen.fields['.system-stock'].value,'6');assert.equal(frozen.fields['.actual-stock'].value,'5');
 assert.equal(fresh.fields['.system-stock'].value,'4.00');assert.equal(fresh.fields['.actual-stock'].value,'4.00');
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result = subprocess.run([shutil.which('node'), '-e', program, str(asset)],
        capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr

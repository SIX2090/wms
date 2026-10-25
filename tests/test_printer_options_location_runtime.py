"""Exercise actual API consumers and inbound save payload without a live service."""
from pathlib import Path
import json
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')


@pytest.mark.skipif(NODE is None, reason='Node.js required')
@pytest.mark.parametrize('mode', ['populated', 'empty', 'network', 'http', 'business'])
def test_known_printers_use_unwrapped_api_data(mode):
    result = subprocess.run([NODE, str(ROOT / 'tests/frontend_printer_options.cjs'), mode],
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(NODE is None, reason='Node.js required')
@pytest.mark.parametrize(('location', 'location_enabled'), [('', False), ('   ', True), ('A-01', True), ('  项目仓-货架2  ', True)])
def test_inbound_save_retains_validated_location(location, location_enabled):
    source = (ROOT / 'app/templates/in_order_add.html').read_text(encoding='utf-8')
    start = source.index('function submitForm(')
    end = source.index("\ndocument.addEventListener('click'", start + 1)
    script = r'''
const vm=require('vm'),p=JSON.parse(require('fs').readFileSync(0,'utf8'));let sent=null,errors=[];
const values={date:'2026-10-25',supplier_id:'7',warehouse_id:'2',location:p.location,business_type:'采购入库',purpose:'fixture',order_id:'',order_no:'IN-QA',remark:''};
const fields=Object.fromEntries(Object.entries(values).map(([k,value])=>[k,{value}]));
if(!p.locationEnabled)delete fields.location;
const row={dataset:{},querySelector:s=>({value:({'.material-code':'M-01','.material-qty':'2','.material-price':'0'}[s]||''),checked:false})};
const ctx={document:{querySelector:s=>fields[(s.match(/name="([^"]+)"/)||[])[1]]||null,querySelectorAll:s=>s==='#materialTableBody tr'?[row]:[]},clearInOrderValidation(){},findMaterialByCode:()=>({id:1}),markRowError(){},showInOrderValidation(e){errors=e;},confirm:()=>true,showToast(){},WMS:{api:{postRaw:(url,data)=>{sent={url,data};return Promise.resolve({status:'error',msg:'测试响应'});}}}};
vm.createContext(ctx);vm.runInContext('let inOrderSubmitting=false;const partyField="supplier_id",partyLabel="供应商",supplierRequired=true,returnAddUrl="/in_order/add";',ctx);vm.runInContext(p.source,ctx);
(async()=>{await ctx.submitForm();process.stdout.write(JSON.stringify({sent,errors}));})().catch(e=>{console.error(e);process.exitCode=1;});
'''
    result = subprocess.run([NODE, '-e', script], input=json.dumps({'source': source[start:end], 'location': location, 'locationEnabled': location_enabled}),
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    actual = json.loads(result.stdout)
    if location_enabled and not location.strip():
        assert actual['sent'] is None
        assert any('库位不能为空' in error['message'] for error in actual['errors'])
        return
    assert actual['errors'] == []
    sent = actual['sent']
    assert (sent['data'].get('location') or '') == location.strip()
    assert sent['data']['warehouse_id'] == '2'
    assert sent['data']['items'][0]['price'] == 0

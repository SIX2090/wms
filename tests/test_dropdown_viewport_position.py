"""Execute dropdown placement against viewport edges and scrolling."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('case', ['bottom', 'top', 'short', 'right', 'scroll', 'menu_scroll', 'resize'])
def test_dropdown_stays_inside_viewport(case):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    script = r"""
const assert=require('assert'),fs=require('fs');
let scroll,resize;
const window={innerHeight:700,innerWidth:900,WMS:{},addEventListener(n,fn){resize=fn;},getComputedStyle(){return {minWidth:'380px'};}};
const document={addEventListener(n,fn){scroll=fn;}};
let rect={left:50,right:250,top:640,bottom:668,width:200};
const menu={style:{},offsetWidth:380,isConnected:true,getClientRects(){return [{}];},contains(target){return target===this;}};
const input={isConnected:true,getBoundingClientRect(){return rect;}};
const scenario=CASE;
if(scenario==='top')rect={left:50,right:250,top:50,bottom:78,width:200};
if(scenario==='short'){window.innerHeight=170;rect={left:50,right:250,top:80,bottom:108,width:200};}
if(scenario==='right'){window.innerWidth=320;rect={left:250,right:310,top:640,bottom:668,width:60};}
eval(fs.readFileSync(SOURCE,'utf8'));
window.WMS.positionDropdown(input,menu);
const height=parseFloat(menu.style.maxHeight),width=parseFloat(menu.style.width),left=parseFloat(menu.style.left);
assert(left>=8);assert(left+width<=window.innerWidth-8);
if(scenario==='top'){assert.equal(menu.style.top,'83px');assert.equal(menu.style.bottom,'auto');}
else {assert.equal(menu.style.top,'auto');assert(parseFloat(menu.style.bottom)>=window.innerHeight-rect.top);}
assert(height>=0 && height<=280);
if(scenario==='short')assert(height<=67);
if(scenario==='scroll'){rect={left:50,right:250,top:40,bottom:68,width:200};scroll({type:'scroll',target:document});assert.equal(menu.style.top,'73px');}
if(scenario==='resize'){window.innerHeight=1000;resize({type:'resize',target:window});assert.equal(menu.style.top,'673px');assert.equal(menu.style.bottom,'auto');}
if(scenario==='menu_scroll'){rect={left:50,right:250,top:40,bottom:68,width:200};scroll({type:'scroll',target:menu});assert.equal(menu.style.top,'auto');}
""".replace('CASE',json.dumps(case)).replace('SOURCE',json.dumps(str(ROOT/'app/static/js/dropdown-position.js')))
    result=subprocess.run([node,'-e',script],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode == 0,result.stderr


@pytest.mark.parametrize('template', ['in_order_add.html','out_order_add.html','document_table_form.html','after_sale_out_add.html','adjustment_add.html','purchase_order_add.html','purchase_request_add.html','sales_order_add.html','sales_order_edit.html','in_order_detail.html','out_order_detail.html','opening_stock.html'])
def test_material_picker_uses_shared_placement(template):
    source=(ROOT/'app/templates'/template).read_text(encoding='utf-8')
    assert 'WMS.positionDropdown(' in source


def test_helper_loaded_before_template_scripts():
    source=(ROOT/'app/templates/base.html').read_text(encoding='utf-8')
    assert source.index('js/dropdown-position.js') < source.index('{% block extra_js %}')

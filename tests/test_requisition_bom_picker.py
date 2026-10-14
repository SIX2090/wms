"""BOM-driven requisition creation uses the existing validated draft endpoint."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from app import db, BOM, User, Warehouse, ProductionRequisition
from routes import options_api

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('role,visible', [('admin',True),('production',True),('warehouse',False)])
def test_requisition_bom_button_and_selection_dialog_follow_roles(bom_case, role, visible):
    client, ids = bom_case
    db.session.get(User, ids['user']).role = role
    db.session.commit()
    html = client.get('/requisition?embedded=1').get_data(as_text=True)
    assert ('id="openBomRequisition"' in html) == visible
    assert ('id="bomRequisitionForm"' in html) == visible
    if visible:
        assert '按BOM领料' in html and 'data-ks="bom_active"' in html
        assert 'id="bomRequisitionWarehouse"' in html


@pytest.mark.parametrize('sql', [False,True])
def test_bom_draft_picker_excludes_disabled_boms_and_searches_version(bom_case, sql):
    _, ids = bom_case
    db.session.add(BOM(bom_no='DISABLED',product_code='B-P',product_name='审计产品',version='V2',status='inactive'))
    db.session.commit()
    rows = options_api._sql_like_pool('bom_active','V1') if sql else options_api._build_entity_pool('bom_active')
    assert [row['id'] for row in rows] == [ids['bom']]
    assert 'V1' in rows[0]['sub']


def test_bom_generated_draft_has_empty_editable_headers_instead_of_none(bom_case):
    client, ids = bom_case
    warehouse = Warehouse(code='PICK-W',name='领料测试仓库',status='active')
    db.session.add(warehouse)
    db.session.commit()
    response = client.post(f"/bom/{ids['bom']}/create_requisition",json={'warehouse_id':warehouse.id})
    assert response.status_code == 200
    draft = db.session.get(ProductionRequisition,response.get_json()['id'])
    assert draft.status == 'pending' and draft.bom_id == ids['bom']
    assert draft.production_order == draft.purpose == draft.picker == draft.remark == ''


def test_bom_creation_controller_validates_selection_and_recovers_from_failure():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    script = r'''
const fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(JSON.parse(process.argv[1]),'utf8');
let valid=true,fail=false,calls=[],toasts=[];
const fields={bomRequisitionForm:{reportValidity:()=>valid},bomRequisitionId:{value:''},
 bomRequisitionWarehouse:{value:'2'},bomRequisitionLocation:{value:'A-01'},bomRequisitionSubmit:{disabled:false}};
const document={getElementById:id=>fields[id]||null,addEventListener(){}};
const window={location:{search:'?embedded=1',href:''}};
function showToast(message){toasts.push(message);}
const WMS={api:{post:async(url,data)=>{calls.push({url,data});if(fail)throw Error('网络失败');return {id:42};}}};
eval(source);
const event={preventDefault(){}};
(async()=>{
 await submitBomRequisition(event);assert.equal(calls.length,0);
 fields.bomRequisitionId.value='12';valid=false;await submitBomRequisition(event);assert.equal(calls.length,0);
 valid=true;fields.bomRequisitionSubmit.disabled=true;await submitBomRequisition(event);assert.equal(calls.length,0);
 fields.bomRequisitionSubmit.disabled=false;await submitBomRequisition(event);
 assert.deepEqual(calls[0],{url:'/bom/12/create_requisition',data:{warehouse_id:2,location:'A-01'}});
 assert.equal(window.location.href,'/requisition/42?embedded=1');assert.equal(fields.bomRequisitionSubmit.disabled,false);
 fail=true;await submitBomRequisition(event);assert.equal(fields.bomRequisitionSubmit.disabled,false);
 assert.equal(toasts.at(-1),'网络失败');
})().catch(e=>{console.error(e);process.exit(1);});
'''
    result = subprocess.run([node,'-e',script,json.dumps(str(ROOT/'app/static/js/requisition-bom.js'))],
                            capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode == 0, result.stderr


def test_bom_toolbar_uses_one_button_and_clears_stale_selection():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    script = r'''
const fs=require('node:fs'),assert=require('node:assert/strict');
let ready,resetCount=0,searchHandler,modalHandler,moved;
const button={},next={},bar={children:[{},next],insertBefore:(item,before)=>{moved=item;assert.equal(before,next);}};
const fields={openBomRequisition:button,cbGlobalActionBar:bar,
 bomRequisitionId:{value:'12'},bomRequisitionForm:{addEventListener(){},reset(){resetCount++;}},
 bomRequisitionSearch:{addEventListener:(name,fn)=>{assert.equal(name,'input');searchHandler=fn;}},
 bomRequisitionModal:{addEventListener:(name,fn)=>{assert.equal(name,'show.bs.modal');modalHandler=fn;}}};
const document={getElementById:id=>fields[id],addEventListener:(name,fn)=>{ready=fn;}};
eval(fs.readFileSync(JSON.parse(process.argv[1]),'utf8'));ready();assert.equal(moved,button);
searchHandler();assert.equal(fields.bomRequisitionId.value,'');
fields.bomRequisitionId.value='12';modalHandler();assert.equal(fields.bomRequisitionId.value,'');assert.equal(resetCount,1);
'''
    result = subprocess.run([node,'-e',script,json.dumps(str(ROOT/'app/static/js/requisition-bom.js'))],
                            capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode == 0, result.stderr

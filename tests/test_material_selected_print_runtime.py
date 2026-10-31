"""BUG-2026-10-31-015: material toolbar prints every selected material."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('scenario', [
    'empty', 'one', 'two', 'three', 'select_all', 'clear_all',
    'unrelated_checkbox', 'changed_selection',
])
def test_material_toolbar_selected_print_runtime(scenario):
    source = (ROOT / 'app/templates/material.html').read_text(encoding='utf-8')
    toolbar = source[source.index('function getSelectedSingleId()'):
                     source.index('function toolbarFindImage()')]
    # Keep adjacent helpers added before the original single-selection helper.
    helper = re.search(r'^function getSelectedMaterialIds\([^)]*\) \{.*?^\}', source, re.M | re.S)
    if helper:
        toolbar = helper[0] + '\n' + toolbar
    printing = source[source.index('function printLabels()'):source.index('function doPrint()')]
    printing = re.sub(r'\{\{.*?\}\}', '/label/batch_print', printing)
    shared = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    check_all = shared[shared.index('function initCheckAll('):shared.index('// 批量删除')]
    program = r'''
const vm=require('node:vm'), assert=require('node:assert/strict');
const p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const nodes={}, opened=[], posts=[], toasts=[];
const table={listeners:{},addEventListener(type,fn){(this.listeners[type]??=[]).push(fn)}};
function checkbox(id,value,isItem){return {id,value,checked:false,disabled:false,listeners:{},
 classList:{contains:name=>isItem&&name==='check-item'},
 addEventListener(type,fn){(this.listeners[type]??=[]).push(fn)},
 change(){for(const fn of this.listeners.change||[])fn({target:this});
   for(const fn of table.listeners.change||[])fn({target:this});}};}
const header=checkbox('checkAll','on',false), boxes=[11,22,33,44].map(id=>checkbox('',String(id),true));
const outsider=checkbox('unrelated','999',true);outsider.checked=true;
nodes.materialTable=table;
for(const id of ['Edit','Copy','Print','RemotePrint','FindImage','Delete','Merge'])
 nodes['toolbar'+id+'Btn']={disabled:true};
table.querySelector=s=>s==='#checkAll'?header:null;
table.querySelectorAll=s=>{assert.equal(s,'.check-item');return boxes};
const document={getElementById:id=>nodes[id],querySelectorAll:s=>{
 if(s==='#materialTable .check-item:checked')return boxes.filter(b=>b.checked);
 if(s==='.check-item:checked')return [...boxes,outsider].filter(b=>b.checked);
 throw Error('Unexpected selector '+s);
}};
const ctx=vm.createContext({document,window:{open:(...args)=>opened.push(args)},
 WMS:{api:{post:async(url,body)=>{posts.push({url,body});return {msg:'queued'}}}},
 showToast:(...args)=>toasts.push(args),__notify:(...args)=>toasts.push(args)});
vm.runInContext(p.check_all+'\n'+p.toolbar+'\n'+p.printing,ctx);
ctx.initCheckAll('materialTable');ctx.initToolbarActions();
function choose(n){boxes.forEach((b,i)=>{b.checked=i<n;b.change()})}
if(p.scenario==='one')choose(1);
if(p.scenario==='two')choose(2);
if(p.scenario==='three'||p.scenario==='unrelated_checkbox')choose(3);
if(p.scenario==='select_all'){header.checked=true;header.change()}
if(p.scenario==='clear_all'){header.checked=true;header.change();header.checked=false;header.change()}
if(p.scenario==='changed_selection'){choose(3);boxes[0].checked=false;boxes[0].change();boxes[3].checked=true;boxes[3].change()}
const selected=boxes.filter(b=>b.checked).map(b=>b.value);
for(const id of ['Print','RemotePrint'])assert.equal(nodes['toolbar'+id+'Btn'].disabled,selected.length===0,id);
for(const id of ['Edit','Copy','FindImage','Delete'])assert.equal(nodes['toolbar'+id+'Btn'].disabled,selected.length!==1,id);
assert.equal(nodes.toolbarMergeBtn.disabled,selected.length<1||selected.length>2);
ctx.toolbarPrint();ctx.sendLabelsToPrintStation();
if(selected.length){
 assert.equal(opened.length,1);assert.equal(opened[0][0],'/label/batch_print?ids='+selected.join(','));
 assert.equal(opened[0][1],'_blank');assert.equal(posts.length,1);
 assert.equal(posts[0].url,'/print_queue/jobs');assert.equal(posts[0].body.job_type,'label');
 assert.equal(posts[0].body.target_ids,selected.join(','));
 ctx.printLabels();assert.equal(opened[1][0],opened[0][0]);
}else{assert.equal(opened.length,0);assert.equal(posts.length,0)}
'''
    result = subprocess.run([shutil.which('node'), '-e', program],
                            input=json.dumps(dict(scenario=scenario, toolbar=toolbar,
                                                  printing=printing, check_all=check_all)),
                            text=True, encoding='utf-8', capture_output=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_three_selected_materials_reach_label_preview_and_queue(monkeypatch):
    from app import app, db, Material, PrintJob, User
    monkeypatch.setitem(app.config, 'TESTING', True)
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', False)
    with app.app_context():
        assert str(db.engine.url) == 'sqlite:///:memory:'
        db.session.remove()
        db.drop_all()
        db.create_all()
        user = User(username='selected-print', role='admin', password_hash='unused',
                    must_change_password=False)
        materials = [Material(code=f'SEL-{n}', name=f'勾选打印物料{n}') for n in range(4)]
        db.session.add_all([user, *materials])
        db.session.commit()
        uid = user.id
        selected = [m.id for m in materials[:3]]
        client = app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(uid)
            session['_fresh'] = True
        ids = ','.join(map(str, selected))
        response = client.get('/label/batch_print', query_string={'ids': ids})
        assert response.status_code == 200
        match = re.search(r'var MATERIALS = (\[.*?\]);', response.get_data(as_text=True), re.S)
        assert match is not None
        rows = json.loads(match[1])
        assert {row['id'] for row in rows} == set(selected)
        assert len(rows) == 3
        assert PrintJob.query.count() == 0  # Preview alone never enqueues a job.
        response = client.post('/print_queue/jobs', json={'job_type': 'label', 'target_ids': ids})
        assert response.status_code == 200
        job = db.session.get(PrintJob, response.json['job_id'])
        assert job.target_ids == ids and job.status == 'pending'
        assert PrintJob.query.count() == 1
        db.session.remove()
        db.drop_all()

"""BUG-2026-10-24-016: real subcontract input and save lifecycle."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize("page", ["issue", "receive"])
@pytest.mark.parametrize("scenario", [
    "ambiguous", "duplicate_name", "code_priority", "exact", "exact_name", "unique", "clear", "zero",
    "unknown", "outside", "outside_partial", "duplicate_click", "change", "change_back",
    "quantity", "warehouse", "remove", "replace", "close", "close_reopen",
    "network", "http", "http_success", "unauthorized", "expired", "business", "shape", "bad_name", "wrong_code", "bad_id", "duplicate_result",
    "later_batch_failure", "batch", "multirow", "retry", "post_failure", "post_pending",
])
def test_real_input_and_save(page, scenario):
    source=(ROOT/f"app/templates/subcontract_{page}.html").read_text(encoding="utf-8")
    binding=source[source.index("function bindMaterialInput(input)"):source.index("// 初始绑定")]
    submit=source[source.index("// 提交新增"):source.index("// 查看详情")]
    shared=ROOT/"app/static/js/subcontract-material-selection.js"
    payload=dict(page=page, scenario=scenario, binding=binding, submit=submit,
                 shared=shared.read_text(encoding="utf-8") if shared.exists() else "",
                 api=(ROOT/"app/static/js/api.js").read_text(encoding="utf-8"))
    result=subprocess.run([shutil.which("node"), "-e", HARNESS], input=json.dumps(payload),
                          encoding="utf-8", capture_output=True, timeout=20,
                          env=dict(os.environ, NODE_OPTIONS="--max-old-space-size=96"))
    assert result.returncode == 0, result.stdout+result.stderr

@pytest.mark.parametrize("page", ["issue", "receive"])
def test_rendered_template_loads_shared_script_before_consumers(page):
    from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader
    from types import SimpleNamespace
    env = Environment(autoescape=True, loader=ChoiceLoader([
        DictLoader({"base.html": "{% block content %}{% endblock %}{% block extra_js %}{% endblock %}"}),
        FileSystemLoader(ROOT / "app/templates"),
    ]))
    html = env.get_template(f"subcontract_{page}.html").render(
        current_user=SimpleNamespace(role="admin"), request=SimpleNamespace(args={}),
        filters=dict(status="", search="", date_start="", date_end=""),
        csrf_token=lambda: "fixture", STATIC_VERSION="fixture-version",
        url_for=lambda endpoint, **kw: "/static/" + kw["filename"] + "?v=" + kw["v"],
        units=[], warehouses=[], suppliers=[], subcontract_orders=[], issues=[], receives=[])
    src='/static/js/subcontract-material-selection.js?v=fixture-version'
    assert html.count(src) == 1
    assert html.index(src) < html.index("function bindMaterialInput") < html.index("createSaver")
    assert 'id="addForm"' in html and 'id="addModal"' in html and 'id="submitAdd"' in html


def test_exact_lookup_contract_and_static_asset_in_isolated_app(monkeypatch):
    from app import app, db, User, Unit, MaterialCategory, Material
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"
    monkeypatch.setitem(app.config, "TESTING", True)
    monkeypatch.setitem(app.config, "WTF_CSRF_ENABLED", False)
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        try:
            user = User(username="material-selection-fixture", role="admin", password_hash="fixture-unused", must_change_password=False)
            unit = Unit(code="FIX-U", name="piece")
            category = MaterialCategory(code="FIX-C", name="fixture")
            db.session.add_all([user, unit, category])
            db.session.flush()
            for code in ["B", "B001", "B002"]:
                db.session.add(Material(code=code, name="Bolt", unit_id=unit.id, category_id=category.id))
            db.session.commit()
            client = app.test_client()
            with client.session_transaction() as session:
                session["_user_id"] = str(user.id)
                session["_fresh"] = True
            result = client.get("/material/api/by_codes?code=B").get_json()
            assert result["status"] == "success"
            assert [item["code"] for item in result["data"]] == ["B"]
            assert result["total_pages"] == 1
            assert client.get("/material/api/by_codes?code=Bolt").get_json()["data"] == []
            assert client.get("/material/api/by_codes", query_string=[("code", str(i)) for i in range(201)]).status_code == 400
            asset = client.get("/static/js/subcontract-material-selection.js?v=fixture-version")
            assert asset.status_code == 200
            assert asset.data == (ROOT / "app/static/js/subcontract-material-selection.js").read_bytes()
            assert asset.headers.get("ETag")
            assert client.get("/static/js/subcontract-material-selection.js?v=fixture-version", headers={"If-None-Match":asset.headers["ETag"]}).status_code == 304
        finally:
            db.session.remove()
            db.drop_all()


HARNESS = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),p=JSON.parse(fs.readFileSync(0,'utf8'));
let events={},button={disabled:false},requests=[],messages=[],reloads=0,gets=[],postResolvers=[],pending=[],mode=p.scenario;
function node(value=''){return {value,events:{},isConnected:true,addEventListener(n,f){(this.events[n]??=[]).push(f)},dispatch(n){(this.events[n]||[]).forEach(f=>f({target:this}))}}}
let rows=[];function row(code='',id=''){let r={};for(const [k,v] of Object.entries({material_code:code,material_id:id,quantity:'2',unit_id:'1',item_remark:'quote & 中文',scrap_quantity:'0',price:'3'}))r[k]=node(v);r.material_code.row=r;rows.push(r);return r;}
const first=row();const warehouse=node('2'),modal=node();modal.id='addModal';
const form=node();form.id='addForm';form.querySelectorAll=()=>rows.map(r=>r.material_code);
function allEntries(){return [['csrf_token','fixture'],['warehouse_id',warehouse.value],['subcontract_order_id','9'],...rows.flatMap(r=>Object.entries(r).filter(([k])=>p.page==='receive'||!['scrap_quantity','price'].includes(k)).map(([k,n])=>[k,n.value]))]}
class FormData{constructor(f){this.form=f;this.rows=allEntries().map(x=>x.slice())}entries(){return this.rows[Symbol.iterator]()}get(k){return this.rows.find(x=>x[0]===k)?.[1]??null}getAll(k){return this.rows.filter(x=>x[0]===k).map(x=>x[1])}delete(k){this.rows=this.rows.filter(x=>x[0]!==k)}append(k,v){this.rows.push([k,String(v)])}}
function wrap(arg){let nodes=arg==='inputs'?rows.map(r=>r.material_code):Array.isArray(arg)?arg:[arg];return {0:nodes[0],length:nodes.length,
 find(s){if(s==='.material-input')return wrap(rows.map(r=>r.material_code));let r=nodes[0],key=s==='.material-id'?'material_id':s==='.material-input'?'material_code':s.match(/name="([^"]+)"/)?.[1];return wrap(r[key])},
 on(n,fn){nodes.forEach(x=>x.addEventListener(n,fn));return this},click(fn){events.save=fn;return this},
 val(v){if(arguments.length){nodes.forEach(x=>x.value=String(v));return this}return nodes[0].value},
 closest(){return wrap(nodes[0].row)},trigger(n){nodes.forEach(x=>(x.events[n]||[]).forEach(f=>f.call(x)));return this},
 each(fn){nodes.forEach((x,i)=>fn.call(x,i,x));return this},prop(k,v){if(v===undefined)return nodes[0][k];nodes.forEach(x=>x[k]=v);return this}}}
function $(arg){if(arg==='#itemTableBody .material-input')return wrap('inputs');if(arg==='#itemTableBody')return wrap({});if(arg==='#addForm')return wrap(form);if(arg==='#submitAdd')return wrap(button);if(arg==='#addModal')return wrap(modal);if(typeof arg==='string'&&arg.endsWith('Warehouse'))return wrap(warehouse);return wrap(arg)}
const document={getElementById:id=>id==='addForm'?form:id==='addModal'?modal:id==='submitAdd'?button:id.endsWith('Warehouse')?warehouse:null,querySelector:s=>s.includes('csrf-token')?{content:'fixture'}:null};
const cache=[{id:1,code:'A001',name:'Bearing',unit:{id:1}},{id:2,code:'B001',name:'Bolt',unit:{id:1}},{id:3,code:'B002',name:'Bolt',unit:{id:1}},{id:4,code:'P001',name:'A001',unit:{id:1}}];
const ctx={document,$,FormData,Promise,URLSearchParams,Number,Set,Map,JSON,materialsCache:cache,console,
 showToast:(m,t)=>messages.push({m,t}),alert(){},location:{reload(){reloads++}},confirm:()=>false,setTimeout(){},
 fetch:(url,options)=>{requests.push({url,options});return new Promise((resolve,reject)=>{let req={url,options,resolve,reject};if(options.method==='GET'){gets.push(req);pending.push(req)}else if(mode==='post_pending')postResolvers.push(req);else resolve(response(mode==='post_failure'?{status:'error',msg:'post denied'}:{status:'success'}));})}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);if(p.shared)vm.runInContext(p.shared,ctx);vm.runInContext(p.binding,ctx);ctx.bindMaterialInput($('#itemTableBody'));vm.runInContext(p.submit,ctx);
function input(value,r=first){r.material_code.value=value;$(r.material_code).trigger('input');form.dispatch('input')}
function response(data,status=200){return{ok:status===200,status,json:()=>Promise.resolve(data)}}
function answer(req,kind='success'){if(kind==='network'){req.reject(Error('offline'));return}let codes=new URL(req.url,'http://local').searchParams.getAll('code');let data=codes.map((code,i)=>({id:1000+gets.indexOf(req)*200+i,code,name:'resolved'}));
 if(kind==='bad_name')data=[{id:999,code:codes[0],name:null}];if(kind==='unknown')data=[];if(kind==='shape')data={};if(kind==='wrong_code')data=[{id:999,code:'WRONG',name:'wrong'}];if(kind==='bad_id')data=[{id:0,code:codes[0],name:'wrong'}];if(kind==='duplicate_result')data.push(data[0]);
 req.resolve(response(['business','http'].includes(kind)?{status:'error',msg:'denied'}:{status:'success',data},['http','http_success'].includes(kind)?503:kind==='unauthorized'?401:kind==='expired'?419:200));}
const tick=()=>new Promise(r=>setImmediate(r));const save=()=>events.save.call(button);
(async()=>{
 input('A001');assert.equal(first.material_id.value,'1','exact code must win over another material name');
 if(mode==='code_priority'){cache.unshift(cache.pop());input('A001');assert.equal(first.material_id.value,'1');return}
 if(mode==='exact'){input('B002');assert.equal(first.material_id.value,'3');return}
 if(mode==='exact_name'){input('Bearing');assert.equal(first.material_id.value,'1');return}
 if(mode==='unique'){input('Bear');assert.equal(first.material_id.value,'1');return}
 if(mode==='clear'){input('');assert.equal(first.material_id.value,'');return}
 if(mode==='zero'){input('outside');assert.equal(first.material_id.value,'');return}
 if(mode==='ambiguous'||mode==='duplicate_name'){input(mode==='ambiguous'?'B00':'Bolt');assert.equal(first.material_id.value,'','ambiguous edit must clear old ID');return}
 if(mode==='batch'||mode==='later_batch_failure'){rows=[];for(let i=0;i<201;i++)row('X'+i);ctx.bindMaterialInput($('#itemTableBody'));}
 else if(mode==='multirow'){input('B00');row('MISSING');ctx.bindMaterialInput($('#itemTableBody'));}
 else input(mode==='outside_partial'?'B':'OUTSIDE');
 let work=save();await tick();assert.equal(gets.length,1,'unresolved code requires exact read');assert.equal(button.disabled,true);
 if(mode==='duplicate_click'){save();await tick();assert.equal(gets.length,1)}
 if(mode==='change'||mode==='change_back'){input('CHANGED');if(mode==='change_back')input('OUTSIDE')}
 if(mode==='quantity'){first.quantity.value='5';form.dispatch('input')}
 if(mode==='warehouse'){warehouse.value='4';form.dispatch('change')}
 if(mode==='remove')rows=[];
 if(mode==='replace'){rows=[];row('OUTSIDE')}
 if(mode==='close'||mode==='close_reopen'){modal.dispatch('hide.bs.modal');if(mode==='close_reopen')modal.dispatch('shown.bs.modal')}
 const failure=['network','http','http_success','unauthorized','expired','business','shape','bad_name','wrong_code','bad_id','duplicate_result','unknown'];
 answer(pending.shift(),failure.includes(mode)?mode:['multirow','retry'].includes(mode)?'unknown':'success');await tick();
 if(mode==='batch'||mode==='later_batch_failure'){assert.equal(gets.length,2);assert.equal(new URL(gets[0].url,'http://x').searchParams.getAll('code').length,200);assert.equal(new URL(gets[1].url,'http://x').searchParams.getAll('code').length,1);answer(pending.shift(),mode==='later_batch_failure'?'network':'success');await tick()}
 if(mode==='post_pending'){assert.equal(postResolvers.length,1);save();await tick();assert.equal(postResolvers.length,1);postResolvers[0].resolve(response({status:'success'}))}
 await work;await tick();
 let posts=requests.filter(r=>r.options.method==='POST');
 const blocked=[...failure,'change','change_back','quantity','warehouse','remove','replace','close','close_reopen','multirow','later_batch_failure','retry'];
 if(blocked.includes(mode)){assert.equal(posts.length,0);assert.equal(reloads,0);assert(messages.length>0);}
 else {assert.equal(posts.length,1);const body=posts[0].options.body;assert(body instanceof FormData);assert.equal(body.get('warehouse_id'),'2');assert.equal(body.get('csrf_token'),'fixture');assert.equal(body.get('item_remark'),'quote & 中文');assert.equal(body.getAll('material_id').length,rows.length);assert(body.getAll('material_id').every(id=>Number(id)>=1000));assert.equal(new Headers(posts[0].options.headers).get('X-CSRFToken'),'fixture');assert.equal(reloads,mode==='post_failure'?0:1)}
 assert.equal(button.disabled,!blocked.includes(mode)&&mode!=='post_failure');
 if(button.disabled){save();await tick();assert.equal(requests.filter(r=>r.options.method==='POST').length,1,'success stays locked until navigation')}
 if(mode==='retry'||mode==='post_failure'){mode='outside';let again=save();await tick();answer(pending.shift());await again;assert.equal(requests.filter(r=>r.options.method==='POST').length,p.scenario==='retry'?1:2)}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1});
'''

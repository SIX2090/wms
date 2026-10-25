"""Sales collectors distinguish untouched padding from incomplete material rows."""
from datetime import date
import json
from pathlib import Path
import re
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


def _run(page, scenario, field=None, value=None):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for real sales collector and save handlers')
    source = (ROOT / 'app/templates' / ('sales_order_' + page + '.html')).read_text(encoding='utf-8')
    functions = ['var unitName = function(', 'var findMaterial = function(',
                 'function recalcRow(', 'function recalc(', 'function fillRow(',
                 'function addRow(', 'function renumber(', 'function collect(',
                 'function ensureBlankRows(', 'async function save(']
    script = '\n'.join(_block(source, marker) + ';' for marker in functions)
    script += '\nvar originalSave = save;\n' + _block(source, 'save = async function(') + ';'
    script += '\n' + _block(source, "document.getElementById('saveTemplateBtn').addEventListener") + ');'
    script += '\n' + '\n'.join(re.findall(
        r"document\.getElementById\('save(?:New)?Btn'\)\.addEventListener\('click', function\(\) \{ save\([^;]*; \}\);", source))
    script += '\n' + re.search(r'window.submitForm = function\(\) \{ return save\([^;]*; \};', source)[0]
    script = script.replace('{{ url_for("sales_order_add") }}', '/sales/add').replace('{{ url_for("sales_order_add_page") }}', '/sales/add')
    program = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const p=JSON.parse(fs.readFileSync(0,'utf8')),rows=[],totals={},buttons={},handlers={},storage={},writes=[],requests=[],pending=[];
let href='original',promptCount=0,focused=null;
function input(value='') {
    let current=String(value);
    return {get value(){return current;},set value(v){current=String(v);},
        textContent:'',style:{},dataset:{},validity:{badInput:false},disabled:false,
        focus(){focused=this;},select(){},addEventListener(){},querySelectorAll(){return [];}};
}
function makeRow() {
    const fields={},row={dataset:{},querySelector:s=>fields[s],
        querySelectorAll:s=>s==='input'?Object.values(fields).filter(n=>n.isInput):[],remove(){}};
    Object.defineProperty(row,'innerHTML',{set(html){
        for(const m of html.matchAll(/<(input|div|button|td)\b([^>]*)>/g)) {
            const classes=m[2].match(/class="([^"]*)"/);if(!classes)continue;
            const value=m[2].match(/\bvalue="([^"]*)"/),n=input(value?value[1]:'');
            n.isInput=m[1]==='input';for(const c of classes[1].split(' '))fields['.'+c]=n;
        }
    }});
    return row;
}
const body={appendChild:r=>rows.push(r),querySelectorAll:s=>s==='tr'?rows:s==='.row-no'?rows.map(r=>r.querySelector(s)):[],
    querySelector:s=>s==='tr:last-child'?rows.at(-1):s==='tr'?rows[0]:null};
const headers={order_no:'SO-COLLECTION',date:'2026-10-25',customer_id:'1',delivery_date:'',warehouse_id:'1',salesperson_id:'',project_no:'',currency:'CNY',settlement_method:'',remark:''};
const ctx={Headers,FormData,body,defaultTaxRate:0.13,activeDropdown:null,salesSaveBusy:false,editUrl:'/sales/1/edit',
    formFields:p.fields,SALES_TEMPLATE_KEY:'templates',
    materials:[{code:'FREE',name:'Fixture material',spec:'M8',unit:'PCS',price:125}],
    escAttr:v=>String(v),handleKeydown(){},showDropdown(){},showValidation(){},rememberRecent(){},showToast(){},loadTemplates(){},
    prompt(){promptCount++;return p.scenario==='template_cancel'?null:'Fixture template';},confirm:()=>false,setTimeout(){},
    localStorage:{getItem:k=>storage[k]??null,setItem:(k,v)=>{writes.push({k,v});storage[k]=v;}},
    location:{get href(){return href;},set href(v){href=v;}},
    document:{createElement:()=>makeRow(),
        querySelector:s=>s.includes('meta')?{content:'fixture-csrf'}:{value:headers[s.match(/name="([^"]+)"/)?.[1]]??''},
        querySelectorAll:()=>[buttons.saveBtn,buttons.saveNewBtn].filter(Boolean),
        getElementById:id=>{
            if(['saveBtn','saveNewBtn','saveTemplateBtn'].includes(id))
                return buttons[id]??=Object.assign(input(),{addEventListener:(event,fn)=>handlers[id]=fn});
            return totals[id]??=input();
        }},
    fetch:(url,options)=>{
        requests.push({url,options,body:JSON.parse(options.body)});
        return new Promise(resolve=>pending.push(failure=>resolve({ok:!failure,status:failure?500:200,
            json:()=>Promise.resolve(failure?{status:'error',msg:'fixture server failure'}:{status:'success',id:1})})));
    }};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.script,ctx);
const flush=()=>new Promise(r=>setImmediate(r));
function populate(row) {
    row.querySelector('.material-code').value='FREE';row.querySelector('.qty').value='2';
    row.querySelector('.price').value='0';row.querySelector('.tax-rate').value='0';
    ctx.fillRow(row,ctx.materials[0]);
}
(async()=>{
    if(p.page==='edit')ctx.addRow({code:'FREE',quantity:2,price:0,tax_rate:0});else{ctx.addRow();populate(rows[0]);}
    ctx.ensureBlankRows(15);assert.equal(rows.length,15);
    if(p.scenario==='empty') {
        rows.length=0;ctx.ensureBlankRows(15);handlers.saveBtn();await flush();
        assert.equal(requests.length,0);assert(totals.entryStatus.textContent.includes('有效销售明细'));
        handlers.saveTemplateBtn();assert.equal(writes.length,0);assert.equal(promptCount,0);
        assert(totals.entryStatus.textContent.includes('单据为空'));return;
    }
    const target=rows[3];
    if(p.scenario==='half'||p.scenario==='template_half'||p.scenario==='export_half') {
        if(p.field==='clear_code'){populate(target);target.querySelector('.material-code').value='';}
        else if(p.field==='bad_number')target.querySelector('.qty').validity.badInput=true;
        else target.querySelector(p.field).value=p.value;
        if(p.scenario==='template_half') {
            handlers.saveTemplateBtn();assert.equal(writes.length,0);assert.equal(promptCount,0);
        }else {
            handlers.saveBtn();await ctx.submitForm();await flush();assert.equal(requests.length,0,'incomplete rows must block before HTTP');
            assert(!buttons.saveBtn.disabled,'validation failure must leave save available');
        }
        assert(totals.entryStatus.textContent.includes('第 4 行缺少物料编码'),totals.entryStatus.textContent);
        assert.equal(focused,target.querySelector('.material-code'));
        if(p.scenario==='export_half') {
            const fields={code:'.material-code',quantity:'.qty',price:'.price',tax_rate:'.tax-rate',batch_no:'.batch-no',serial_no:'.serial-no',contract_no:'.line-contract-no',project_name:'.line-project-name',remark:'.line-remark'};
            const raw=[rows[0],target].map(r=>Object.fromEntries(Object.entries(fields).map(([k,s])=>[k,r.querySelector(s).value])));
            process.stdout.write(JSON.stringify({blocked:true,rawItems:raw,requests:requests.length}));return;
        }
        // Correct the row after validation: the original save entrypoint must work.
        target.querySelector('.material-code').value='FREE';target.querySelector('.qty').value='2';
        target.querySelector('.qty').validity.badInput=false;
        handlers.saveBtn();await flush();assert.equal(requests.length,1);assert.equal(requests[0].body.items.length,2);
        pending.shift()(false);await flush();return;
    }
    const collected=ctx.collect();assert.equal(collected.items.length,1,'untouched padding must be omitted');
    assert.equal(collected.items[0].price,'0');assert.equal(collected.items[0].tax_rate,'0');
    if(p.scenario==='template'||p.scenario==='template_cancel') {
        if(p.scenario==='template_cancel') {
            handlers.saveTemplateBtn();assert.equal(promptCount,1);assert.equal(writes.length,0);return;
        }
        handlers.saveTemplateBtn();assert.equal(writes.length,1);assert.equal(promptCount,1);
        const saved=JSON.parse(storage.templates);assert.equal(saved[0].items.length,1);assert.equal(saved[0].items[0].price,'0');return;
    }
    handlers.saveBtn();await ctx.submitForm();await flush();assert.equal(requests.length,1,'DOM/global save share pending lock');
    assert.equal(requests[0].body.items.length,1);assert.equal(requests[0].body.items[0].price,'0');
    assert.equal(new Headers(requests[0].options.headers).get('X-CSRFToken'),'fixture-csrf');
    const payload=requests[0].body;
    if(p.scenario==='failure') {
        pending.shift()(true);await flush();await flush();assert(!buttons.saveBtn.disabled);assert.equal(href,'original');
        assert(totals.entryStatus.textContent.includes('fixture server failure'));
        handlers.saveBtn();await flush();assert.equal(requests.length,2);assert.equal(requests[1].body.items.length,1);
    }
    pending.shift()(false);await flush();await flush();assert.equal(href,'/sales/1');
    handlers.saveBtn();await ctx.submitForm();assert.equal(requests.length,p.scenario==='failure'?2:1,'success navigation remains locked');
    process.stdout.write(JSON.stringify({payload,requests:requests.length}));
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    completed = subprocess.run([node, '-e', program], input=json.dumps({
        'script': script, 'api': (ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'),
        'fields': json.loads(re.search(r'var formFields = (\[[^;]+\]);', source)[1].replace("'", '"')),
        'page': page, 'scenario': scenario, 'field': field, 'value': value,
    }), encoding='utf-8', capture_output=True, timeout=15)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout) if completed.stdout else None


@pytest.mark.parametrize('page', ['add', 'edit'])
@pytest.mark.parametrize('scenario', ['success', 'failure', 'template', 'template_cancel', 'empty'])
def test_sales_padding_save_and_template_entrypoints(page, scenario):
    _run(page, scenario)


@pytest.mark.parametrize('page', ['add', 'edit'])
@pytest.mark.parametrize('field,value', [
    ('.qty', '7'), ('.qty', '0'), ('.price', '0'), ('.tax-rate', '0'),
    ('.batch-no', 'BATCH'), ('.serial-no', 'SERIAL'),
    ('.line-contract-no', 'CONTRACT'), ('.line-project-name', 'PROJECT'),
    ('.line-remark', 'keep this row'), ('bad_number', ''), ('clear_code', ''),
])
def test_sales_incomplete_rows_keep_original_line_number_and_block_http(page, field, value):
    _run(page, 'half', field, value)


@pytest.mark.parametrize('page', ['add', 'edit'])
def test_sales_template_validation_does_not_write_storage(page):
    _run(page, 'template_half', '.price', '0')


@pytest.fixture
def sales_case(monkeypatch):
    from app import (app, db, Customer, Material, MaterialCategory, SalesOrder,
                     SalesOrderItem, Unit, User, Warehouse)
    monkeypatch.setitem(app.config, 'TESTING', True)
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', False)
    with app.app_context():
        assert db.engine.url.database in ('', None, ':memory:')
        db.session.remove()
        db.drop_all()
        db.create_all()
        unit = Unit(code='COL-U', name='PCS')
        category = MaterialCategory(code='COL-CAT', name='Collection fixture')
        customer = Customer(code='COL-CUSTOMER', name='Collection fixture customer')
        warehouse = Warehouse(code='COL-W', name='Collection fixture warehouse',
                              status='active', is_default=True)
        user = User(username='collection-fixture', role='admin', password_hash='fixture-only',
                    must_change_password=False)
        material = Material(code='FREE', name='Collection fixture material', price=125,
                            stock=100, unit=unit, category=category)
        db.session.add_all([unit, category, customer, warehouse, user, material])
        db.session.flush()
        order = SalesOrder(order_no='SO-COLLECTION-ORIGINAL', customer_id=customer.id,
                           warehouse=warehouse.name, warehouse_id=warehouse.id,
                           date=date(2026, 10, 25), status='draft', shipment_status='pending')
        db.session.add(order)
        db.session.flush()
        db.session.add(SalesOrderItem(sales_order_id=order.id, material_id=material.id,
                                     quantity=3, price=19.95, amount=59.85, tax_rate=0))
        db.session.commit()
        client = app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user.id)
            session['_fresh'] = True
        yield client, {'customer': customer.id, 'warehouse': warehouse.id,
                       'order': order.id, 'material': material.id}, (db, SalesOrder, Material)
        db.session.remove()


@pytest.mark.parametrize('page', ['add', 'edit'])
def test_sales_collected_padding_payload_saves_in_isolated_real_backend(page, sales_case):
    client, ids, models = sales_case
    db, SalesOrder, Material = models
    payload = _run(page, 'success')['payload']
    payload.update(customer_id=ids['customer'], warehouse_id=ids['warehouse'])
    url = '/sales/add' if page == 'add' else '/sales/' + str(ids['order']) + '/edit'
    response = client.post(url, json=payload)
    assert response.status_code == 200, response.get_json()
    db.session.expire_all()
    order = db.session.get(SalesOrder, response.get_json()['id'])
    assert len(order.items) == 1
    assert order.items[0].price == 0
    assert order.items[0].quantity == 2
    assert order.total_amount == 0
    assert db.session.get(Material, ids['material']).stock == 100


@pytest.mark.parametrize('page', ['add', 'edit'])
def test_sales_incomplete_payload_control_preserves_original_draft(page, sales_case):
    client, ids, models = sales_case
    db, SalesOrder, Material = models
    result = _run(page, 'export_half', '.qty', '7')
    assert result['blocked'] and result['requests'] == 0
    payload = {'customer_id': ids['customer'], 'warehouse_id': ids['warehouse'],
               'date': '2026-10-25', 'items': result['rawItems']}
    url = '/sales/add' if page == 'add' else '/sales/' + str(ids['order']) + '/edit'
    # Bypassing the UI must still fail atomically in the existing backend.
    response = client.post(url, json=payload)
    assert response.status_code == 400
    db.session.expire_all()
    order = db.session.get(SalesOrder, ids['order'])
    assert SalesOrder.query.count() == 1
    assert len(order.items) == 1
    assert order.items[0].price == 19.95
    assert order.items[0].quantity == 3
    assert db.session.get(Material, ids['material']).stock == 100

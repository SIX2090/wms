"""AI-C13-FIX-FORECAST-LIFECYCLE-001: run the whole page with the production HTTP client."""
import json
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]

PROGRAM = r'''
const vm=require('node:vm'),fs=require('node:fs'),p=JSON.parse(fs.readFileSync(0,'utf8'));
const states=new Map(),requests=[],toasts=[];
function state(id){if(!states.has(id))states.set(id,{value:id==='#forecastDays'?'30':id==='#actionFilter'?'all':'',visible:false,text:'',html:'',disabled:false,options:[],handlers:{}});return states.get(id);}
const document={querySelector:()=>({content:'qa-csrf'}),createElement:()=>({click(){}})};
function $(id){if(id===document)return {ready(fn){fn();}};const s=state(id);const q={val(v){if(arguments.length){s.value=v;return q;}return s.value;},text(v){s.text=v;return q;},html(v){s.html=v;return q;},show(){s.visible=true;return q;},hide(){s.visible=false;return q;},prop(k,v){s[k]=v;return q;},on(name,fn){s.handlers[name]=fn;return q;},find(){return {remove(){s.value='';s.options=[];}};},append(v){s.options.push(v);return q;}};return q;}
const c={document,$,FormData:class{},URL,AbortController,setTimeout,clearTimeout,showToast:(...args)=>toasts.push(args),confirm:()=>false,fetch:(url,opts)=>new Promise((resolve,reject)=>requests.push({url,opts,resolve,reject}))};c.window=c;
vm.createContext(c);vm.runInContext(p.escape+'\n'+p.api+'\n'+p.script,c);
const flush=async()=>{for(let i=0;i<20;i++)await Promise.resolve();};
const response=(data,status=200)=>({ok:status>=200&&status<300,status,json:async()=>data});
const row=(code,action='库存充足')=>({material_code:code,material_name:'物料'+code,category:'电气',current_stock:1,unit:'个',avg_daily:1,forecast_qty:7,gap:0,stability:'稳定',action,urgency:'常规'});
const body=(code='NEW')=>({status:'success',summary:{total:1,need_restock:0,stock_sufficient:1,stock_excess:0},forecasts:[row(code)],categories:['电气'],ai_analysis:'建议'});
function change(id,value){$(id).val(value);if(state(id).handlers.change)state(id).handlers.change();}
(async()=>{
 const name=p.scenario;
 if(name==='duplicate'){c.generateForecast();c.generateForecast();await flush();}
 else if(name==='race'||name==='stale_error'||name==='stale_finally'){
  c.generateForecast();change('#forecastDays','7');c.generateForecast();
  if(name==='stale_finally'){requests[0].resolve(response(body('OLD')));await flush();}
  else {requests[1].resolve(response(body('NEW')));await flush();if(name==='race')requests[0].resolve(response(body('OLD')));else requests[0].reject(Error('old failure'));await flush();}
 } else if(name==='change_pending'||name==='change_no_event'||name==='change_loaded'){
  c.generateForecast();
  if(name==='change_loaded'){requests[0].resolve(response(body()));await flush();change('#categoryFilter','其他');}
  else {if(name==='change_no_event')$('#forecastDays').val('7');else change('#categoryFilter','其他');requests[0].resolve(response(body('OLD')));await flush();}
 } else if(name==='retry'){
  c.generateForecast();requests[0].reject(Error('offline'));await flush();c.generateForecast();requests[1].resolve(response(body()));await flush();
 } else if(name==='category'||name==='removed_category'||name==='text'||name==='status_filter'){
  const data=body();
  if(name==='category'||name==='removed_category'){$('#categoryFilter').val('电气');if(name==='removed_category')data.categories=['其他'];}
  if(name==='status_filter'){$('#actionFilter').val('需补货');data.forecasts=[row('RESTOCK','需补货'),row('ENOUGH')];data.summary={total:2,need_restock:1,stock_sufficient:1,stock_excess:0};}
  if(name==='text'){data.forecasts=[Object.assign(row('M<CODE> & 1'),{material_name:'电缆 <b>铜芯</b> & 25A',category:'低压 <AC> & "DC"',unit:'个<UNIT> & 套',stability:'稳<定> & 波动'})];data.categories=[data.forecasts[0].category];}
  c.generateForecast();requests[0].resolve(response(data));await flush();
 } else if(name==='empty'||name==='empty_categories'||name==='normal'){
  c.generateForecast();const data=name==='normal'?body():p.emptyBody||{status:'success',forecasts:[],msg:'暂无物料数据'};if(name==='empty_categories')data.categories=[];requests[0].resolve(response(data));await flush();
 } else if(name==='invalid_days'){$('#forecastDays').val('invalid');c.generateForecast();await flush();}
 else {
  c.generateForecast();let data=body(),status=200;
  if(name==='http500')status=500;
  if(name==='business')data={status:'error',msg:'权限不足'};
  if(name==='null')data=null;
  if(name==='bad_array')data.forecasts={};
  if(name==='bad_row')data.forecasts=[null];
  if(name==='bad_summary')data.summary={};
  if(name==='bad_categories')data.categories=[null];
  if(name==='network')requests[0].reject(Error('offline'));
  else requests[0].resolve(response(data,status));await flush();
 }
 process.stdout.write(JSON.stringify({states:Object.fromEntries(states),requests:requests.map(r=>({url:r.url,method:r.opts.method,headers:r.opts.headers,body:r.opts.body&&JSON.parse(r.opts.body)})),toasts}));
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''


def run_page(scenario, empty_body=None):
    template = (ROOT / 'app/templates/ai_demand_forecast.html').read_text(encoding='utf8')
    script = template.split('<script>', 1)[1].split('</script>', 1)[0]
    shared = (ROOT / 'app/static/js/app.js').read_text(encoding='utf8')
    start = shared.index('function escapeHtml(')
    escape = shared[start:shared.index('\n}', start) + 2]
    payload = dict(script=script, api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf8'), escape=escape, scenario=scenario, emptyBody=empty_body)
    proc = subprocess.run([shutil.which('node') or 'node', '--max-old-space-size=64', '-e', PROGRAM], input=json.dumps(payload), text=True, capture_output=True, encoding='utf8', timeout=20)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.parametrize('scenario', ['race', 'stale_error'])
def test_latest_prediction_survives_older_result_or_error(scenario):
    result = run_page(scenario)
    assert 'NEW' in result['states']['#forecastTable']['html']
    assert 'OLD' not in result['states']['#forecastTable']['html']
    assert result['toasts'] == []
    assert result['states']['#forecastDays']['value'] == '7'


def test_old_finally_does_not_unlock_new_prediction():
    result = run_page('stale_finally')
    assert result['states']['#loadingArea']['visible']
    assert result['states']['#generateForecastBtn']['disabled']
    assert not result['states']['#resultArea']['visible']


@pytest.mark.parametrize('scenario', ['change_pending', 'change_no_event', 'change_loaded'])
def test_changed_query_hides_or_rejects_previous_result(scenario):
    result = run_page(scenario)
    assert not result['states']['#resultArea']['visible']
    assert not result['states']['#loadingArea']['visible']
    assert result['toasts'] == []


def test_duplicate_generation_has_one_request_and_real_csrf_header():
    result = run_page('duplicate')
    assert len(result['requests']) == 1
    assert result['requests'][0]['method'] == 'POST'
    assert result['requests'][0]['headers']['X-CSRFToken'] == 'qa-csrf'
    assert result['requests'][0]['body'] == {'forecast_days': 30, 'category': ''}


@pytest.mark.parametrize('scenario', ['http500', 'business', 'null', 'bad_array', 'bad_row', 'bad_summary', 'bad_categories', 'network'])
def test_failure_hides_results_and_allows_retry(scenario):
    result = run_page(scenario)
    assert not result['states']['#resultArea']['visible']
    assert not result['states']['#loadingArea']['visible']
    assert not result['states']['#generateForecastBtn']['disabled']
    assert len(result['toasts']) == 1
    assert result['toasts'][0][1] == 'danger'


def test_failed_request_can_be_retried():
    result = run_page('retry')
    assert len(result['requests']) == 2
    assert result['states']['#resultArea']['visible']
    assert 'NEW' in result['states']['#forecastTable']['html']


@pytest.mark.parametrize('scenario', ['category', 'removed_category'])
def test_refresh_preserves_query_category_even_if_removed_from_options(scenario):
    result = run_page(scenario)
    assert result['states']['#categoryFilter']['value'] == '电气'
    assert result['requests'][0]['body']['category'] == '电气'
    assert any('电气' in option for option in result['states']['#categoryFilter']['options'])


@pytest.mark.parametrize('scenario', ['empty', 'empty_categories'])
def test_legitimate_empty_response_renders_zero_summary(scenario):
    result = run_page(scenario)
    assert result['states']['#resultArea']['visible']
    assert result['states']['#summaryTotal']['text'] == 0
    assert '暂无预测数据' in result['states']['#forecastTable']['html']
    assert result['states']['#aiAnalysis']['text'] == '暂无物料数据'
    assert result['toasts'] == []


def test_new_result_keeps_current_action_filter():
    result = run_page('status_filter')
    assert result['states']['#actionFilter']['value'] == '需补货'
    assert 'RESTOCK' in result['states']['#forecastTable']['html']
    assert 'ENOUGH' not in result['states']['#forecastTable']['html']
    assert result['states']['#summaryTotal']['text'] == 2


class RenderedHTML(HTMLParser):
    def __init__(self, source):
        super().__init__(); self.tags = []; self.text = []; self.options = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == 'option': self.options.append(dict(attrs))

    def handle_data(self, value):
        self.text.append(value)


def test_response_table_values_are_literal_text():
    result = run_page('text')
    parsed = RenderedHTML(result['states']['#forecastTable']['html'])
    assert set(parsed.tags) <= {'tr', 'td', 'span', 'strong'}
    for value in ['M<CODE> & 1', '电缆 <b>铜芯</b> & 25A', '低压 <AC> & "DC"', '个<UNIT> & 套', '稳<定> & 波动']:
        assert value in ''.join(parsed.text)


def test_category_options_keep_literal_value_and_text():
    result = run_page('text')
    parsed = RenderedHTML(''.join(result['states']['#categoryFilter']['options']))
    assert parsed.tags == ['option']
    assert parsed.options[0]['value'] == '低压 <AC> & "DC"'
    assert ''.join(parsed.text) == '低压 <AC> & "DC"'


def test_normal_result_and_invalid_period_controls():
    normal = run_page('normal')
    assert normal['states']['#resultArea']['visible']
    assert 'NEW' in normal['states']['#forecastTable']['html']
    invalid = run_page('invalid_days')
    assert invalid['requests'] == []
    assert invalid['toasts'][0][1] == 'danger'


def test_real_isolated_backend_empty_envelope_is_accepted(monkeypatch):
    import app as wms
    with wms.app.app_context():
        wms.db.drop_all(); wms.db.create_all()
        monkeypatch.setattr(wms, '_ai_capability_allowed', lambda capability: True)
        with wms.app.test_request_context('/api/ai/demand_forecast', method='POST', json={'forecast_days': 30}):
            response = wms.api_demand_forecast.__wrapped__()
            assert response.status_code == 200
            body = response.get_json()
            assert body == {'status': 'success', 'forecasts': [], 'msg': '暂无物料数据'}
    result = run_page('empty', body)
    assert result['states']['#resultArea']['visible']
    assert result['states']['#summaryTotal']['text'] == 0
    assert result['toasts'] == []

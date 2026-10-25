"""BUG-2026-10-25-008: execute real shared delete entries and the production client."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENTRIES = ['batch', 'single', 'toolbar', 'detail']


@pytest.mark.parametrize('entry', ENTRIES)
@pytest.mark.parametrize('scenario', [
    'success', 'business', 'http_success', 'html', 'invalid_json', '401', '419',
    'network', 'null', 'primitive', 'array', 'empty_object', 'cancel',
    'busy_request', 'cross_entry', 'navigation_wait', 'failure_retry',
    'snapshot', 'sync_fetch_throw', 'sync_confirm_throw', 'sync_navigation_throw',
])
def test_shared_delete_runtime(entry, scenario):
    run(entry, scenario)


@pytest.mark.parametrize('entry', ['single', 'toolbar', 'detail'])
def test_confirmation_is_part_of_shared_lock(entry):
    run(entry, 'busy_confirm')


@pytest.mark.parametrize('entry', ['batch', 'toolbar', 'detail'])
def test_empty_selection_does_not_lock_or_send(entry):
    run(entry, 'empty')


@pytest.mark.parametrize('scenario', [
    'detail_mixed', 'detail_all_error', 'detail_encoded', 'fallback_record',
    'detail_mixed_http', 'detail_mixed_null',
])
def test_detail_fallback_keeps_individual_protocol_and_summary(scenario):
    run('detail', scenario)


def run(entry, scenario):
    node = shutil.which('node')
    assert node, 'Node is required for shared deletion runtime coverage'
    program = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const p=JSON.parse(fs.readFileSync(0,'utf8'));
const source=fs.readFileSync(p.root+'/app/static/js/app.js','utf8');
const base=fs.readFileSync(p.root+'/app/templates/base.html','utf8');
const api=fs.readFileSync(p.root+'/app/static/js/api.js','utf8');
const scripts=[
 base.slice(base.indexOf('    var __wmsLastErrToast ='),base.indexOf('    // F2.14 全局兜底：')),
 source.slice(source.indexOf('// 批量删除'),source.indexOf('function setupSortableHeaders(')),
 source.slice(source.indexOf('// 单个删除'),source.indexOf('const WMS_ACTION_MODULES')),
 source.slice(source.indexOf('function getSelectedIds('),source.indexOf('function printCurrent(')),
 source.slice(source.indexOf('function buildModuleUrl('),source.indexOf('function buildCurrentFilteredUrl(')),
 base.slice(base.indexOf('    function csrfFetch('),base.indexOf('    // Deprecated alias'))
];
let mode=p.scenario, checked=[{value:'71'},{value:'72'}], calls=[],messages=[],confirmations=[],sessionConfirmations=[],timers=[],reloads=0,navigations=[],httpWait=[],confirmWait=[];
let confirmationValue=true,recordId=null,navigationThrows=mode==='sync_navigation_throw';
const table={id:'fixtureTable',querySelectorAll:()=>checked};
const location={pathname:'/subcontract_issue',origin:'http://qa.invalid',reload(){if(navigationThrows)throw new Error('fixture navigation failure');reloads++;}};
Object.defineProperty(location,'href',{get(){return navigations.at(-1)||'/subcontract_issue?embedded=1';},set(value){if(navigationThrows)throw new Error('fixture navigation failure');navigations.push(value);}});
const document={querySelector:selector=>selector==='meta[name="csrf-token"]'?{content:'fixture-csrf'}:null,getElementById:()=>table,querySelectorAll:()=>checked};
const valid={status:'success',msg:'fixture deleted'};
function response(status,data,invalid=false){return {ok:status>=200&&status<300,status,json:()=>invalid?Promise.reject(new SyntaxError('fixture invalid JSON')):Promise.resolve(data)};}
function nextResponse(index){
 if(mode==='http_success')return response(500,valid);
 if(mode==='401'||mode==='419')return response(Number(mode),valid);
 if(mode==='html'||mode==='invalid_json')return response(200,null,true);
 if(mode==='null')return response(200,null);
 if(mode==='primitive')return response(200,'not a result');
 if(mode==='array')return response(200,[]);
 if(mode==='empty_object')return response(200,{});
 if(mode==='business'||mode==='failure_retry'||mode==='detail_all_error')return response(200,{status:'error',msg:'fixture rejected'});
 if(mode==='detail_mixed'&&index%2===1)return response(200,{status:'error',msg:'fixture rejected second'});
 if(mode==='detail_mixed_http'&&index%2===1)return response(500,valid);
 if(mode==='detail_mixed_null'&&index%2===1)return response(200,null);
 return response(200,valid);
}
const ctx={Headers,FormData,URL,URLSearchParams,Promise,console,document,location,
 getCsrfToken:()=> 'fixture-csrf',getCurrentRecordId:()=>recordId,
 showToast:(message,type)=>messages.push({message,type}),
 confirm:(message)=>{if(message.startsWith('登录已过期')){sessionConfirmations.push(message);return false;}confirmations.push(message);if(mode==='sync_confirm_throw')throw new Error('fixture confirmation failure');return confirmationValue;},
 showConfirm:(message)=>{confirmations.push(message);if(mode==='sync_confirm_throw')throw new Error('fixture confirmation failure');if(mode==='busy_confirm'||mode==='snapshot')return new Promise(resolve=>confirmWait.push(resolve));return Promise.resolve(confirmationValue);},
 setTimeout:(callback,delay)=>{timers.push({callback,delay});return timers.length;},
 fetch:(url,options)=>{const index=calls.length;calls.push({url,options});if(mode==='sync_fetch_throw')throw new Error('fixture synchronous transport failure');if(mode==='network')return Promise.reject(new Error('fixture network failure'));if(mode==='busy_request'||mode==='cross_entry')return new Promise(resolve=>httpWait.push({resolve,index}));return Promise.resolve(nextResponse(index));}
};ctx.window=ctx;ctx.globalThis=ctx;vm.createContext(ctx);vm.runInContext(api,ctx);scripts.forEach(script=>vm.runInContext(script,ctx));
const module={tableId:'fixtureTable',deleteUrl:'/subcontract_issue/batch_delete',detailDeleteUrl:'/subcontract_issue/{id}/delete',listUrl:'/original-list?embedded=1'};
const detailModule={...module,deleteUrl:null};
const pending=[];
function invoke(entry=p.entry){const returned=entry==='batch'?ctx.batchDelete('/user/delete','fixtureTable'):entry==='single'?ctx.deleteItem('/material/delete',71):ctx.deleteCurrent(entry==='detail'?detailModule:module);pending.push(Promise.resolve(returned));}
const flush=async()=>{for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));};
const count=()=>p.entry==='detail'?checked.length:1;
const succeeded=()=>reloads+navigations.length+timers.filter(t=>t.delay===600||t.delay===650).length>0;
const runTimers=()=>{const batch=timers.splice(0);for(const timer of batch)if(timer.delay===600||timer.delay===650)timer.callback();};
function assertSent(expectedCount){assert.equal(calls.length,expectedCount,'unexpected number of actual POST requests');for(const call of calls){assert.equal(call.options.method,'POST');assert.equal(new Headers(call.options.headers).get('X-CSRFToken'),'fixture-csrf');assert.equal(new Headers(call.options.headers).get('X-Requested-With'),'XMLHttpRequest');assert.equal(call.options.credentials,'same-origin');}}
function assertNoNavigation(){assert.equal(reloads,0);assert.equal(navigations.length,0);assert(!timers.some(t=>t.delay===600||t.delay===650),'failure scheduled a success navigation');}
function assertFailed(){assertNoNavigation();assert(messages.some(x=>x.type==='danger'),'failure needs a visible error');assert(!messages.some(x=>x.type==='success'),'failure was announced as success');}
function assertProtocol(){
 if(p.entry==='detail'){assert(calls.every(c=>c.options.body===undefined),'individual detail DELETE POST must retain its absent body');}
 else {const payload=JSON.parse(calls[0].options.body);assert.deepEqual(payload,{ids:p.entry==='single'?[71]:['71','72']});}
}
(async()=>{
 if(mode==='cancel')confirmationValue=false;
 if(mode==='empty')checked=[];
 if(mode==='detail_encoded')checked=[{value:'A/B ?'},{value:'72'}];
 if(mode==='fallback_record'){checked=[];recordId='91';}
 const expected=count()||1;
 invoke();await flush();
 if(mode==='cancel'||mode==='empty'){
  assertSent(0);assertNoNavigation();mode='success';checked=[{value:'71'},{value:'72'}];confirmationValue=true;invoke();await flush();assertSent(p.entry==='detail'?2:1);assert(succeeded(),'cancel/empty must leave a usable manual retry');
 }else if(mode==='busy_request'||mode==='cross_entry'){
  assertSent(expected);const firstConfirmCount=confirmations.length;
  if(mode==='cross_entry'){invoke('single');invoke('batch');invoke('toolbar');}else invoke();await flush();
  assertSent(expected);assert.equal(confirmations.length,firstConfirmCount,'busy deletion reopened confirmation');
  mode='success';for(const item of httpWait.splice(0))item.resolve(nextResponse(item.index));await flush();assert(succeeded());
 }else if(mode==='busy_confirm'){
  assertSent(0);invoke();invoke('batch');await flush();assert.equal(confirmations.length,1,'shared lock must start before async confirmation');assertSent(0);
  mode='success';for(const resolve of confirmWait.splice(0))resolve(true);await flush();assertSent(expected);assert(succeeded());
 }else if(mode==='snapshot'){
  if(p.entry==='batch'){assertSent(1);assertProtocol();}
  else {assertSent(0);checked=[{value:'999'}];module.deleteUrl='/wrong-endpoint';module.detailDeleteUrl='/wrong/{id}';module.listUrl='/wrong-list';detailModule.detailDeleteUrl='/wrong/{id}';detailModule.listUrl='/wrong-list';mode='success';for(const resolve of confirmWait.splice(0))resolve(true);await flush();assertSent(expected);assertProtocol();if(p.entry==='detail')assert.deepEqual(calls.map(c=>c.url),['/subcontract_issue/71/delete','/subcontract_issue/72/delete'],'detail endpoints changed after confirmation');}
  runTimers();if(p.entry==='toolbar'||p.entry==='detail')assert.deepEqual(navigations,['/original-list?embedded=1'],'navigation target changed after confirmation');
 }else if(mode==='navigation_wait'){
  assertSent(expected);assert(succeeded());const firstConfirmCount=confirmations.length;invoke();invoke('single');await flush();assertSent(expected);assert.equal(confirmations.length,firstConfirmCount);runTimers();assert.equal(reloads+navigations.length,1);
 }else if(mode==='failure_retry'){
  assertSent(expected);assertFailed();mode='success';invoke();await flush();assertSent(expected*2);assert(succeeded(),'manual retry did not recover');
 }else if(mode==='sync_navigation_throw'){
  runTimers();await flush();assert(messages.some(x=>x.type==='danger'&&x.message==='删除已完成，但页面刷新/跳转失败，请手动刷新核对'),'a successful deletion must not be announced as a failed deletion when navigation fails');navigationThrows=false;mode='success';invoke();await flush();assertSent(expected*2);runTimers();assert.equal(reloads+navigations.length,1);
 }else if(mode==='detail_mixed'||mode==='detail_mixed_http'||mode==='detail_mixed_null'){
  assertSent(2);assertProtocol();assert(messages.some(x=>/1 条删除成功，1 条失败/.test(x.message)),'individual partial summary was lost');assert(succeeded());
 }else if(mode==='detail_all_error'){
  assertSent(2);assertFailed();assert(messages.some(x=>/0 条删除成功，2 条失败/.test(x.message)));
 }else if(mode==='detail_encoded'){
  assertSent(2);assertProtocol();assert.equal(calls[0].url,'/subcontract_issue/A%2FB%20%3F/delete');assert(succeeded());
 }else if(mode==='fallback_record'){
  assertSent(1);assert.equal(calls[0].url,'/subcontract_issue/91/delete');assertProtocol();assert(succeeded());
 }else if(mode==='success'){
  assertSent(expected);assertProtocol();assert(succeeded());if(p.entry==='single')assert(timers.some(t=>t.delay===600));if(p.entry==='toolbar'||p.entry==='detail')assert(timers.some(t=>t.delay===650));
 }else{
  assertSent(mode==='sync_confirm_throw'?0:expected);assertFailed();
  if(['null','primitive','array','empty_object','html','invalid_json'].includes(mode))assert(messages.some(x=>/[\u4e00-\u9fff]/.test(x.message)),'invalid result should have Chinese recovery feedback');
 }
 if(p.scenario==='401'||p.scenario==='419')assert.equal(sessionConfirmations.length,1,'the existing API session prompt should occur once and be explicitly declined');
 await Promise.all(pending);
 console.log(JSON.stringify({entry:p.entry,scenario:p.scenario,requests:calls.map(c=>({url:c.url,body:c.options.body??null})),messages,reloads,navigations,timers:timers.map(t=>t.delay)}));
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
'''
    result = subprocess.run(
        [node, '-e', program], input=json.dumps({'root': ROOT.as_posix(), 'entry': entry, 'scenario': scenario}),
        capture_output=True, text=True, encoding='utf-8', timeout=30,
    )
    assert result.returncode == 0, f'{entry}/{scenario}\n{result.stdout}\n{result.stderr}'
    return json.loads(result.stdout)

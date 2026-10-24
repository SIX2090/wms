"""Run the real AI shell initializer, API client, event handlers and SSE reads."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def assistant_source():
    template = (ROOT / 'app/templates/base.html').read_text(encoding='utf-8')
    if "filename='js/pages/ai-assistant.js'" in template:
        return (ROOT / 'app/static/js/pages/ai-assistant.js').read_text(encoding='utf-8')
    return next(body for body in re.findall(r'<script>(.*?)</script>', template, re.S) if "const button = document.getElementById('aiAssistantButton')" in body)


@pytest.mark.parametrize('mode', ['clear', 'feedback', 'attachment', 'stream'])
@pytest.mark.parametrize('scenario', ['success', 'business', 'http', 'html', 'network', '401', '419'])
def test_actual_assistant_transport(mode, scenario):
    run(mode, scenario)


@pytest.mark.parametrize('scenario', ['read_failure', 'partial_failure', 'no_reader', 'json_error', 'history', 'embedded', 'markdown'])
def test_actual_assistant_lifecycle(scenario):
    run('stream', scenario)


def run(mode, scenario):
    source = assistant_source()
    # Expose existing closure functions only in this fixture, without replacing them.
    ending = source.rindex('})();')
    source = source[:ending] + "window.fixtureAssistant={sendAssistantMessage,submitFeedback,renderMarkdown,chatHistory};\n" + source[ending:]
    node = shutil.which('node')
    assert node, 'Node.js is required for AI shell lifecycle verification'
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const events={},requests=[],toasts=[],confirmations=[],unhandled=[];let resolveRequest;
process.on('unhandledRejection',error=>unhandled.push(error));
function el(){const classes=new Set();return {style:{},dataset:{},attrs:{},children:[],handlers:{},value:'',disabled:false,innerHTML:'',textContent:'',scrollHeight:0,
 className:'',classList:{contains:k=>classes.has(k),add:k=>classes.add(k),remove:k=>classes.delete(k),toggle(k,on){on=on===undefined?!classes.has(k):on;if(on)classes.add(k);else classes.delete(k);return on;}},
 addEventListener(k,fn){this.handlers[k]=fn;},setAttribute(k,v){this.attrs[k]=v;},getAttribute(k){return this.attrs[k]??null;},
 appendChild(n){n.parent=this;this.children.push(n);},remove(){if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);},focus(){},
 querySelector(s){return this.children.find(n=>n.className.split(' ').includes(s.slice(1)))||null;},querySelectorAll(){return [];},closest(){return null;}};}
const ids={};for(const id of ['aiAssistantButton','aiAssistantPanel','aiAssistantClose','aiHistoryClear','aiAssistantForm','aiAssistantInput','aiAssistantMessages','aiPasteButton','aiUploadButton','aiImageInput','aiPendingAttachments','aiAssistantHideBtn'])ids[id]=el();
const messages=ids.aiAssistantMessages,panel=ids.aiAssistantPanel,input=ids.aiAssistantInput;
const doc={title:'仓库页面',body:el(),documentElement:{scrollHeight:0},getElementById:id=>ids[id]||null,
 createElement:()=>el(),addEventListener(k,f){events[k]=f;},querySelector:()=>({content:'csrf-fixture'})};
let activeScenario=p.scenario;
function response(url){const scenario=activeScenario;
 if(scenario==='network')return Promise.reject(Error('fixture offline'));
 const status=scenario==='http'?503:['401','419'].includes(scenario)?Number(scenario):scenario==='html'?502:200;
 let data={status:scenario==='business'?'error':'success',msg:scenario==='business'?'业务拒绝':'server-message',reply:'安全回复',cards:[{title:'卡片'}],actions:[]};
 if(url.includes('conversations?'))data={status:'success',conversations:[{id:9,status:'active'}]};
 if(url.includes('conversations/'))data={status:'success',messages:[{role:'user',content:'历史问题'},{role:'assistant',content:'历史回答'}]};
 if(scenario==='json_error')data={status:'error',msg:'未启用模型'};
 const streamSuccess=url.endsWith('/stream')&&['success','read_failure','partial_failure','no_reader'].includes(scenario);
 let index=0;const all='data: '+JSON.stringify({type:'token',content:'中'})+'\n\ndata: '+JSON.stringify({type:'cards',content:[{title:'流式卡片'}]})+'\n\ndata: '+JSON.stringify({type:'done',content:'中文回复'})+'\n\n';
 const bytes=new TextEncoder().encode(all),split=all.indexOf('中')+1;
 const chunks=[bytes.slice(0,split),bytes.slice(split,split+1),bytes.slice(split+1)];
 const reader={read(){if(scenario==='read_failure')return Promise.reject(Error('stream disconnected'));
 if(scenario==='partial_failure'){if(index++===0)return Promise.resolve({done:false,value:new TextEncoder().encode('data: '+JSON.stringify({type:'token',content:'部分回复'})+'\n\n')});return Promise.reject(Error('stream disconnected'));}
 return Promise.resolve(index<chunks.length?{done:false,value:chunks[index++]}:{done:true});}};
 return Promise.resolve({status,ok:status>=200&&status<300,headers:{get:()=>streamSuccess?'text/event-stream':'application/json'},
 json:()=>scenario==='html'?Promise.reject(SyntaxError('HTML response')):Promise.resolve(data),body:streamSuccess&&scenario!=='no_reader'?{getReader:()=>reader}:null});
}
const ctx={document:doc,Headers,FormData,TextDecoder,Promise,Date,console:{error(){},warn(){}},
 navigator:{clipboard:{}},localStorage:{getItem:()=>null,setItem(){}},setTimeout:()=>1,clearTimeout(){},
 showToast:(msg,type)=>toasts.push({msg,type}),confirm:msg=>{confirmations.push(msg);return false;},
 escapeHtml:v=>String(v??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'),
 fetch:(url,options={})=>{requests.push({url,options});return new Promise((resolve,reject)=>{resolveRequest=()=>response(url).then(resolve,reject);});},
 location:{origin:'https://wms.test',pathname:'/material',search:'?warehouse=2'},addEventListener(){},crypto:{randomUUID:()=> 'fixture-request-id'},WmsTabs:{getActiveContext:()=>({url:'/opening_stock?embedded=1',title:'期初库存'})},$:{ajaxSetup(){}}};
ctx.window=ctx;ctx.self=ctx;ctx.top=p.scenario==='embedded'?{}:ctx;
vm.createContext(ctx);vm.runInContext(p.wrapper,ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.source,ctx);
const flush=()=>new Promise(setImmediate);
function rendered(){return messages.children.map(n=>n.children.map(c=>c.textContent+' '+c.innerHTML).join(' ')).join('\n');}
async function finish(){for(let i=0;i<14;i++)await flush();}
(async()=>{
 if(p.scenario==='embedded'){assert.equal(ctx.fixtureAssistant,undefined);assert.equal(requests.length,0);assert.equal(panel.parent,undefined);return;}
 const api=ctx.fixtureAssistant;assert(api);assert.equal(requests.length,0,'do not load history before first opening');
 if(p.scenario==='markdown'){const html=api.renderMarkdown('<img src=x onerror=attack()>\n**强调**\n|a|b|\n|--|--|\n|1|2|');assert(!html.includes('<img'));assert(html.includes('&lt;img'));assert(html.includes('<strong>强调</strong>'));assert(html.includes('<table>'));return;}
 if(p.scenario==='history'){
  ids.aiAssistantButton.handlers.click();assert.equal(requests[0].url,'/api/ai/conversations?limit=1');resolveRequest();await finish();
  assert.equal(requests[1].url,'/api/ai/conversations/9?limit=20');resolveRequest();await finish();
  assert.equal(api.chatHistory.length,2);assert(rendered().includes('历史问题'));assert(rendered().includes('历史回答'));
  ids.aiAssistantClose.handlers.click();ids.aiAssistantButton.handlers.click();assert.equal(requests.length,2);return;
 }
 api.chatHistory.push({role:'assistant',content:'old'});
 if(p.mode==='clear')ids.aiHistoryClear.handlers.click();
 else if(p.mode==='feedback')api.submitFeedback(7,'match_error');
 else api.sendAssistantMessage('查询物料',p.mode==='attachment'?[{name:'fixture.png',data_url:'data:image/png;base64,AAAA'}]:[]);
 assert.equal(requests.length,1);
 const request=requests[0],expected={clear:'/api/ai/chat/clear',feedback:'/api/ai/feedback',attachment:'/api/ai/warehouse_assistant',stream:'/api/ai/chat/stream'};
 assert.equal(request.url,expected[p.mode]);assert.equal(request.options.method,'POST');
 if(p.mode==='attachment'||p.mode==='stream'){
  const payload=JSON.parse(request.options.body);assert.equal(payload.request_id,'fixture-request-id');assert.equal(payload.message,'查询物料');
  assert.equal(payload.page_url,'/opening_stock?embedded=1');assert.equal(payload.page_title,'期初库存');
  if(p.mode==='attachment')assert.equal(payload.attachments.length,1);else assert.equal(payload.history[0].content,'old');
  assert.equal(input.disabled,true);api.sendAssistantMessage('重复点击',[]);assert.equal(requests.length,1);
 }
 if(p.mode==='feedback')assert.deepEqual(JSON.parse(request.options.body),{rating:'not_helpful',error_type:'match_error',ai_message_id:7});
 resolveRequest();await finish();
 if(p.scenario==='no_reader'){assert.equal(requests.length,2);resolveRequest();await finish();}
 const success=['success','no_reader'].includes(p.scenario);
 if(p.mode==='clear'){
  assert.equal(api.chatHistory.length,0,'keep the existing local-context fallback');
  if(success)assert(rendered().includes('已清空对话历史'));
  else {assert(!rendered().includes('已清空对话历史，可以开始新的对话'),'must not claim server history was cleared');assert(rendered().includes('本地'));}
 }else if(p.mode==='feedback'){
  assert.equal(toasts.some(t=>t.type==='success'),success,'feedback must never acknowledge an HTTP failure');
  if(!success)assert(toasts.some(t=>t.type==='danger'),'feedback failures must be visible');
 }else{
  assert.equal(input.disabled,false,'every terminal outcome must release the sending lock');
  assert.equal(panel.classList.contains('is-busy'),false);
  if(success)assert(rendered().includes(p.mode==='attachment'||p.scenario==='no_reader'?'安全回复':'中文回复'));
  else {assert(!messages.children.some(n=>n.className==='ai-card'),'HTTP/business failures must not render success cards');assert(rendered().includes('处理失败')||rendered().includes('未启用模型')||rendered().includes('业务拒绝'));}
 }
 assert.equal(unhandled.length,0,'stream reader rejection must reach the normal error path');
 assert.equal(request.options.credentials??'same-origin','same-origin');assert.equal(request.options.headers['X-CSRFToken'],'csrf-fixture');assert.equal(request.options.headers['X-Requested-With'],'XMLHttpRequest');
 if(['401','419'].includes(p.scenario))assert.equal(confirmations.length,1);
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''
    base = (ROOT / 'app/templates/base.html').read_text(encoding='utf-8')
    wrapper = re.findall(r'<script>(.*?)</script>', base, re.S)[0].split('    // F2.14 全局兜底：')[0]
    result = subprocess.run([node, '-e', program], input=json.dumps(dict(source=source, wrapper=wrapper, api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'), mode=mode, scenario=scenario)),
                            capture_output=True, text=True, encoding='utf-8', timeout=25)
    assert result.returncode == 0, result.stdout + result.stderr

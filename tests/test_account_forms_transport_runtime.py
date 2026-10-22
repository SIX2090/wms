"""Account form callbacks execute in Node with production api.js; no live accounts."""
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest
from jinja2 import DictLoader, Environment
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
PAGES = {'my_profile': ('myProfileForm', 'myProfileMsg', '/profile/edit'),
         'change_password': ('changePasswordForm', 'message', '/user/change_password')}


class Fields(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.fields = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('input', 'textarea') and attrs.get('name') and 'disabled' not in attrs:
            self.fields.append(attrs['name'])


PROGRAM = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let calls=[],pending=[],sessions=0;
const fields=Object.fromEntries(p.fields.map(name=>[name,'  fixture-'+name+' & <literal>  ']));
const button={disabled:false},message={className:'',textContent:'',innerHTML:'never changed'};
const form={dataset:{},querySelector:selector=>{assert.equal(selector,'button[type="submit"]');return button;},addEventListener:(name,callback)=>{assert.equal(name,'submit');form.handler=callback;}};
class FD {constructor(source){assert.equal(source,form);this.values={...fields};}get(key){return this.values[key];}}
const document={getElementById:id=>id===p.form?form:id===p.message?message:null,querySelector:()=>({content:'fixture-csrf'})};
const ctx={document,FormData:FD,fetch:(url,options)=>{calls.push({url,options});return new Promise((resolve,reject)=>pending.push({resolve,reject}));},Promise,location:{href:'/fixture/current'},confirm:()=>{sessions++;return false;},setTimeout:()=>0};ctx.window=ctx;
vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.script,ctx);
const submit=()=>form.handler.call(form,{preventDefault(){}});
const evil='<img src=x onerror="alert(1)"> & 失败';
function response(scenario){const status={http:400,http_success:400,html:502,unauthorized:401,expired:419}[scenario]||200;return {status,ok:status===200,json:()=>['html','html200','malformed'].includes(scenario)?Promise.reject(new SyntaxError('Invalid JSON')):Promise.resolve(scenario==='null'?null:scenario==='business'||scenario==='http'?{status:'error',msg:evil}:scenario==='success_default'?{status:'success'}:{status:'success',msg:evil,redirect:'/fixture/continue'})};}
const finish=async(index,scenario,work)=>{if(scenario==='network')pending[index].reject(new Error(evil));else pending[index].resolve(response(scenario));await work;for(let i=0;i<3;i++)await new Promise(r=>setImmediate(r));};
(async()=>{
 const work=submit();assert.equal(calls.length,1);assert.equal(button.disabled,true);assert.equal(message.textContent,'正在保存...');
 const duplicate=submit();await duplicate;assert.equal(calls.length,1,'busy form must reject repeated submit events');
 assert.equal(calls[0].url,p.url);const options=calls[0].options;assert.equal(options.method,'POST');assert.equal(options.credentials,'same-origin');assert.equal(options.headers['X-CSRFToken'],'fixture-csrf');assert.equal(options.headers['X-Requested-With'],'XMLHttpRequest');assert(!('Content-Type' in options.headers));assert(options.body instanceof FD);assert.deepEqual(options.body.values,fields);
 await finish(0,p.scenario,work);const navigating=p.page==='change_password'&&['success','success_default'].includes(p.scenario);assert.equal(button.disabled,navigating);assert.equal(form.dataset.submitting,navigating?'true':'');assert.equal(message.innerHTML,'never changed');
 if(['success','success_default'].includes(p.scenario)){assert(message.className.includes('alert-success'));assert.equal(ctx.location.href,p.page==='change_password'?(p.scenario==='success_default'?'/':'/fixture/continue'):'/fixture/current');}
 else {assert(message.className.includes('alert-danger'));assert.notEqual(message.textContent,'正在保存...');assert.equal(ctx.location.href,'/fixture/current');if(['unauthorized','expired'].includes(p.scenario))assert.equal(sessions,1);if(['business','http','network'].includes(p.scenario))assert(message.textContent.includes(evil));
 const retry=submit();assert.equal(calls.length,2,'retry requires a new manual submit');assert.deepEqual(calls[1].options.body.values,fields);await finish(1,'success',retry);assert(message.className.includes('alert-success'));assert.equal(button.disabled,p.page==='change_password');}
 if(p.page==='change_password'){const count=calls.length;await submit();assert.equal(calls.length,count,'successful password navigation must keep submit locked');}
 assert.deepEqual(Object.keys(fields).sort(),p.expected.sort());process.stdout.write(JSON.stringify({message:message.textContent,calls:calls.length}));
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''


def execute(page, scenario):
    node = shutil.which('node')
    assert node, 'Node.js is required for account callback regression tests'
    source = (ROOT / f'app/templates/{page}.html').read_text(encoding='utf-8')
    script = re.search(r'<script>(.*?)</script>', source, re.S)
    assert script
    form, message, url = PAGES[page]
    endpoints = {'edit_my_profile': '/profile/edit', 'change_own_password': '/user/change_password'}
    rendered = Environment().from_string(script.group(1)).render(url_for=lambda endpoint: endpoints[endpoint])
    expected = ['csrf_token', 'email', 'phone', 'bio'] if page == 'my_profile' else [
        'csrf_token', 'current_password', 'new_password', 'confirm_password']
    payload = dict(page=page, scenario=scenario, form=form, message=message, url=url,
                   fields=Fields(source).fields, expected=expected, script=rendered,
                   api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'))
    result = subprocess.run([node, '--max-old-space-size=64', '-e', PROGRAM], input=json.dumps(payload),
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize('page', PAGES)
@pytest.mark.parametrize('scenario', ['success', 'success_default', 'business', 'http', 'http_success',
                                    'html', 'html200', 'malformed', 'null', 'unauthorized', 'expired', 'network'])
def test_real_form_submission_preserves_fields_busy_feedback_retry_and_navigation(page, scenario):
    execute(page, scenario)


@pytest.mark.parametrize('role', ['admin', 'warehouse', 'purchase', 'production', 'sales', 'viewer', 'finance', 'user'])
def test_actual_profile_template_respects_finance_readonly_without_blocking_own_password(role):
    source = (ROOT / 'app/templates/my_profile.html').read_text(encoding='utf-8')
    env = Environment(loader=DictLoader({'profile': source, 'base.html': '{% block content %}{% endblock %}'}))
    profile = SimpleNamespace(role=role, username='fixture', email='fixture@example.test', phone='123', bio='fixture')
    html = env.get_template('profile').render(profile_user=profile, csrf_token=lambda: 'fixture',
                                             url_for=lambda endpoint: '/profile/edit')
    class Controls(HTMLParser):
        def __init__(self):
            super().__init__()
            self.nodes = []
        def handle_starttag(self, tag, attrs):
            self.nodes.append((tag, dict(attrs)))
    controls = Controls()
    controls.feed(html)
    buttons = [attrs for tag, attrs in controls.nodes if tag == 'button' and attrs.get('type') == 'submit']
    fields = [attrs for tag, attrs in controls.nodes if attrs.get('name') in ('email', 'phone', 'bio')]
    assert len(fields) == 3
    assert any(tag == 'a' and attrs.get('href') == '/user/change_password' for tag, attrs in controls.nodes)
    if role == 'finance':
        assert not buttons
        assert all('readonly' in attrs for attrs in fields)
    else:
        assert len(buttons) == 1
        assert all('readonly' not in attrs for attrs in fields)

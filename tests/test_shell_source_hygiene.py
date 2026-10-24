"""Source cleanup must preserve CSRF refresh outcomes, locking and warnings."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('scenario', ['success', 'disabled', 'failure'])
def test_csrf_refresh_is_quiet_on_success_but_keeps_failure_diagnostics(scenario):
    source = (ROOT / 'app/templates/base.html').read_text(encoding='utf-8')
    start = source.index('    (function() {\n        var meta =')
    end = source.index('    })();', start) + len('    })();')
    node = shutil.which('node')
    assert node, 'Node.js is required to verify refresh behavior'
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const requests=[],logs=[],warnings=[],listeners={};let content='old-token',tick;
const document={hidden:false,querySelector:()=>({setAttribute:(key,value)=>{assert.equal(key,'content');content=value;}}),addEventListener:(name,fn)=>listeners[name]=fn};
const context={document,console:{log:(...args)=>logs.push(args),warn:(...args)=>warnings.push(args)},setInterval:(fn,delay)=>{assert.equal(delay,25*60*1000);tick=fn;},fetch:(url,options)=>new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}))};
vm.runInNewContext(p.source,context);
(async()=>{
  assert.equal(requests.length,0);
  tick();tick();assert.equal(requests.length,1,'in-flight refresh must stay single');
  const request=requests[0];assert.equal(request.url,'/api/csrf_refresh');assert.equal(request.options.method,'POST');assert.equal(request.options.credentials,'same-origin');assert.equal(request.options.headers['X-Requested-With'],'XMLHttpRequest');
  if(p.scenario==='failure')request.reject(new Error('fixture offline'));
  else request.resolve({json:()=>Promise.resolve(p.scenario==='success'?{status:'success',csrf_token:'new-token'}:{csrf_disabled:true})});
  await new Promise(setImmediate);
  assert.equal(content,p.scenario==='success'?'new-token':'old-token');
  assert.equal(logs.length,0,'routine refresh must not write debug logs');
  assert.equal(warnings.length,p.scenario==='failure'?1:0);
  if(p.scenario==='failure')assert.match(warnings[0][0],/刷新失败/);
  document.hidden=true;listeners.visibilitychange();assert.equal(requests.length,1);
  document.hidden=false;listeners.visibilitychange();assert.equal(requests.length,2,'success/disabled/failure all release refresh lock');
  requests[1].resolve({json:()=>Promise.resolve({status:'success',csrf_token:'retry-token'})});
  await new Promise(setImmediate);assert.equal(content,'retry-token');
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''
    result = subprocess.run([node, '-e', program], input=json.dumps(dict(source=source[start:end], scenario=scenario)), capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('path,comment,count', [
    ('app/static/css/shell.css', '侧边栏子菜单：T+ 风格横向展开', 1),
    ('app/static/css/shell.css', '样式由 custom.css 统一管理', 2),
    ('app/static/css/shell.css', '操作按钮栏', 1),
    ('app/static/js/pages/shell-navigation.js', '// 禁止触摸多指缩放', 1),
    ('app/static/js/pages/shell-navigation.js', '// 禁止双击缩放', 1),
    ('app/static/js/pages/shell-navigation.js', '// 禁止滚轮缩放', 1),
])
def test_shell_comments_remain_readable_utf8(path, comment, count):
    source = (ROOT / path).read_text(encoding='utf-8')
    assert source.count(comment) == count
    assert not any(marker in source for marker in ['濮斿', '鏍峰紡', '鎿嶄綔', '褰诲簳', '绂佹'])

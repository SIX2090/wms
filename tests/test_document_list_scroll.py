"""Execute exact-entry list scroll restoration without cross-account/filter memory."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('template', ['in_order', 'out_order', 'transfer', 'check'])
def test_list_scroll_consumer(template):
    source = (ROOT / 'app/templates' / (template + '.html')).read_text(encoding='utf-8')
    assert source.count("filename='js/pages/document-list-scroll.js'") == 1
    assert 'data-user-id="{{ current_user.get_id() }}"' in source


@pytest.mark.parametrize('case', ['save', 'back', 'account', 'query', 'fresh', 'zero',
                                 'invalid', 'unavailable', 'bfcache', 'anchor'])
def test_list_scroll_runtime(case):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    source = (ROOT / 'app/static/js/pages/document-list-scroll.js').read_text(encoding='utf-8')
    script = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(process.argv[1]);
const listeners={},windowListeners={},element={scrollTop:0,scrollLeft:0,style:{}};
const saved={key:'7:/in_order?warehouse_id=1',position:[{top:120,left:15}]};
if(p.case==='account')saved.key='8:/in_order?warehouse_id=1';
if(p.case==='query')saved.key='7:/in_order?warehouse_id=2';
if(p.case==='zero')saved.position=[{top:0,left:0}];
if(p.case==='invalid')saved.position=[{top:'120',left:NaN}];
const document={currentScript:{dataset:{userId:'7'}},scrollingElement:element,
 querySelectorAll:()=>[],addEventListener(k,f){listeners[k]=f;}};
const history={state:{untouched:'keep',wmsDocumentListScroll:saved},replaceState(state){
 if(p.case==='unavailable')throw Error('unavailable');this.state=state;}};
const context={document,history,location:{pathname:'/in_order',search:'?warehouse_id=1'},
 window:{addEventListener(k,f){windowListeners[k]=f;}},
 performance:{getEntriesByType:()=>[{type:p.case==='fresh'?'navigate':'back_forward'}]},requestAnimationFrame:f=>f()};
vm.runInNewContext(p.source,context);
if(p.case==='save'){element.scrollTop=240;element.scrollLeft=32;listeners.scroll();assert.equal(history.state.wmsDocumentListScroll.position[0].top,240);assert.equal(history.state.wmsDocumentListScroll.position[0].left,32);assert.equal(history.state.untouched,'keep');element.scrollTop=0;windowListeners.pagehide();assert.equal(history.state.wmsDocumentListScroll.position[0].top,0);}
if(p.case==='back'){assert.equal(element.scrollTop,120);assert.equal(element.scrollLeft,15);}
if(['account','query','fresh','zero','invalid'].includes(p.case))assert.equal(element.scrollTop,0);
if(p.case==='unavailable'){listeners.scroll();windowListeners.pagehide();}
if(p.case==='bfcache'){element.scrollTop=0;windowListeners.pageshow({persisted:true});assert.equal(element.scrollTop,120);}
if(p.case==='anchor')assert.equal(element.style.overflowAnchor,'none');
'''
    result = subprocess.run([node, '--max-old-space-size=96', '-e', script,
                             json.dumps({'source': source, 'case': case})],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr

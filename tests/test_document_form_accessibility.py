"""Execute the opted-in form names and paste-dialog keyboard/focus behavior."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ['document_table_form', 'adjustment_add', 'purchase_order_add',
             'purchase_request_add', 'sales_order_add', 'sales_order_edit',
             'transfer', 'check', 'requisition']


@pytest.mark.parametrize('template', TEMPLATES)
def test_form_accessibility_consumer(template):
    source = (ROOT / 'app/templates' / (template + '.html')).read_text(encoding='utf-8')
    assert source.count("filename='js/pages/document-form-accessibility.js'") == 1
    if template in ('document_table_form', 'adjustment_add'):
        paste = source.split('function showPasteModal() {', 1)[1].split('async function parsePastedData()', 1)[0]
        assert "if (document.getElementById('pasteModal')) return;" in paste
        assert 'WmsFormAccessibility.openPasteDialog(modal);' in paste
        assert 'setTimeout' not in paste
        # Keep cancellation and the existing in-flight cancellation guard.
        assert "document.getElementById('pasteModal').remove()" in paste
        assert 'pasteArea.isConnected' in source


@pytest.mark.parametrize('case', ['label', 'existing', 'date', 'hidden', 'ids', 'rows',
                                 'renamed', 'explicit', 'open', 'escape', 'forward',
                                 'backward', 'outside', 'focus', 'removed', 'gone',
                                 'bootstrap', 'risk', 'body-opener'])
def test_document_form_accessibility_runtime(case):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    source = (ROOT / 'app/static/js/pages/document-form-accessibility.js').read_text(encoding='utf-8')
    script = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(process.argv[1]);
const listeners={},ids={},document={readyState:'loading',activeElement:null,
 getElementById:id=>ids[id]||null,addEventListener(k,f){listeners[k]=f;}};
function control(){return {id:'',type:'text',attrs:{},dataset:{},isConnected:true,tabIndex:0,
 setAttribute(k,v){this.attrs[k]=v;},getAttribute(k){return this.attrs[k]??null;},
 hasAttribute(k){return k in this.attrs;},focus(){document.activeElement=this;},
 getClientRects:()=>[{}],matches:()=>true};}
const input=control(),first=control(),last=control(),opener=control();document.activeElement=opener;
const label={htmlFor:'',parentElement:{querySelector:()=>input}},title=control();
let titleText='数量';const header={dataset:{columnKey:'quantity',defaultLabel:'数量'},get childNodes(){return [{nodeType:3,textContent:titleText}];}};
const cell={dataset:{columnKey:'quantity'},cellIndex:0,querySelectorAll:()=>[input]};
const table={querySelectorAll:q=>q==='thead th'?[header]:[{cells:[cell]},{cells:[cell]}]};
const dialog={attrs:{},isConnected:true,setAttribute(k,v){this.attrs[k]=v;},
 querySelector:q=>q==='h5'?title:input,querySelectorAll:()=>[first,last],
 contains:n=>[first,last,input].includes(n),remove(){this.isConnected=false;}};
const context={document,window:{requestAnimationFrame:f=>f()},WeakMap,MutationObserver:function(){this.observe=()=>{};}};
vm.createContext(context);vm.runInContext(p.source.replace('window.WmsFormAccessibility = {openPasteDialog: openPasteDialog};',
 'window.WmsFormAccessibility = {openPasteDialog, labelControl, nameRows, controlId, refresh, dialogControls};'),context);
const api=context.window.WmsFormAccessibility;
if(p.case==='label'){api.labelControl(label);assert.equal(label.htmlFor,input.id);assert(input.id);}
if(p.case==='existing'){input.id='known';ids.known=input;label.htmlFor='known';api.labelControl(label);assert.equal(label.htmlFor,'known');}
if(p.case==='date'){const visible=control();input.type='hidden';input._flatpickr={altInput:visible};api.labelControl(label);assert.equal(label.htmlFor,visible.id);assert(visible.id);assert.equal(input.type,'hidden');}
if(p.case==='hidden'){input.type='hidden';api.labelControl(label);assert.equal(label.htmlFor,'');}
if(p.case==='ids'){ids['wms-document-field-1']=control();api.labelControl(label);assert.equal(input.id,'wms-document-field-2');api.labelControl(label);assert.equal(input.id,'wms-document-field-2');}
if(['rows','renamed','explicit'].includes(p.case)){if(p.case==='explicit')input.attrs['aria-label']='原明确名称';api.nameRows(table);if(p.case==='explicit')assert.equal(input.attrs['aria-label'],'原明确名称');else{assert.equal(input.attrs['aria-label'],'第2行 数量');if(p.case==='renamed'){titleText='领用数';api.nameRows(table);assert.equal(input.attrs['aria-label'],'第2行 领用数');}}}
if(['open','escape','forward','backward','outside','focus','removed','gone','bootstrap'].includes(p.case)){
 api.openPasteDialog(dialog);assert.equal(document.activeElement,input);assert.equal(dialog.attrs.role,'dialog');assert.equal(dialog.attrs['aria-modal'],'true');assert.equal(dialog.attrs['aria-labelledby'],title.id);assert.equal(input.attrs['aria-label'],'粘贴导入内容');
 let prevented=0,stopped=0;const event={key:'Tab',shiftKey:false,preventDefault(){prevented++;},stopImmediatePropagation(){stopped++;}};
 if(p.case==='escape'){event.key='Escape';listeners.keydown(event);assert(!dialog.isConnected);assert.equal(document.activeElement,opener);assert.equal(stopped,1);assert.equal(prevented,1);}
 if(['forward','backward','outside'].includes(p.case)){document.activeElement=p.case==='forward'?last:p.case==='backward'?first:opener;event.shiftKey=p.case==='backward';listeners.keydown(event);assert.equal(prevented,1);assert.equal(document.activeElement,event.shiftKey?last:first);}
 if(p.case==='focus'){listeners.focusin({target:opener});assert.equal(document.activeElement,first);}
 if(p.case==='removed'||p.case==='gone'){document.querySelectorAll=()=>[];dialog.isConnected=false;opener.isConnected=p.case==='removed';api.refresh();assert.equal(document.activeElement,p.case==='removed'?opener:input);}
 if(p.case==='bootstrap'){listeners['show.bs.modal']({target:dialog,relatedTarget:opener});listeners['hidden.bs.modal']({target:dialog});assert.equal(document.activeElement,opener);}
}
if(p.case==='risk'){
 document.querySelectorAll=()=>[];ids.completeConfirmModal=dialog;dialog.querySelector=q=>q==='h5'?title:null;
 api.refresh();assert.equal(document.activeElement,first);assert.equal(dialog.attrs.role,'dialog');
 listeners.keydown({key:'Escape',preventDefault(){},stopImmediatePropagation(){}});assert.equal(document.activeElement,opener);assert(!dialog.isConnected);
}
if(p.case==='body-opener'){
 document.body={};listeners.focusin({target:opener});document.activeElement=document.body;api.openPasteDialog(dialog);
 listeners.keydown({key:'Escape',preventDefault(){},stopImmediatePropagation(){}});assert.equal(document.activeElement,opener);
}
'''
    result = subprocess.run([node, '--max-old-space-size=96', '-e', script,
                             json.dumps({'source': source, 'case': case})],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr

"""Shared escaping and CSRF contracts without weakening page behavior checks."""
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = "adjustment_add after_sale_out_add ai_data_retention base document_ocr document_table_form in_order in_order_add in_order_detail material opening_stock out_order_add out_order_detail purchase_order_add purchase_request_add report_view subcontract_detail system_settings".split()


def _function(text, name):
    start = re.search(r"function " + name + r"\(", text).start()
    opening = text.index("{", start)
    depth = 0
    for end in range(opening, len(text)):
        depth += (text[end] == "{") - (text[end] == "}")
        if not depth:
            return text[start:end + 1]
    raise AssertionError(name)


@pytest.mark.parametrize("page", PAGES)
def test_normal_templates_share_escaping(page):
    text = (ROOT / f"app/templates/{page}.html").read_text(encoding="utf-8")
    assert not re.search(r"function\s+escapeHtml\s*\(", text)


def test_csrf_has_one_canonical_implementation():
    paths = [ROOT / "app/static/js/app.js", *list((ROOT / "app/templates").glob("*.html"))]
    definitions = [(p.name, len(re.findall(r"function\s+csrfFetch\s*\(", p.read_text(encoding="utf-8")))) for p in paths]
    assert sum(n for _, n in definitions) == 1, definitions
    assert dict(definitions)["base.html"] == 1
    assert "function escapeHtml" in (ROOT / "app/static/js/app.js").read_text(encoding="utf-8")
    # The standalone editor has no app shell and retains its local encoder.
    assert "function escapeHtml" in (ROOT / "app/templates/print_template_editor.html").read_text(encoding="utf-8")


class Markup(HTMLParser):
    def __init__(self, html):
        super().__init__(); self.tags = []; self.attrs = []; self.text = []
        self.feed(html)
    def handle_starttag(self, tag, attrs):
        self.tags.append(tag); self.attrs.extend(attrs)
    def handle_data(self, value):
        self.text.append(value)


def _node(script, payload):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required")
    result = subprocess.run([node, "-e", script, json.dumps(payload)], capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("marker", ["data-column-key", "column.defaultLabel", "cb-doc-nav-icon", "cb-actionbar-label"])
@pytest.mark.parametrize("value", ['<img src=x onerror="alert(1)">', '\" autofocus onfocus=\"alert(1)', "A&B <零件> '单引号'", "正常中文"])
def test_configured_labels_stay_text(marker, value):
    source = (ROOT / "app/static/js/app.js").read_text(encoding="utf-8")
    line = next(line.strip() for line in source.splitlines() if ".innerHTML =" in line and marker in line)
    script = r'''
const vm=require('node:vm');const p=JSON.parse(process.argv[1]);const ctx={column:{key:p.value,label:p.value,defaultLabel:p.value,locked:false},item:{icon:p.value,label:p.value},actionLabel:p.value,index:0,option:{},row:{},btn:{}};
vm.createContext(ctx);vm.runInContext(p.helper,ctx);vm.runInContext(p.line,ctx);process.stdout.write(JSON.stringify({html:ctx.option.innerHTML||ctx.row.innerHTML||ctx.btn.innerHTML}));
'''
    result = _node(script, {"helper": _function(source, "escapeHtml"), "line": line, "value": value})
    parsed = Markup(result["html"])
    assert not set(parsed.tags) & {"img", "svg", "script", "iframe"}
    assert not any(key.startswith("on") or key == "autofocus" for key, _ in parsed.attrs)
    if marker == "data-column-key":
        assert dict(parsed.attrs)["data-column-key"] == value
    assert value in "".join(parsed.text)


@pytest.mark.parametrize("kind", ["meta", "hidden", "parent", "cross_origin", "empty"])
def test_shared_csrf_token_sources(kind):
    source = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
    script = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');const p=JSON.parse(process.argv[1]);let sent;
const doc={querySelector:s=>p.kind==='meta'&&s.startsWith('meta')?{content:'meta-token'}:p.kind==='hidden'&&s.startsWith('input')?{value:'hidden-token'}:null};
const parent={};Object.defineProperty(parent,'document',{get(){if(p.kind==='cross_origin')throw Error('denied');return {querySelector:()=>p.kind==='parent'?{content:'parent-token'}:null};}});
const ctx={document:doc,window:{parent},Headers,fetch:(url,options)=>{sent={url,options};return Promise.resolve({});}};vm.createContext(ctx);vm.runInContext(p.token+';'+p.fetch,ctx);
const expected={meta:'meta-token',hidden:'hidden-token',parent:'parent-token',cross_origin:'',empty:''}[p.kind];assert.equal(ctx.getCsrfToken(),expected);
ctx.csrfFetch('/save',{headers:{'X-CSRFToken':'explicit'},body:'raw'});assert.equal(sent.options.headers.get('X-CSRFToken'),'explicit');assert.equal(sent.options.body,'raw');assert.equal(sent.options.method,'POST');assert.equal(sent.options.credentials,'same-origin');
ctx.csrfFetch('/save');assert.equal(sent.options.headers.get('X-CSRFToken'),expected||null);process.stdout.write('{}');
'''
    _node(script, {"kind": kind, "token": _function(source, "getCsrfToken"), "fetch": _function(source, "csrfFetch")})

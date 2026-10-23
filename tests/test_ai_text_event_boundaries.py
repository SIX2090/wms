"""HTML entities must never become JavaScript arguments in generated handlers."""
import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAYLOADS = ["O'Reilly", "x');globalThis.__wmsProbe=1;//", '<img src=x onerror="globalThis.__wmsProbe=1"> & "零件"']


def node(program, payload):
    executable = shutil.which('node')
    assert executable, 'Node.js required for actual page handlers'
    result = subprocess.run([executable, '--max-old-space-size=64', '-e', program], input=json.dumps(payload), capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


class Buttons(HTMLParser):
    def __init__(self, html):
        super().__init__(); self.buttons = []; self.other = []; self.events = []; self.text = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.events.extend(name for name, value in attrs if name.startswith('on'))
        if tag == 'button':
            self.buttons.append(dict(attrs))
        elif tag not in {'tr', 'td'}:
            self.other.append(tag)

    def handle_data(self, value):
        self.text.append(value)


@pytest.mark.parametrize('value', PAYLOADS)
def test_quality_detail_keeps_data_out_of_event_source(value):
    template = (ROOT / 'app/templates/ai_business_quality.html').read_text(encoding='utf-8')
    source = template[template.index('function renderLowQualitySamples('):template.index('// 显示样本详情')]
    shared = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    start = shared.index('function escapeHtml(')
    source = shared[start:shared.index('\n}', start) + 2] + '\n' + source
    program = r'''
const vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const calls=[];const buttons=(p.attributes||[]).map(a=>({dataset:{dimension:a['data-dimension'],value:a['data-value']},addEventListener:(name,fn)=>{if(name!=='click')throw Error(name);buttons[0].click=fn;}}));
const tbody={innerHTML:'',querySelectorAll:()=>buttons};
const ctx={document:{querySelector:()=>tbody},showSampleDetail:(...args)=>calls.push(args)};
vm.createContext(ctx);vm.runInContext(p.source,ctx);ctx.renderLowQualitySamples(p.snapshot);
if(p.attributes)buttons.forEach(button=>button.click());
process.stdout.write(JSON.stringify({html:tbody.innerHTML,calls}));
'''
    metrics = {key: 0 for key in ['classification_accuracy', 'header_accuracy', 'line_recall', 'material_match_rate', 'human_correction_rate']}
    payload = dict(source=source, snapshot={'by_dimension': {'model': {value: metrics}}})
    rendered = node(program, payload)
    parsed = Buttons(rendered['html'])
    assert parsed.other == []
    assert len(parsed.buttons) == 1
    attributes = parsed.buttons[0]
    assert not any(name.startswith('on') for name in attributes)
    assert attributes['type'] == 'button'
    assert attributes['data-dimension'] == 'model'
    assert attributes['data-value'] == value  # HTMLParser decodes entities like a browser.
    result = node(program, dict(payload, attributes=parsed.buttons))
    assert result['calls'] == [['model', value]]


@pytest.mark.parametrize('value', PAYLOADS)
def test_location_search_uses_text_nodes_and_original_click_arguments(value):
    template = (ROOT / 'app/templates/ai_location_recommendation.html').read_text(encoding='utf-8')
    source = template[template.index("$('#materialSearch').on('input'"):template.index('// 点击外部关闭下拉')]
    program = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let input;const calls=[];
const material={id:7,code:'CODE',name:p.value,spec:p.value};
function element(tag){const e={tagName:tag,children:[],textContent:'',className:'',appendChild(child){this.children.push(child);},addEventListener(name,fn){this[name]=fn;}};Object.defineProperty(e,'innerHTML',{set(){assert.fail('untrusted material fields must use textContent');}});return e;}
const dropdown={children:[],html(value){this.markup=value;this.children=[];},empty(){this.children=[];},append(node){this.children.push(node);},addClass(){},removeClass(){}};
const search={on:(name,fn)=>input=fn};
const ctx={document:{createElement:element},allMaterials:[material],selectMaterial:(...args)=>calls.push(args),$:selector=>selector==='#materialSearch'?search:selector==='#materialDropdown'?dropdown:{val:()=>p.query||'CODE'}};
vm.runInNewContext(p.source,ctx);input.call({});
assert.equal(dropdown.children.length,1,'one material must remain selectable');
const option=dropdown.children[0];assert.equal(option.children.length,3);
assert.deepEqual(option.children.map(child=>child.textContent),['CODE',p.value,p.value]);
option.click();assert.deepEqual(calls,[[7,'CODE',p.value]]);
input.call({});assert.equal(dropdown.children.length,1,'rerender must replace old options');
process.stdout.write('{}');
'''
    node(program, dict(source=source, value=value))


@pytest.mark.parametrize('value', PAYLOADS)
def test_location_result_treats_location_unit_and_labels_as_text(value):
    template = (ROOT / 'app/templates/ai_location_recommendation.html').read_text(encoding='utf-8')
    start = template.index('function renderResult(')
    source = template[start:template.index('</script>', start)]
    shared = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    start = shared.index('function escapeHtml(')
    source = shared[start:shared.index('\n}', start) + 2] + '\n' + source
    program = r'''
const vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8')),html={};
const ctx={$:selector=>({text(){},show(){},html(value){html[selector]=value;}})};
vm.createContext(ctx);vm.runInContext(p.source,ctx);
ctx.renderResult({material:{code:'CODE',name:p.value,unit:p.value},turnover:{total:1,level:p.value,description:p.value},current_locations:[{location:p.value,quantity:2}],recommendations:[{location:p.value,score:80,material_count:1,total_qty:2}],ai_analysis:p.value});
process.stdout.write(JSON.stringify(html));
'''
    rendered = node(program, dict(source=source, value=value))
    for selector in ['#statLevel', '#currentLocations', '#recommendationsArea']:
        parsed = Buttons(rendered[selector])
        assert not parsed.events
        assert not {'img', 'script', 'iframe'}.intersection(parsed.other)
        assert value in ''.join(parsed.text)

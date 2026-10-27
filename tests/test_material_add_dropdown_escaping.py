"""Execute dropdown rendering and selection; parse output as HTML to catch injection."""
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from tests.test_frontend_remaining_page_transport import callback

ROOT = Path(__file__).resolve().parents[1]


class DropdownHTML(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.text = ''
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_data(self, text):
        self.text += text


@pytest.mark.parametrize('kind', ['Unit', 'Supplier'])
@pytest.mark.parametrize('value', [
    '正常中文单位', '<img src=x onerror="globalThis.injected=true">',
    '</span><script>globalThis.injected=true</script><span>',
    '\" onmouseover=\"globalThis.injected=true', "' & < > \\ \n", None,
])
def test_dropdown_renders_untrusted_fields_as_literal_text_and_preserves_selection(kind, value):
    source = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    helper = re.search(r'function escapeHtml\(value\) \{.*?\n\}', source, re.S).group()
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(process.argv[1]);let click;
const row={dataset:{id:'7'},style:{},querySelector:()=>({textContent:p.value==null?'':p.value}),addEventListener:(type,fn)=>{if(type==='click')click=fn;}};
const dropdown={style:{display:'none'},innerHTML:'',querySelectorAll:()=>[row]},search={value:''},hidden={value:''};
let positions=0;
const ctx={unitDropdown:dropdown,supplierDropdown:dropdown,unitSearch:search,supplierSearch:search,unitIdHidden:hidden,supplierIdHidden:hidden,WMS:{positionDropdown(input,menu){assert.equal(input,search);assert.equal(menu,dropdown);positions++;}}};vm.createContext(ctx);
vm.runInContext(p.helper+'\n'+p.handler,ctx);ctx['show'+p.kind+'Dropdown']([{id:7,name:p.value,code:p.value,contact:p.value,phone:p.value}]);
assert.equal(positions,1);assert.equal(dropdown.style.display,'block');click.call(row);assert.equal(search.value,p.value==null?'':p.value);assert.equal(hidden.value,'7');assert.equal(dropdown.style.display,'none');
const html=dropdown.innerHTML;ctx['show'+p.kind+'Dropdown']([]);assert.equal(dropdown.style.display,'none');
process.stdout.write(JSON.stringify({html}));
'''
    payload = dict(kind=kind, value=value, helper=helper,
                   handler=callback('material_add', f'function show{kind}Dropdown(list)'))
    result = subprocess.run([shutil.which('node'), '-e', program, json.dumps(payload)], capture_output=True, text=True, encoding='utf-8', timeout=10)
    assert result.returncode == 0, result.stderr
    parsed = DropdownHTML(json.loads(result.stdout)['html'])
    assert all(tag in ('div', 'span') for tag, _ in parsed.elements), 'Untrusted text created active markup'
    assert all(not key.lower().startswith('on') for _, attrs in parsed.elements for key in attrs), 'Untrusted text created an event handler'
    assert parsed.elements[0][1]['data-id'] == '7'
    if value is not None:
        count = 2 if kind == 'Unit' else 3
        assert parsed.text.count(value) == count
    else:
        assert parsed.text == ''

"""Render the real designer and execute its script without a database or network."""
import json
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader


ROOT = Path(__file__).resolve().parents[1]


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.active = False

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.active = True
            self.scripts.append("")

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.scripts[-1] += data


@pytest.mark.parametrize("label", [
    "正常中文标签",
    '</script><script>globalThis.injected=true</script>',
    '</ScRiPt><img src=x onerror="globalThis.injected=true">',
    "引号'\"与反斜线\\及换行\n\u2028\u2029",
    '<!-- & < > -->',
])
def test_layout_remains_data_in_rendered_designer(label):
    layout = {"0-0": {"field": "name", "label": label, "style": {}}, "marginTop": 3}
    _assert_rendered_layout(json.dumps(layout, ensure_ascii=False), layout)


@pytest.mark.parametrize("stored", [None, "", "{}"])
def test_empty_layout_remains_editable(stored):
    _assert_rendered_layout(stored, {})


def _assert_rendered_layout(stored, expected):
    env = Environment(loader=ChoiceLoader([
        DictLoader({"base.html": "{% block content %}{% endblock %}"}),
        FileSystemLoader(str(ROOT / "app" / "templates")),
    ]), autoescape=True)
    html = env.get_template("label_template_detail.html").render(
        template=SimpleNamespace(id=1, name="测试", width=50, height=30,
                                 cols=2, rows=2, layout=stored),
        url_for=lambda *args, **kwargs: "/test",
    )
    parsed = Scripts()
    parsed.feed(html)
    assert len(parsed.scripts) == 1, "Stored data escaped the script element"
    node = shutil.which("node")
    assert node, "Node is required to verify executable JavaScript behavior"
    harness = """
const vm = require('node:vm');
const fs = require('node:fs');
const ctx = vm.createContext({document: {addEventListener() {}}});
const source = JSON.parse(fs.readFileSync(0, 'utf8'));
// let/const 不会挂到全局对象，必须在同一段脚本里取值
vm.runInContext(source + '\\n;globalThis.__probe = {layout: layoutData, injected: globalThis.injected === true};', ctx, {timeout: 1000});
process.stdout.write(JSON.stringify(ctx.__probe));
"""
    result = subprocess.run([node, "-e", harness], input=json.dumps(parsed.scripts[0]),
                            capture_output=True, text=True, encoding="utf-8", timeout=10)
    assert result.returncode == 0, result.stderr
    decoded = json.loads(result.stdout)
    assert decoded == {"layout": expected, "injected": False}

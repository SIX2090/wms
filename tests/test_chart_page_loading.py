"""Chart assets belong to chart pages and must precede their consumers."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'app/templates'
LIBRARY = 'cdn/chart.umd-4.4.1.min.js'


def render_scripts(page, **context):
    env = Environment(loader=ChoiceLoader([
        DictLoader({'base.html': '{% block extra_js %}{% endblock %}'}),
        FileSystemLoader(TEMPLATES),
    ]), autoescape=True)
    env.globals['url_for'] = lambda endpoint, **kwargs: '/static/' + kwargs['filename']
    return env.get_template(page + '.html').render(**context)


def test_shell_does_not_download_chart_library():
    assert LIBRARY not in (TEMPLATES / 'base.html').read_text(encoding='utf-8')


@pytest.mark.parametrize('page,count', [('report_dashboard', 4), ('sales_reconciliation_report', 2)])
def test_chart_pages_load_once_before_initializing(page, count):
    chart_data = dict(
        trend=dict(labels=['2026-10'], in_qty=[3], out_qty=[1]),
        category=dict(labels=['分类'], values=[2]),
        top_stock=dict(labels=['物料'], values=[2]),
        monthly_amount=dict(labels=['2026-10'], in_amount=[30], out_amount=[10]),
        summary=dict(passed=1, failed=0, total=1, total_shipped=1, total_completed=1, total_diff=0),
    )
    html = render_scripts(page, stats={'total': 1}, chart_data=chart_data)
    assert html.count(LIBRARY) == 1
    assert html.index(LIBRARY) < html.index('new Chart(')
    node = shutil.which('node')
    assert node, 'Node.js is required to verify chart initialization'
    scripts = re.findall(r'<script([^>]*)>(.*?)</script>', html, re.S)
    runtime = """
const vm = require('vm');
const calls = [], events = [];
const context = vm.createContext({document: {
  getElementById: id => ({id}),
  addEventListener: (event, callback) => events.push(callback)
}});
for (const [attributes, source] of JSON.parse(process.argv[1])) {
  if (attributes.includes('chart.umd')) {
    context.Chart = function(canvas, config) { calls.push({id: canvas.id, type: config.type}); };
  } else { vm.runInContext(source, context); }
}
events.forEach(callback => callback());
process.stdout.write(JSON.stringify(calls));
"""
    result = subprocess.run([node, '-e', runtime, json.dumps(scripts)], capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr
    calls = json.loads(result.stdout)
    assert len(calls) == count
    assert len({c['id'] for c in calls}) == count


def test_dashboard_without_warehouse_does_not_load_charts():
    html = render_scripts('report_dashboard', stats=None)
    assert LIBRARY not in html
    assert 'new Chart(' not in html

"""Completed dashboard facts and actual assistant history lifecycle regressions."""
import ast
from datetime import date
import json
from pathlib import Path
import shutil
import subprocess

import pytest
import app as wms
from services.warehouse_stock_service import apply_stock_delta

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def dashboard_rows(monkeypatch):
    monkeypatch.setitem(wms.app.config, 'TESTING', True)
    with wms.app.test_request_context('/'):
        wms.db.drop_all(); wms.db.create_all()
        a = wms.Warehouse(code='QA19-A', name='QA19仓A', is_default=True, status='active')
        b = wms.Warehouse(code='QA19-B', name='QA19仓B', status='active')
        material = wms.Material(code='QA19-M', name='合成物料', price=2, stock=0)
        wms.db.session.add_all([a, b, material]); wms.db.session.flush()
        for warehouse, qty in [(a, 10), (b, 20)]:
            ok, error = apply_stock_delta(material, qty, transaction_type='in', reference_type='qa19_seed', warehouse=warehouse)
            assert ok, error
        today = date.today()
        previous = wms._shift_month_start(today.replace(day=1), -1)
        specs = [
            ('in', a.name, today, 'completed', 2), ('in', a.code, today, 'completed', 4),
            ('in', a.name, today, 'pending', 100), ('in', a.code, today, 'pending', 50),
            ('in', a.name, previous, 'completed', 3), ('in', a.code, previous, 'pending', 40),
            ('in', b.name, today, 'completed', 7), ('in', b.code, today, 'pending', 70),
            ('in', None, today, 'completed', 9),
            ('out', a.name, today, 'completed', 1), ('out', a.code, today, 'completed', 2),
            ('out', a.name, today, 'pending', 90),
            ('out', a.code, previous, 'completed', 1), ('out', a.name, previous, 'pending', 80),
        ]
        for index, (kind, warehouse, when, status, qty) in enumerate(specs):
            model, item_model, foreign_key = (wms.InOrder, wms.InOrderItem, 'in_order_id') if kind == 'in' else (wms.OutOrder, wms.OutOrderItem, 'out_order_id')
            order = model(order_no=f'QA19-{index}', date=when, warehouse=warehouse, status=status, total_amount=qty * 2)
            wms.db.session.add(order); wms.db.session.flush()
            wms.db.session.add(item_model(**{foreign_key: order.id}, material_id=material.id, quantity=qty, price=2, amount=qty * 2))
        wms.db.session.commit()
        yield a, b
        wms.db.session.remove(); wms.db.drop_all()


@pytest.mark.parametrize('field,expected', [
    ('month_in_amount', 12), ('month_in_count', 2), ('month_out_amount', 6), ('month_out_count', 2),
    ('last_month_in_amount', 6), ('last_month_in_count', 1), ('last_month_out_amount', 2), ('last_month_out_count', 1),
])
def test_dashboard_completed_cards(dashboard_rows, field, expected):
    stats, _ = wms.build_report_dashboard_context(dashboard_rows[0])
    assert stats[field] == expected


def test_dashboard_completed_charts_and_warehouse_boundaries(dashboard_rows):
    a, b = dashboard_rows
    stats_a, charts = wms.build_report_dashboard_context(a)
    stats_b, _ = wms.build_report_dashboard_context(b)
    assert charts['trend']['in_qty'][-1] == 6
    assert charts['trend']['out_qty'][-1] == 3
    assert charts['monthly_amount']['in_amount'][-1] == 12
    assert charts['monthly_amount']['out_amount'][-1] == 6
    assert stats_a['month_in_amount'] + stats_b['month_in_amount'] == 26
    assert stats_b['month_in_count'] == 1
    assert stats_a['total_stock'] == 10 and stats_b['total_stock'] == 20


def test_ai_mom_same_completed_facts(dashboard_rows):
    reply = wms._ai_report_mom_insights()
    assert '| 入库金额 | ¥44.00 | ¥6.00 |' in reply
    assert '| 入库单数 | 4 | 1 |' in reply
    assert '| 领料金额 | ¥6.00 | ¥2.00 |' in reply


@pytest.mark.parametrize('case', ['restore-format', 'restore-user-text', 'restore-once', 'ask-reopen', 'late-list', 'late-detail', 'clear-late-detail', 'unsafe-history'])
def test_actual_history_lifecycle(case):
    # Reuse the established actual-shell/API/SSE DOM fixture without altering its assertions.
    existing = (ROOT / 'tests/test_ai_shell_transport_runtime.py').read_text(encoding='utf-8')
    tree = ast.parse(existing)
    program = next(node.value.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == 'program' for target in node.targets)
                   and isinstance(node.value, ast.Constant))
    cases = (ROOT / 'tests/frontend_history_restore.cjs').read_text(encoding='utf-8')
    marker = " api.chatHistory.push({role:'assistant',content:'old'});"
    assert marker in program
    program = program.replace(marker, cases + '\n await historyScenario(); return;\n' + marker)
    program = program.replace("content:'历史回答'", 'content:' + json.dumps('**历史回答**\n\n|a|b|\n|--|--|\n|1|2|\n<img src=x onerror=attack()>'))
    program = program.replace("content:'历史问题'", 'content:' + json.dumps('历史问题 <tag>& "quote"'))
    source = (ROOT / 'app/static/js/pages/ai-assistant.js').read_text(encoding='utf-8')
    ending = source.rindex('})();')
    source = source[:ending] + 'window.fixtureAssistant={sendAssistantMessage,submitFeedback,renderMarkdown,chatHistory};\n' + source[ending:]
    base = (ROOT / 'app/templates/base.html').read_text(encoding='utf-8')
    import re
    wrapper = re.findall(r'<script>(.*?)</script>', base, re.S)[0].split('    // F2.14 全局兜底：')[0]
    result = subprocess.run([shutil.which('node'), '-e', program], input=json.dumps(dict(source=source, wrapper=wrapper,
        api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'), mode='stream', scenario='success', history_case=case)),
        capture_output=True, text=True, encoding='utf-8', timeout=25)
    assert result.returncode == 0, result.stdout + result.stderr

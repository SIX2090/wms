"""BUG-2026-10-07-008 契约测试：AI 按供应商查入库

验证 query_supplier_deliveries 意图被正确实现。
"""

import re
from pathlib import Path


def test_supplier_deliveries_function_exists():
    """函数定义存在"""
    app_py = Path(__file__).parent.parent / 'app' / 'app.py'
    content = app_py.read_text(encoding='utf-8', errors='replace')
    assert 'def _ai_supplier_deliveries(' in content
    assert 'BUG-2026-10-07-008' in content


def test_supplier_deliveries_queries_supplier():
    """函数查询供应商"""
    app_py = Path(__file__).parent.parent / 'app' / 'app.py'
    content = app_py.read_text(encoding='utf-8', errors='replace')
    match = re.search(r'def _ai_supplier_deliveries\(.*?\n(.*?)(?=\ndef |\Z)', content, re.DOTALL)
    assert match
    func_body = match.group(1)
    assert 'Supplier.query' in func_body
    assert 'supplier_name' in func_body


def test_supplier_deliveries_queries_in_order():
    """函数查询入库单（in_order 表，不是 stock_transaction）"""
    app_py = Path(__file__).parent.parent / 'app' / 'app.py'
    content = app_py.read_text(encoding='utf-8', errors='replace')
    match = re.search(r'def _ai_supplier_deliveries\(.*?\n(.*?)(?=\ndef |\Z)', content, re.DOTALL)
    assert match
    func_body = match.group(1)
    assert 'InOrderItem.query' in func_body
    assert 'InOrder.supplier_id' in func_body


def test_supplier_deliveries_supports_days():
    """函数支持 days 参数（今天/最近7天/最近N天）"""
    app_py = Path(__file__).parent.parent / 'app' / 'app.py'
    content = app_py.read_text(encoding='utf-8', errors='replace')
    match = re.search(r'def _ai_supplier_deliveries\(.*?\n(.*?)(?=\ndef |\Z)', content, re.DOTALL)
    assert match
    func_body = match.group(1)
    assert 'days' in func_body
    assert 'timedelta' in func_body


def test_intent_in_llm_prompt():
    """LLM prompt 包含 query_supplier_deliveries 意图"""
    app_py = Path(__file__).parent.parent / 'app' / 'app.py'
    content = app_py.read_text(encoding='utf-8', errors='replace')
    # 找到 _ai_call_llm_intent 函数体
    match = re.search(r'def _ai_call_llm_intent\(.*?\n(.*?)(?=\ndef |\Z)', content, re.DOTALL)
    assert match
    func_body = match.group(1)
    assert 'query_supplier_deliveries' in func_body
    assert 'supplier' in func_body


def test_execute_intent_branch():
    """_ai_execute_intent 有 query_supplier_deliveries 分支"""
    app_py = Path(__file__).parent.parent / 'app' / 'app.py'
    content = app_py.read_text(encoding='utf-8', errors='replace')
    match = re.search(r'def _ai_execute_intent\(.*?\n(.*?)(?=\ndef |\Z)', content, re.DOTALL)
    assert match
    func_body = match.group(1)
    assert "if intent == 'query_supplier_deliveries':" in func_body
    assert '_ai_supplier_deliveries(' in func_body

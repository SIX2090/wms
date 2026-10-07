"""BUG-2026-10-07-007 契约测试：AI prompt 注入基础资料上下文

验证 `_ai_business_context_text()` 被正确调用并拼接到 LLM system_prompt。
"""

import re
from pathlib import Path


def test_business_context_function_exists():
    """函数定义存在"""
    app_py = Path(__file__).parent.parent / 'app' / 'app.py'
    content = app_py.read_text(encoding='utf-8', errors='replace')
    assert 'def _ai_business_context_text():' in content
    assert 'BUG-2026-10-07-007' in content


def test_business_context_called_in_chat():
    """_ai_call_llm_chat 中调用"""
    app_py = Path(__file__).parent.parent / 'app' / 'app.py'
    content = app_py.read_text(encoding='utf-8', errors='replace')
    # 找到 _ai_call_llm_chat 函数体
    match = re.search(r'def _ai_call_llm_chat\(.*?\n(.*?)(?=\ndef |\Z)', content, re.DOTALL)
    assert match, '_ai_call_llm_chat function not found'
    func_body = match.group(1)
    assert 'system_prompt += _ai_business_context_text()' in func_body


def test_business_context_called_in_intent():
    """_ai_call_llm_intent 中调用"""
    app_py = Path(__file__).parent.parent / 'app' / 'app.py'
    content = app_py.read_text(encoding='utf-8', errors='replace')
    # 找到 _ai_call_llm_intent 函数体
    match = re.search(r'def _ai_call_llm_intent\(.*?\n(.*?)(?=\ndef |\Z)', content, re.DOTALL)
    assert match, '_ai_call_llm_intent function not found'
    func_body = match.group(1)
    assert 'system_prompt += _ai_business_context_text()' in func_body


def test_business_context_queries_warehouse():
    """函数查询仓库"""
    app_py = Path(__file__).parent.parent / 'app' / 'app.py'
    content = app_py.read_text(encoding='utf-8', errors='replace')
    match = re.search(r'def _ai_business_context_text\(\):\n(.*?)(?=\ndef |\Z)', content, re.DOTALL)
    assert match
    func_body = match.group(1)
    assert 'get_active_warehouses()' in func_body


def test_business_context_queries_category():
    """函数查询分类"""
    app_py = Path(__file__).parent.parent / 'app' / 'app.py'
    content = app_py.read_text(encoding='utf-8', errors='replace')
    match = re.search(r'def _ai_business_context_text\(\):\n(.*?)(?=\ndef |\Z)', content, re.DOTALL)
    assert match
    func_body = match.group(1)
    assert 'MaterialCategory.query' in func_body


def test_business_context_exception_safe():
    """异常时返回空字符串"""
    app_py = Path(__file__).parent.parent / 'app' / 'app.py'
    content = app_py.read_text(encoding='utf-8', errors='replace')
    match = re.search(r'def _ai_business_context_text\(\):\n(.*?)(?=\ndef |\Z)', content, re.DOTALL)
    assert match
    func_body = match.group(1)
    assert 'except Exception:' in func_body
    assert "return ''" in func_body

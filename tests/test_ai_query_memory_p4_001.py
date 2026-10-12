# -*- coding: utf-8 -*-
"""P4-2026-10-12 查询记忆机制测试。

覆盖：模块层（归一化/相似度/记录/LRU/持久化）+ 注入层（few-shot 注入
prompt、成功选择被记录、记录失败不影响主链路）。
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from ai.query_memory import (  # noqa: E402
    find_similar,
    memory_examples_text,
    record_query_memory,
    _similarity,
    _normalize,
)
from ai.query_tools import build_tool_call_prompt  # noqa: E402


class TestSimilarity(unittest.TestCase):
    def test_normalize_strips_punctuation_keeps_digits(self):
        self.assertEqual(_normalize('  6*10的 铜排，还有多少？ '), '6*10的铜排还有多少')

    def test_similarity_identical(self):
        self.assertGreater(_similarity('铜排库存还有多少', '铜排库存还有多少'), 0.99)

    def test_similarity_similar_questions(self):
        score = _similarity('6*10的铜排库存还有多少', '6*10铜排的库存还剩多少')
        self.assertGreaterEqual(score, 0.35)

    def test_similarity_unrelated(self):
        self.assertLess(_similarity('铜排库存', '今天天气怎么样'), 0.35)

    def test_similarity_empty(self):
        self.assertEqual(_similarity('', '铜排'), 0.0)


class TestRecordAndFind(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp()
        self.mem_path = os.path.join(self.tmpdir, 'query_memory.json')
        patcher = patch('ai.query_memory._memory_path', return_value=self.mem_path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_record_and_find_similar(self):
        self.assertTrue(record_query_memory('6*10的铜排库存还有多少', 'query_stock',
                                            {'material_name': '铜排', 'spec': '6*10'}))
        hits = find_similar('6*10铜排的库存还剩多少')
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]['tool'], 'query_stock')
        self.assertEqual(hits[0]['params']['spec'], '6*10')

    def test_record_rejects_invalid(self):
        self.assertFalse(record_query_memory('', 'query_stock', {}))
        self.assertFalse(record_query_memory('问', 'query_stock', {}))
        self.assertFalse(record_query_memory('正常的问题', '', {}))

    def test_record_updates_existing_entry(self):
        record_query_memory('铜排库存', 'query_stock', {'material_name': '铜排'})
        record_query_memory('铜排库存', 'query_flow', {'material_name': '铜排'})
        with open(self.mem_path, 'r', encoding='utf-8') as fh:
            entries = json.load(fh)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['tool'], 'query_flow')

    def test_lru_limit(self):
        import ai.query_memory as qm
        with patch.object(qm, 'MEMORY_LIMIT', 5):
            for i in range(8):
                record_query_memory(f'编号{i}的物料{i}库存查询还剩多少', 'query_stock',
                                    {'material_name': f'物料{i}'})
        with open(self.mem_path, 'r', encoding='utf-8') as fh:
            entries = json.load(fh)
        self.assertEqual(len(entries), 5)
        tools = [e['params']['material_name'] for e in entries]
        self.assertNotIn('物料0', tools)  # 最旧的被挤出
        self.assertIn('物料7', tools)

    def test_find_similar_no_file(self):
        self.assertEqual(find_similar('任何问题'), [])

    def test_memory_examples_text(self):
        record_query_memory('6*10的铜排库存还有多少', 'query_stock',
                            {'material_name': '铜排', 'spec': '6*10'})
        text = memory_examples_text('6*10铜排的库存还剩多少')
        self.assertIn('历史成功案例', text)
        self.assertIn('query_stock', text)
        self.assertIn('6*10', text)

    def test_memory_examples_text_no_match(self):
        record_query_memory('铜排库存还有多少', 'query_stock', {'material_name': '铜排'})
        self.assertEqual(memory_examples_text('完全无关的话题内容'), '')


class TestPromptInjection(unittest.TestCase):
    def test_build_prompt_with_memory(self):
        prompt = build_tool_call_prompt(
            '6*10铜排库存',
            memory_text='【历史成功案例】\n- 问题："6*10的铜排库存" → {"tool": "query_stock", "params": {}}',
        )
        self.assertIn('历史成功案例', prompt)
        self.assertIn('query_stock', prompt)
        self.assertIn('可用工具', prompt)

    def test_build_prompt_without_memory(self):
        prompt = build_tool_call_prompt('6*10铜排库存')
        self.assertNotIn('历史成功案例', prompt)
        self.assertIn('系统数据说明', prompt)


class TestDispatchIntegration(unittest.TestCase):
    """调度层集成：记忆注入 prompt + 成功选择被记录。"""

    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp()
        self.mem_path = os.path.join(self.tmpdir, 'query_memory.json')
        from app import app as flask_app  # noqa: F401
        from app import app
        self.app = app
        patchers = [
            patch('app._ai_capability_allowed', return_value=True),
            patch('app._voice_llm_chat', return_value='{"tool": "query_stock", "params": {"material_name": "铜排", "spec": "6*10"}}'),
            patch('app._ai_stock_query_response', return_value=MagicMock(status=200)),
            patch('ai.query_memory._memory_path', return_value=self.mem_path),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_successful_dispatch_recorded_to_memory(self):
        with self.app.test_request_context('/'):
            from app import _ai_tool_call_dispatch_response
            response = _ai_tool_call_dispatch_response('帮我看看6*10的铜排还有多少库存')
        self.assertIsNotNone(response)
        with open(self.mem_path, 'r', encoding='utf-8') as fh:
            entries = json.load(fh)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['tool'], 'query_stock')
        self.assertEqual(entries[0]['params']['spec'], '6*10')

    def test_record_failure_does_not_break_dispatch(self):
        with patch('ai.query_memory.record_query_memory') as mock_ai_record:
            mock_ai_record.side_effect = RuntimeError('disk full')
            with self.app.test_request_context('/'):
                from app import _ai_tool_call_dispatch_response
                response = _ai_tool_call_dispatch_response('帮我看看6*10的铜排还有多少库存')
        self.assertIsNotNone(response)  # 记录失败不影响回答


if __name__ == '__main__':
    unittest.main()

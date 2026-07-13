#!/usr/bin/env python3
"""阶段1验证脚本：AI平台化重构验证。

验证内容：
1. 新增数据模型（AIConversation, AIFeedback）
2. Provider 模块（熔断器、统一LLM调用）
3. 工具模块（inventory/purchase/navigation）
4. v2 路由注册
5. 向后兼容性（v1 路由仍可用）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-stage1-secret'
sys.path.insert(0, str(APP_DIR))


def test_data_models():
    print("测试数据模型...")
    try:
        from app import db, AIConversation, AIFeedback

        assert AIConversation.__tablename__ == 'ai_conversation'
        assert AIFeedback.__tablename__ == 'ai_feedback'

        assert hasattr(AIConversation, 'user_id')
        assert hasattr(AIConversation, 'session_id')
        assert hasattr(AIConversation, 'role')
        assert hasattr(AIConversation, 'content')
        assert hasattr(AIConversation, 'intent')

        assert hasattr(AIFeedback, 'user_id')
        assert hasattr(AIFeedback, 'rating')
        assert hasattr(AIFeedback, 'reason')
        assert hasattr(AIFeedback, 'ai_run_id')

        print("  PASS: AIConversation 模型正确")
        print("  PASS: AIFeedback 模型正确")
        return True
    except Exception as e:
        print(f"  FAIL: 数据模型测试失败: {e}")
        return False


def test_provider_module():
    print("测试 Provider 模块...")
    try:
        from ai.providers import (
            CircuitBreaker,
            OpenAICompatibleConfig,
            call_llm,
            call_llm_chat,
            call_llm_intent,
            call_llm_vision,
            get_all_breakers_status,
            reset_breakers,
        )

        breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=60)
        assert breaker.state == 'closed'
        assert breaker.allow_request() is True

        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == 'closed'

        breaker.record_failure()
        assert breaker.state == 'open'
        assert breaker.allow_request() is False

        print("  PASS: 熔断器逻辑正确")

        config = OpenAICompatibleConfig(
            enabled=True,
            endpoint='https://api.openai.com/v1/chat/completions',
            model='gpt-3.5-turbo',
            api_key='test-key',
            timeout_seconds=30,
            max_tokens=512,
            vision_enabled=True,
        )
        assert config.configured is True
        assert config.safe_endpoint is True
        assert 'Bearer test-key' in config.headers()['Authorization']

        print("  PASS: OpenAICompatibleConfig 正确")

        assert callable(call_llm)
        assert callable(call_llm_chat)
        assert callable(call_llm_intent)
        assert callable(call_llm_vision)
        assert callable(get_all_breakers_status)
        assert callable(reset_breakers)

        print("  PASS: 便捷函数可用")

        status = get_all_breakers_status()
        assert 'intent' in status
        assert 'chat' in status
        assert 'vision' in status

        reset_breakers()
        status2 = get_all_breakers_status()
        assert status2['intent']['state'] == 'closed'

        print("  PASS: 熔断器状态查询/重置正确")
        return True
    except Exception as e:
        print(f"  FAIL: Provider 模块测试失败: {e}")
        return False


def test_tool_modules():
    print("测试工具模块...")
    try:
        from ai.tools.inventory import (
            material_query, stock_transactions, inventory_health,
            low_stock_report, stock_value_analysis,
        )
        assert callable(material_query)
        assert callable(stock_transactions)
        assert callable(inventory_health)
        assert callable(low_stock_report)
        assert callable(stock_value_analysis)
        print("  PASS: inventory 工具模块可用")

        from ai.tools.purchase import (
            purchase_insights, supplier_analysis, pending_purchase_orders,
        )
        assert callable(purchase_insights)
        assert callable(supplier_analysis)
        assert callable(pending_purchase_orders)
        print("  PASS: purchase 工具模块可用")

        from ai.tools.navigation import (
            skill_catalog, system_api_catalog, usage_help,
        )
        assert callable(skill_catalog)
        assert callable(system_api_catalog)
        assert callable(usage_help)
        print("  PASS: navigation 工具模块可用")

        return True
    except Exception as e:
        print(f"  FAIL: 工具模块测试失败: {e}")
        return False


def test_v2_routes():
    print("测试 v2 路由...")
    try:
        from app import app

        v2_rules = [rule for rule in app.url_map.iter_rules() if rule.rule.startswith('/api/ai/v2/')]

        expected_endpoints = [
            '/api/ai/v2/tools/inventory/material',
            '/api/ai/v2/tools/inventory/transactions',
            '/api/ai/v2/tools/inventory/health',
            '/api/ai/v2/tools/inventory/low-stock',
            '/api/ai/v2/tools/inventory/value',
            '/api/ai/v2/tools/purchase/insights',
            '/api/ai/v2/tools/purchase/suppliers',
            '/api/ai/v2/tools/purchase/pending',
            '/api/ai/v2/tools/navigation/skills',
            '/api/ai/v2/tools/navigation/apis',
            '/api/ai/v2/tools/navigation/help',
            '/api/ai/v2/llm/chat',
            '/api/ai/v2/llm/intent',
            '/api/ai/v2/circuit-breakers',
            '/api/ai/v2/circuit-breakers/reset',
            '/api/ai/v2/feedback',
            '/api/ai/v2/conversations',
        ]

        v2_rule_strings = [rule.rule for rule in v2_rules]

        for endpoint in expected_endpoints:
            if endpoint not in v2_rule_strings:
                print(f"  FAIL: 缺少端点: {endpoint}")
                return False

        print(f"  PASS: 已注册 {len(v2_rules)} 个 v2 端点")
        return True
    except Exception as e:
        print(f"  FAIL: v2 路由测试失败: {e}")
        return False


def test_backward_compatibility():
    print("测试向后兼容性...")
    try:
        from app import app

        v1_rules = [rule for rule in app.url_map.iter_rules()
                    if rule.rule.startswith('/api/ai/') and not rule.rule.startswith('/api/ai/v2/')]

        expected_v1_endpoints = [
            '/api/ai/tools',
            '/api/ai/chat/clear',
            '/api/ai/draft_check',
            '/api/ai/warehouse_assistant',
            '/api/ai/chat/stream',
        ]

        v1_rule_strings = [rule.rule for rule in v1_rules]

        for endpoint in expected_v1_endpoints:
            if endpoint not in v1_rule_strings:
                print(f"  FAIL: v1 端点缺失: {endpoint}")
                return False

        print(f"  PASS: v1 端点全部保留 ({len(v1_rules)} 个)")
        return True
    except Exception as e:
        print(f"  FAIL: 向后兼容性测试失败: {e}")
        return False


def main():
    print("=" * 60)
    print("阶段1验证：AI平台化重构")
    print("=" * 60)

    results = []
    results.append(("数据模型", test_data_models()))
    results.append(("Provider模块", test_provider_module()))
    results.append(("工具模块", test_tool_modules()))
    results.append(("v2路由", test_v2_routes()))
    results.append(("向后兼容", test_backward_compatibility()))

    print("\n" + "=" * 60)
    print("验证结果汇总:")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("PASS: 阶段1验证全部通过")
        return 0
    else:
        print("FAIL: 阶段1验证存在失败项")
        return 1


if __name__ == "__main__":
    sys.exit(main())

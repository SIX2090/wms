#!/usr/bin/env python3
"""阶段3验证脚本：仓库与采购受控Agent。

验证内容：
1. Agent框架（计划/步骤/权限/审计/取消）
2. 仓库主管每日巡检Agent
3. 采购到货跟进Agent
4. 低库存补货Agent
5. 草稿检查Agent
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-stage3-secret'
sys.path.insert(0, str(APP_DIR))


def test_agent_framework():
    print("测试Agent框架...")
    try:
        from ai.agents.framework import (
            AgentStep, AgentPlan, AgentRun, AgentExecutor,
            AgentStepStatus, AgentRunStatus, create_agent_run,
        )

        # 测试创建Agent运行
        steps = [
            {'name': '步骤1', 'description': '测试步骤1', 'tool_name': 'test_tool', 'is_write': False},
            {'name': '步骤2', 'description': '测试步骤2', 'tool_name': 'test_tool2', 'is_write': True, 'requires_confirmation': True},
        ]
        run = create_agent_run('test_agent', user_id=1, goal='测试目标', steps=steps)

        assert run.agent_name == 'test_agent'
        assert run.user_id == 1
        assert len(run.plan.steps) == 2
        assert run.plan.steps[0].name == '步骤1'
        assert run.plan.steps[1].is_write is True
        assert run.plan.steps[1].requires_confirmation is True

        print("  PASS: Agent运行创建正确")

        # 测试执行器
        executor = AgentExecutor(run)
        executor.register_tool('test_tool', lambda **ctx: 'result1')
        executor.register_tool('test_tool2', lambda **ctx: 'result2')

        executor.execute()

        assert run.status == AgentRunStatus.COMPLETED
        assert run.plan.steps[0].status == AgentStepStatus.SUCCESS
        assert run.plan.steps[0].result == 'result1'
        assert run.plan.steps[1].status == AgentStepStatus.SKIPPED  # 需要确认，跳过

        print("  PASS: Agent执行正确（写操作需确认时跳过）")

        # 测试取消
        run2 = create_agent_run('test_agent2', user_id=1, goal='测试', steps=[
            {'name': '步骤1', 'description': '测试', 'tool_name': 'slow_tool', 'is_write': False},
            {'name': '步骤2', 'description': '测试', 'tool_name': 'slow_tool', 'is_write': False},
        ])
        executor2 = AgentExecutor(run2)
        executor2.register_tool('slow_tool', lambda **ctx: 'result')

        # 模拟取消
        executor2.cancel()
        assert run2.status == AgentRunStatus.CANCELLED
        assert all(s.status == AgentStepStatus.CANCELLED for s in run2.plan.steps)

        print("  PASS: Agent取消正确")

        # 测试摘要
        summary = executor.get_summary()
        assert summary['total_steps'] == 2
        assert summary['success'] == 1
        assert summary['skipped'] == 1

        print("  PASS: Agent摘要正确")

        return True
    except Exception as e:
        print(f"  FAIL: Agent框架测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_warehouse_patrol():
    print("测试仓库主管每日巡检Agent...")
    try:
        from ai.agents.warehouse_patrol import (
            warehouse_patrol_agent, format_patrol_report,
            _check_negative_stock, _check_low_stock,
            _check_pending_documents, _check_stale_drafts,
        )

        # 测试函数存在
        assert callable(warehouse_patrol_agent)
        assert callable(format_patrol_report)
        assert callable(_check_negative_stock)
        assert callable(_check_low_stock)
        assert callable(_check_pending_documents)
        assert callable(_check_stale_drafts)

        print("  PASS: 仓库巡检Agent函数可用")

        # 测试空数据库（无模型时返回空结果）
        result1 = _check_negative_stock()
        assert result1 == []

        result2 = _check_low_stock()
        assert result2 == []

        result3 = _check_pending_documents()
        assert result3 == {}

        result4 = _check_stale_drafts()
        assert result4 == []

        print("  PASS: 空数据库返回正确")

        return True
    except Exception as e:
        print(f"  FAIL: 仓库巡检Agent测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_purchase_followup():
    print("测试采购到货跟进Agent...")
    try:
        from ai.agents.purchase_followup import (
            purchase_followup_agent, format_followup_report,
            _get_overdue_orders, _generate_followup_message,
        )

        assert callable(purchase_followup_agent)
        assert callable(format_followup_report)
        assert callable(_get_overdue_orders)
        assert callable(_generate_followup_message)

        print("  PASS: 采购跟进Agent函数可用")

        # 测试催交话术生成
        orders = [
            {
                'order_no': 'PO001',
                'expected_date': '2026-01-01',
                'days_overdue': 5,
                'items': [{'material_code': 'A001', 'material_name': '轴承', 'quantity': 100}],
                'status': 'overdue',
            }
        ]
        message = _generate_followup_message('测试供应商', orders)
        assert '测试供应商' in message
        assert 'PO001' in message
        assert '逾期' in message

        print("  PASS: 催交话术生成正确")

        return True
    except Exception as e:
        print(f"  FAIL: 采购跟进Agent测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_replenishment():
    print("测试低库存补货Agent...")
    try:
        from ai.agents.replenishment import (
            replenishment_agent, format_replenishment_report,
            _get_materials_needing_replenishment, _generate_replenishment_explanation,
        )

        assert callable(replenishment_agent)
        assert callable(format_replenishment_report)
        assert callable(_get_materials_needing_replenishment)
        assert callable(_generate_replenishment_explanation)

        print("  PASS: 补货Agent函数可用")

        # 测试补货解释生成
        item = {
            'code': 'A001',
            'name': '轴承',
            'current_qty': 10,
            'min_stock': 100,
            'open_po_qty': 20,
            'pending_pr_qty': 10,
            'shortage': 60,
            'suggested_qty': 60,
            'unit': '个',
        }
        explanation = _generate_replenishment_explanation(item)
        assert 'A001' in explanation
        assert '轴承' in explanation
        assert '当前库存：10' in explanation
        assert '安全库存：100' in explanation
        assert '建议补货：60' in explanation

        print("  PASS: 补货解释生成正确")

        return True
    except Exception as e:
        print(f"  FAIL: 补货Agent测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_draft_check():
    print("测试草稿检查Agent...")
    try:
        from ai.agents.draft_check import (
            draft_check_agent, format_draft_check_report,
            _check_required_fields, _check_duplicate_materials,
            _check_quantity_anomalies, _check_stock_sufficiency,
            _check_po_quantity,
        )

        assert callable(draft_check_agent)
        assert callable(format_draft_check_report)
        assert callable(_check_required_fields)
        assert callable(_check_duplicate_materials)
        assert callable(_check_quantity_anomalies)
        assert callable(_check_stock_sufficiency)
        assert callable(_check_po_quantity)

        print("  PASS: 草稿检查Agent函数可用")

        # 测试必填字段检查
        class MockOrder:
            warehouse_id = None
            supplier_id = 'S001'

        errors = _check_required_fields(MockOrder(), ['warehouse_id', 'supplier_id'])
        assert len(errors) == 1
        assert 'warehouse_id' in errors[0]

        print("  PASS: 必填字段检查正确")

        # 测试重复物料检查
        class MockItem:
            def __init__(self, material_id):
                self.material_id = material_id

        items = [MockItem(1), MockItem(2), MockItem(1)]
        errors = _check_duplicate_materials(items)
        assert len(errors) == 1
        assert '重复' in errors[0]

        print("  PASS: 重复物料检查正确")

        # 测试异常数量检查
        class MockItem2:
            def __init__(self, quantity):
                self.quantity = quantity

        items2 = [MockItem2(10), MockItem2(10), MockItem2(10), MockItem2(10000)]
        errors2 = _check_quantity_anomalies(items2, max_ratio=2.0)
        assert len(errors2) >= 1
        assert '异常' in errors2[0]

        print("  PASS: 异常数量检查正确")

        return True
    except Exception as e:
        print(f"  FAIL: 草稿检查Agent测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("阶段3验证：仓库与采购受控Agent")
    print("=" * 60)

    results = []
    results.append(("Agent框架", test_agent_framework()))
    results.append(("仓库巡检Agent", test_warehouse_patrol()))
    results.append(("采购跟进Agent", test_purchase_followup()))
    results.append(("补货Agent", test_replenishment()))
    results.append(("草稿检查Agent", test_draft_check()))

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
        print("PASS: 阶段3验证全部通过")
        return 0
    else:
        print("FAIL: 阶段3验证存在失败项")
        return 1


if __name__ == "__main__":
    sys.exit(main())

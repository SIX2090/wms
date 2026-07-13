#!/usr/bin/env python3
"""阶段4验证脚本：知识、分析与主数据增强。

验证内容：
1. 知识库增强（13条SOP/规则）
2. 库存周转分析工具
3. 呆滞物料分析工具
4. 缺料分析工具
5. 预计可用天数分析工具
6. 供应商履约分析工具
7. 主数据质量评分工具
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-stage4-secret'
sys.path.insert(0, str(APP_DIR))


def test_knowledge_base():
    print("测试知识库增强...")
    try:
        from ai.knowledge import AI_KNOWLEDGE_BASE, search_knowledge_entries

        # 验证知识库条目数量
        assert len(AI_KNOWLEDGE_BASE) == 13, f"Expected 13 entries, got {len(AI_KNOWLEDGE_BASE)}"
        print("  PASS: 知识库包含13条条目")

        # 验证新增条目
        keys = [e.key for e in AI_KNOWLEDGE_BASE]
        assert 'transfer_sop' in keys
        assert 'adjustment_sop' in keys
        assert 'negative_stock_handling' in keys
        assert 'replenishment_rule' in keys
        assert 'document_lifecycle' in keys
        assert 'ai_permission_rule' in keys
        assert 'ocr_confirmation_rule' in keys
        print("  PASS: 新增7条知识库条目")

        # 验证搜索功能
        results = search_knowledge_entries('调拨怎么操作', limit=2)
        assert len(results) > 0
        assert any('transfer' in r.key for r in results)
        print("  PASS: 知识库搜索功能正常")

        return True
    except Exception as e:
        print(f"  FAIL: 知识库测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_turnover_analysis():
    print("测试库存周转分析工具...")
    try:
        from ai.analysis.turnover import inventory_turnover_analysis

        # 测试空数据库
        result = inventory_turnover_analysis()
        assert 'turnover_rate' in result
        assert 'turnover_days' in result
        assert 'fast_moving' in result
        assert 'slow_moving' in result
        assert 'materials' in result
        assert result['turnover_rate'] == 0.0
        assert result['materials'] == []
        print("  PASS: 空数据库返回正确")

        # 验证函数签名
        import inspect
        sig = inspect.signature(inventory_turnover_analysis)
        assert 'db' in sig.parameters
        assert 'Material' in sig.parameters
        assert 'Stock' in sig.parameters
        assert 'StockTransaction' in sig.parameters
        assert 'days' in sig.parameters
        assert 'limit' in sig.parameters
        print("  PASS: 函数签名正确")

        return True
    except Exception as e:
        print(f"  FAIL: 周转分析测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_stagnant_analysis():
    print("测试呆滞物料分析工具...")
    try:
        from ai.analysis.stagnant import stagnant_material_analysis

        result = stagnant_material_analysis()
        assert 'stagnant_count' in result
        assert 'stagnant_value' in result
        assert 'materials' in result
        assert result['stagnant_count'] == 0
        assert result['stagnant_value'] == 0.0
        print("  PASS: 空数据库返回正确")

        import inspect
        sig = inspect.signature(stagnant_material_analysis)
        assert 'stagnant_days' in sig.parameters
        assert sig.parameters['stagnant_days'].default == 180
        print("  PASS: 默认呆滞天数180天")

        return True
    except Exception as e:
        print(f"  FAIL: 呆滞分析测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_shortage_analysis():
    print("测试缺料分析工具...")
    try:
        from ai.analysis.shortage import shortage_analysis

        result = shortage_analysis()
        assert 'shortage_count' in result
        assert 'materials' in result
        assert result['shortage_count'] == 0
        print("  PASS: 空数据库返回正确")

        import inspect
        sig = inspect.signature(shortage_analysis)
        assert 'OutOrder' in sig.parameters
        assert 'OutOrderItem' in sig.parameters
        assert 'PurchaseOrder' in sig.parameters
        assert 'PurchaseOrderItem' in sig.parameters
        print("  PASS: 支持出库单和采购订单依赖")

        return True
    except Exception as e:
        print(f"  FAIL: 缺料分析测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_available_days_analysis():
    print("测试预计可用天数分析工具...")
    try:
        from ai.analysis.available_days import available_days_analysis

        result = available_days_analysis()
        assert 'critical_count' in result
        assert 'low_count' in result
        assert 'materials' in result
        assert result['critical_count'] == 0
        assert result['low_count'] == 0
        print("  PASS: 空数据库返回正确")

        import inspect
        sig = inspect.signature(available_days_analysis)
        assert 'days' in sig.parameters
        assert sig.parameters['days'].default == 30
        print("  PASS: 默认消耗速度计算天数30天")

        return True
    except Exception as e:
        print(f"  FAIL: 可用天数分析测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_supplier_performance_analysis():
    print("测试供应商履约分析工具...")
    try:
        from ai.analysis.supplier_performance import supplier_performance_analysis

        result = supplier_performance_analysis()
        assert 'suppliers' in result
        assert result['suppliers'] == []
        print("  PASS: 空数据库返回正确")

        import inspect
        sig = inspect.signature(supplier_performance_analysis)
        assert 'days' in sig.parameters
        assert sig.parameters['days'].default == 90
        print("  PASS: 默认分析天数90天")

        return True
    except Exception as e:
        print(f"  FAIL: 供应商履约分析测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_master_data_quality():
    print("测试主数据质量评分工具...")
    try:
        from ai.analysis.master_data_quality import master_data_quality_score

        result = master_data_quality_score()
        assert 'overall_score' in result
        assert 'material_score' in result
        assert 'supplier_score' in result
        assert 'customer_score' in result
        assert 'issues' in result
        assert result['overall_score'] == 0
        print("  PASS: 空数据库返回正确")

        import inspect
        sig = inspect.signature(master_data_quality_score)
        assert 'Material' in sig.parameters
        assert 'Supplier' in sig.parameters
        assert 'Customer' in sig.parameters
        print("  PASS: 支持物料/供应商/客户模型")

        return True
    except Exception as e:
        print(f"  FAIL: 主数据质量评分测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("阶段4验证：知识、分析与主数据增强")
    print("=" * 60)

    results = []
    results.append(("知识库增强", test_knowledge_base()))
    results.append(("库存周转分析", test_turnover_analysis()))
    results.append(("呆滞物料分析", test_stagnant_analysis()))
    results.append(("缺料分析", test_shortage_analysis()))
    results.append(("预计可用天数", test_available_days_analysis()))
    results.append(("供应商履约分析", test_supplier_performance_analysis()))
    results.append(("主数据质量评分", test_master_data_quality()))

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
        print("PASS: 阶段4验证全部通过")
        return 0
    else:
        print("FAIL: 阶段4验证存在失败项")
        return 1


if __name__ == "__main__":
    sys.exit(main())

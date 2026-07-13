#!/usr/bin/env python3
"""阶段5验证脚本：生产化、评估和灰度发布。

验证内容：
1. AI运维监控看板（健康检查/指标统计/告警规则/趋势数据）
2. Feature Flags灰度发布（发布模式/功能开关/用户灰度）
3. LLM熔断回退链（主模型→备用模型→本地规则）
4. 分角色灰度发布（角色能力映射/功能权限）
5. AI效果评估框架（用例管理/评估执行/反馈统计）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-stage5-secret'
sys.path.insert(0, str(APP_DIR))


def test_ops_monitor():
    print("测试AI运维监控看板...")
    try:
        from ai.ops.monitor import (
            OpsMonitor, HealthStatus, AIMetrics, AlertRule, get_ops_monitor,
        )

        monitor = OpsMonitor()

        # 测试健康检查
        checks = monitor.check_health(llm_configured=True, llm_reachable=True, db_healthy=True)
        assert len(checks) == 2
        assert all(c.status == HealthStatus.HEALTHY for c in checks)
        print("  PASS: 健康检查（全正常）")

        checks2 = monitor.check_health(llm_configured=False, db_healthy=True)
        assert any(c.status == HealthStatus.DEGRADED for c in checks2)
        print("  PASS: 健康检查（LLM未配置降级）")

        # 测试记录请求和指标
        for i in range(10):
            monitor.record_request(
                success=(i < 8),
                latency_ms=100 + i * 10,
                tool_name='test_tool',
                fallback=(i >= 8),
            )

        metrics = monitor.get_metrics(hours=24)
        assert metrics.total_requests == 10
        assert metrics.success_count == 8
        assert metrics.failure_count == 2
        assert metrics.fallback_count == 2
        assert metrics.success_rate == 80.0
        assert metrics.fallback_rate == 20.0
        print("  PASS: 指标统计正确")

        # 测试告警规则
        monitor.add_alert_rule(AlertRule(
            name='test_success_rate',
            metric='success_rate',
            operator='lt',
            threshold=90.0,
            severity='critical',
        ))

        triggered = monitor.evaluate_alerts(metrics)
        assert len(triggered) == 1
        assert triggered[0]['name'] == 'test_success_rate'
        print("  PASS: 告警规则触发正确")

        # 测试趋势数据
        trend = monitor.get_trend_data(hours=24, granularity='hour')
        assert len(trend) == 24
        print("  PASS: 趋势数据生成正确")

        # 测试全局实例
        global_monitor = get_ops_monitor()
        assert isinstance(global_monitor, OpsMonitor)
        print("  PASS: 全局监控实例可用")

        return True
    except Exception as e:
        print(f"  FAIL: 监控看板测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_feature_flags():
    print("测试Feature Flags灰度发布...")
    try:
        from ai.ops.feature_flags import (
            FeatureFlag, FeatureFlagManager, RolloutMode, get_feature_manager,
        )

        fm = FeatureFlagManager()

        # 测试发布模式
        fm.set_rollout_mode(RolloutMode.ALL)
        assert fm.get_rollout_mode() == RolloutMode.ALL
        print("  PASS: 发布模式设置正确")

        # 测试Feature Flag注册
        flag = FeatureFlag(
            name='test_feature',
            enabled=True,
            rollout_percentage=100,
            description='测试功能',
        )
        fm.register_flag(flag)
        assert fm.get_flag('test_feature') is not None
        print("  PASS: Feature Flag注册正确")

        # 测试功能可用性
        assert fm.is_feature_available('test_feature', user_id=1, user_role='viewer')
        print("  PASS: 功能可用性检查正确")

        # 测试只读模式
        fm.set_rollout_mode(RolloutMode.READ_ONLY)
        assert fm.is_feature_available('knowledge_base', user_id=1, user_role='viewer')
        assert not fm.is_feature_available('in_order_draft', user_id=1, user_role='viewer')
        print("  PASS: 只读模式限制正确")

        # 测试草稿模式
        fm.set_rollout_mode(RolloutMode.READ_DRAFT)
        assert fm.is_feature_available('in_order_draft', user_id=1, user_role='viewer')
        assert not fm.is_feature_available('warehouse_patrol_agent', user_id=1, user_role='viewer')
        print("  PASS: 草稿模式限制正确")

        # 测试管理员模式
        fm.set_rollout_mode(RolloutMode.ADMIN_ONLY)
        assert fm.is_feature_available('test_feature', user_id=1, user_role='admin')
        assert not fm.is_feature_available('test_feature', user_id=1, user_role='viewer')
        print("  PASS: 管理员模式限制正确")

        # 测试百分比灰度
        fm.set_rollout_mode(RolloutMode.ALL)
        flag2 = FeatureFlag(
            name='percent_test',
            enabled=True,
            rollout_percentage=50,
        )
        fm.register_flag(flag2)
        # user_id=1: 1%100=1 < 50, 应该启用
        assert flag2.is_enabled_for(user_id=1)
        # user_id=60: 60%100=60 >= 50, 应该禁用
        assert not flag2.is_enabled_for(user_id=60)
        print("  PASS: 百分比灰度正确")

        # 测试全局实例
        global_fm = get_feature_manager()
        assert isinstance(global_fm, FeatureFlagManager)
        print("  PASS: 全局Feature Flag管理器可用")

        return True
    except Exception as e:
        print(f"  FAIL: Feature Flags测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_fallback_chain():
    print("测试LLM熔断回退链...")
    try:
        # 检查 requests 是否可用
        try:
            import requests  # noqa: F401
        except ImportError:
            print("  SKIP: requests 未安装，跳过回退链测试")
            return True

        from ai.ops.fallback import FallbackChain, FallbackLevel, get_fallback_chain

        chain = FallbackChain()

        # 测试无配置时回退到本地规则
        def local_handler(messages):
            return 'local response'

        chain.set_local_handler(local_handler)
        result, level = chain.execute([{'role': 'user', 'content': 'test'}])
        assert result == 'local response'
        assert level == FallbackLevel.LOCAL_RULES
        print("  PASS: 无模型时回退到本地规则")

        # 测试统计
        stats = chain.get_stats()
        assert stats['local_fallback'] == 1
        assert stats['total_calls'] == 1
        print("  PASS: 回退统计正确")

        # 测试重置统计
        chain.reset_stats()
        stats2 = chain.get_stats()
        assert stats2['local_fallback'] == 0
        print("  PASS: 统计重置正确")

        # 测试全局实例
        global_chain = get_fallback_chain()
        assert isinstance(global_chain, FallbackChain)
        print("  PASS: 全局回退链实例可用")

        return True
    except Exception as e:
        print(f"  FAIL: 回退链测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_role_rollout():
    print("测试分角色灰度发布...")
    try:
        from ai.ops.role_rollout import (
            get_allowed_features, is_feature_allowed, get_role_capabilities,
            get_role_comparison,
        )

        # 测试角色功能映射
        admin_features = get_allowed_features('admin')
        assert len(admin_features) > 20
        assert 'ai_chat' in admin_features
        assert 'warehouse_patrol_agent' in admin_features
        print("  PASS: 管理员角色功能完整")

        viewer_features = get_allowed_features('viewer')
        assert len(viewer_features) < 10
        assert 'ai_chat' in viewer_features
        assert 'warehouse_patrol_agent' not in viewer_features
        print("  PASS: 普通用户角色功能受限")

        # 测试功能权限检查
        assert is_feature_allowed('ai_chat', user_role='admin')
        assert is_feature_allowed('warehouse_patrol_agent', user_role='warehouse_manager')
        assert not is_feature_allowed('warehouse_patrol_agent', user_role='viewer')
        print("  PASS: 功能权限检查正确")

        # 测试角色能力概览
        caps = get_role_capabilities('warehouse_manager')
        assert caps['role'] == 'warehouse_manager'
        assert caps['chat'] is True
        assert caps['vision'] is True
        assert caps['drafts'] is True
        assert caps['agents'] is True
        print("  PASS: 角色能力概览正确")

        # 测试角色对比
        comparison = get_role_comparison()
        assert 'admin' in comparison
        assert 'warehouse_manager' in comparison
        assert 'purchase' in comparison
        assert 'production' in comparison
        assert 'viewer' in comparison
        print("  PASS: 角色对比数据完整")

        return True
    except Exception as e:
        print(f"  FAIL: 角色灰度测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def test_evaluation_framework():
    print("测试AI效果评估框架...")
    try:
        from ai.ops.evaluation import (
            Evaluator, EvaluationCase, EvaluationResult, EvaluationReport, get_evaluator,
        )

        evaluator = Evaluator()

        # 测试添加用例
        case1 = EvaluationCase(
            id='test_1',
            category='L1',
            input_text='你好',
            expected_intent='basic_conversation',
            expected_output_contains=['你好'],
        )
        evaluator.add_case(case1)
        assert len(evaluator._cases) == 1
        print("  PASS: 评估用例添加正确")

        # 测试评估（无函数时全部通过）
        report = evaluator.evaluate()
        assert report.total_cases == 1
        assert report.passed_cases == 1
        assert report.pass_rate == 100.0
        print("  PASS: 评估执行正确")

        # 测试反馈记录
        evaluator.record_feedback('run_1', user_id=1, thumbs='up', comment='很好')
        evaluator.record_feedback('run_2', user_id=2, thumbs='down', comment='不准确')
        feedback_stats = evaluator.get_feedback_stats()
        assert feedback_stats['total_feedback'] == 2
        assert feedback_stats['thumbs_up'] == 1
        assert feedback_stats['thumbs_down'] == 1
        assert feedback_stats['satisfaction_rate'] == 50.0
        print("  PASS: 反馈统计正确")

        # 测试全局实例
        global_evaluator = get_evaluator()
        assert isinstance(global_evaluator, Evaluator)
        print("  PASS: 全局评估器实例可用")

        return True
    except Exception as e:
        print(f"  FAIL: 评估框架测试失败: {e}")
        import traceback; traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("阶段5验证：生产化、评估和灰度发布")
    print("=" * 60)

    results = []
    results.append(("运维监控看板", test_ops_monitor()))
    results.append(("Feature Flags", test_feature_flags()))
    results.append(("LLM回退链", test_fallback_chain()))
    results.append(("角色灰度发布", test_role_rollout()))
    results.append(("效果评估框架", test_evaluation_framework()))

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
        print("PASS: 阶段5验证全部通过")
        return 0
    else:
        print("FAIL: 阶段5验证存在失败项")
        return 1


if __name__ == "__main__":
    sys.exit(main())

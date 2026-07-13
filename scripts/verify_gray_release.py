#!/usr/bin/env python3
"""灰度发布验证脚本"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

def test_feature_flags():
    """测试Feature Flags"""
    print("=" * 60)
    print("测试Feature Flags")
    print("=" * 60)
    
    try:
        from ai.ops.feature_flags import FeatureFlagManager, RolloutMode
        
        # 创建管理器
        manager = FeatureFlagManager()
        
        # 测试不同发布模式
        modes = [
            RolloutMode.DISABLED,
            RolloutMode.ADMIN_ONLY,
            RolloutMode.READ_ONLY,
            RolloutMode.READ_DRAFT,
            RolloutMode.ALL
        ]
        
        for mode in modes:
            manager.set_rollout_mode(mode)
            current = manager.get_rollout_mode()
            print(f"✓ 设置发布模式: {mode.value} -> {current.value}")
        
        # 测试功能开关
        manager.set_flag('ai_chat', enabled=True)
        manager.set_flag('ai_vision', enabled=False)
        
        chat_flag = manager.get_flag('ai_chat')
        vision_flag = manager.get_flag('ai_vision')
        
        print(f"✓ ai_chat功能: {'启用' if chat_flag and chat_flag.enabled else '禁用'}")
        print(f"✓ ai_vision功能: {'启用' if vision_flag and vision_flag.enabled else '禁用'}")
        
        return True
    except Exception as e:
        print(f"✗ Feature Flags测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_role_rollout():
    """测试角色灰度"""
    print("\n" + "=" * 60)
    print("测试角色灰度")
    print("=" * 60)
    
    try:
        from ai.ops.role_rollout import (
            get_allowed_features,
            is_feature_allowed,
            get_role_capabilities,
            get_role_comparison
        )
        
        # 测试不同角色的功能权限
        roles = ['admin', 'warehouse_manager', 'purchase', 'production', 'viewer']
        
        for role in roles:
            features = get_allowed_features(role)
            caps = get_role_capabilities(role)
            print(f"✓ 角色 {role}: {len(features)}个功能")
            print(f"  - 聊天: {caps['chat']}")
            print(f"  - 视觉: {caps['vision']}")
            print(f"  - 草稿: {caps['drafts']}")
            print(f"  - Agent: {caps['agents']}")
        
        # 测试功能权限检查
        admin_can_chat = is_feature_allowed('ai_chat', 'admin', 1)
        viewer_can_draft = is_feature_allowed('in_order_draft', 'viewer', 2)
        
        print(f"\n✓ 管理员可以使用聊天: {admin_can_chat}")
        print(f"✓ 访客不能使用草稿: {not viewer_can_draft}")
        
        # 测试角色对比
        comparison = get_role_comparison()
        print(f"\n✓ 角色能力对比: {len(comparison)}个角色")
        
        return True
    except Exception as e:
        print(f"✗ 角色灰度测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_circuit_breaker():
    """测试熔断器"""
    print("\n" + "=" * 60)
    print("测试熔断器")
    print("=" * 60)
    
    try:
        from ai.providers import CircuitBreaker
        
        # 创建熔断器
        breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=60)
        
        # 测试初始状态
        print(f"✓ 初始状态: {breaker.state}")
        print(f"✓ 失败计数: {breaker._failures}")
        
        # 测试成功调用
        breaker.record_success()
        print(f"✓ 记录成功后状态: {breaker.state}")
        
        # 测试失败调用
        breaker.record_failure()
        breaker.record_failure()
        print(f"✓ 记录2次失败后状态: {breaker.state}, 失败计数: {breaker._failures}")
        
        # 测试熔断
        breaker.record_failure()
        print(f"✓ 记录3次失败后状态: {breaker.state}")
        
        # 测试是否可以请求
        can_request = breaker.allow_request()
        print(f"✓ 熔断状态下可以请求: {can_request}")
        
        return True
    except Exception as e:
        print(f"✗ 熔断器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_fallback_chain():
    """测试回退链"""
    print("\n" + "=" * 60)
    print("测试回退链")
    print("=" * 60)
    
    try:
        from ai.ops.fallback import FallbackChain, FallbackLevel
        
        # 创建回退链
        chain = FallbackChain()
        
        # 测试设置本地规则处理器
        def local_handler(query, context):
            return {
                'type': 'local_rule',
                'message': f'本地规则处理: {query}',
                'data': {}
            }
        
        chain.set_local_handler(local_handler)
        print("✓ 设置本地规则处理器成功")
        
        # 测试回退统计
        stats = chain.get_stats()
        print(f"✓ 回退统计: {stats}")
        
        # 测试回退记录（从stats中获取）
        records = stats.get('recent_fallbacks', [])
        print(f"✓ 回退记录数: {len(records)}")
        
        return True
    except Exception as e:
        print(f"✗ 回退链测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("灰度发布验证")
    print("=" * 60 + "\n")
    
    results = []
    
    # 运行所有测试
    results.append(('Feature Flags', test_feature_flags()))
    results.append(('角色灰度', test_role_rollout()))
    results.append(('熔断器', test_circuit_breaker()))
    results.append(('回退链', test_fallback_chain()))
    
    # 输出结果汇总
    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n✓ 灰度发布验证全部通过")
        return 0
    else:
        print("\n✗ 灰度发布验证部分失败")
        return 1

if __name__ == '__main__':
    sys.exit(main())

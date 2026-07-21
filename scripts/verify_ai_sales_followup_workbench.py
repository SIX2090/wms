"""AI-SALES-F02 销售履约 AI 工作台页面接入验证脚本。

# AI_TASK: AI-SALES-F02

验证内容：
1. 工作台页面路由存在且可访问
2. API 端点存在且返回正确结构
3. 导航菜单包含工作台入口
4. 页面模板包含 7 类业务队列
5. 页面只读校验（不含写操作按钮）
6. 页面包含空态提示
7. 页面包含跳转链接
8. 页面包含刷新功能
9. 工作台 ops 模块验收校验（read_only + metric_scope + count_consistency）
10. 权限三表一致性（sales_insights + sales_followup_agent 在三表+registry 中存在）
11. Agent 模块（agents/sales_followup.py）函数签名正确

退出码 0=通过，1=失败。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


# 设置测试环境变量
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-verification')
os.environ.setdefault('WMS_ALLOW_AUTO_SECRET_KEY', '1')


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_workbench_page_route() -> None:
    """测试1：工作台页面路由存在。"""
    from app import app

    with app.test_client() as client:
        resp = client.get('/ai/sales_workbench', follow_redirects=False)
        assert resp.status_code in [302, 401], f'未登录应重定向，实际 {resp.status_code}'

    print('测试1 通过: 工作台页面路由存在')


def test_workbench_api_endpoint() -> None:
    """测试2：API 端点存在。"""
    from app import app

    with app.test_client() as client:
        resp = client.get('/api/ai/sales_followup_workbench', follow_redirects=False)
        assert resp.status_code in [302, 401, 403], f'未登录应拒绝，实际 {resp.status_code}'

    print('测试2 通过: API 端点存在')


def test_navigation_menu_entry() -> None:
    """测试3：导航菜单包含工作台入口。"""
    nav_file = ROOT / 'app' / 'templates' / 'base.html'
    content = nav_file.read_text(encoding='utf-8')

    assert '/ai/sales_workbench' in content, '导航菜单缺少工作台链接'
    assert '销售工作台' in content, '导航菜单缺少工作台文本'

    print('测试3 通过: 导航菜单包含工作台入口')


def test_template_exists() -> None:
    """测试4：页面模板存在且包含 7 类业务队列。"""
    template_file = ROOT / 'app' / 'templates' / 'ai_sales_workbench.html'
    assert template_file.exists(), '模板文件不存在'

    content = template_file.read_text(encoding='utf-8')

    # 检查 7 类业务队列
    assert 'pending_shipment' in content or '待发货' in content, '缺少待发货'
    assert 'overdue_shipment' in content or '逾期' in content, '缺少逾期未发货'
    assert 'partial_stalled' in content or '停滞' in content, '缺少部分停滞'
    assert 'short_stock' in content or '缺货' in content, '缺少缺货待核对'
    assert 'customer_urgency' in content or '催发货' in content, '缺少客户催发货话术'
    assert 'merge_candidates' in content or '合并' in content, '缺少合并发货候选'
    assert 'customer_followup_list' in content or '客户跟进' in content, '缺少客户跟进清单'

    print('测试4 通过: 页面模板存在且包含 7 类业务队列')


def test_read_only_constraint() -> None:
    """测试5：页面只读校验（不含写操作按钮）。"""
    template_file = ROOT / 'app' / 'templates' / 'ai_sales_workbench.html'
    content = template_file.read_text(encoding='utf-8')

    # 检查不应包含写操作按钮
    forbidden_actions = ['send', 'submit', 'audit', 'delete', 'void', 'complete', 'confirm_post', 'cancel', 'auto_dispatch']
    for action in forbidden_actions:
        assert action not in content.lower(), f'页面包含写操作按钮: {action}'

    # 检查应包含只读提示
    assert '只读' in content or 'read-only' in content.lower() or 'read_only' in content, '缺少只读提示'
    assert '人工确认' in content or 'manual_confirmation' in content, '缺少人工确认提示'

    print('测试5 通过: 页面只读校验通过')


def test_empty_state_hint() -> None:
    """测试6：页面包含空态提示。"""
    template_file = ROOT / 'app' / 'templates' / 'ai_sales_workbench.html'
    content = template_file.read_text(encoding='utf-8')

    # 检查空态提示
    assert 'empty_hint' in content or '暂无' in content or '空态' in content, '缺少空态提示'

    print('测试6 通过: 页面包含空态提示')


def test_jump_links() -> None:
    """测试7：页面包含跳转链接。"""
    template_file = ROOT / 'app' / 'templates' / 'ai_sales_workbench.html'
    content = template_file.read_text(encoding='utf-8')

    # 检查跳转链接
    assert 'jump_url' in content or 'href=' in content, '缺少跳转链接'
    assert '查看全部' in content or '查看' in content, '缺少查看按钮'

    print('测试7 通过: 页面包含跳转链接')


def test_refresh_functionality() -> None:
    """测试8：页面包含刷新功能。"""
    template_file = ROOT / 'app' / 'templates' / 'ai_sales_workbench.html'
    content = template_file.read_text(encoding='utf-8')

    # 检查刷新功能
    assert 'loadWorkbench' in content or '刷新' in content, '缺少刷新功能'
    assert 'DOMContentLoaded' in content or 'onload' in content.lower(), '缺少自动加载'

    print('测试8 通过: 页面包含刷新功能')


def test_workbench_ops_validation() -> None:
    """测试9：工作台 ops 模块验收校验（read_only + metric_scope + count_consistency）。"""
    from ai.ops.sales_followup_workbench import (
        build_sales_followup_workbench,
        validate_followup_read_only,
        validate_metric_scope_clear,
        validate_count_consistency,
    )

    # mock 7 个 query 回调
    snap = build_sales_followup_workbench(
        query_pending_shipment=lambda: (2, [
            {'id': 1, 'title': 'SO-001', 'subtitle': '客户A', 'detail': '应发 2026-07-25', 'jump_url': '/sales_order/detail/1'},
            {'id': 2, 'title': 'SO-002', 'subtitle': '客户B', 'detail': '应发 2026-07-26', 'jump_url': '/sales_order/detail/2'},
        ]),
        query_overdue_shipment=lambda: (1, [
            {'id': 3, 'title': 'SO-003', 'subtitle': '客户C', 'detail': '逾期 3 天', 'jump_url': '/sales_order/detail/3'},
        ]),
        query_partial_stalled=lambda: (0, []),
        query_short_stock=lambda: (0, []),
        query_customer_urgency=lambda: (1, [
            {'id': 1, 'title': '客户A', 'subtitle': '逾期 1 单', 'detail': '催发货话术', 'jump_url': '/sales_order/list?customer_id=1'},
        ]),
        query_merge_candidates=lambda: (0, []),
        query_customer_followup_list=lambda: [
            {
                'customer_id': 1, 'customer_name': '客户A',
                'pending_count': 2, 'overdue_count': 1, 'short_stock_count': 0,
                'followup_suggestion': '建议催发货', 'needs_manual_confirmation': True,
                'jump_url': '/sales_order/list?customer_id=1',
            }
        ],
        user_id=1, role='sales',
    )

    # 校验 read_only
    ok_ro, viols_ro = validate_followup_read_only(snap)
    assert ok_ro, f'read_only 校验失败：{viols_ro}'

    # 校验 metric_scope
    ok_scope, viols_scope = validate_metric_scope_clear(snap)
    assert ok_scope, f'metric_scope 校验失败：{viols_scope}'

    # 校验 count_consistency
    ok_count, viols_count = validate_count_consistency(
        snap,
        expected_counts={
            'pending_shipment': 2,
            'overdue_shipment': 1,
            'partial_stalled': 0,
            'short_stock': 0,
            'customer_urgency': 1,
            'merge_candidates': 0,
            'customer_followup_list': 1,
        },
    )
    assert ok_count, f'count_consistency 校验失败：{viols_count}'

    # 校验 sections 数量
    assert len(snap.sections) == 7, f'sections 数量应为 7，实际 {len(snap.sections)}'

    # 校验 total_attention_count
    assert snap.total_attention_count == 4, f'total_attention_count 应为 4（2+1+0+0+1+0），实际 {snap.total_attention_count}'

    print('测试9 通过: 工作台 ops 模块验收校验通过')


def test_permission_three_table_consistency() -> None:
    """测试10：权限三表一致性（sales_insights + sales_followup_agent 在三表 + registry 中存在）。"""
    from ai.policies import (
        AI_CAPABILITY_ROLES,
        AI_CAPABILITY_BUSINESS_ENDPOINTS,
        AI_CAPABILITY_RISK_LEVELS,
    )
    from ai.tools.registry import AI_TOOL_REGISTRY

    # 三表键集一致
    keys_roles = set(AI_CAPABILITY_ROLES.keys())
    keys_endpoints = set(AI_CAPABILITY_BUSINESS_ENDPOINTS.keys())
    keys_risk = set(AI_CAPABILITY_RISK_LEVELS.keys())
    assert keys_roles == keys_endpoints == keys_risk, (
        f'三表键集不一致：roles={len(keys_roles)} endpoints={len(keys_endpoints)} risk={len(keys_risk)}'
    )

    # registry 键集与 policies 键集一致
    keys_registry = set(AI_TOOL_REGISTRY.keys())
    assert keys_registry == keys_roles, (
        f'registry 与 policies 键集不一致：registry={len(keys_registry)} policies={len(keys_roles)}'
    )

    # 新增两键存在
    for key in ('sales_insights', 'sales_followup_agent'):
        assert key in AI_CAPABILITY_ROLES, f'AI_CAPABILITY_ROLES 缺少 {key}'
        assert key in AI_CAPABILITY_BUSINESS_ENDPOINTS, f'AI_CAPABILITY_BUSINESS_ENDPOINTS 缺少 {key}'
        assert key in AI_CAPABILITY_RISK_LEVELS, f'AI_CAPABILITY_RISK_LEVELS 缺少 {key}'
        assert key in AI_TOOL_REGISTRY, f'AI_TOOL_REGISTRY 缺少 {key}'

    # 角色和风险级别正确
    assert AI_CAPABILITY_ROLES['sales_insights'] == frozenset({'sales'}), (
        f'sales_insights 角色集错误：{AI_CAPABILITY_ROLES["sales_insights"]}'
    )
    assert AI_CAPABILITY_ROLES['sales_followup_agent'] == frozenset({'sales'}), (
        f'sales_followup_agent 角色集错误：{AI_CAPABILITY_ROLES["sales_followup_agent"]}'
    )
    assert AI_CAPABILITY_RISK_LEVELS['sales_insights'] == 'read', (
        f'sales_insights 风险级别错误：{AI_CAPABILITY_RISK_LEVELS["sales_insights"]}'
    )
    assert AI_CAPABILITY_RISK_LEVELS['sales_followup_agent'] == 'read', (
        f'sales_followup_agent 风险级别错误：{AI_CAPABILITY_RISK_LEVELS["sales_followup_agent"]}'
    )

    print('测试10 通过: 权限三表一致性校验通过')


def test_agent_module_signatures() -> None:
    """测试11：Agent 模块（agents/sales_followup.py）函数签名正确。"""
    from ai.agents.sales_followup import (
        sales_followup_agent,
        format_sales_followup_report,
        _get_pending_and_overdue_orders,
        _generate_customer_followup_message,
    )

    assert callable(sales_followup_agent), 'sales_followup_agent 不可调用'
    assert callable(format_sales_followup_report), 'format_sales_followup_report 不可调用'
    assert callable(_get_pending_and_overdue_orders), '_get_pending_and_overdue_orders 不可调用'
    assert callable(_generate_customer_followup_message), '_generate_customer_followup_message 不可调用'

    # 测试 _generate_customer_followup_message 输出含"需人工确认"
    msg = _generate_customer_followup_message('客户A', [
        {'order_no': 'SO-001', 'delivery_date': '2026-07-15', 'days_overdue': 3, 'status': 'overdue', 'items': []},
    ])
    assert '需人工确认' in msg, '催发货话术缺少"需人工确认"提示'
    assert '客户A' in msg, '催发货话术缺少客户名'

    print('测试11 通过: Agent 模块函数签名校验通过')


def main() -> int:
    """运行所有测试。"""
    tests = [
        test_workbench_page_route,
        test_workbench_api_endpoint,
        test_navigation_menu_entry,
        test_template_exists,
        test_read_only_constraint,
        test_empty_state_hint,
        test_jump_links,
        test_refresh_functionality,
        test_workbench_ops_validation,
        test_permission_three_table_consistency,
        test_agent_module_signatures,
    ]

    failures = 0
    for test in tests:
        try:
            test()
        except Exception as e:
            failures += 1
            print(f'FAIL {test.__name__}: {type(e).__name__}: {e}')
            import traceback
            traceback.print_exc()

    print(f'\n=== AI-SALES-F02 Sales Followup Workbench Verification Summary ===')
    print(f'total={len(tests)} passed={len(tests) - failures} failed={failures}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())

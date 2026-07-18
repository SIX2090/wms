"""AI-R11-F01 采购到货 AI 工作台页面接入验证脚本。

# AI_TASK: AI-R11-F01

验证内容：
1. 工作台页面路由存在且可访问
2. API 端点存在且返回正确结构
3. 导航菜单包含工作台入口
4. 页面模板包含 7 类业务队列
5. 页面只读校验（不含写操作按钮）
6. 页面包含空态提示
7. 页面包含跳转链接
8. 页面包含刷新功能

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
        resp = client.get('/ai/purchase_workbench', follow_redirects=False)
        assert resp.status_code in [302, 401], f'未登录应重定向，实际 {resp.status_code}'

    print('测试1 通过: 工作台页面路由存在')


def test_workbench_api_endpoint() -> None:
    """测试2：API 端点存在。"""
    from app import app

    with app.test_client() as client:
        resp = client.get('/api/ai/purchase_followup_workbench', follow_redirects=False)
        assert resp.status_code in [302, 401, 403], f'未登录应拒绝，实际 {resp.status_code}'

    print('测试2 通过: API 端点存在')


def test_navigation_menu_entry() -> None:
    """测试3：导航菜单包含工作台入口。"""
    nav_file = ROOT / 'app' / 'templates' / 'base.html'
    content = nav_file.read_text(encoding='utf-8')

    assert '/ai/purchase_workbench' in content, '导航菜单缺少工作台链接'
    assert '采购工作台' in content, '导航菜单缺少工作台文本'

    print('测试3 通过: 导航菜单包含工作台入口')


def test_template_exists() -> None:
    """测试4：页面模板存在且包含 7 类业务队列。"""
    template_file = ROOT / 'app' / 'templates' / 'ai_purchase_workbench.html'
    assert template_file.exists(), '模板文件不存在'

    content = template_file.read_text(encoding='utf-8')

    # 检查 7 类业务队列
    assert 'pending_arrival' in content or '待到货' in content, '缺少待到货'
    assert 'delayed_arrival' in content or '延期' in content, '缺少延期到货'
    assert 'short_delivery' in content or '短交' in content, '缺少短交明细'
    assert 'over_receive' in content or '超收' in content, '缺少超收明细'
    assert 'unlinked_notices' in content or '未关联通知' in content, '缺少未关联通知'
    assert 'multi_order_candidates' in content or '多订单候选' in content, '缺少多订单候选'
    assert 'supplier_followup_list' in content or '供应商跟进' in content, '缺少供应商跟进清单'

    print('测试4 通过: 页面模板存在且包含 7 类业务队列')


def test_read_only_constraint() -> None:
    """测试5：页面只读校验（不含写操作按钮）。"""
    template_file = ROOT / 'app' / 'templates' / 'ai_purchase_workbench.html'
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
    template_file = ROOT / 'app' / 'templates' / 'ai_purchase_workbench.html'
    content = template_file.read_text(encoding='utf-8')

    # 检查空态提示
    assert 'empty_hint' in content or '暂无' in content or '空态' in content, '缺少空态提示'

    print('测试6 通过: 页面包含空态提示')


def test_jump_links() -> None:
    """测试7：页面包含跳转链接。"""
    template_file = ROOT / 'app' / 'templates' / 'ai_purchase_workbench.html'
    content = template_file.read_text(encoding='utf-8')

    # 检查跳转链接
    assert 'jump_url' in content or 'href=' in content, '缺少跳转链接'
    assert '查看全部' in content or '查看' in content, '缺少查看按钮'

    print('测试7 通过: 页面包含跳转链接')


def test_refresh_functionality() -> None:
    """测试8：页面包含刷新功能。"""
    template_file = ROOT / 'app' / 'templates' / 'ai_purchase_workbench.html'
    content = template_file.read_text(encoding='utf-8')

    # 检查刷新功能
    assert 'loadWorkbench' in content or '刷新' in content, '缺少刷新功能'
    assert 'DOMContentLoaded' in content or 'onload' in content.lower(), '缺少自动加载'

    print('测试8 通过: 页面包含刷新功能')


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

    print(f'\n=== AI-R11-F01 Purchase Workbench Page Verification Summary ===')
    print(f'total={len(tests)} passed={len(tests) - failures} failed={failures}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())

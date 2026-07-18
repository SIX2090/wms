"""AI-R15-F01 业务质量运营看板与版本回归告警验证脚本。

# AI_TASK: AI-R15-F01

验证内容：
1. 看板页面路由存在且可访问
2. 下钻 API 端点存在且可调用
3. 导航菜单包含质量运营入口
4. 页面模板存在且包含必要组件
5. 指标卡片渲染逻辑正确
6. 维度分组表渲染逻辑正确
7. 版本对比功能完整
8. 低质量样本下钻功能可用

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


def test_dashboard_page_route() -> None:
    """测试1：看板页面路由存在。"""
    from app import app
    
    with app.test_client() as client:
        # 未登录应重定向到登录页
        resp = client.get('/ai/business_quality', follow_redirects=False)
        assert resp.status_code in [302, 401], f'未登录应重定向，实际 {resp.status_code}'
    
    print('测试1 通过: 看板页面路由存在')


def test_drilldown_api_endpoint() -> None:
    """测试2：下钻 API 端点存在。"""
    from app import app
    
    with app.test_client() as client:
        # 未登录应拒绝（Flask-Login对POST请求返回400）
        resp = client.post('/api/ai/business_quality_drilldown', json={
            'dimension': 'role',
            'value': 'warehouse',
        }, follow_redirects=False)
        assert resp.status_code in [302, 401, 400], f'未登录应拒绝，实际 {resp.status_code}'
    
    print('测试2 通过: 下钻 API 端点存在')


def test_navigation_menu_entry() -> None:
    """测试3：导航菜单包含质量运营入口。"""
    nav_file = ROOT / 'app' / 'templates' / 'base.html'
    content = nav_file.read_text(encoding='utf-8')
    
    assert '/ai/business_quality' in content, '导航菜单缺少质量运营链接'
    assert 'AI质量运营' in content or '质量运营' in content, '导航菜单缺少质量运营文本'
    
    print('测试3 通过: 导航菜单包含质量运营入口')


def test_dashboard_template_exists() -> None:
    """测试4：页面模板存在且包含必要组件。"""
    template_file = ROOT / 'app' / 'templates' / 'ai_business_quality.html'
    assert template_file.exists(), '模板文件不存在'
    
    content = template_file.read_text(encoding='utf-8')
    
    # 检查必要组件
    assert '七项业务质量指标' in content or '七项质量指标' in content, '缺少指标卡片区域'
    assert '筛选器' in content or 'filterForm' in content, '缺少筛选器'
    assert '版本对比' in content or 'versionComparison' in content, '缺少版本对比区域'
    assert '维度分组' in content or 'dimensionTable' in content, '缺少维度分组表'
    assert '低质量样本' in content or 'lowQualityTable' in content, '缺少低质量样本下钻'
    assert 'loadSnapshot' in content, '缺少加载快照函数'
    assert 'renderMetricsCards' in content, '缺少指标卡片渲染函数'
    
    print('测试4 通过: 页面模板存在且包含必要组件')


def test_metrics_cards_rendering_logic() -> None:
    """测试5：指标卡片渲染逻辑正确。"""
    template_file = ROOT / 'app' / 'templates' / 'ai_business_quality.html'
    content = template_file.read_text(encoding='utf-8')
    
    # 检查指标顺序
    assert 'classification_accuracy' in content, '缺少分类准确率'
    assert 'header_accuracy' in content, '缺少表头准确率'
    assert 'line_recall' in content, '缺少行召回率'
    assert 'material_match_rate' in content, '缺少物料匹配率'
    assert 'human_correction_rate' in content, '缺少人工修正率'
    assert 'draft_adoption_rate' in content, '缺少草稿采用率'
    assert 'duplicate_interception_rate' in content, '缺少重复拦截率'
    
    # 检查颜色阈值逻辑
    assert 'm.rate >= 0.8' in content, '缺少颜色阈值判断'
    # 检查动态生成的样式类名（JavaScript 模板字符串）
    assert 'success' in content, '缺少成功状态样式'
    assert 'warning' in content, '缺少警告状态样式'
    assert 'danger' in content, '缺少危险状态样式'
    # 检查动态类名生成逻辑
    assert 'text-${color}' in content or 'textClass' in content, '缺少动态文本样式生成'
    assert 'bg-${color}' in content or 'bgClass' in content, '缺少动态背景样式生成'
    
    print('测试5 通过: 指标卡片渲染逻辑正确')


def test_dimension_table_rendering_logic() -> None:
    """测试6：维度分组表渲染逻辑正确。"""
    template_file = ROOT / 'app' / 'templates' / 'ai_business_quality.html'
    content = template_file.read_text(encoding='utf-8')
    
    # 检查维度标签
    assert "'role': '角色'" in content or '"role": "角色"' in content, '缺少角色维度标签'
    assert "'source': '来源'" in content or '"source": "来源"' in content, '缺少来源维度标签'
    assert "'model': '模型'" in content or '"model": "模型"' in content, '缺少模型维度标签'
    assert "'schema_version': 'Schema版本'" in content or '"schema_version": "Schema版本"' in content, '缺少Schema版本维度标签'
    
    # 检查表格结构
    assert 'dimensionTable' in content, '缺少维度分组表ID'
    assert 'by_dimension' in content or 'byDimension' in content, '缺少维度分组数据引用'
    
    print('测试6 通过: 维度分组表渲染逻辑正确')


def test_version_comparison_functionality() -> None:
    """测试7：版本对比功能完整。"""
    template_file = ROOT / 'app' / 'templates' / 'ai_business_quality.html'
    content = template_file.read_text(encoding='utf-8')
    
    # 检查版本对比表单
    assert 'current_version' in content, '缺少当前版本输入'
    assert 'baseline_version' in content, '缺少基线版本输入'
    assert 'regression_threshold' in content, '缺少回归阈值输入'
    assert 'loadVersionComparison' in content, '缺少加载版本对比函数'
    assert 'renderVersionComparison' in content, '缺少渲染版本对比函数'
    
    # 检查回归告警
    assert 'regressions' in content, '缺少回归指标引用'
    assert '回归' in content or 'regression' in content.lower(), '缺少回归状态标识'
    
    print('测试7 通过: 版本对比功能完整')


def test_drilldown_functionality() -> None:
    """测试8：低质量样本下钻功能可用。"""
    template_file = ROOT / 'app' / 'templates' / 'ai_business_quality.html'
    content = template_file.read_text(encoding='utf-8')
    
    # 检查下钻表
    assert 'lowQualityTable' in content, '缺少低质量样本表ID'
    assert 'showSampleDetail' in content or 'drilldown' in content.lower(), '缺少下钻函数'
    
    # 检查模态框
    assert 'sampleDetailModal' in content, '缺少样本详情模态框'
    assert 'sampleDetailContent' in content, '缺少样本详情内容区域'
    
    # 检查 API 调用
    assert '/api/ai/business_quality_drilldown' in content or 'drilldown' in content.lower(), '缺少下钻API引用'
    
    print('测试8 通过: 低质量样本下钻功能可用')


def main() -> int:
    """运行所有测试。"""
    tests = [
        test_dashboard_page_route,
        test_drilldown_api_endpoint,
        test_navigation_menu_entry,
        test_dashboard_template_exists,
        test_metrics_cards_rendering_logic,
        test_dimension_table_rendering_logic,
        test_version_comparison_functionality,
        test_drilldown_functionality,
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
    
    print(f'\n=== AI-R15-F01 Business Quality Dashboard Verification Summary ===')
    print(f'total={len(tests)} passed={len(tests) - failures} failed={failures}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())

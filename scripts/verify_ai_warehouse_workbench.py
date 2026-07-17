"""AI-R10 仓库角色 AI 工作台整合验证脚本。

# AI_TASK: AI-R10

验收要点：
1. 数量与原业务列表一致。
2. 工作台只读或跳转对应流程，不在报表卡片中直接提交或审核。

测试覆盖（8 项）：
1. 工作台含 7 个 section（今日待收/待出/待盘/异常库存/文档待确认/失败任务/未完成草稿）
2. 各 section count 与原业务列表一致（validate_count_consistency）
3. read_only 恒为 True（不在卡片中提交或审核）
4. jump_url 不含写动作（submit/audit/delete/void/complete）
5. query 回调异常降级为 (0, []) 不中断工作台构建
6. total_pending_count 汇总正确（异常库存单独计）
7. 空数据时 empty_hint 展示正确
8. items 前 N 条详情结构正确（id/title/subtitle/detail/jump_url/extra）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
sys.path.insert(0, str(APP_DIR))

os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault('WMS_SKIP_STARTUP_DB_UPGRADE', '1')
os.environ.setdefault('SECRET_KEY', 'verify-ai-warehouse-workbench-secret')

from ai.ops.warehouse_workbench import (
    WarehouseWorkbenchSnapshot,
    WorkbenchItem,
    WorkbenchSection,
    build_warehouse_workbench,
    validate_count_consistency,
    validate_workbench_read_only,
)


def _make_query_fn(count: int, items: list[dict] = None):
    """构造 mock query 回调，返回 (count, items)。"""
    def _fn():
        return count, items or []
    return _fn


def _make_sample_items(n: int, prefix: str = 'item') -> list[dict]:
    """构造 n 个示例 item dict。"""
    return [
        {
            'id': i + 1,
            'title': f'{prefix}-{i+1}',
            'subtitle': f'副标题{i+1}',
            'detail': f'详情{i+1}',
            'jump_url': f'/{prefix}/view/{i+1}',
            'extra': {'severity': 'medium', 'created_at': '2026-07-17T00:00:00'},
        }
        for i in range(n)
    ]


def test_workbench_has_seven_sections() -> bool:
    """测试1：工作台含 7 个 section。"""
    snapshot = build_warehouse_workbench(
        query_today_inbound_pending=_make_query_fn(5, _make_sample_items(5, 'in_order')),
        query_today_outbound_pending=_make_query_fn(3, _make_sample_items(3, 'out_order')),
        query_inventory_check_pending=_make_query_fn(2, _make_sample_items(2, 'inv_check')),
        query_abnormal_stock=_make_query_fn(4, _make_sample_items(4, 'material')),
        query_documents_pending_confirmation=_make_query_fn(1, _make_sample_items(1, 'doc')),
        query_failed_tasks=_make_query_fn(2, _make_sample_items(2, 'task')),
        query_unfinished_drafts=_make_query_fn(3, _make_sample_items(3, 'draft')),
    )
    if len(snapshot.sections) != 7:
        print(f'FAIL 测试1：期望 7 个 section，实际 {len(snapshot.sections)} 个')
        return False
    expected_keys = {
        'today_inbound_pending', 'today_outbound_pending', 'inventory_check_pending',
        'abnormal_stock', 'documents_pending_confirmation', 'failed_tasks',
        'unfinished_drafts',
    }
    actual_keys = {s.key for s in snapshot.sections}
    if actual_keys != expected_keys:
        print(f'FAIL 测试1：section key 不匹配，缺失 {expected_keys - actual_keys}，多余 {actual_keys - expected_keys}')
        return False
    print(f'PASS 测试1：工作台含 7 个 section（{", ".join(s.key for s in snapshot.sections)}）')
    return True


def test_count_consistency() -> bool:
    """测试2：各 section count 与原业务列表一致。"""
    expected = {
        'today_inbound_pending': 5,
        'today_outbound_pending': 3,
        'inventory_check_pending': 2,
        'abnormal_stock': 4,
        'documents_pending_confirmation': 1,
        'failed_tasks': 2,
        'unfinished_drafts': 3,
    }
    snapshot = build_warehouse_workbench(
        query_today_inbound_pending=_make_query_fn(5),
        query_today_outbound_pending=_make_query_fn(3),
        query_inventory_check_pending=_make_query_fn(2),
        query_abnormal_stock=_make_query_fn(4),
        query_documents_pending_confirmation=_make_query_fn(1),
        query_failed_tasks=_make_query_fn(2),
        query_unfinished_drafts=_make_query_fn(3),
    )
    is_valid, mismatches = validate_count_consistency(snapshot, expected_counts=expected)
    if not is_valid:
        print(f'FAIL 测试2：count 不一致：{mismatches}')
        return False
    print(f'PASS 测试2：7 个 section count 与原业务列表一致')
    return True


def test_count_consistency_mismatch_detected() -> bool:
    """测试3：count 不一致时能被检测到。"""
    expected = {
        'today_inbound_pending': 5,
        'today_outbound_pending': 3,
    }
    snapshot = build_warehouse_workbench(
        query_today_inbound_pending=_make_query_fn(10),  # 实际 10，期望 5
        query_today_outbound_pending=_make_query_fn(3),
    )
    is_valid, mismatches = validate_count_consistency(snapshot, expected_counts=expected)
    if is_valid:
        print('FAIL 测试3：count 不一致但未检测到')
        return False
    if not any('today_inbound_pending' in m for m in mismatches):
        print(f'FAIL 测试3：未报告 today_inbound_pending 不一致：{mismatches}')
        return False
    print(f'PASS 测试3：count 不一致被检测到（{mismatches[0]}）')
    return True


def test_read_only_always_true() -> bool:
    """测试4：read_only 恒为 True（不在卡片中提交或审核）。"""
    snapshot = build_warehouse_workbench(
        query_today_inbound_pending=_make_query_fn(1, _make_sample_items(1)),
        query_today_outbound_pending=_make_query_fn(1, _make_sample_items(1)),
        query_inventory_check_pending=_make_query_fn(1, _make_sample_items(1)),
        query_abnormal_stock=_make_query_fn(1, _make_sample_items(1)),
        query_documents_pending_confirmation=_make_query_fn(1, _make_sample_items(1)),
        query_failed_tasks=_make_query_fn(1, _make_sample_items(1)),
        query_unfinished_drafts=_make_query_fn(1, _make_sample_items(1)),
    )
    for s in snapshot.sections:
        if not s.read_only:
            print(f'FAIL 测试4：section {s.key} read_only=False（应为 True）')
            return False
    is_valid, violations = validate_workbench_read_only(snapshot)
    if not is_valid:
        print(f'FAIL 测试4：read_only 校验失败：{violations}')
        return False
    print('PASS 测试4：7 个 section read_only 恒为 True')
    return True


def test_jump_url_no_write_actions() -> bool:
    """测试5：jump_url 不含写动作（submit/audit/delete/void/complete）。"""
    # 构造含写动作的 item，应被检测到
    bad_items = [
        {'id': 1, 'title': 't', 'subtitle': 's', 'detail': 'd',
         'jump_url': '/in_order/submit/1', 'extra': {}},
    ]
    snapshot = build_warehouse_workbench(
        query_today_inbound_pending=_make_query_fn(1, bad_items),
    )
    is_valid, violations = validate_workbench_read_only(snapshot)
    if is_valid:
        print('FAIL 测试5：含 submit 写动作的 jump_url 未被检测到')
        return False
    if not any('submit' in v for v in violations):
        print(f'FAIL 测试5：未报告 submit 写动作：{violations}')
        return False
    # 正常的只读 jump_url 不应报错
    good_items = [
        {'id': 1, 'title': 't', 'subtitle': 's', 'detail': 'd',
         'jump_url': '/in_order/view/1', 'extra': {}},
    ]
    snapshot2 = build_warehouse_workbench(
        query_today_inbound_pending=_make_query_fn(1, good_items),
    )
    is_valid2, violations2 = validate_workbench_read_only(snapshot2)
    if not is_valid2:
        print(f'FAIL 测试5：只读 jump_url 被误报：{violations2}')
        return False
    print('PASS 测试5：写动作 jump_url 被检测，只读 jump_url 通过')
    return True


def test_query_exception_degradation() -> bool:
    """测试6：query 回调异常降级为 (0, []) 不中断工作台构建。"""
    def bad_query():
        raise RuntimeError('DB 连接失败')
    snapshot = build_warehouse_workbench(
        query_today_inbound_pending=bad_query,
        query_today_outbound_pending=None,  # None 也应降级
        query_inventory_check_pending=_make_query_fn(2),
    )
    # 异常和 None 的 section count 应为 0
    inbound = next(s for s in snapshot.sections if s.key == 'today_inbound_pending')
    outbound = next(s for s in snapshot.sections if s.key == 'today_outbound_pending')
    inv_check = next(s for s in snapshot.sections if s.key == 'inventory_check_pending')
    if inbound.count != 0 or len(inbound.items) != 0:
        print(f'FAIL 测试6：异常 query 应降级为 (0, [])，实际 count={inbound.count} items={len(inbound.items)}')
        return False
    if outbound.count != 0:
        print(f'FAIL 测试6：None query 应降级为 0，实际 count={outbound.count}')
        return False
    if inv_check.count != 2:
        print(f'FAIL 测试6：正常 query count 应为 2，实际 {inv_check.count}')
        return False
    print('PASS 测试6：query 异常降级为 (0, []) 不中断工作台构建')
    return True


def test_total_pending_count_excludes_abnormal_stock() -> bool:
    """测试7：total_pending_count 汇总正确（异常库存单独计）。"""
    snapshot = build_warehouse_workbench(
        query_today_inbound_pending=_make_query_fn(5),
        query_today_outbound_pending=_make_query_fn(3),
        query_inventory_check_pending=_make_query_fn(2),
        query_abnormal_stock=_make_query_fn(4),
        query_documents_pending_confirmation=_make_query_fn(1),
        query_failed_tasks=_make_query_fn(2),
        query_unfinished_drafts=_make_query_fn(3),
    )
    # total_pending = 5+3+2+1+2+3 = 16（异常库存 4 不计入）
    if snapshot.total_pending_count != 16:
        print(f'FAIL 测试7：total_pending_count 应为 16，实际 {snapshot.total_pending_count}')
        return False
    if snapshot.abnormal_stock_count != 4:
        print(f'FAIL 测试7：abnormal_stock_count 应为 4，实际 {snapshot.abnormal_stock_count}')
        return False
    print(f'PASS 测试7：total_pending_count={snapshot.total_pending_count}（异常库存 {snapshot.abnormal_stock_count} 单独计）')
    return True


def test_empty_hint_and_items_structure() -> bool:
    """测试8：空数据时 empty_hint 展示正确 + items 前 N 条详情结构正确。"""
    # 全空数据
    snapshot = build_warehouse_workbench()
    for s in snapshot.sections:
        if s.count != 0:
            print(f'FAIL 测试8：空数据 section {s.key} count 应为 0，实际 {s.count}')
            return False
        if not s.empty_hint:
            print(f'FAIL 测试8：section {s.key} empty_hint 为空')
            return False
        if len(s.items) != 0:
            print(f'FAIL 测试8：空数据 section {s.key} items 应为空，实际 {len(s.items)} 条')
            return False
    # 有数据时 items 结构正确
    items_data = _make_sample_items(5, 'in_order')
    snapshot2 = build_warehouse_workbench(
        query_today_inbound_pending=_make_query_fn(5, items_data),
    )
    section = next(s for s in snapshot2.sections if s.key == 'today_inbound_pending')
    if len(section.items) != 5:
        print(f'FAIL 测试8：items 应为 5 条，实际 {len(section.items)}')
        return False
    item = section.items[0]
    required = {'id', 'title', 'subtitle', 'detail', 'jump_url', 'extra'}
    missing = required - set(item.to_dict().keys())
    if missing:
        print(f'FAIL 测试8：item 缺字段 {missing}')
        return False
    if item.id != 1 or item.title != 'in_order-1' or item.jump_url != '/in_order/view/1':
        print(f'FAIL 测试8：item 字段值不正确 id={item.id} title={item.title} url={item.jump_url}')
        return False
    if item.extra.get('severity') != 'medium':
        print(f'FAIL 测试8：item.extra.severity 应为 medium，实际 {item.extra.get("severity")}')
        return False
    print(f'PASS 测试8：空数据 empty_hint 正确 + 有数据 items 结构正确（6 字段）')
    return True


def main() -> int:
    tests = [
        test_workbench_has_seven_sections,
        test_count_consistency,
        test_count_consistency_mismatch_detected,
        test_read_only_always_true,
        test_jump_url_no_write_actions,
        test_query_exception_degradation,
        test_total_pending_count_excludes_abnormal_stock,
        test_empty_hint_and_items_structure,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as exc:
            print(f'FAIL {test.__name__} 异常: {exc}')
            failed += 1
    print(f'\n=== AI-R10 仓库角色工作台整合: {passed} PASS / {failed} FAIL ===')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

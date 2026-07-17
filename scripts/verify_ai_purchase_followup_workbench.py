"""AI-R11 采购到货跟进 AI 工作台整合验证脚本。

# AI_TASK: AI-R11

验收要点：
1. 指标口径和时间范围明确。
2. 对外沟通和业务提交必须人工确认。

测试覆盖（8 项）：
1. 工作台含 7 个 section（待到/延期/短交/超收/未关联通知/多订单候选/供应商跟进清单）
2. 各 section count 与原业务列表一致（validate_count_consistency）
3. read_only 恒为 True（不在卡片中提交或审核）
4. jump_url 不含写动作（send/submit/audit/delete/void/complete）
5. 供应商跟进 needs_manual_confirmation 恒为 True（对外沟通必须人工确认）
6. 指标口径和时间范围明确（validate_metric_scope_clear）
7. total_attention_count 汇总正确（供应商跟进清单不计入避免重复）
8. query 回调异常降级为 (0, []) 不中断工作台构建
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
os.environ.setdefault('SECRET_KEY', 'verify-ai-purchase-followup-workbench-secret')

from ai.ops.purchase_followup_workbench import (
    PurchaseFollowupSnapshot,
    build_purchase_followup_workbench,
    validate_count_consistency,
    validate_followup_read_only,
    validate_metric_scope_clear,
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
            'subtitle': f'供应商{i+1}',
            'detail': f'详情{i+1}',
            'jump_url': f'/{prefix}/view/{i+1}',
            'metric_scope': f'指标口径{i+1}',
            'extra': {'status': 'pending'},
        }
        for i in range(n)
    ]


def _make_supplier_followup(n: int) -> list[dict]:
    """构造 n 个供应商跟进清单 dict。"""
    return [
        {
            'supplier_id': i + 1,
            'supplier_name': f'供应商{i+1}',
            'pending_count': i + 1,
            'delayed_count': 1 if i % 2 == 0 else 0,
            'short_delivery_count': 1 if i % 3 == 0 else 0,
            'followup_suggestion': f'建议催交供应商{i+1}',
            'needs_manual_confirmation': True,
            'jump_url': f'/purchase_order/list?supplier_id={i+1}',
        }
        for i in range(n)
    ]


def test_workbench_has_seven_sections() -> bool:
    """测试1：工作台含 7 个 section。"""
    snapshot = build_purchase_followup_workbench(
        query_pending_arrival=_make_query_fn(5, _make_sample_items(5, 'po')),
        query_delayed_arrival=_make_query_fn(3, _make_sample_items(3, 'po')),
        query_short_delivery=_make_query_fn(2, _make_sample_items(2, 'item')),
        query_over_receive=_make_query_fn(1, _make_sample_items(1, 'item')),
        query_unlinked_notices=_make_query_fn(4, _make_sample_items(4, 'notice')),
        query_multi_order_candidates=_make_query_fn(2, _make_sample_items(2, 'doc')),
        query_supplier_followup_list=lambda: _make_supplier_followup(3),
    )
    if len(snapshot.sections) != 7:
        print(f'FAIL 测试1：期望 7 个 section，实际 {len(snapshot.sections)} 个')
        return False
    expected_keys = {
        'pending_arrival', 'delayed_arrival', 'short_delivery', 'over_receive',
        'unlinked_notices', 'multi_order_candidates', 'supplier_followup_list',
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
        'pending_arrival': 5,
        'delayed_arrival': 3,
        'short_delivery': 2,
        'over_receive': 1,
        'unlinked_notices': 4,
        'multi_order_candidates': 2,
        'supplier_followup_list': 3,
    }
    snapshot = build_purchase_followup_workbench(
        query_pending_arrival=_make_query_fn(5),
        query_delayed_arrival=_make_query_fn(3),
        query_short_delivery=_make_query_fn(2),
        query_over_receive=_make_query_fn(1),
        query_unlinked_notices=_make_query_fn(4),
        query_multi_order_candidates=_make_query_fn(2),
        query_supplier_followup_list=lambda: _make_supplier_followup(3),
    )
    is_valid, mismatches = validate_count_consistency(snapshot, expected_counts=expected)
    if not is_valid:
        print(f'FAIL 测试2：count 不一致：{mismatches}')
        return False
    print(f'PASS 测试2：7 个 section count 与原业务列表一致')
    return True


def test_count_consistency_mismatch_detected() -> bool:
    """测试3：count 不一致时能被检测到。"""
    expected = {'pending_arrival': 5, 'delayed_arrival': 3}
    snapshot = build_purchase_followup_workbench(
        query_pending_arrival=_make_query_fn(10),  # 实际 10，期望 5
        query_delayed_arrival=_make_query_fn(3),
    )
    is_valid, mismatches = validate_count_consistency(snapshot, expected_counts=expected)
    if is_valid:
        print('FAIL 测试3：count 不一致但未检测到')
        return False
    if not any('pending_arrival' in m for m in mismatches):
        print(f'FAIL 测试3：未报告 pending_arrival 不一致：{mismatches}')
        return False
    print(f'PASS 测试3：count 不一致被检测到（{mismatches[0]}）')
    return True


def test_read_only_always_true() -> bool:
    """测试4：read_only 恒为 True（不在卡片中提交或审核）。"""
    snapshot = build_purchase_followup_workbench(
        query_pending_arrival=_make_query_fn(1, _make_sample_items(1)),
        query_delayed_arrival=_make_query_fn(1, _make_sample_items(1)),
        query_short_delivery=_make_query_fn(1, _make_sample_items(1)),
        query_over_receive=_make_query_fn(1, _make_sample_items(1)),
        query_unlinked_notices=_make_query_fn(1, _make_sample_items(1)),
        query_multi_order_candidates=_make_query_fn(1, _make_sample_items(1)),
        query_supplier_followup_list=lambda: _make_supplier_followup(1),
    )
    for s in snapshot.sections:
        if not s.read_only:
            print(f'FAIL 测试4：section {s.key} read_only=False（应为 True）')
            return False
    is_valid, violations = validate_followup_read_only(snapshot)
    if not is_valid:
        print(f'FAIL 测试4：read_only 校验失败：{violations}')
        return False
    print('PASS 测试4：7 个 section read_only 恒为 True')
    return True


def test_jump_url_no_write_actions() -> bool:
    """测试5：jump_url 不含写动作（send/submit/audit/delete/void/complete）。"""
    # 构造含写动作的 item，应被检测到
    bad_items = [
        {'id': 1, 'title': 't', 'subtitle': 's', 'detail': 'd',
         'jump_url': '/purchase_order/send_followup/1', 'metric_scope': 'm', 'extra': {}},
    ]
    snapshot = build_purchase_followup_workbench(
        query_pending_arrival=_make_query_fn(1, bad_items),
        query_supplier_followup_list=lambda: _make_supplier_followup(1),
    )
    is_valid, violations = validate_followup_read_only(snapshot)
    if is_valid:
        print('FAIL 测试5：含 send 写动作的 jump_url 未被检测到')
        return False
    if not any('send' in v for v in violations):
        print(f'FAIL 测试5：未报告 send 写动作：{violations}')
        return False
    # 正常的只读 jump_url 不应报错
    good_items = [
        {'id': 1, 'title': 't', 'subtitle': 's', 'detail': 'd',
         'jump_url': '/purchase_order/view/1', 'metric_scope': 'm', 'extra': {}},
    ]
    snapshot2 = build_purchase_followup_workbench(
        query_pending_arrival=_make_query_fn(1, good_items),
        query_supplier_followup_list=lambda: _make_supplier_followup(1),
    )
    is_valid2, violations2 = validate_followup_read_only(snapshot2)
    if not is_valid2:
        print(f'FAIL 测试5：只读 jump_url 被误报：{violations2}')
        return False
    print('PASS 测试5：写动作 jump_url 被检测，只读 jump_url 通过')
    return True


def test_supplier_followup_needs_manual_confirmation() -> bool:
    """测试6：供应商跟进 needs_manual_confirmation 恒为 True（对外沟通必须人工确认）。"""
    # 构造 needs_manual_confirmation=False 的供应商，应被检测到
    bad_supplier = [{
        'supplier_id': 1, 'supplier_name': '坏供应商',
        'pending_count': 1, 'delayed_count': 0, 'short_delivery_count': 0,
        'followup_suggestion': '建议', 'needs_manual_confirmation': False,  # 破坏
        'jump_url': '/purchase_order/list',
    }]
    snapshot = build_purchase_followup_workbench(
        query_supplier_followup_list=lambda: bad_supplier,
    )
    is_valid, violations = validate_followup_read_only(snapshot)
    if is_valid:
        print('FAIL 测试6：needs_manual_confirmation=False 未被检测到')
        return False
    if not any('needs_manual_confirmation' in v for v in violations):
        print(f'FAIL 测试6：未报告 needs_manual_confirmation 违规：{violations}')
        return False
    # 正常的 needs_manual_confirmation=True 应通过
    good_supplier = _make_supplier_followup(1)
    snapshot2 = build_purchase_followup_workbench(
        query_supplier_followup_list=lambda: good_supplier,
    )
    is_valid2, violations2 = validate_followup_read_only(snapshot2)
    if not is_valid2:
        print(f'FAIL 测试6：正常供应商被误报：{violations2}')
        return False
    print('PASS 测试6：供应商 needs_manual_confirmation 恒 True（对外沟通必须人工确认）')
    return True


def test_metric_scope_clear() -> bool:
    """测试7：指标口径和时间范围明确（validate_metric_scope_clear）。"""
    snapshot = build_purchase_followup_workbench(
        query_pending_arrival=_make_query_fn(1, _make_sample_items(1)),
        query_delayed_arrival=_make_query_fn(1, _make_sample_items(1)),
        query_short_delivery=_make_query_fn(1, _make_sample_items(1)),
        query_over_receive=_make_query_fn(1, _make_sample_items(1)),
        query_unlinked_notices=_make_query_fn(1, _make_sample_items(1)),
        query_multi_order_candidates=_make_query_fn(1, _make_sample_items(1)),
        query_supplier_followup_list=lambda: _make_supplier_followup(1),
    )
    is_valid, violations = validate_metric_scope_clear(snapshot)
    if not is_valid:
        print(f'FAIL 测试7：指标口径/时间范围不明确：{violations}')
        return False
    # 检查每个 section 都有 metric_scope 和 time_range
    for s in snapshot.sections:
        if not s.metric_scope:
            print(f'FAIL 测试7：section {s.key} metric_scope 为空')
            return False
        if not s.time_range:
            print(f'FAIL 测试7：section {s.key} time_range 为空')
            return False
    print('PASS 测试7：7 个 section 指标口径和时间范围明确')
    return True


def test_total_attention_excludes_supplier_followup() -> bool:
    """测试8：total_attention_count 汇总正确（供应商跟进清单不计入避免重复）+ query 异常降级。"""
    snapshot = build_purchase_followup_workbench(
        query_pending_arrival=_make_query_fn(5),
        query_delayed_arrival=_make_query_fn(3),
        query_short_delivery=_make_query_fn(2),
        query_over_receive=_make_query_fn(1),
        query_unlinked_notices=_make_query_fn(4),
        query_multi_order_candidates=_make_query_fn(2),
        query_supplier_followup_list=lambda: _make_supplier_followup(10),  # 10 个供应商
    )
    # total_attention = 5+3+2+1+4+2 = 17（供应商跟进 10 不计入避免重复）
    if snapshot.total_attention_count != 17:
        print(f'FAIL 测试8：total_attention_count 应为 17，实际 {snapshot.total_attention_count}')
        return False
    if len(snapshot.supplier_followup_list) != 10:
        print(f'FAIL 测试8：supplier_followup_list 应为 10，实际 {len(snapshot.supplier_followup_list)}')
        return False
    # query 异常降级测试
    def bad_query():
        raise RuntimeError('DB 连接失败')
    snapshot2 = build_purchase_followup_workbench(
        query_pending_arrival=bad_query,
        query_delayed_arrival=None,
        query_short_delivery=_make_query_fn(2),
    )
    pending = next(s for s in snapshot2.sections if s.key == 'pending_arrival')
    delayed = next(s for s in snapshot2.sections if s.key == 'delayed_arrival')
    short = next(s for s in snapshot2.sections if s.key == 'short_delivery')
    if pending.count != 0 or delayed.count != 0:
        print(f'FAIL 测试8：异常/None query 应降级为 0，pending={pending.count} delayed={delayed.count}')
        return False
    if short.count != 2:
        print(f'FAIL 测试8：正常 query count 应为 2，实际 {short.count}')
        return False
    print(f'PASS 测试8：total_attention={snapshot.total_attention_count}（供应商 10 不计入）+ 异常降级正常')
    return True


def main() -> int:
    tests = [
        test_workbench_has_seven_sections,
        test_count_consistency,
        test_count_consistency_mismatch_detected,
        test_read_only_always_true,
        test_jump_url_no_write_actions,
        test_supplier_followup_needs_manual_confirmation,
        test_metric_scope_clear,
        test_total_attention_excludes_supplier_followup,
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
    print(f'\n=== AI-R11 采购到货跟进工作台整合: {passed} PASS / {failed} FAIL ===')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

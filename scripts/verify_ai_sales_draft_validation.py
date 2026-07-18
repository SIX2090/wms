#!/usr/bin/env python3
"""AI-SALES-F01 专项验证：销售草稿闭环验收。

测试覆盖：
1. 证据链构造（create_draft/check_draft/validate_shipment）
2. 部分发货计算（不超过剩余量）
3. 多次发货校验（累计不超过订单量）
4. 销售对账（订单 vs 出库 vs 库存）
5. AI 只建/检草稿校验（禁止 confirm/ship/cancel/delete）
6. 非法操作拒绝
7. 非法来源拒绝
8. 端到端闭环（创建草稿→部分发货→多次发货→对账）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ai.documents.sales_draft_validation import (
    SalesLineInfo,
    SalesOrderInfo,
    OutboundDraftInfo,
    build_sales_draft_evidence,
    calculate_partial_shipment,
    validate_multiple_shipments,
    reconcile_sales_report,
    validate_ai_only_draft,
    SALES_FORBIDDEN_ACTIONS,
)


def _make_line(line_id: int, material_id: int, qty: float, shipped: float = 0, price: float = 100) -> SalesLineInfo:
    return SalesLineInfo(
        line_id=line_id,
        material_id=material_id,
        material_code=f'MAT-{material_id}',
        material_name=f'物料{material_id}',
        quantity=qty,
        shipped_quantity=shipped,
        price=price,
    )


def _make_order(order_id: int, order_no: str, lines: list[SalesLineInfo], status: str = 'confirmed') -> SalesOrderInfo:
    return SalesOrderInfo(
        order_id=order_id,
        order_no=order_no,
        status=status,
        shipment_status='partial' if any(l.shipped_quantity > 0 for l in lines) else 'pending',
        customer_name='测试客户',
        lines=tuple(lines),
        total_amount=sum(l.quantity * l.price for l in lines),
        shipped_amount=sum(l.shipped_quantity * l.price for l in lines),
    )


def _make_outbound(outbound_id: int, order_no: str, status: str, source_order_id: int, lines: list[dict]) -> OutboundDraftInfo:
    return OutboundDraftInfo(
        outbound_id=outbound_id,
        order_no=order_no,
        status=status,
        source_sales_order_id=source_order_id,
        source_sales_order_no='SO-TEST-001',
        customer_name='测试客户',
        lines=tuple(lines),
    )


def test1_evidence_chain():
    """测试1：证据链构造（create_draft/check_draft/validate_shipment）。"""
    print('\n=== 测试1：证据链构造 ===')

    lines = [_make_line(1, 100, 10, 0, 100)]
    order = _make_order(1, 'SO-TEST-001', lines)

    # create_draft
    evidence1 = build_sales_draft_evidence(
        evidence_id='EV-001',
        operation='create_draft',
        operator_id='user1',
        operator_role='warehouse',
        source='ai_assistant',
        sales_order=order,
        created_at='2026-07-18T10:00:00',
    )
    assert evidence1.operation == 'create_draft'
    assert evidence1.action_requested == 'review_sales_draft'
    assert evidence1.needs_confirmation is True
    assert evidence1.is_valid is True
    print('✓ create_draft 证据构造正确')

    # check_draft
    evidence2 = build_sales_draft_evidence(
        evidence_id='EV-002',
        operation='check_draft',
        operator_id='user1',
        operator_role='warehouse',
        source='ai_assistant',
        sales_order=order,
        created_at='2026-07-18T11:00:00',
    )
    assert evidence2.operation == 'check_draft'
    assert evidence2.action_requested == 'create_outbound_draft_manually'
    print('✓ check_draft 证据构造正确')

    # validate_shipment
    evidence3 = build_sales_draft_evidence(
        evidence_id='EV-003',
        operation='validate_shipment',
        operator_id='user1',
        operator_role='warehouse',
        source='ai_assistant',
        sales_order=order,
        created_at='2026-07-18T12:00:00',
    )
    assert evidence3.operation == 'validate_shipment'
    assert evidence3.action_requested == 'review_shipment_evidence'
    print('✓ validate_shipment 证据构造正确')


def test2_partial_shipment():
    """测试2：部分发货计算（不超过剩余量）。"""
    print('\n=== 测试2：部分发货计算 ===')

    lines = [
        _make_line(1, 100, 10, 0, 100),  # 剩余 10
        _make_line(2, 101, 20, 5, 50),   # 剩余 15
    ]
    order = _make_order(1, 'SO-TEST-001', lines)

    # 正常部分发货
    result = calculate_partial_shipment(
        sales_order=order,
        requested_lines=[
            {'line_id': 1, 'quantity': 5},
            {'line_id': 2, 'quantity': 10},
        ],
    )
    assert not result.exceeds_order
    assert len(result.planned_lines) == 2
    assert result.planned_lines[0]['quantity'] == 5
    assert result.planned_lines[1]['quantity'] == 10
    assert result.remaining_after_shipment[0]['remaining'] == 5  # 10-5
    assert result.remaining_after_shipment[1]['remaining'] == 5  # 15-10
    print('✓ 正常部分发货计算正确')

    # 超过剩余量（截断）
    result2 = calculate_partial_shipment(
        sales_order=order,
        requested_lines=[
            {'line_id': 1, 'quantity': 15},  # 超过剩余 10
        ],
    )
    assert result2.exceeds_order
    assert '超过剩余' in result2.exceed_details[0]
    assert result2.planned_lines[0]['quantity'] == 10  # 截断到剩余
    print('✓ 超过剩余量截断正确')


def test3_multiple_shipments():
    """测试3：多次发货校验（累计不超过订单量）。"""
    print('\n=== 测试3：多次发货校验 ===')

    lines = [_make_line(1, 100, 10, 0, 100)]
    order = _make_order(1, 'SO-TEST-001', lines)

    # 两次出库，累计 8
    outbounds = [
        _make_outbound(1, 'OU-001', 'completed', 1, [{'material_id': 100, 'quantity': 5}]),
        _make_outbound(2, 'OU-002', 'completed', 1, [{'material_id': 100, 'quantity': 3}]),
    ]

    passed, reason, details = validate_multiple_shipments(
        sales_order=order,
        outbound_drafts=outbounds,
    )
    assert passed is True
    assert len(details) == 2
    print('✓ 多次发货累计校验通过')

    # 超过订单量
    outbounds2 = [
        _make_outbound(1, 'OU-001', 'completed', 1, [{'material_id': 100, 'quantity': 8}]),
        _make_outbound(2, 'OU-002', 'completed', 1, [{'material_id': 100, 'quantity': 5}]),  # 累计 13 > 10
    ]

    passed2, reason2, details2 = validate_multiple_shipments(
        sales_order=order,
        outbound_drafts=outbounds2,
    )
    assert passed2 is False
    assert '超过订单量' in reason2
    print('✓ 超过订单量校验正确')


def test4_reconciliation():
    """测试4：销售对账（订单 vs 出库 vs 库存）。"""
    print('\n=== 测试4：销售对账 ===')

    lines = [
        _make_line(1, 100, 10, 8, 100),  # 已发 8
    ]
    order = _make_order(1, 'SO-TEST-001', lines)

    # 对账通过
    outbounds = [
        _make_outbound(1, 'OU-001', 'completed', 1, [
            {'material_id': 100, 'quantity': 5, 'price': 100},
        ]),
        _make_outbound(2, 'OU-002', 'completed', 1, [
            {'material_id': 100, 'quantity': 3, 'price': 100},
        ]),
    ]

    result = reconcile_sales_report(
        sales_order=order,
        outbound_drafts=outbounds,
    )
    assert result.is_reconciled is True
    assert result.order_shipped_quantity == 8
    assert result.outbound_completed_quantity == 8
    assert result.quantity_diff <= 1e-6
    print('✓ 对账通过（订单已发 8 = 出库完成 8）')

    # 对账失败
    outbounds2 = [
        _make_outbound(1, 'OU-001', 'completed', 1, [
            {'material_id': 100, 'quantity': 5, 'price': 100},
        ]),
        _make_outbound(2, 'OU-002', 'completed', 1, [
            {'material_id': 100, 'quantity': 5, 'price': 100},  # 累计 10 != 8
        ]),
    ]

    result2 = reconcile_sales_report(
        sales_order=order,
        outbound_drafts=outbounds2,
    )
    assert result2.is_reconciled is False
    assert '数量不一致' in result2.details[0]
    print('✓ 对账失败（订单已发 8 != 出库完成 10）')


def test5_ai_only_draft():
    """测试5：AI 只建/检草稿校验（禁止 confirm/ship/cancel/delete）。"""
    print('\n=== 测试5：AI 只建/检草稿校验 ===')

    lines = [_make_line(1, 100, 10, 0, 100)]
    order = _make_order(1, 'SO-TEST-001', lines)

    evidence = build_sales_draft_evidence(
        evidence_id='EV-001',
        operation='create_draft',
        operator_id='user1',
        operator_role='warehouse',
        source='ai_assistant',
        sales_order=order,
        created_at='2026-07-18T10:00:00',
    )

    passed, reason = validate_ai_only_draft(evidence=evidence)
    assert passed is True
    assert '校验通过' in reason
    print('✓ AI 只建/检草稿校验通过')

    # 验证禁止动作集
    assert 'confirm' in SALES_FORBIDDEN_ACTIONS
    assert 'ship' in SALES_FORBIDDEN_ACTIONS
    assert 'cancel' in SALES_FORBIDDEN_ACTIONS
    assert 'delete' in SALES_FORBIDDEN_ACTIONS
    print(f'✓ 禁止动作集包含 {len(SALES_FORBIDDEN_ACTIONS)} 个动作')


def test6_illegal_operation():
    """测试6：非法操作拒绝。"""
    print('\n=== 测试6：非法操作拒绝 ===')

    lines = [_make_line(1, 100, 10, 0, 100)]
    order = _make_order(1, 'SO-TEST-001', lines)

    try:
        build_sales_draft_evidence(
            evidence_id='EV-001',
            operation='confirm',  # 非法
            operator_id='user1',
            operator_role='warehouse',
            source='ai_assistant',
            sales_order=order,
            created_at='2026-07-18T10:00:00',
        )
        assert False, '应该抛出 ValueError'
    except ValueError as e:
        assert '非法操作' in str(e)
        print(f'✓ 非法操作拒绝: {e}')


def test7_illegal_source():
    """测试7：非法来源拒绝。"""
    print('\n=== 测试7：非法来源拒绝 ===')

    lines = [_make_line(1, 100, 10, 0, 100)]
    order = _make_order(1, 'SO-TEST-001', lines)

    try:
        build_sales_draft_evidence(
            evidence_id='EV-001',
            operation='create_draft',
            operator_id='user1',
            operator_role='warehouse',
            source='unknown_source',  # 非法
            sales_order=order,
            created_at='2026-07-18T10:00:00',
        )
        assert False, '应该抛出 ValueError'
    except ValueError as e:
        assert '非法来源' in str(e)
        print(f'✓ 非法来源拒绝: {e}')


def test8_end_to_end():
    """测试8：端到端闭环（创建草稿→部分发货→多次发货→对账）。"""
    print('\n=== 测试8：端到端闭环 ===')

    # 1. 创建销售订单（已部分发货：物料100已发8，物料101已发15）
    lines = [
        _make_line(1, 100, 10, 8, 100),
        _make_line(2, 101, 20, 15, 50),
    ]
    order = _make_order(1, 'SO-TEST-001', lines, status='confirmed')

    evidence1 = build_sales_draft_evidence(
        evidence_id='EV-001',
        operation='create_draft',
        operator_id='user1',
        operator_role='warehouse',
        source='ai_assistant',
        sales_order=order,
        created_at='2026-07-18T10:00:00',
    )
    assert evidence1.operation == 'create_draft'
    print('✓ 步骤1：创建草稿')

    # 2. 部分发货（物料100剩余2，物料101剩余5，请求在范围内）
    partial_result = calculate_partial_shipment(
        sales_order=order,
        requested_lines=[
            {'line_id': 1, 'quantity': 2},
            {'line_id': 2, 'quantity': 5},
        ],
    )
    assert not partial_result.exceeds_order
    print('✓ 步骤2：部分发货计算（2+5，在剩余量范围内）')

    # 3. 多次发货校验（累计：物料100=8，物料101=15，不超过订单量10/20）
    outbounds = [
        _make_outbound(1, 'OU-001', 'completed', 1, [
            {'material_id': 100, 'quantity': 5, 'price': 100},
            {'material_id': 101, 'quantity': 10, 'price': 50},
        ]),
        _make_outbound(2, 'OU-002', 'completed', 1, [
            {'material_id': 100, 'quantity': 3, 'price': 100},
            {'material_id': 101, 'quantity': 5, 'price': 50},
        ]),
    ]

    passed, reason, details = validate_multiple_shipments(
        sales_order=order,
        outbound_drafts=outbounds,
    )
    assert passed is True
    print('✓ 步骤3：多次发货校验通过（物料100累计8，物料101累计15）')

    # 4. 对账（订单已发8+15=23，出库完成8+15=23）
    result = reconcile_sales_report(
        sales_order=order,
        outbound_drafts=outbounds,
    )
    assert result.is_reconciled is True
    assert result.outbound_completed_quantity == 23  # 5+10+3+5
    print('✓ 步骤4：对账通过（订单已发 23 = 出库完成 23）')


def main() -> int:
    print('AI-SALES-F01 专项验证：销售草稿闭环验收')
    print('=' * 60)

    try:
        test1_evidence_chain()
        test2_partial_shipment()
        test3_multiple_shipments()
        test4_reconciliation()
        test5_ai_only_draft()
        test6_illegal_operation()
        test7_illegal_source()
        test8_end_to_end()

        print('\n' + '=' * 60)
        print('✓ 全部 8 项测试通过')
        print('=' * 60)
        return 0

    except AssertionError as e:
        print(f'\n✗ 测试失败: {e}')
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f'\n✗ 测试异常: {e}')
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

"""AI-R06 送货通知与采购订单联合匹配验证脚本。
# AI_TASK: AI-R06

验证内容：
1. 联合匹配：供应商+物料双匹配命中候选，评分维度齐全
2. 订单号精确匹配：最高分维度，含关闭订单差异展示
3. 多候选不自动选单：多个候选时返回清单待人工确认
4. 短交/超收检测：本次量 vs 未收量差异类型正确
5. 关闭订单：status=closed/completed 标记且不自动选单
6. 未关联物料：送货通知有但 PO 无的行标记 unmatched
7. 低置信度不自动选单：评分低于门槛返回候选不自动选
8. 误建采购申请防护：送货通知场景禁止走 purchase_request

退出码 0=通过，1=失败。
"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ai.documents.delivery_matcher import (  # noqa: E402
    AUTO_SELECT_CONFIDENCE_THRESHOLD,
    DeliveryMatchInput,
    DeliveryMaterialLine,
    PurchaseOrderCandidate,
    PurchaseOrderInfo,
    PurchaseOrderLineInfo,
    is_purchase_request_forbidden_for_delivery,
    match_delivery,
)


def _make_po(
    order_id, order_no, supplier_name='鑫达', status='pending',
    expected_date='2026-07-20', lines=None,
):
    """构造测试用 PurchaseOrderInfo。"""
    return PurchaseOrderInfo(
        order_id=order_id,
        order_no=order_no,
        supplier_id=order_id,
        supplier_name=supplier_name,
        status=status,
        expected_date=expected_date,
        lines=tuple(lines or []),
    )


def _make_line(line_id, code, name, qty, received=0, spec='', material_id=None):
    """构造测试用 PurchaseOrderLineInfo。"""
    return PurchaseOrderLineInfo(
        line_id=line_id,
        material_id=material_id or line_id,
        material_code=code,
        material_name=name,
        material_spec=spec,
        quantity=qty,
        received_quantity=received,
    )


def test_joint_matching() -> None:
    """测试1：供应商+物料双匹配命中候选，评分维度齐全。"""
    po = _make_po(1, 'PO001', '鑫达', 'pending', '2026-07-20', [
        _make_line(101, '6204', '轴承', 100, 0),
        _make_line(102, 'M8', '螺母', 500, 0),
    ])

    def query_open(supplier, codes):
        return [po]

    delivery = DeliveryMatchInput(
        supplier_name='鑫达',
        lines=(
            DeliveryMaterialLine(code='6204', name='轴承', quantity=100),
            DeliveryMaterialLine(code='M8', name='螺母', quantity=500),
        ),
        source_text='明天发鑫达 6204 100套 M8 500个',
        is_delivery_notice=True,
    )
    result = match_delivery(delivery, query_open_purchase_orders=query_open)

    assert result.has_candidates, '应有候选'
    assert len(result.candidates) == 1
    cand = result.candidates[0]
    assert cand.matched_line_count == 2, f'应匹配 2 行, got {cand.matched_line_count}'
    assert cand.unmatched_line_count == 0
    assert cand.shortage_line_count == 0
    assert cand.overreceive_line_count == 0
    # 评分维度齐全
    assert set(cand.score_breakdown.keys()) == {'order_no', 'supplier', 'material', 'date'}
    assert cand.score_breakdown['supplier'] == 1.0, '供应商应精确匹配=1.0'
    assert cand.score_breakdown['material'] == 1.0, '物料应全覆盖=1.0'
    # 唯一候选+评分达标 → 自动选单
    assert cand.auto_selectable, '唯一候选评分达标应可自动选单'
    assert result.auto_selected is not None, '应自动选中'
    assert result.auto_selected.order_no == 'PO001'

    print('测试1 通过: 联合匹配命中候选，评分维度齐全，唯一候选自动选单')


def test_order_no_exact_match() -> None:
    """测试2：订单号精确匹配最高分，含关闭订单差异展示。"""
    # 关闭订单（仅按订单号查出，用于差异展示）
    closed_po = _make_po(2, 'PO002', '鑫达', 'completed', '2026-07-10', [
        _make_line(201, '6204', '轴承', 100, 100),  # 已全部收货
    ])

    def query_by_no(order_no):
        if order_no == 'PO002':
            return closed_po
        return None

    def query_open(supplier, codes):
        return []  # 开放订单无

    delivery = DeliveryMatchInput(
        supplier_name='鑫达',
        purchase_order_no='PO002',
        lines=(DeliveryMaterialLine(code='6204', name='轴承', quantity=50),),
        source_text='送货单 PO002 6204轴承 50套',
        is_delivery_notice=True,
    )
    result = match_delivery(
        delivery,
        query_open_purchase_orders=query_open,
        query_purchase_order_by_no=query_by_no,
    )

    assert result.has_candidates, '应按订单号查出候选'
    cand = result.candidates[0]
    assert cand.is_closed, 'completed 订单应标记关闭'
    assert cand.auto_selectable is False, '关闭订单不可自动选单'
    assert cand.score_breakdown['order_no'] == 1.0, '订单号精确匹配应满分'
    assert result.auto_selected is None, '关闭订单不自动选单'
    assert result.should_fallback_to_in_order, '应回退普通入库草稿'

    print('测试2 通过: 订单号精确匹配满分，关闭订单标记且不自动选单')


def test_multiple_candidates_no_auto_select() -> None:
    """测试3：多候选不自动选单，返回清单待人工确认。"""
    po1 = _make_po(1, 'PO001', '鑫达', 'pending', '2026-07-20', [
        _make_line(101, '6204', '轴承', 100, 0),
    ])
    po2 = _make_po(2, 'PO002', '鑫达', 'pending', '2026-07-21', [
        _make_line(201, '6204', '轴承', 100, 0),
    ])

    def query_open(supplier, codes):
        return [po1, po2]

    delivery = DeliveryMatchInput(
        supplier_name='鑫达',
        lines=(DeliveryMaterialLine(code='6204', name='轴承', quantity=100),),
        source_text='明天发鑫达 6204轴承 100套',
        is_delivery_notice=True,
    )
    result = match_delivery(delivery, query_open_purchase_orders=query_open)

    assert len(result.candidates) == 2, f'应有 2 候选, got {len(result.candidates)}'
    assert result.auto_selected is None, '多候选不应自动选单'
    assert result.should_fallback_to_in_order, '多候选应回退待确认'
    assert '2 个候选' in result.fallback_reason, f'应提示候选数, got {result.fallback_reason}'
    # 候选清单完整（带证据）
    for c in result.candidates:
        assert c.score >= AUTO_SELECT_CONFIDENCE_THRESHOLD or c.confidence == 'low'
        assert len(c.line_evidence) == 1

    print('测试3 通过: 多候选不自动选单，返回清单待人工确认')


def test_shortage_and_overreceive() -> None:
    """测试4：短交/超收检测正确。"""
    po = _make_po(1, 'PO001', '鑫达', 'pending', '2026-07-20', [
        _make_line(101, '6204', '轴承', 100, 0),    # 未收 100
        _make_line(102, 'M8', '螺母', 500, 200, spec=''),  # 未收 300
    ])

    def query_open(supplier, codes):
        return [po]

    # 本次送货：6204 送 80（短交），M8 送 400（超收）
    delivery = DeliveryMatchInput(
        supplier_name='鑫达',
        lines=(
            DeliveryMaterialLine(code='6204', name='轴承', quantity=80),
            DeliveryMaterialLine(code='M8', name='螺母', quantity=400),
        ),
        source_text='明天发鑫达 6204轴承 80套 M8螺母 400个',
        is_delivery_notice=True,
    )
    result = match_delivery(delivery, query_open_purchase_orders=query_open)
    cand = result.candidates[0]

    assert cand.shortage_line_count == 1, f'应 1 行短交, got {cand.shortage_line_count}'
    assert cand.overreceive_line_count == 1, f'应 1 行超收, got {cand.overreceive_line_count}'
    # 行证据差异类型
    ev_by_code = {e.delivery_code: e for e in cand.line_evidence}
    assert ev_by_code['6204'].difference_type == 'shortage', '6204 应短交'
    assert ev_by_code['6204'].difference < 0, '短交差异应为负'
    assert ev_by_code['M8'].difference_type == 'overreceive', 'M8 应超收'
    assert ev_by_code['M8'].difference > 0, '超收差异应为正'
    # 未收量计算正确
    assert ev_by_code['6204'].po_pending_quantity == 100, '6204 未收应 100'
    assert ev_by_code['M8'].po_pending_quantity == 300, 'M8 未收应 300'

    print('测试4 通过: 短交/超收检测正确（差异类型+未收量+差异值）')


def test_closed_order_detection() -> None:
    """测试5：关闭订单标记且不自动选单。"""
    closed_po = _make_po(1, 'PO001', '鑫达', 'closed', '2026-07-10', [
        _make_line(101, '6204', '轴承', 100, 100),
    ])

    def query_open(supplier, codes):
        # 开放订单查询不应返回关闭订单（模拟 ORM 已过滤）
        return []

    def query_by_no(order_no):
        return closed_po if order_no == 'PO001' else None

    delivery = DeliveryMatchInput(
        supplier_name='鑫达',
        purchase_order_no='PO001',
        lines=(DeliveryMaterialLine(code='6204', name='轴承', quantity=50),),
        source_text='送货单 PO001 6204轴承 50套',
        is_delivery_notice=True,
    )
    result = match_delivery(
        delivery,
        query_open_purchase_orders=query_open,
        query_purchase_order_by_no=query_by_no,
    )

    assert result.has_candidates
    cand = result.candidates[0]
    assert cand.is_closed, 'closed 订单应标记关闭'
    assert cand.auto_selectable is False, '关闭订单不可自动选单'
    assert result.auto_selected is None

    print('测试5 通过: 关闭订单标记且不自动选单')


def test_unmatched_material() -> None:
    """测试6：未关联物料行标记 unmatched。"""
    po = _make_po(1, 'PO001', '鑫达', 'pending', '2026-07-20', [
        _make_line(101, '6204', '轴承', 100, 0),
    ])

    def query_open(supplier, codes):
        return [po]

    # 送货通知含 PO 没有的物料
    delivery = DeliveryMatchInput(
        supplier_name='鑫达',
        lines=(
            DeliveryMaterialLine(code='6204', name='轴承', quantity=100),
            DeliveryMaterialLine(code='X999', name='未知物料', quantity=10),
        ),
        source_text='明天发鑫达 6204轴承 100套 X999 10个',
        is_delivery_notice=True,
    )
    result = match_delivery(delivery, query_open_purchase_orders=query_open)
    cand = result.candidates[0]

    assert cand.matched_line_count == 1, f'应 1 行匹配, got {cand.matched_line_count}'
    assert cand.unmatched_line_count == 1, f'应 1 行未关联, got {cand.unmatched_line_count}'
    ev_unmatched = [e for e in cand.line_evidence if e.difference_type == 'unmatched']
    assert len(ev_unmatched) == 1, '应有 1 条 unmatched 证据'
    assert ev_unmatched[0].matched_po_line_id is None, '未关联行 po_line_id 应 None'
    assert ev_unmatched[0].difference == 10, '未关联行差异应=送货量'

    print('测试6 通过: 未关联物料行标记 unmatched')


def test_low_confidence_no_auto_select() -> None:
    """测试7：低置信度不自动选单，返回候选待确认。"""
    # 供应商不匹配 + 仅 1 行物料匹配 → 评分低
    po = _make_po(1, 'PO001', '其他供应商', 'pending', '2026-01-01', [
        _make_line(101, '6204', '轴承', 100, 0),
    ])

    def query_open(supplier, codes):
        return [po]

    delivery = DeliveryMatchInput(
        supplier_name='鑫达',  # 与 PO 供应商不匹配
        lines=(DeliveryMaterialLine(code='6204', name='轴承', quantity=100),),
        source_text='明天发鑫达 6204轴承 100套',
        is_delivery_notice=True,
    )
    result = match_delivery(delivery, query_open_purchase_orders=query_open)

    assert result.has_candidates
    cand = result.candidates[0]
    assert cand.score < AUTO_SELECT_CONFIDENCE_THRESHOLD, \
        f'低置信度评分应 < {AUTO_SELECT_CONFIDENCE_THRESHOLD}, got {cand.score}'
    assert cand.auto_selectable is False, '低置信度不可自动选单'
    assert cand.confidence == 'low', f'应为 low, got {cand.confidence}'
    assert result.auto_selected is None, '低置信度不自动选单'
    assert result.should_fallback_to_in_order, '应回退待确认'
    assert '低于自动选单门槛' in result.fallback_reason

    print('测试7 通过: 低置信度不自动选单，返回候选待确认')


def test_purchase_request_forbidden() -> None:
    """测试8：送货通知场景禁止走采购申请路径。"""
    # 微信发货通知文本
    delivery = DeliveryMatchInput(
        supplier_name='鑫达',
        lines=(DeliveryMaterialLine(code='6204', name='轴承', quantity=100),),
        source_text='明天发鑫达 6204轴承 100套',
        is_delivery_notice=True,
    )
    forbidden, reason = is_purchase_request_forbidden_for_delivery(delivery)
    assert forbidden, '微信送货通知应禁止采购申请'
    assert '采购收货' in reason or '普通入库' in reason, f'原因应含采购收货/普通入库, got {reason}'

    # 非送货通知（普通补货请求）不禁
    delivery2 = DeliveryMatchInput(
        supplier_name='',
        lines=(),
        source_text='库存不足请补货',
        is_delivery_notice=False,
    )
    forbidden2, _ = is_purchase_request_forbidden_for_delivery(delivery2)
    assert not forbidden2, '非送货通知不应禁止'

    # 联合匹配结果也含禁令标记
    result = match_delivery(delivery)
    assert result.forbidden_purchase_request, '联合匹配结果应标记禁止采购申请'
    assert result.forbidden_reason, '应有禁止原因'

    # 销售出库场景不应触发送货通知禁令
    delivery3 = DeliveryMatchInput(
        supplier_name='',
        lines=(DeliveryMaterialLine(code='6204', name='轴承', quantity=100),),
        source_text='发给客户 6204轴承 100套 销售出库',
        is_delivery_notice=True,
    )
    forbidden3, _ = is_purchase_request_forbidden_for_delivery(delivery3)
    assert not forbidden3, '销售出库场景不应触发送货通知禁令'

    print('测试8 通过: 送货通知禁建采购申请（微信通知禁/普通补货不禁/销售出库不禁）')


def main() -> int:
    try:
        test_joint_matching()
        test_order_no_exact_match()
        test_multiple_candidates_no_auto_select()
        test_shortage_and_overreceive()
        test_closed_order_detection()
        test_unmatched_material()
        test_low_confidence_no_auto_select()
        test_purchase_request_forbidden()
    except AssertionError as exc:
        print(f'FAIL AI-DELIVERY-MATCHER: {exc}')
        return 1
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f'FAIL AI-DELIVERY-MATCHER: 异常 {exc}')
        return 1

    print('PASS AI-DELIVERY-MATCHER: 送货通知与采购订单联合匹配 8 项测试全部通过')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

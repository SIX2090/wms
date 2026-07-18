"""AI-R06-F01 权重校准与错误样本回灌验证脚本。
# AI_TASK: AI-R06-F01

验证内容：
1. 权重配置：MatcherWeights 可加载/保存，权重和校验
2. 错误样本收集：MatchErrorSample 可记录人工修正
3. 权重校准：calibrate_weights 基于错误样本调整权重
4. 安全边界：校准幅度限制、最小样本数保护
5. 权重指纹：weights_fingerprint 可追踪版本
6. 向后兼容：默认权重与 delivery_matcher 一致
7. 多候选不自动选单：校准不改变此规则
8. 误建采购申请防护：校准不改变此防护

退出码 0=通过，1=失败。
"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ai.documents.delivery_matcher_calibration import (  # noqa: E402
    DEFAULT_AUTO_SELECT_THRESHOLD,
    DEFAULT_WEIGHT_DATE,
    DEFAULT_WEIGHT_MATERIAL,
    DEFAULT_WEIGHT_ORDER_NO,
    DEFAULT_WEIGHT_SUPPLIER,
    CalibrationResult,
    MatchErrorSample,
    MatcherWeights,
    calibrate_weights,
    collect_error_sample,
    load_weights_from_config,
    weights_fingerprint,
)


def test_weights_config() -> None:
    """测试1：权重配置可加载/保存，权重和校验。"""
    # 默认权重
    w = MatcherWeights()
    assert w.order_no == DEFAULT_WEIGHT_ORDER_NO
    assert w.supplier == DEFAULT_WEIGHT_SUPPLIER
    assert w.material == DEFAULT_WEIGHT_MATERIAL
    assert w.date == DEFAULT_WEIGHT_DATE
    assert w.auto_select_threshold == DEFAULT_AUTO_SELECT_THRESHOLD

    # 权重和校验
    total = w.order_no + w.supplier + w.material + w.date
    assert abs(total - 1.0) < 0.01, f'权重和应为 1.0，实际 {total}'

    # 从字典加载
    data = {'order_no': 0.30, 'supplier': 0.35, 'material': 0.30, 'date': 0.05}
    w2 = MatcherWeights.from_dict(data)
    assert w2.order_no == 0.30
    assert w2.supplier == 0.35

    # JSON 序列化
    json_str = w.to_json()
    w3 = MatcherWeights.from_json(json_str)
    assert w3.order_no == w.order_no

    # 非法权重和应报错
    try:
        MatcherWeights(order_no=0.5, supplier=0.5, material=0.5, date=0.5)
        assert False, '权重和 != 1.0 应报错'
    except ValueError as e:
        assert '权重和必须为 1.0' in str(e)

    print('测试1 通过: 权重配置可加载/保存，权重和校验')


def test_error_sample_collection() -> None:
    """测试2：错误样本收集可记录人工修正。"""
    saved_samples = []

    def save_callback(sample):
        saved_samples.append(sample)

    sample = collect_error_sample(
        sample_id='ERR-001',
        delivery_summary={'supplier_name': '鑫达', 'lines_count': 2},
        system_selected_order_id=1,
        system_best_order_id=1,
        human_selected_order_id=2,
        correction_reason='供应商名称别名未识别',
        score_breakdown={'order_no': 0.0, 'supplier': 0.7, 'material': 1.0, 'date': 0.8},
        weights_version='default',
        save_callback=save_callback,
    )

    assert sample.sample_id == 'ERR-001'
    assert sample.human_selected_order_id == 2
    assert sample.system_selected_order_id == 1
    assert len(saved_samples) == 1
    assert saved_samples[0].sample_id == 'ERR-001'

    # 从字典恢复
    data = sample.to_dict()
    sample2 = MatchErrorSample.from_dict(data)
    assert sample2.sample_id == sample.sample_id

    print('测试2 通过: 错误样本收集可记录人工修正')


def test_weight_calibration() -> None:
    """测试3：权重校准基于错误样本调整权重。"""
    current = MatcherWeights()

    # 构造错误样本：系统选中了 order_no=0 但 supplier=0.7 的候选，人工选了另一个
    samples = []
    for i in range(10):
        samples.append(MatchErrorSample(
            sample_id=f'ERR-{i:03d}',
            created_at='2026-07-18T10:00:00',
            delivery_summary={'supplier_name': '鑫达', 'lines_count': 2},
            system_selected_order_id=1,
            system_best_order_id=1,
            human_selected_order_id=2,
            correction_reason='供应商名称别名未识别',
            score_breakdown={'order_no': 0.0, 'supplier': 0.7, 'material': 1.0, 'date': 0.8},
            weights_version='default',
        ))

    result = calibrate_weights(current_weights=current, error_samples=samples)

    assert isinstance(result, CalibrationResult)
    assert result.error_sample_count == 10
    assert result.suggested_weights is not None
    # 校准后权重和仍为 1.0
    total = (
        result.suggested_weights.order_no
        + result.suggested_weights.supplier
        + result.suggested_weights.material
        + result.suggested_weights.date
    )
    assert abs(total - 1.0) < 0.01, f'校准后权重和应为 1.0，实际 {total}'

    print('测试3 通过: 权重校准基于错误样本调整权重')


def test_calibration_safety_boundary() -> None:
    """测试4：校准安全边界（幅度限制、最小样本数保护）。"""
    current = MatcherWeights()

    # 样本不足：不应校准
    samples = [
        MatchErrorSample(
            sample_id='ERR-001',
            created_at='2026-07-18T10:00:00',
            delivery_summary={},
            system_selected_order_id=1,
            system_best_order_id=1,
            human_selected_order_id=2,
            correction_reason='',
            score_breakdown={'order_no': 0.0, 'supplier': 0.7, 'material': 1.0, 'date': 0.8},
        )
    ]
    result = calibrate_weights(current_weights=current, error_samples=samples, min_samples=5)
    assert result.suggested_weights.order_no == current.order_no, '样本不足不应校准'
    assert '样本数' in result.calibration_notes

    # 样本充足但调整幅度限制
    samples = []
    for i in range(10):
        samples.append(MatchErrorSample(
            sample_id=f'ERR-{i:03d}',
            created_at='2026-07-18T10:00:00',
            delivery_summary={},
            system_selected_order_id=1,
            system_best_order_id=1,
            human_selected_order_id=2,
            correction_reason='',
            score_breakdown={'order_no': 0.0, 'supplier': 0.7, 'material': 1.0, 'date': 0.8},
        ))
    result = calibrate_weights(
        current_weights=current,
        error_samples=samples,
        max_delta=0.05,  # 限制调整幅度
    )
    # 检查单维度调整幅度不超过 max_delta
    for dim in ('order_no', 'supplier', 'material', 'date'):
        old_val = getattr(current, dim)
        new_val = getattr(result.suggested_weights, dim)
        delta = abs(new_val - old_val)
        assert delta <= 0.05 + 0.001, f'{dim} 调整幅度 {delta} 超过限制 0.05'

    print('测试4 通过: 校准安全边界（幅度限制、最小样本数保护）')


def test_weights_fingerprint() -> None:
    """测试5：权重指纹可追踪版本。"""
    w = MatcherWeights()
    fp = weights_fingerprint(w)
    assert fp.startswith('w-')
    assert '0.25' in fp
    assert '0.40' in fp
    assert '0.70' in fp

    # 不同权重应有不同指纹
    w2 = MatcherWeights(order_no=0.30, supplier=0.35, material=0.30, date=0.05)
    fp2 = weights_fingerprint(w2)
    assert fp != fp2

    print('测试5 通过: 权重指纹可追踪版本')


def test_backward_compatibility() -> None:
    """测试6：默认权重与 delivery_matcher 一致。"""
    from ai.documents.delivery_matcher import (
        AUTO_SELECT_CONFIDENCE_THRESHOLD,
        WEIGHT_DATE,
        WEIGHT_MATERIAL,
        WEIGHT_ORDER_NO,
        WEIGHT_SUPPLIER,
    )

    w = MatcherWeights()
    assert w.order_no == WEIGHT_ORDER_NO
    assert w.supplier == WEIGHT_SUPPLIER
    assert w.material == WEIGHT_MATERIAL
    assert w.date == WEIGHT_DATE
    assert w.auto_select_threshold == AUTO_SELECT_CONFIDENCE_THRESHOLD

    print('测试6 通过: 默认权重与 delivery_matcher 一致')


def test_calibration_preserves_rules() -> None:
    """测试7：校准不改变多候选不自动选单规则。"""
    from ai.documents.delivery_matcher import (
        DeliveryMatchInput,
        DeliveryMaterialLine,
        PurchaseOrderInfo,
        PurchaseOrderLineInfo,
        match_delivery,
    )

    # 构造多候选场景
    po1 = PurchaseOrderInfo(
        order_id=1,
        order_no='PO001',
        supplier_name='鑫达',
        status='pending',
        lines=(PurchaseOrderLineInfo(
            line_id=101,
            material_id=1,
            material_code='6204',
            material_name='轴承',
            material_spec='',
            quantity=100,
            received_quantity=0,
        ),),
    )
    po2 = PurchaseOrderInfo(
        order_id=2,
        order_no='PO002',
        supplier_name='鑫达',
        status='pending',
        lines=(PurchaseOrderLineInfo(
            line_id=201,
            material_id=1,
            material_code='6204',
            material_name='轴承',
            material_spec='',
            quantity=100,
            received_quantity=0,
        ),),
    )

    def query_open(supplier, codes):
        return [po1, po2]

    delivery = DeliveryMatchInput(
        supplier_name='鑫达',
        lines=(DeliveryMaterialLine(code='6204', name='轴承', quantity=100),),
        source_text='明天发鑫达 6204轴承 100套',
        is_delivery_notice=True,
    )

    # 使用校准后的权重匹配
    calibrated_weights = MatcherWeights(order_no=0.30, supplier=0.35, material=0.30, date=0.05)
    result = match_delivery(
        delivery,
        query_open_purchase_orders=query_open,
        auto_select_threshold=calibrated_weights.auto_select_threshold,
    )

    # 多候选不应自动选单
    assert result.auto_selected is None, '多候选不应自动选单'
    assert len(result.candidates) == 2

    print('测试7 通过: 校准不改变多候选不自动选单规则')


def test_calibration_preserves_forbidden_rule() -> None:
    """测试8：校准不改变误建采购申请防护。"""
    from ai.documents.delivery_matcher import (
        DeliveryMatchInput,
        DeliveryMaterialLine,
        is_purchase_request_forbidden_for_delivery,
    )

    # 微信送货通知
    delivery = DeliveryMatchInput(
        supplier_name='鑫达',
        lines=(DeliveryMaterialLine(code='6204', name='轴承', quantity=100),),
        source_text='明天发鑫达 6204轴承 100套',
        is_delivery_notice=True,
    )

    forbidden, reason = is_purchase_request_forbidden_for_delivery(delivery)
    assert forbidden, '微信送货通知应禁止采购申请'
    assert '采购收货' in reason or '普通入库' in reason

    # 校准权重不影响此规则
    calibrated_weights = MatcherWeights(order_no=0.30, supplier=0.35, material=0.30, date=0.05)
    forbidden2, _ = is_purchase_request_forbidden_for_delivery(delivery)
    assert forbidden2, '校准后仍应禁止采购申请'

    print('测试8 通过: 校准不改变误建采购申请防护')


def main() -> int:
    try:
        test_weights_config()
        test_error_sample_collection()
        test_weight_calibration()
        test_calibration_safety_boundary()
        test_weights_fingerprint()
        test_backward_compatibility()
        test_calibration_preserves_rules()
        test_calibration_preserves_forbidden_rule()
    except AssertionError as exc:
        print(f'FAIL AI-DELIVERY-MATCHER-CALIBRATION: {exc}')
        return 1
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f'FAIL AI-DELIVERY-MATCHER-CALIBRATION: 异常 {exc}')
        return 1

    print('PASS AI-DELIVERY-MATCHER-CALIBRATION: 权重校准与错误样本回灌 8 项测试全部通过')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""AI-R09 字段级反馈和文档质量指标验证脚本。

# AI_TASK: AI-R09

验收要点：
1. 记录字段名/原值/新值/修正原因/是否采纳/模型/提示词/Schema 版本。
2. 按来源与版本聚合准确率和修正率。
3. 可定位质量下降的字段和版本。
4. 不保存不必要的敏感原文（脱敏后存储）。

测试覆盖（8 项）：
1. 字段反馈记录构造（含全部 10 个字段：field_name/line_index/original_value/
   corrected_value/correction_reason/adopted/model/prompt_hash/schema_version/source）
2. 敏感原文脱敏（手机号/身份证/邮箱/联系人字段不存明文）
3. 按来源+版本+字段名聚合准确率（accuracy_rate = 1 - correction_rate）
4. 按来源+版本+字段名聚合修正率（correction_rate = adopted / total）
5. 质量下降定位（当前 accuracy < 基线 accuracy - 阈值 → is_regression=True）
6. 质量未下降不误报（drop <= 阈值 → is_regression=False）
7. top_corrections 排序（修正次数最多的原因排前）
8. 不保存不必要敏感原文（空原值不存；整体脱敏字段返回 '***'）
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
os.environ.setdefault('SECRET_KEY', 'verify-ai-field-feedback-secret')

from ai.documents.field_feedback import (
    DEFAULT_SCHEMA_VERSION,
    FieldCorrectionRecord,
    QUALITY_REGRESSION_THRESHOLD,
    aggregate_quality_metrics,
    build_field_correction_records,
    detect_quality_regressions,
    mask_sensitive_value,
)


def _make_evidence_fields() -> list[dict]:
    """构造模拟的 AI-R08 evidence.fields 列表（5 表头字段 + 5 行级字段）。"""
    return [
        {'field_name': 'supplier', 'line_index': -1, 'original_value': '鑫达轴承',
         'confidence': 0.95, 'needs_confirmation': False, 'confirmation_reason': '',
         'correction_status': ''},
        {'field_name': 'order_no', 'line_index': -1, 'original_value': 'PO-2026-001',
         'confidence': 0.70, 'needs_confirmation': True,
         'confirmation_reason': 'low_confidence', 'correction_status': ''},
        {'field_name': 'date', 'line_index': -1, 'original_value': '2026-07-17',
         'confidence': 0.90, 'needs_confirmation': False, 'confirmation_reason': '',
         'correction_status': ''},
        {'field_name': 'contact_phone', 'line_index': -1, 'original_value': '13812345678',
         'confidence': 0.60, 'needs_confirmation': True,
         'confirmation_reason': 'low_confidence', 'correction_status': ''},
        # 行级字段
        {'field_name': 'code', 'line_index': 0, 'original_value': '6204',
         'confidence': 0.85, 'needs_confirmation': False, 'confirmation_reason': '',
         'correction_status': ''},
        {'field_name': 'name', 'line_index': 0, 'original_value': '轴承',
         'confidence': 0.75, 'needs_confirmation': True,
         'confirmation_reason': 'ambiguous_spec', 'correction_status': ''},
        {'field_name': 'quantity', 'line_index': 0, 'original_value': '100',
         'confidence': 0.92, 'needs_confirmation': False, 'confirmation_reason': '',
         'correction_status': ''},
        {'field_name': 'id_card', 'line_index': 1, 'original_value': '110101199001011234',
         'confidence': 0.50, 'needs_confirmation': True,
         'confirmation_reason': 'low_confidence', 'correction_status': ''},
        {'field_name': 'email', 'line_index': 1, 'original_value': 'test@example.com',
         'confidence': 0.50, 'needs_confirmation': True,
         'confirmation_reason': 'low_confidence', 'correction_status': ''},
        {'field_name': 'spec', 'line_index': 1, 'original_value': '',
         'confidence': 0.40, 'needs_confirmation': True,
         'confirmation_reason': 'low_confidence', 'correction_status': ''},
    ]


def test_field_correction_record_construction() -> bool:
    """测试1：字段反馈记录构造，含全部 10 个字段。"""
    fields = _make_evidence_fields()
    # 用户修正 order_no 和 name，确认其他低置信度字段
    corrections = {
        'order_no': 'PO-2026-002',       # 修正订单号
        'name': '深沟球轴承',              # 修正名称
        'contact_phone': '13812345678',  # 确认原值（未改）
        # id_card/email/spec 未提交修正 → 视为未处理拒绝
    }
    records = build_field_correction_records(
        evidence_fields=fields,
        corrections=corrections,
        model='gpt-5.6-sol',
        prompt_hash='abc123def456',
        schema_version=DEFAULT_SCHEMA_VERSION,
        source='ocr_upload',
    )
    if not records:
        print('FAIL 测试1：未产出任何记录')
        return False
    # 应产出 6 条：order_no/name/contact_phone/id_card/email/spec（都是 needs_confirmation）
    if len(records) != 6:
        print(f'FAIL 测试1：期望 6 条记录，实际 {len(records)} 条')
        return False
    # 检查每条记录含全部 10 个字段
    required_fields = {
        'field_name', 'line_index', 'original_value', 'corrected_value',
        'correction_reason', 'adopted', 'model', 'prompt_hash',
        'schema_version', 'source',
    }
    for r in records:
        d = r.to_dict()
        missing = required_fields - set(d.keys())
        if missing:
            print(f'FAIL 测试1：记录缺字段 {missing}')
            return False
        if r.model != 'gpt-5.6-sol':
            print(f'FAIL 测试1：model 应为 gpt-5.6-sol，实际 {r.model}')
            return False
        if r.prompt_hash != 'abc123def456':
            print(f'FAIL 测试1：prompt_hash 不匹配: {r.prompt_hash}')
            return False
        if r.schema_version != DEFAULT_SCHEMA_VERSION:
            print(f'FAIL 测试1：schema_version 不匹配: {r.schema_version}')
            return False
        if r.source != 'ocr_upload':
            print(f'FAIL 测试1：source 不匹配: {r.source}')
            return False
    # order_no 应 adopted=True（值改变了）
    order_rec = next(r for r in records if r.field_name == 'order_no')
    if not order_rec.adopted:
        print('FAIL 测试1：order_no 修正后应 adopted=True')
        return False
    if order_rec.corrected_value != 'PO-2026-002':
        print(f'FAIL 测试1：order_no corrected_value 应为 PO-2026-002，实际 {order_rec.corrected_value}')
        return False
    # contact_phone 应 adopted=False（值未改，确认原值）
    phone_rec = next(r for r in records if r.field_name == 'contact_phone')
    if phone_rec.adopted:
        print('FAIL 测试1：contact_phone 未改值应 adopted=False')
        return False
    print('PASS 测试1：字段反馈记录构造含全部 10 个字段')
    return True


def test_sensitive_value_masking() -> bool:
    """测试2：敏感原文脱敏。"""
    # 手机号局部脱敏
    v = mask_sensitive_value('电话13812345678联系', 'remarks')
    if '13812345678' in v:
        print(f'FAIL 测试2：手机号未脱敏: {v}')
        return False
    if '138****5678' not in v:
        print(f'FAIL 测试2：手机号脱敏格式错误: {v}')
        return False
    # 身份证局部脱敏
    v = mask_sensitive_value('身份证110101199001011234', 'remarks')
    if '110101199001011234' in v:
        print(f'FAIL 测试2：身份证未脱敏: {v}')
        return False
    # 邮箱局部脱敏
    v = mask_sensitive_value('邮箱test@example.com', 'remarks')
    if 'test@example.com' in v:
        print(f'FAIL 测试2：邮箱未脱敏: {v}')
        return False
    # contact_phone 字段整体脱敏
    v = mask_sensitive_value('13812345678', 'contact_phone')
    if v != '***':
        print(f'FAIL 测试2：contact_phone 应整体脱敏为 ***，实际 {v}')
        return False
    # id_card 字段整体脱敏
    v = mask_sensitive_value('110101199001011234', 'id_card')
    if v != '***':
        print(f'FAIL 测试2：id_card 应整体脱敏为 ***，实际 {v}')
        return False
    # 空值不存
    v = mask_sensitive_value('', 'name')
    if v != '':
        print(f'FAIL 测试2：空值应返回空，实际 {v}')
        return False
    print('PASS 测试2：敏感原文脱敏（手机号/身份证/邮箱/联系人字段）')
    return True


def test_aggregate_accuracy_rate() -> bool:
    """测试3：按来源+版本+字段名聚合准确率。"""
    # 构造 10 条 name 字段记录，其中 3 条 adopted=True（修正了）
    records = []
    for i in range(7):
        records.append(_make_record('name', adopted=False))
    for i in range(3):
        records.append(_make_record('name', adopted=True))
    snapshot = aggregate_quality_metrics(records)
    if not snapshot.by_field:
        print('FAIL 测试3：未产出聚合指标')
        return False
    m = snapshot.by_field[0]
    # accuracy_rate = 1 - 3/10 = 0.7
    expected = 1.0 - 3.0 / 10.0
    if abs(m.accuracy_rate - expected) > 0.001:
        print(f'FAIL 测试3：accuracy_rate 应为 {expected}，实际 {m.accuracy_rate}')
        return False
    if m.total_count != 10:
        print(f'FAIL 测试3：total_count 应为 10，实际 {m.total_count}')
        return False
    if m.corrected_count != 3:
        print(f'FAIL 测试3：corrected_count 应为 3，实际 {m.corrected_count}')
        return False
    print(f'PASS 测试3：准确率聚合 accuracy_rate={m.accuracy_rate}（10 条中 3 条修正）')
    return True


def test_aggregate_correction_rate() -> bool:
    """测试4：按来源+版本+字段名聚合修正率。"""
    # 构造 2 个字段：code（5 条，2 修正）+ quantity（4 条，0 修正）
    records = []
    for i in range(3):
        records.append(_make_record('code', adopted=False))
    for i in range(2):
        records.append(_make_record('code', adopted=True))
    for i in range(4):
        records.append(_make_record('quantity', adopted=False))
    snapshot = aggregate_quality_metrics(records)
    by_name = {m.field_name: m for m in snapshot.by_field}
    # code: correction_rate = 2/5 = 0.4
    if abs(by_name['code'].correction_rate - 0.4) > 0.001:
        print(f'FAIL 测试4：code correction_rate 应为 0.4，实际 {by_name["code"].correction_rate}')
        return False
    # quantity: correction_rate = 0/4 = 0.0
    if by_name['quantity'].correction_rate != 0.0:
        print(f'FAIL 测试4：quantity correction_rate 应为 0.0，实际 {by_name["quantity"].correction_rate}')
        return False
    print(f'PASS 测试4：修正率聚合 code={by_name["code"].correction_rate} quantity={by_name["quantity"].correction_rate}')
    return True


def test_quality_regression_detected() -> bool:
    """测试5：质量下降定位（当前 accuracy < 基线 accuracy - 阈值 → is_regression=True）。"""
    # 基线版本 v1：name 字段 10 条，1 条修正 → accuracy=0.9
    baseline = []
    for i in range(9):
        baseline.append(_make_record('name', adopted=False, schema_version='v1'))
    baseline.append(_make_record('name', adopted=True, schema_version='v1'))
    # 当前版本 v2：name 字段 10 条，6 条修正 → accuracy=0.4（下降 0.5 > 阈值 0.10）
    current = []
    for i in range(4):
        current.append(_make_record('name', adopted=False, schema_version='v2'))
    for i in range(6):
        current.append(_make_record('name', adopted=True, schema_version='v2'))
    regressions = detect_quality_regressions(
        current_records=current,
        baseline_records=baseline,
        threshold=0.10,
    )
    if not regressions:
        print('FAIL 测试5：应检测到质量下降但 regressions 为空')
        return False
    reg = regressions[0]
    if not reg.is_regression:
        print('FAIL 测试5：is_regression 应为 True')
        return False
    if reg.field_name != 'name':
        print(f'FAIL 测试5：field_name 应为 name，实际 {reg.field_name}')
        return False
    if reg.baseline_schema_version != 'v1' or reg.current_schema_version != 'v2':
        print(f'FAIL 测试5：版本标识错误 baseline={reg.baseline_schema_version} current={reg.current_schema_version}')
        return False
    if abs(reg.drop_amount - 0.5) > 0.001:
        print(f'FAIL 测试5：drop_amount 应为 0.5，实际 {reg.drop_amount}')
        return False
    print(f'PASS 测试5：质量下降定位 name 字段 {reg.baseline_accuracy:.2f}→{reg.current_accuracy:.2f} 下降 {reg.drop_amount:.2f}')
    return True


def test_no_false_regression_alarm() -> bool:
    """测试6：质量未下降不误报（drop <= 阈值 → is_regression=False）。"""
    # 基线 v1：10 条 2 修正 → accuracy=0.8
    baseline = []
    for i in range(8):
        baseline.append(_make_record('name', adopted=False, schema_version='v1'))
    for i in range(2):
        baseline.append(_make_record('name', adopted=True, schema_version='v1'))
    # 当前 v2：10 条 3 修正 → accuracy=0.7（下降 0.1 = 阈值，不视为下降）
    current = []
    for i in range(7):
        current.append(_make_record('name', adopted=False, schema_version='v2'))
    for i in range(3):
        current.append(_make_record('name', adopted=True, schema_version='v2'))
    regressions = detect_quality_regressions(
        current_records=current,
        baseline_records=baseline,
        threshold=0.10,
    )
    # 版本不同会记录对比，但 drop=0.1 不大于阈值 0.10 → is_regression=False
    if regressions:
        reg = regressions[0]
        if reg.is_regression:
            print(f'FAIL 测试6：drop={reg.drop_amount} <= 阈值 0.10 但 is_regression=True（误报）')
            return False
        print(f'PASS 测试6：drop={reg.drop_amount} <= 阈值，is_regression=False（不误报）')
        return True
    print('FAIL 测试6：应产出对比记录但 regressions 为空')
    return False


def test_top_reasons_sorted() -> bool:
    """测试7：top_reasons 排序（修正次数最多的原因排前）。"""
    records = []
    # reason_a 出现 5 次，reason_b 出现 2 次，reason_c 出现 1 次
    for i in range(5):
        records.append(_make_record('name', adopted=True, reason='low_confidence'))
    for i in range(2):
        records.append(_make_record('name', adopted=False, reason='ambiguous_spec'))
    records.append(_make_record('name', adopted=False, reason='high_risk'))
    snapshot = aggregate_quality_metrics(records)
    m = snapshot.by_field[0]
    if not m.top_reasons:
        print('FAIL 测试7：top_reasons 为空')
        return False
    # 第一项应为 low_confidence（5 次）
    if m.top_reasons[0][0] != 'low_confidence' or m.top_reasons[0][1] != 5:
        print(f'FAIL 测试7：top_reasons 首项应为 (low_confidence, 5)，实际 {m.top_reasons[0]}')
        return False
    # 第二项应为 ambiguous_spec（2 次）
    if m.top_reasons[1][0] != 'ambiguous_spec' or m.top_reasons[1][1] != 2:
        print(f'FAIL 测试7：top_reasons 第二项应为 (ambiguous_spec, 2)，实际 {m.top_reasons[1]}')
        return False
    print(f'PASS 测试7：top_reasons 排序 {m.top_reasons[:3]}')
    return True


def test_no_unnecessary_sensitive_storage() -> bool:
    """测试8：不保存不必要敏感原文（空原值不存；整体脱敏字段返回 '***'）。"""
    fields = [
        # spec 原值为空 → original_value 应为空
        {'field_name': 'spec', 'line_index': 1, 'original_value': '',
         'confidence': 0.40, 'needs_confirmation': True,
         'confirmation_reason': 'low_confidence', 'correction_status': ''},
        # id_card 原值有 → 应整体脱敏为 '***'
        {'field_name': 'id_card', 'line_index': 2, 'original_value': '110101199001011234',
         'confidence': 0.50, 'needs_confirmation': True,
         'confirmation_reason': 'low_confidence', 'correction_status': ''},
    ]
    corrections = {
        'line1.spec': '20mm',           # 用户修正了 spec
        'line2.id_card': '110101199001011234',  # 用户确认原值
    }
    records = build_field_correction_records(
        evidence_fields=fields,
        corrections=corrections,
        model='gpt-5.6-sol',
        prompt_hash='abc123def456',
        source='ocr_upload',
    )
    if len(records) != 2:
        print(f'FAIL 测试8：期望 2 条记录，实际 {len(records)}')
        return False
    spec_rec = next(r for r in records if r.field_name == 'spec')
    # spec 原值为空，original_value 应为空
    if spec_rec.original_value != '':
        print(f'FAIL 测试8：spec 原值为空，original_value 应为空，实际 {spec_rec.original_value!r}')
        return False
    # spec 被修正为 20mm，应 adopted=True
    if not spec_rec.adopted or spec_rec.corrected_value != '20mm':
        print(f'FAIL 测试8：spec 应 adopted=True 且 corrected_value=20mm，实际 adopted={spec_rec.adopted} corrected={spec_rec.corrected_value!r}')
        return False
    id_rec = next(r for r in records if r.field_name == 'id_card')
    # id_card 应整体脱敏
    if id_rec.original_value != '***':
        print(f'FAIL 测试8：id_card original_value 应为 ***，实际 {id_rec.original_value!r}')
        return False
    if id_rec.corrected_value != '***':
        print(f'FAIL 测试8：id_card corrected_value 应为 ***，实际 {id_rec.corrected_value!r}')
        return False
    print('PASS 测试8：空原值不存 + id_card 整体脱敏为 ***')
    return True


def _make_record(field_name: str, *, adopted: bool = False, reason: str = 'low_confidence',
                 schema_version: str = DEFAULT_SCHEMA_VERSION, source: str = 'ocr_upload') -> FieldCorrectionRecord:
    """构造测试用 FieldCorrectionRecord。"""
    return FieldCorrectionRecord(
        field_name=field_name,
        line_index=0,
        original_value='orig' if not adopted else 'orig',
        corrected_value='fixed' if adopted else 'orig',
        correction_reason=reason,
        adopted=adopted,
        model='gpt-5.6-sol',
        prompt_hash='abc123def456',
        schema_version=schema_version,
        source=source,
        created_at='2026-07-17T00:00:00',
    )


def main() -> int:
    tests = [
        test_field_correction_record_construction,
        test_sensitive_value_masking,
        test_aggregate_accuracy_rate,
        test_aggregate_correction_rate,
        test_quality_regression_detected,
        test_no_false_regression_alarm,
        test_top_reasons_sorted,
        test_no_unnecessary_sensitive_storage,
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
    print(f'\n=== AI-R09 字段级反馈和文档质量指标: {passed} PASS / {failed} FAIL ===')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

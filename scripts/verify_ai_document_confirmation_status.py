"""AI-R08-F01 文档确认状态与提交前强制门禁验证脚本。

# AI_TASK: AI-R08-F01

验证内容：
1. 字段确认记录构造：build_field_confirmation_record 正确构造 FieldConfirmationRecord
2. 状态常量校验：VALID_CONFIRMATION_STATUSES 包含 4 种状态
3. 字段确认校验：validate_field_confirmation 校验规则正确性
4. 全字段确认校验：validate_all_fields_confirmed 检查所有字段非 pending
5. 草稿创建门禁：validate_draft_creation_allowed 六项校验规则
6. 重复风险拦截：duplicate_risk=True 时拒绝创建
7. 低置信度拦截：低置信度字段未确认时拒绝创建
8. 高风险物料拦截：高风险物料未确认时拒绝创建

退出码 0=通过，1=失败。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ai.documents.document_confirmation_status import (  # noqa: E402
    STATUS_CONFIRMED_ORIGINAL,
    STATUS_CORRECTED,
    STATUS_PENDING,
    STATUS_REJECTED,
    VALID_CONFIRMATION_STATUSES,
    FieldConfirmationRecord,
    build_field_confirmation_record,
    validate_all_fields_confirmed,
    validate_draft_creation_allowed,
    validate_field_confirmation,
)


def test_field_confirmation_record_construction() -> None:
    """测试1：字段确认记录构造正确性。"""
    record = build_field_confirmation_record(
        field_id=100,
        task_id=200,
        line_id=5,
        field_name='material_name',
        confirmation_status=STATUS_CONFIRMED_ORIGINAL,
        original_value='轴承',
        confirmed_value='轴承',
        correction_reason=None,
        evidence_source='ocr',
        model='qwen-vl-max',
        prompt_version='v1.2',
        schema_version='document-extraction-v1',
        confirmed_by=10,
        confirmed_at=datetime(2026, 7, 18, 10, 0, 0),
    )

    assert isinstance(record, FieldConfirmationRecord), '应返回 FieldConfirmationRecord 实例'
    assert record.field_id == 100
    assert record.task_id == 200
    assert record.line_id == 5
    assert record.field_name == 'material_name'
    assert record.confirmation_status == STATUS_CONFIRMED_ORIGINAL
    assert record.original_value == '轴承'
    assert record.confirmed_value == '轴承'
    assert record.correction_reason is None
    assert record.evidence_source == 'ocr'
    assert record.model == 'qwen-vl-max'
    assert record.prompt_version == 'v1.2'
    assert record.schema_version == 'document-extraction-v1'
    assert record.confirmed_by == 10
    assert record.confirmed_at == datetime(2026, 7, 18, 10, 0, 0)

    # 测试 to_dict 方法
    record_dict = record.to_dict()
    assert record_dict['field_id'] == 100
    assert record_dict['field_name'] == 'material_name'
    assert record_dict['confirmation_status'] == STATUS_CONFIRMED_ORIGINAL

    print('测试1 通过: 字段确认记录构造正确性')


def test_status_constants_validation() -> None:
    """测试2：状态常量校验。"""
    assert STATUS_PENDING == 'pending'
    assert STATUS_CONFIRMED_ORIGINAL == 'confirmed_original'
    assert STATUS_CORRECTED == 'corrected'
    assert STATUS_REJECTED == 'rejected'

    assert len(VALID_CONFIRMATION_STATUSES) == 4
    assert STATUS_PENDING in VALID_CONFIRMATION_STATUSES
    assert STATUS_CONFIRMED_ORIGINAL in VALID_CONFIRMATION_STATUSES
    assert STATUS_CORRECTED in VALID_CONFIRMATION_STATUSES
    assert STATUS_REJECTED in VALID_CONFIRMATION_STATUSES

    print('测试2 通过: 状态常量校验')


def test_field_confirmation_validation() -> None:
    """测试3：字段确认校验规则正确性。"""
    # 场景1: confirmed_original 状态，有确认人和时间 → 通过
    record1 = build_field_confirmation_record(
        field_id=1,
        task_id=1,
        line_id=None,
        field_name='supplier',
        confirmation_status=STATUS_CONFIRMED_ORIGINAL,
        original_value='鑫达',
        confirmed_value='鑫达',
        correction_reason=None,
        evidence_source='ocr',
        model='local-rules',
        prompt_version='',
        schema_version='v1',
        confirmed_by=10,
        confirmed_at=datetime.now(),
    )
    is_valid1, reason1 = validate_field_confirmation(record1)
    assert is_valid1, f'confirmed_original 应通过校验, got {reason1}'

    # 场景2: corrected 状态，缺少修正原因 → 失败（通过直接构造记录绕过创建时验证）
    record2 = FieldConfirmationRecord(
        field_id=2,
        task_id=1,
        line_id=0,
        field_name='material_name',
        confirmation_status=STATUS_CORRECTED,
        original_value='轴承',
        confirmed_value='轴承6204',
        correction_reason=None,  # 缺少修正原因
        evidence_source='ocr',
        model='local-rules',
        prompt_version='',
        schema_version='v1',
        confirmed_by=10,
        confirmed_at=datetime.now(),
        created_at=datetime.now(),
    )
    is_valid2, reason2 = validate_field_confirmation(record2)
    assert not is_valid2, 'corrected 状态缺少修正原因应失败'
    assert '修正原因' in reason2

    # 场景3: corrected 状态，有修正原因 → 通过
    record3 = build_field_confirmation_record(
        field_id=3,
        task_id=1,
        line_id=0,
        field_name='material_name',
        confirmation_status=STATUS_CORRECTED,
        original_value='轴承',
        confirmed_value='轴承6204',
        correction_reason='用户修正物料名称',
        evidence_source='ocr',
        model='local-rules',
        prompt_version='',
        schema_version='v1',
        confirmed_by=10,
        confirmed_at=datetime.now(),
    )
    is_valid3, reason3 = validate_field_confirmation(record3)
    assert is_valid3, f'corrected 状态有修正原因应通过, got {reason3}'

    # 场景4: pending 状态 → 通过（但后续 validate_all_fields_confirmed 会拦截）
    record4 = build_field_confirmation_record(
        field_id=4,
        task_id=1,
        line_id=None,
        field_name='order_no',
        confirmation_status=STATUS_PENDING,
        original_value='PO001',
        confirmed_value='PO001',
        correction_reason=None,
        evidence_source='ocr',
        model='local-rules',
        prompt_version='',
        schema_version='v1',
        confirmed_by=0,
        confirmed_at=None,
    )
    is_valid4, reason4 = validate_field_confirmation(record4)
    assert is_valid4, f'pending 状态应通过校验, got {reason4}'

    print('测试3 通过: 字段确认校验规则正确性')


def test_all_fields_confirmed_validation() -> None:
    """测试4：全字段确认校验。"""
    # 场景1: 所有字段已确认 → 通过
    records1 = [
        build_field_confirmation_record(
            field_id=1, task_id=1, line_id=None, field_name='supplier',
            confirmation_status=STATUS_CONFIRMED_ORIGINAL,
            original_value='鑫达', confirmed_value='鑫达', correction_reason=None,
            evidence_source='ocr', model='local-rules', prompt_version='', schema_version='v1',
            confirmed_by=10, confirmed_at=datetime.now(),
        ),
        build_field_confirmation_record(
            field_id=2, task_id=1, line_id=0, field_name='material_name',
            confirmation_status=STATUS_CORRECTED,
            original_value='轴承', confirmed_value='轴承6204', correction_reason='用户修正',
            evidence_source='ocr', model='local-rules', prompt_version='', schema_version='v1',
            confirmed_by=10, confirmed_at=datetime.now(),
        ),
    ]
    is_valid1, reasons1 = validate_all_fields_confirmed(records1)
    assert is_valid1, f'所有字段已确认应通过, got {reasons1}'
    assert len(reasons1) == 0

    # 场景2: 有 pending 字段 → 失败
    records2 = [
        build_field_confirmation_record(
            field_id=1, task_id=1, line_id=None, field_name='supplier',
            confirmation_status=STATUS_CONFIRMED_ORIGINAL,
            original_value='鑫达', confirmed_value='鑫达', correction_reason=None,
            evidence_source='ocr', model='local-rules', prompt_version='', schema_version='v1',
            confirmed_by=10, confirmed_at=datetime.now(),
        ),
        build_field_confirmation_record(
            field_id=2, task_id=1, line_id=0, field_name='material_name',
            confirmation_status=STATUS_PENDING,  # 未确认
            original_value='轴承', confirmed_value='轴承', correction_reason=None,
            evidence_source='ocr', model='local-rules', prompt_version='', schema_version='v1',
            confirmed_by=0, confirmed_at=None,
        ),
    ]
    is_valid2, reasons2 = validate_all_fields_confirmed(records2)
    assert not is_valid2, '有 pending 字段应失败'
    assert len(reasons2) > 0
    assert any('未确认' in r for r in reasons2)

    print('测试4 通过: 全字段确认校验')


def test_draft_creation_gate_all_rules() -> None:
    """测试5：草稿创建门禁六项校验规则。"""
    # 构造已确认的字段记录
    confirmed_records = [
        build_field_confirmation_record(
            field_id=1, task_id=1, line_id=None, field_name='supplier',
            confirmation_status=STATUS_CONFIRMED_ORIGINAL,
            original_value='鑫达', confirmed_value='鑫达', correction_reason=None,
            evidence_source='ocr', model='local-rules', prompt_version='', schema_version='v1',
            confirmed_by=10, confirmed_at=datetime.now(),
        ),
        build_field_confirmation_record(
            field_id=2, task_id=1, line_id=0, field_name='material_name',
            confirmation_status=STATUS_CONFIRMED_ORIGINAL,
            original_value='轴承', confirmed_value='轴承', correction_reason=None,
            evidence_source='ocr', model='local-rules', prompt_version='', schema_version='v1',
            confirmed_by=10, confirmed_at=datetime.now(),
        ),
    ]

    # 场景1: 所有条件满足 → 允许创建
    is_allowed1, reasons1 = validate_draft_creation_allowed(
        field_records=confirmed_records,
        duplicate_risk=False,
        low_confidence_fields=[],
        material_ambiguity=False,
        specification_conflict=False,
        high_risk_material=False,
    )
    assert is_allowed1, f'所有条件满足应允许创建, got {reasons1}'
    assert len(reasons1) == 0

    # 场景2: 有 pending 字段 → 拒绝
    pending_records = [
        build_field_confirmation_record(
            field_id=1, task_id=1, line_id=None, field_name='supplier',
            confirmation_status=STATUS_PENDING,
            original_value='鑫达', confirmed_value='鑫达', correction_reason=None,
            evidence_source='ocr', model='local-rules', prompt_version='', schema_version='v1',
            confirmed_by=0, confirmed_at=None,
        ),
    ]
    is_allowed2, reasons2 = validate_draft_creation_allowed(
        field_records=pending_records,
        duplicate_risk=False,
        low_confidence_fields=[],
        material_ambiguity=False,
        specification_conflict=False,
        high_risk_material=False,
    )
    assert not is_allowed2, '有 pending 字段应拒绝'
    assert any('未确认' in r for r in reasons2)

    print('测试5 通过: 草稿创建门禁六项校验规则')


def test_duplicate_risk_blocks_creation() -> None:
    """测试6：重复风险拦截。"""
    confirmed_records = [
        build_field_confirmation_record(
            field_id=1, task_id=1, line_id=None, field_name='supplier',
            confirmation_status=STATUS_CONFIRMED_ORIGINAL,
            original_value='鑫达', confirmed_value='鑫达', correction_reason=None,
            evidence_source='ocr', model='local-rules', prompt_version='', schema_version='v1',
            confirmed_by=10, confirmed_at=datetime.now(),
        ),
    ]

    is_allowed, reasons = validate_draft_creation_allowed(
        field_records=confirmed_records,
        duplicate_risk=True,  # 有重复风险
        low_confidence_fields=[],
        material_ambiguity=False,
        specification_conflict=False,
        high_risk_material=False,
    )
    assert not is_allowed, '重复风险应拒绝创建'
    assert any('重复风险' in r for r in reasons)

    print('测试6 通过: 重复风险拦截')


def test_low_confidence_fields_blocks_creation() -> None:
    """测试7：低置信度字段拦截。"""
    # 场景1: 低置信度字段未确认 → 拒绝
    records1 = [
        build_field_confirmation_record(
            field_id=1, task_id=1, line_id=0, field_name='material_name',
            confirmation_status=STATUS_PENDING,  # 未确认
            original_value='轴承', confirmed_value='轴承', correction_reason=None,
            evidence_source='ocr', model='local-rules', prompt_version='', schema_version='v1',
            confirmed_by=0, confirmed_at=None,
        ),
    ]
    is_allowed1, reasons1 = validate_draft_creation_allowed(
        field_records=records1,
        duplicate_risk=False,
        low_confidence_fields=['material_name'],  # 低置信度字段
        material_ambiguity=False,
        specification_conflict=False,
        high_risk_material=False,
    )
    assert not is_allowed1, '低置信度字段未确认应拒绝'
    assert any('低置信度' in r for r in reasons1)

    # 场景2: 低置信度字段已确认 → 允许
    records2 = [
        build_field_confirmation_record(
            field_id=1, task_id=1, line_id=0, field_name='material_name',
            confirmation_status=STATUS_CONFIRMED_ORIGINAL,  # 已确认
            original_value='轴承', confirmed_value='轴承', correction_reason=None,
            evidence_source='ocr', model='local-rules', prompt_version='', schema_version='v1',
            confirmed_by=10, confirmed_at=datetime.now(),
        ),
    ]
    is_allowed2, reasons2 = validate_draft_creation_allowed(
        field_records=records2,
        duplicate_risk=False,
        low_confidence_fields=['material_name'],  # 低置信度字段
        material_ambiguity=False,
        specification_conflict=False,
        high_risk_material=False,
    )
    assert is_allowed2, f'低置信度字段已确认应允许, got {reasons2}'

    print('测试7 通过: 低置信度字段拦截')


def test_high_risk_material_blocks_creation() -> None:
    """测试8：高风险物料拦截。"""
    # 场景1: 高风险物料未确认 → 拒绝
    records1 = [
        build_field_confirmation_record(
            field_id=1, task_id=1, line_id=0, field_name='material_name',
            confirmation_status=STATUS_PENDING,  # 未确认
            original_value='IC芯片', confirmed_value='IC芯片', correction_reason=None,
            evidence_source='ocr', model='local-rules', prompt_version='', schema_version='v1',
            confirmed_by=0, confirmed_at=None,
        ),
    ]
    is_allowed1, reasons1 = validate_draft_creation_allowed(
        field_records=records1,
        duplicate_risk=False,
        low_confidence_fields=[],
        material_ambiguity=False,
        specification_conflict=False,
        high_risk_material=True,  # 高风险物料
    )
    assert not is_allowed1, '高风险物料未确认应拒绝'
    assert any('高风险' in r for r in reasons1)

    # 场景2: 高风险物料已确认 → 允许
    records2 = [
        build_field_confirmation_record(
            field_id=1, task_id=1, line_id=0, field_name='material_name',
            confirmation_status=STATUS_CONFIRMED_ORIGINAL,  # 已确认
            original_value='IC芯片', confirmed_value='IC芯片', correction_reason=None,
            evidence_source='ocr', model='local-rules', prompt_version='', schema_version='v1',
            confirmed_by=10, confirmed_at=datetime.now(),
        ),
    ]
    is_allowed2, reasons2 = validate_draft_creation_allowed(
        field_records=records2,
        duplicate_risk=False,
        low_confidence_fields=[],
        material_ambiguity=False,
        specification_conflict=False,
        high_risk_material=True,  # 高风险物料
    )
    assert is_allowed2, f'高风险物料已确认应允许, got {reasons2}'

    print('测试8 通过: 高风险物料拦截')


def main() -> int:
    try:
        test_field_confirmation_record_construction()
        test_status_constants_validation()
        test_field_confirmation_validation()
        test_all_fields_confirmed_validation()
        test_draft_creation_gate_all_rules()
        test_duplicate_risk_blocks_creation()
        test_low_confidence_fields_blocks_creation()
        test_high_risk_material_blocks_creation()
    except AssertionError as exc:
        print(f'FAIL AI-DOCUMENT-CONFIRMATION-STATUS: {exc}')
        return 1
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f'FAIL AI-DOCUMENT-CONFIRMATION-STATUS: 异常 {exc}')
        return 1

    print('PASS AI-DOCUMENT-CONFIRMATION-STATUS: 文档确认状态与门禁 8 项测试全部通过')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

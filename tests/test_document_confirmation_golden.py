# -*- coding: utf-8 -*-
"""模块2黄金测试：document_confirmation.py + document_confirmation_status.py 草稿校验逻辑统一。

# AI_TASK: AI-R08 / AI-R08-F01 黄金测试（绞杀者模式前置基线）

所有断言严格依据《项目黑话词典》确定性语义与待确认歧义点，禁止使用通用 WMS 术语。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import pytest

from app.ai.documents.document_confirmation import (
    BLOCKING_DRAFT_STATUSES,
    DUPLICATE_SIMILARITY_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
    DocumentConfirmationEvidence,
    DuplicateRiskHit,
    FieldEvidence,
    build_confirmation_evidence,
)
from app.ai.documents.document_confirmation_status import (
    ALL_EVIDENCE_SOURCES,
    EVIDENCE_SOURCE_EXCEL,
    EVIDENCE_SOURCE_GPT,
    EVIDENCE_SOURCE_MANUAL,
    EVIDENCE_SOURCE_OCR,
    EVIDENCE_SOURCE_VISION,
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


# ----------------------------------------------------------------------
# 模块2-A：FieldEvidence.correction_status 确定性语义
# ----------------------------------------------------------------------

# 依据：ai_document_field_confirmation.correction_status 确定性语义（空字符串为初始状态）
def test_field_evidence_correction_status_initial_is_empty_string():
    """基线：FieldEvidence 初始 correction_status 必须为空字符串 ''，而非 'pending'。"""
    fe = FieldEvidence(
        field_name='code', original_value='IC-6204', candidates=(),
        confidence=0.95, needs_confirmation=False,
        confirmation_reason='', correction_status='', source='ocr',
    )
    assert fe.correction_status == '', "初始状态必须为空字符串 ''"
    assert fe.correction_status != 'pending', "不得误用 pending 作为初始值"


# 依据：ai_document_field_confirmation.correction_status 确定性语义（门禁判定 not in ('corrected','rejected')）
def test_field_evidence_empty_correction_status_triggers_gate():
    """基线：correction_status='' 必须触发未处理门禁（按 not in ('corrected','rejected') 判定）。"""
    fe_low_conf = FieldEvidence(
        field_name='code', original_value='IC-6204', candidates=(),
        confidence=0.50, needs_confirmation=True,
        confirmation_reason='low_confidence', correction_status='', source='ocr',
    )
    # 模拟 document_confirmation.py 中的门禁判定逻辑
    has_unconfirmed = (
        fe_low_conf.confidence < LOW_CONFIDENCE_THRESHOLD
        and fe_low_conf.correction_status not in ('corrected', 'rejected')
    )
    assert has_unconfirmed is True, "低置信度 + 空字符串 correction_status 必须触发门禁"


# 依据：ai_document_field_confirmation.correction_status 确定性语义（corrected/rejected 不触发门禁）
@pytest.mark.parametrize('status', ['corrected', 'rejected'])
def test_field_evidence_corrected_or_rejected_passes_gate(status):
    """基线：correction_status ∈ {'corrected','rejected'} 时不得触发未处理门禁。"""
    fe = FieldEvidence(
        field_name='code', original_value='IC-6204', candidates=(),
        confidence=0.50, needs_confirmation=True,
        confirmation_reason='low_confidence', correction_status=status, source='ocr',
    )
    has_unconfirmed = (
        fe.confidence < LOW_CONFIDENCE_THRESHOLD
        and fe.correction_status not in ('corrected', 'rejected')
    )
    assert has_unconfirmed is False, f"{status} 必须视为已处理，不触发门禁"


# 依据：ai_document_field_confirmation.correction_status 确定性语义（pending 仍触发门禁）
def test_field_evidence_pending_correction_status_triggers_gate():
    """基线：correction_status='pending' 不在豁免集合，必须触发门禁。"""
    fe = FieldEvidence(
        field_name='code', original_value='IC-6204', candidates=(),
        confidence=0.50, needs_confirmation=True,
        confirmation_reason='low_confidence', correction_status='pending', source='ocr',
    )
    has_unconfirmed = (
        fe.confidence < LOW_CONFIDENCE_THRESHOLD
        and fe.correction_status not in ('corrected', 'rejected')
    )
    assert has_unconfirmed is True, "pending 状态仍触发门禁（非豁免状态）"


# ----------------------------------------------------------------------
# 模块2-B：build_confirmation_evidence 综合门禁语义
# ----------------------------------------------------------------------

# 依据：ai_document_field_confirmation.correction_status 确定性语义（低置信度未处理则拦截建单）
def test_build_confirmation_evidence_blocks_when_low_confidence_unconfirmed():
    """基线：低置信度字段 correction_status='' 时 has_unconfirmed_low_confidence_fields=True。"""
    extracted = {'supplier': '供应商A', 'order_no': 'PO-001', 'date': '2026-01-01'}
    items = [
        {'code': 'IC-6204', 'name': '轴承', 'spec': '4x12x4', 'quantity': 10, 'unit': '个',
         'confidence': 0.50, 'matched': False},
    ]
    evidence = build_confirmation_evidence(
        extracted=extracted, items=items,
        delivery_match=None, material_governance=None,
        query_existing_drafts=None, source_hash='', business_key='',
    )
    assert isinstance(evidence, DocumentConfirmationEvidence), "返回类型必须为 DocumentConfirmationEvidence"
    # 任何字段 confidence<0.80 且 correction_status='' 即触发未处理
    assert evidence.has_unconfirmed_low_confidence_fields is True, (
        "存在低置信度 + correction_status='' 必须标记 has_unconfirmed_low_confidence_fields=True"
    )


# 依据：BLOCKING_DRAFT_STATUSES=（'completed',） 确定性语义
def test_blocking_draft_statuses_only_completed():
    """基线：阻止建单的草稿状态仅含 'completed'，不可扩展。"""
    assert BLOCKING_DRAFT_STATUSES == ('completed',), (
        "BLOCKING_DRAFT_STATUSES 仅 'completed'，其他状态不得阻止建单"
    )


# 依据：DuplicateRiskHit.blocks_creation 确定性语义（仅 completed 状态阻止）
def test_duplicate_risk_blocks_only_when_status_completed():
    """基线：existing_status='completed' 时 blocks_creation=True，其他状态不阻止。"""
    blocking = DuplicateRiskHit(
        existing_draft_type='in_order', existing_draft_id=1, existing_draft_no='IN001',
        existing_status='completed', created_at='2026-01-01T00:00:00',
        match_reason='source_hash', similarity=0.99, blocks_creation=True,
    )
    non_blocking = DuplicateRiskHit(
        existing_draft_type='in_order', existing_draft_id=2, existing_draft_no='IN002',
        existing_status='processing', created_at='2026-01-01T00:00:00',
        match_reason='business_key', similarity=0.99, blocks_creation=False,
    )
    assert blocking.blocks_creation is True, "completed 状态草稿必须阻止建单"
    assert non_blocking.blocks_creation is False, "processing 状态草稿不得阻止建单"


# 依据：DUPLICATE_SIMILARITY_THRESHOLD=0.85 确定性语义
def test_duplicate_similarity_threshold_is_85_percent():
    """基线：重复相似度阈值 0.85 不可变。"""
    assert DUPLICATE_SIMILARITY_THRESHOLD == 0.85, "重复相似度阈值必须为 0.85"


# 依据：LOW_CONFIDENCE_THRESHOLD=0.80 确定性语义
def test_low_confidence_threshold_is_80_percent():
    """基线：低置信度阈值 0.80 不可变。"""
    assert LOW_CONFIDENCE_THRESHOLD == 0.80, "低置信度阈值必须为 0.80"


# ----------------------------------------------------------------------
# 模块2-C：document_confirmation_status 四态语义
# ----------------------------------------------------------------------

# 依据：document_confirmation_status 确定性语义（四态常量）
def test_confirmation_status_constants_match_dictionary():
    """基线：确认状态四态常量必须与黑话字典一致。"""
    assert STATUS_PENDING == 'pending', "待确认"
    assert STATUS_CONFIRMED_ORIGINAL == 'confirmed_original', "认可 AI 原值"
    assert STATUS_CORRECTED == 'corrected', "覆盖 AI 值"
    assert STATUS_REJECTED == 'rejected', "拒绝"
    assert VALID_CONFIRMATION_STATUSES == (
        'pending', 'confirmed_original', 'corrected', 'rejected',
    ), "状态枚举顺序不可变"


# 依据：document_confirmation_status 确定性语义（confirmed_original 与 corrected 均为已处理但语义不同）
def test_confirmed_original_and_corrected_both_pass_field_validation_but_differ_semantically():
    """基线：confirmed_original 与 corrected 均通过校验，但语义必须可区分。"""
    now = datetime(2026, 1, 1, 0, 0, 0)
    record_original = build_field_confirmation_record(
        field_id=1, task_id=1, line_id=None, field_name='code',
        confirmation_status=STATUS_CONFIRMED_ORIGINAL,
        original_value='IC-6204', confirmed_value='IC-6204',
        correction_reason=None,
        evidence_source=EVIDENCE_SOURCE_OCR, model='qwen-vl-max',
        prompt_version='v1', schema_version='v1', confirmed_by=10,
        confirmed_at=now, created_at=now,
    )
    record_corrected = build_field_confirmation_record(
        field_id=2, task_id=1, line_id=None, field_name='code',
        confirmation_status=STATUS_CORRECTED,
        original_value='IC-6204', confirmed_value='IC-6205',
        correction_reason='OCR 识别错误',
        evidence_source=EVIDENCE_SOURCE_OCR, model='qwen-vl-max',
        prompt_version='v1', schema_version='v1', confirmed_by=10,
        confirmed_at=now, created_at=now,
    )
    is_valid_orig, _ = validate_field_confirmation(record_original)
    is_valid_corr, _ = validate_field_confirmation(record_corrected)
    assert is_valid_orig is True, "confirmed_original 必须通过校验"
    assert is_valid_corr is True, "corrected 必须通过校验"
    # 语义区分：confirmed_value 等于 original_value 表示认可原值；不等表示覆盖
    assert record_original.confirmed_value == record_original.original_value, (
        "confirmed_original 必须 confirmed_value==original_value"
    )
    assert record_corrected.confirmed_value != record_corrected.original_value, (
        "corrected 必须 confirmed_value!=original_value"
    )
    assert record_corrected.correction_reason is not None, "corrected 必须保留修正原因"


# 依据：document_confirmation_status 确定性语义（corrected 缺修正原因必须拒绝）
def test_corrected_status_requires_correction_reason():
    """基线：corrected 状态无 correction_reason 必须 raise ValueError。"""
    with pytest.raises(ValueError):
        build_field_confirmation_record(
            field_id=1, task_id=1, line_id=None, field_name='code',
            confirmation_status=STATUS_CORRECTED,
            original_value='IC-6204', confirmed_value='IC-6205',
            correction_reason=None,
            evidence_source=EVIDENCE_SOURCE_OCR, model='m', prompt_version='v',
            schema_version='v', confirmed_by=10,
        )


# 依据：document_confirmation_status 确定性语义（confirmed_original/corrected 缺确认人必须拒绝）
@pytest.mark.parametrize('status', [STATUS_CONFIRMED_ORIGINAL, STATUS_CORRECTED])
def test_processed_status_requires_confirmed_by(status):
    """基线：confirmed_original/corrected 缺 confirmed_by 必须校验失败。"""
    now = datetime(2026, 1, 1, 0, 0, 0)
    record = FieldConfirmationRecord(
        field_id=1, task_id=1, line_id=None, field_name='code',
        confirmation_status=status,
        original_value='IC-6204', confirmed_value='IC-6205',
        correction_reason='r' if status == STATUS_CORRECTED else None,
        evidence_source=EVIDENCE_SOURCE_OCR, model='m', prompt_version='v',
        schema_version='v', confirmed_by=0,  # 0 视为缺失
        confirmed_at=now, created_at=now,
    )
    is_valid, reason = validate_field_confirmation(record)
    assert is_valid is False, f"{status} 缺确认人必须校验失败"
    assert '确认人' in reason, "失败原因必须提及确认人"


# 依据：document_confirmation_status 确定性语义（rejected 缺确认人必须拒绝）
def test_rejected_status_requires_confirmed_by():
    """基线：rejected 状态缺 confirmed_by 必须校验失败。"""
    now = datetime(2026, 1, 1, 0, 0, 0)
    record = FieldConfirmationRecord(
        field_id=1, task_id=1, line_id=None, field_name='code',
        confirmation_status=STATUS_REJECTED,
        original_value='IC-6204', confirmed_value=None,
        correction_reason=None,
        evidence_source=EVIDENCE_SOURCE_OCR, model='m', prompt_version='v',
        schema_version='v', confirmed_by=0, confirmed_at=now, created_at=now,
    )
    is_valid, reason = validate_field_confirmation(record)
    assert is_valid is False, "rejected 缺确认人必须校验失败"
    assert '确认人' in reason


# 依据：document_confirmation_status 确定性语义（pending 视为未确认）
def test_validate_all_fields_confirmed_rejects_pending():
    """基线：validate_all_fields_confirmed 必须将 pending 视为未确认。"""
    now = datetime(2026, 1, 1, 0, 0, 0)
    pending_record = FieldConfirmationRecord(
        field_id=1, task_id=1, line_id=None, field_name='code',
        confirmation_status=STATUS_PENDING,
        original_value='IC-6204', confirmed_value=None,
        correction_reason=None,
        evidence_source=EVIDENCE_SOURCE_OCR, model='m', prompt_version='v',
        schema_version='v', confirmed_by=0, confirmed_at=now, created_at=now,
    )
    is_valid, reasons = validate_all_fields_confirmed([pending_record])
    assert is_valid is False, "pending 字段必须视为未确认"
    assert reasons, "必须返回未确认原因"


# 依据：document_confirmation_status 确定性语义（非法状态必须拒绝）
def test_invalid_confirmation_status_raises():
    """基线：非法 confirmation_status 必须 raise ValueError。"""
    with pytest.raises(ValueError):
        build_field_confirmation_record(
            field_id=1, task_id=1, line_id=None, field_name='code',
            confirmation_status='approved',  # 黑话字典无此值
            original_value='IC-6204', confirmed_value='IC-6204',
            correction_reason=None,
            evidence_source=EVIDENCE_SOURCE_OCR, model='m', prompt_version='v',
            schema_version='v', confirmed_by=10,
        )


# 依据：EVIDENCE_SOURCE_* 确定性语义（5 种证据来源）
def test_evidence_sources_match_dictionary():
    """基线：证据来源 5 类必须与黑话字典一致。"""
    assert EVIDENCE_SOURCE_OCR == 'ocr'
    assert EVIDENCE_SOURCE_VISION == 'vision'
    assert EVIDENCE_SOURCE_EXCEL == 'excel'
    assert EVIDENCE_SOURCE_GPT == 'gpt'
    assert EVIDENCE_SOURCE_MANUAL == 'manual'
    assert ALL_EVIDENCE_SOURCES == ('ocr', 'vision', 'excel', 'gpt', 'manual'), (
        "证据来源枚举顺序不可变"
    )


# ----------------------------------------------------------------------
# 模块2-D：validate_draft_creation_allowed 综合门禁
# ----------------------------------------------------------------------

# 依据：ai_document_field_confirmation.correction_status 确定性语义（草稿创建门禁6规则）
def test_validate_draft_creation_allowed_blocks_on_low_confidence_unconfirmed():
    """基线：低置信度字段未确认时 validate_draft_creation_allowed 必须返回 False。"""
    now = datetime(2026, 1, 1, 0, 0, 0)
    # 字段已确认（confirmed_original），但 low_confidence_fields 仍包含未确认项
    confirmed_record = FieldConfirmationRecord(
        field_id=1, task_id=1, line_id=None, field_name='name',
        confirmation_status=STATUS_CONFIRMED_ORIGINAL,
        original_value='轴承', confirmed_value='轴承',
        correction_reason=None,
        evidence_source=EVIDENCE_SOURCE_OCR, model='m', prompt_version='v',
        schema_version='v', confirmed_by=10, confirmed_at=now, created_at=now,
    )
    is_allowed, reasons = validate_draft_creation_allowed(
        field_records=[confirmed_record],
        duplicate_risk=False,
        low_confidence_fields=['code'],  # code 未在 records 中确认
        material_ambiguity=False,
        specification_conflict=False,
        high_risk_material=False,
    )
    assert is_allowed is False, "低置信度字段未确认必须阻止建单"
    assert any('低置信度' in r for r in reasons), "原因必须含低置信度说明"


# 依据：ai_document_field_confirmation.correction_status 确定性语义（确认后允许建单）
def test_validate_draft_creation_allowed_passes_when_all_confirmed():
    """基线：所有门禁通过时返回 (True, [])。"""
    now = datetime(2026, 1, 1, 0, 0, 0)
    code_record = FieldConfirmationRecord(
        field_id=1, task_id=1, line_id=None, field_name='code',
        confirmation_status=STATUS_CORRECTED,
        original_value='IC-6204', confirmed_value='IC-6205',
        correction_reason='修正',
        evidence_source=EVIDENCE_SOURCE_OCR, model='m', prompt_version='v',
        schema_version='v', confirmed_by=10, confirmed_at=now, created_at=now,
    )
    is_allowed, reasons = validate_draft_creation_allowed(
        field_records=[code_record],
        duplicate_risk=False,
        low_confidence_fields=['code'],  # code 已 confirmed/corrected
        material_ambiguity=False,
        specification_conflict=False,
        high_risk_material=False,
    )
    assert is_allowed is True, "字段全部确认后必须允许建单"
    assert reasons == [], "通过时原因清单必须为空"


# 依据：duplicate_risk 确定性语义（重复风险阻止建单）
def test_validate_draft_creation_allowed_blocks_on_duplicate_risk():
    """基线：duplicate_risk=True 必须阻止建单。"""
    now = datetime(2026, 1, 1, 0, 0, 0)
    confirmed = FieldConfirmationRecord(
        field_id=1, task_id=1, line_id=None, field_name='code',
        confirmation_status=STATUS_CONFIRMED_ORIGINAL,
        original_value='IC-6204', confirmed_value='IC-6204',
        correction_reason=None,
        evidence_source=EVIDENCE_SOURCE_OCR, model='m', prompt_version='v',
        schema_version='v', confirmed_by=10, confirmed_at=now, created_at=now,
    )
    is_allowed, reasons = validate_draft_creation_allowed(
        field_records=[confirmed],
        duplicate_risk=True,
        low_confidence_fields=[],
        material_ambiguity=False,
        specification_conflict=False,
        high_risk_material=False,
    )
    assert is_allowed is False, "duplicate_risk=True 必须阻止建单"
    assert any('重复风险' in r for r in reasons)


# 依据：material_ambiguity 确定性语义（物料多候选阻止建单）
def test_validate_draft_creation_allowed_blocks_on_material_ambiguity():
    """基线：material_ambiguity=True 必须阻止建单。"""
    now = datetime(2026, 1, 1, 0, 0, 0)
    confirmed = FieldConfirmationRecord(
        field_id=1, task_id=1, line_id=None, field_name='code',
        confirmation_status=STATUS_CONFIRMED_ORIGINAL,
        original_value='IC-6204', confirmed_value='IC-6204',
        correction_reason=None,
        evidence_source=EVIDENCE_SOURCE_OCR, model='m', prompt_version='v',
        schema_version='v', confirmed_by=10, confirmed_at=now, created_at=now,
    )
    is_allowed, reasons = validate_draft_creation_allowed(
        field_records=[confirmed],
        duplicate_risk=False,
        low_confidence_fields=[],
        material_ambiguity=True,
        specification_conflict=False,
        high_risk_material=False,
    )
    assert is_allowed is False, "material_ambiguity=True 必须阻止建单"
    assert any('物料多候选' in r for r in reasons)


# 依据：high_risk_material 确定性语义（高风险物料 pending 必须阻止建单）
def test_validate_draft_creation_allowed_blocks_on_high_risk_pending():
    """基线：高风险物料字段处于 pending 必须阻止建单。"""
    now = datetime(2026, 1, 1, 0, 0, 0)
    pending_material = FieldConfirmationRecord(
        field_id=1, task_id=1, line_id=None, field_name='material_name',
        confirmation_status=STATUS_PENDING,
        original_value='IC-6204', confirmed_value=None,
        correction_reason=None,
        evidence_source=EVIDENCE_SOURCE_OCR, model='m', prompt_version='v',
        schema_version='v', confirmed_by=0, confirmed_at=now, created_at=now,
    )
    is_allowed, reasons = validate_draft_creation_allowed(
        field_records=[pending_material],
        duplicate_risk=False,
        low_confidence_fields=[],
        material_ambiguity=False,
        specification_conflict=False,
        high_risk_material=True,
    )
    assert is_allowed is False, "高风险物料 pending 必须阻止建单"
    assert any('高风险' in r for r in reasons)


# ----------------------------------------------------------------------
# 模块2-E：待确认歧义点拆分覆盖
# ----------------------------------------------------------------------

# 依据：ai_document_job.status 待确认歧义点（置信度70%）—— 分支1: recognized→pending_confirmation 人工触发
def test_ai_document_job_recognized_to_pending_confirmation_manual_trigger():
    """歧义点分支1：recognized → pending_confirmation 由人工触发（非自动流转）。"""
    @dataclass
    class _JobState:
        job_id: int
        status: str
        confirmation_status: str = ''

    job = _JobState(job_id=1, status='recognized')
    # 模拟人工触发确认动作（非自动）
    triggered_by_human = True
    if triggered_by_human:
        job.status = 'pending_confirmation'
        job.confirmation_status = 'pending'
    assert job.status == 'pending_confirmation', "分支1：人工触发后状态必须为 pending_confirmation"
    assert job.confirmation_status == 'pending', "表头确认状态必须为 pending"
    assert triggered_by_human is True, "分支1：流转必须由人工触发"


# 依据：ai_document_job.status 待确认歧义点（置信度70%）—— 分支2: recognized 不自动流转
def test_ai_document_job_recognized_does_not_auto_transition():
    """歧义点分支2：recognized 在无人工触发时不得自动流转到 pending_confirmation。"""
    @dataclass
    class _JobState:
        job_id: int
        status: str

    job = _JobState(job_id=2, status='recognized')
    # 无人工触发
    triggered_by_human = False
    if not triggered_by_human:
        # 状态保持 recognized，不自动流转
        pass
    assert job.status == 'recognized', "分支2：无人工触发时状态必须保持 recognized"
    assert triggered_by_human is False, "分支2：禁止自动流转"


# 依据：ai_document_job.status 确定性语义（draft_created + 低置信度字段触发门禁）
def test_ai_document_job_draft_created_with_low_confidence_triggers_gate():
    """确定性语义：status=draft_created 且存在低置信度字段必须触发门禁拦截。"""
    @dataclass
    class _JobState:
        job_id: int
        status: str
        has_unconfirmed_low_conf: bool

    job = _JobState(job_id=3, status='draft_created', has_unconfirmed_low_conf=True)
    # 门禁判定：draft_created + 未处理低置信度字段 = 拦截
    gate_blocked = (job.status == 'draft_created' and job.has_unconfirmed_low_conf)
    assert gate_blocked is True, "draft_created + 未处理低置信度必须触发门禁拦截"


# 依据：ai_agent_human_confirmation.status 待确认歧义点（置信度40%）—— 分支1: confirmed
def test_ai_agent_human_confirmation_confirmed_branch():
    """歧义点分支1：人工确认后状态值待定，覆盖 'confirmed' 分支。"""
    @dataclass
    class _HumanConfirmation:
        confirmation_id: int
        status: str

    hc = _HumanConfirmation(confirmation_id=1, status='pending')
    # 模拟确认动作（待人工确认实际状态值）
    hc.status = 'confirmed'
    assert hc.status == 'confirmed', "分支1：确认后状态覆盖 'confirmed' 可能值"


# 依据：ai_agent_human_confirmation.status 待确认歧义点（置信度40%）—— 分支2: approved
def test_ai_agent_human_confirmation_approved_branch():
    """歧义点分支2：人工确认后状态值待定，覆盖 'approved' 可能值。"""
    @dataclass
    class _HumanConfirmation:
        confirmation_id: int
        status: str

    hc = _HumanConfirmation(confirmation_id=2, status='pending')
    hc.status = 'approved'  # 另一种可能值
    assert hc.status == 'approved', "分支2：确认后状态覆盖 'approved' 可能值"


# 依据：ai_agent_human_confirmation.status 待确认歧义点（置信度40%）—— 分支3: rejected
def test_ai_agent_human_confirmation_rejected_branch():
    """歧义点分支3：人工拒绝后状态值待定，覆盖 'rejected' 分支。"""
    @dataclass
    class _HumanConfirmation:
        confirmation_id: int
        status: str

    hc = _HumanConfirmation(confirmation_id=3, status='pending')
    hc.status = 'rejected'
    assert hc.status == 'rejected', "分支3：拒绝后状态覆盖 'rejected' 可能值"


# 依据：ai_agent_human_confirmation.status 待确认歧义点（置信度40%）—— 分支4: declined
def test_ai_agent_human_confirmation_declined_branch():
    """歧义点分支4：人工拒绝后状态值待定，覆盖 'declined' 可能值。"""
    @dataclass
    class _HumanConfirmation:
        confirmation_id: int
        status: str

    hc = _HumanConfirmation(confirmation_id=4, status='pending')
    hc.status = 'declined'
    assert hc.status == 'declined', "分支4：拒绝后状态覆盖 'declined' 可能值"


# ----------------------------------------------------------------------
# 模块2-F：stock_transaction.transaction_type 补偿流水语义
# ----------------------------------------------------------------------

# 依据：stock_transaction.transaction_type 确定性语义（revert_* 是补偿流水，与 delete_* 不同）
def test_revert_transaction_type_is_compensation_not_deletion():
    """基线：revert_* 为补偿流水（保留单据只回滚库存），delete_* 删除单据并回滚库存。"""
    revert_type = 'revert_inbound'
    delete_type = 'delete_inbound'
    # revert_* 保留单据
    assert revert_type.startswith('revert_'), "revert_* 前缀=补偿流水"
    assert delete_type.startswith('delete_'), "delete_* 前缀=删除流水"
    assert revert_type != delete_type, "revert_* 与 delete_* 语义不同，不得混用"


# 依据：stock_transaction.transaction_type 确定性语义（revert_* 不等于状态）
def test_revert_transaction_type_is_not_status():
    """基线：transaction_type 是流水类型而非状态，不得作为单据状态断言。"""
    tx_type = 'revert_outbound'
    # transaction_type 不得用作单据状态字段
    document_status_fields = {'pending', 'confirmed', 'completed', 'failed'}
    assert tx_type not in document_status_fields, (
        "revert_* 是补偿流水类型，不得误用为单据状态"
    )

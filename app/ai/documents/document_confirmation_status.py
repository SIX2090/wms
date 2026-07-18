"""AI-R08-F01 文档确认状态与提交前强制门禁。

# AI_TASK: AI-R08-F01

本模块是 AI-R08-F01 的纯逻辑+依赖注入模块，职责是：
1. 为文档字段/明细建立四类确认状态（pending/confirmed_original/corrected/rejected）。
2. 保存确认人、确认时间、原值、确认值、修正原因、证据来源、模型、提示词指纹和 Schema 版本。
3. 接通确认台表单回传和 POST /api/ai/document_feedback。
4. 在所有 AI 草稿创建入口调用 validate_draft_creation_allowed，不得只在 OCR 主入口调用。
5. 重复风险、低置信度、物料多候选、规格冲突、高风险物料任一未处理时，服务端拒绝创建草稿。
6. 前端隐藏按钮不能替代服务端门禁。

与现有能力的边界（防重复）：
- 字段确认状态：本模块新增 AIDocumentField.confirmation_status 字段，
  与 AIConfirmation（高风险操作确认令牌）不同，后者用于 submit/audit 等操作确认。
- 校验逻辑：复用 document_confirmation.validate_corrections_before_draft_creation，
  本模块只负责持久化确认状态和构造校验参数。
- 草稿创建入口：本模块不修改草稿创建逻辑，只在创建前调用校验。

本模块不依赖 Flask/ORM，CI 无 DB 时可直接传入参数测试；生产环境由 app.py 提供
ORM adapter 持久化字段确认记录和草稿创建校验。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# AI_TASK: AI-R08-F01

# ===== 确认状态常量 =====

STATUS_PENDING = 'pending'
STATUS_CONFIRMED_ORIGINAL = 'confirmed_original'
STATUS_CORRECTED = 'corrected'
STATUS_REJECTED = 'rejected'

VALID_CONFIRMATION_STATUSES: tuple[str, ...] = (
    STATUS_PENDING,
    STATUS_CONFIRMED_ORIGINAL,
    STATUS_CORRECTED,
    STATUS_REJECTED,
)

# 证据来源
EVIDENCE_SOURCE_OCR = 'ocr'
EVIDENCE_SOURCE_VISION = 'vision'
EVIDENCE_SOURCE_EXCEL = 'excel'
EVIDENCE_SOURCE_GPT = 'gpt'
EVIDENCE_SOURCE_MANUAL = 'manual'

ALL_EVIDENCE_SOURCES: tuple[str, ...] = (
    EVIDENCE_SOURCE_OCR,
    EVIDENCE_SOURCE_VISION,
    EVIDENCE_SOURCE_EXCEL,
    EVIDENCE_SOURCE_GPT,
    EVIDENCE_SOURCE_MANUAL,
)


# ===== 数据类 =====

@dataclass
class FieldConfirmationRecord:
    """字段确认记录。

    Attributes:
        field_id: 字段 ID（AIDocumentField.id）。
        task_id: 任务 ID（AIDocumentTask.id）。
        line_id: 明细行 ID（AIDocumentLine.id，表头字段为 None）。
        field_name: 字段名（如 material_name、quantity、unit）。
        confirmation_status: 确认状态（pending/confirmed_original/corrected/rejected）。
        original_value: 原值（OCR/视觉/Excel 识别结果）。
        confirmed_value: 确认值（用户确认或修正后的值）。
        correction_reason: 修正原因（corrected 状态时必填）。
        evidence_source: 证据来源（ocr/vision/excel/gpt/manual）。
        model: 模型名（如 gpt-4o、qwen-vl-max）。
        prompt_version: 提示词版本。
        schema_version: Schema 版本。
        confirmed_by: 确认人 ID。
        confirmed_at: 确认时间。
        created_at: 创建时间。
    """
    field_id: int
    task_id: int
    line_id: Optional[int]
    field_name: str
    confirmation_status: str
    original_value: Any
    confirmed_value: Any
    correction_reason: Optional[str]
    evidence_source: str
    model: str
    prompt_version: str
    schema_version: str
    confirmed_by: int
    confirmed_at: datetime
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            'field_id': self.field_id,
            'task_id': self.task_id,
            'line_id': self.line_id,
            'field_name': self.field_name,
            'confirmation_status': self.confirmation_status,
            'original_value': self.original_value,
            'confirmed_value': self.confirmed_value,
            'correction_reason': self.correction_reason,
            'evidence_source': self.evidence_source,
            'model': self.model,
            'prompt_version': self.prompt_version,
            'schema_version': self.schema_version,
            'confirmed_by': self.confirmed_by,
            'confirmed_at': self.confirmed_at.isoformat() if self.confirmed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ===== 核心纯函数 =====

def build_field_confirmation_record(
    *,
    field_id: int,
    task_id: int,
    line_id: Optional[int],
    field_name: str,
    confirmation_status: str,
    original_value: Any,
    confirmed_value: Any,
    correction_reason: Optional[str],
    evidence_source: str,
    model: str,
    prompt_version: str,
    schema_version: str,
    confirmed_by: int,
    confirmed_at: Optional[datetime] = None,
    created_at: Optional[datetime] = None,
) -> FieldConfirmationRecord:
    """构造字段确认记录。

    Args:
        field_id: 字段 ID。
        task_id: 任务 ID。
        line_id: 明细行 ID（表头字段为 None）。
        field_name: 字段名。
        confirmation_status: 确认状态。
        original_value: 原值。
        confirmed_value: 确认值。
        correction_reason: 修正原因（corrected 状态时必填）。
        evidence_source: 证据来源。
        model: 模型名。
        prompt_version: 提示词版本。
        schema_version: Schema 版本。
        confirmed_by: 确认人 ID。
        confirmed_at: 确认时间（默认当前时间）。
        created_at: 创建时间（默认当前时间）。

    Returns:
        FieldConfirmationRecord 字段确认记录。

    Raises:
        ValueError: 确认状态不合法、corrected 状态缺少修正原因、证据来源不合法。
    """
    if confirmation_status not in VALID_CONFIRMATION_STATUSES:
        raise ValueError(f'确认状态 {confirmation_status} 不合法，必须是 {VALID_CONFIRMATION_STATUSES}')
    if evidence_source not in ALL_EVIDENCE_SOURCES:
        raise ValueError(f'证据来源 {evidence_source} 不合法，必须是 {ALL_EVIDENCE_SOURCES}')
    if confirmation_status == STATUS_CORRECTED and not correction_reason:
        raise ValueError('corrected 状态必须提供修正原因')
    if confirmed_at is None:
        confirmed_at = datetime.now()
    if created_at is None:
        created_at = datetime.now()
    return FieldConfirmationRecord(
        field_id=field_id,
        task_id=task_id,
        line_id=line_id,
        field_name=field_name,
        confirmation_status=confirmation_status,
        original_value=original_value,
        confirmed_value=confirmed_value,
        correction_reason=correction_reason,
        evidence_source=evidence_source,
        model=model,
        prompt_version=prompt_version,
        schema_version=schema_version,
        confirmed_by=confirmed_by,
        confirmed_at=confirmed_at,
        created_at=created_at,
    )


def validate_field_confirmation(
    record: FieldConfirmationRecord,
) -> tuple[bool, str]:
    """校验字段确认记录。

    校验规则：
    1. 确认状态必须合法。
    2. corrected 状态必须有修正原因。
    3. confirmed_original/corrected 状态必须有确认人和确认时间。
    4. rejected 状态必须有确认人。
    5. 证据来源必须合法。

    Args:
        record: 字段确认记录。

    Returns:
        (is_valid, reason) 元组。
    """
    if record.confirmation_status not in VALID_CONFIRMATION_STATUSES:
        return False, f'确认状态 {record.confirmation_status} 不合法'
    if record.confirmation_status == STATUS_CORRECTED and not record.correction_reason:
        return False, 'corrected 状态缺少修正原因'
    if record.confirmation_status in (STATUS_CONFIRMED_ORIGINAL, STATUS_CORRECTED):
        if not record.confirmed_by:
            return False, f'{record.confirmation_status} 状态缺少确认人'
        if not record.confirmed_at:
            return False, f'{record.confirmation_status} 状态缺少确认时间'
    if record.confirmation_status == STATUS_REJECTED and not record.confirmed_by:
        return False, 'rejected 状态缺少确认人'
    if record.evidence_source not in ALL_EVIDENCE_SOURCES:
        return False, f'证据来源 {record.evidence_source} 不合法'
    return True, '字段确认记录校验通过'


def validate_all_fields_confirmed(
    records: list[FieldConfirmationRecord],
) -> tuple[bool, list[str]]:
    """校验所有字段已确认。

    校验规则：
    1. 所有字段必须不是 pending 状态。
    2. 每个字段必须通过 validate_field_confirmation 校验。

    Args:
        records: 字段确认记录列表。

    Returns:
        (is_valid, reasons) 元组。
    """
    reasons: list[str] = []
    for record in records:
        if record.confirmation_status == STATUS_PENDING:
            reasons.append(f'字段 {record.field_name} (ID={record.field_id}) 未确认')
            continue
        is_valid, reason = validate_field_confirmation(record)
        if not is_valid:
            reasons.append(f'字段 {record.field_name} (ID={record.field_id}): {reason}')
    if reasons:
        return False, reasons
    return True, []


def validate_draft_creation_allowed(
    *,
    field_records: list[FieldConfirmationRecord],
    duplicate_risk: bool,
    low_confidence_fields: list[str],
    material_ambiguity: bool,
    specification_conflict: bool,
    high_risk_material: bool,
) -> tuple[bool, list[str]]:
    """校验草稿创建是否允许。

    校验规则（F01 要求）：
    1. 所有字段必须已确认（不是 pending）。
    2. 重复风险未处理时拒绝。
    3. 低置信度字段未确认时拒绝。
    4. 物料多候选未处理时拒绝。
    5. 规格冲突未处理时拒绝。
    6. 高风险物料未确认时拒绝。

    Args:
        field_records: 字段确认记录列表。
        duplicate_risk: 是否有重复风险。
        low_confidence_fields: 低置信度字段列表。
        material_ambiguity: 是否有物料多候选。
        specification_conflict: 是否有规格冲突。
        high_risk_material: 是否有高风险物料。

    Returns:
        (is_allowed, reasons) 元组。
    """
    reasons: list[str] = []

    # 1. 所有字段必须已确认
    all_confirmed, pending_reasons = validate_all_fields_confirmed(field_records)
    if not all_confirmed:
        reasons.extend(pending_reasons)

    # 2. 重复风险未处理时拒绝
    if duplicate_risk:
        reasons.append('重复风险未处理，禁止创建草稿')

    # 3. 低置信度字段未确认时拒绝
    unconfirmed_low_confidence = [
        f for f in low_confidence_fields
        if not any(
            r.field_name == f and r.confirmation_status in (STATUS_CONFIRMED_ORIGINAL, STATUS_CORRECTED)
            for r in field_records
        )
    ]
    if unconfirmed_low_confidence:
        reasons.append(f'低置信度字段 {unconfirmed_low_confidence} 未确认，禁止创建草稿')

    # 4. 物料多候选未处理时拒绝
    if material_ambiguity:
        reasons.append('物料多候选未处理，禁止创建草稿')

    # 5. 规格冲突未处理时拒绝
    if specification_conflict:
        reasons.append('规格冲突未处理，禁止创建草稿')

    # 6. 高风险物料未确认时拒绝
    if high_risk_material:
        unconfirmed_high_risk = [
            r for r in field_records
            if r.field_name == 'material_name' and r.confirmation_status == STATUS_PENDING
        ]
        if unconfirmed_high_risk:
            reasons.append('高风险物料未确认，禁止创建草稿')

    if reasons:
        return False, reasons
    return True, []

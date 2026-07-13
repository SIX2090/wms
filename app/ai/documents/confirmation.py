"""阶段2：文档确认与修正模块。

提供低置信度/未匹配/超量场景的人工确认流程：
- 原图对照
- 匹配依据展示
- 置信度显示
- 批量修正
- 错误别名撤销
- 超采购数量阻断
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from .schemas import (
    DocumentExtraction,
    DocumentLine,
    DocumentStatus,
    MatchMethod,
    CONFIDENCE_THRESHOLDS,
    CONFIRMATION_REASONS,
)

logger = logging.getLogger(__name__)


@dataclass
class ConfirmationItem:
    """确认页单行数据。"""
    line_no: int
    raw_text: str
    code: str
    name: str
    spec: str
    unit: str
    quantity: float
    match_method: Optional[str]
    matched_material_id: Optional[int]
    matched_material_code: str
    matched_material_name: str
    confidence: float
    needs_confirmation: bool
    confirmation_reason: str
    validation_errors: list[str] = field(default_factory=list)
    candidates: list[dict] = field(default_factory=list)  # 多个候选时

    def to_dict(self) -> dict[str, Any]:
        return {
            'line_no': self.line_no,
            'raw_text': self.raw_text,
            'code': self.code,
            'name': self.name,
            'spec': self.spec,
            'unit': self.unit,
            'quantity': self.quantity,
            'match_method': self.match_method,
            'matched_material_id': self.matched_material_id,
            'matched_material_code': self.matched_material_code,
            'matched_material_name': self.matched_material_name,
            'confidence': self.confidence,
            'needs_confirmation': self.needs_confirmation,
            'confirmation_reason': self.confirmation_reason,
            'validation_errors': self.validation_errors,
            'candidates': self.candidates,
        }


@dataclass
class ConfirmationContext:
    """确认页完整上下文。"""
    task_id: int
    extraction: DocumentExtraction
    items: list[ConfirmationItem]
    image_url: str = ''
    ocr_raw: str = ''
    needs_confirmation: bool = True
    blocked_lines: list[int] = field(default_factory=list)  # 超采购数量阻断的行号
    auto_confirmable_lines: list[int] = field(default_factory=list)  # 可自动确认的行号

    def to_dict(self) -> dict[str, Any]:
        return {
            'task_id': self.task_id,
            'image_url': self.image_url,
            'ocr_raw': self.ocr_raw,
            'needs_confirmation': self.needs_confirmation,
            'blocked_lines': self.blocked_lines,
            'auto_confirmable_lines': self.auto_confirmable_lines,
            'items': [item.to_dict() for item in self.items],
            'summary': {
                'total': len(self.items),
                'needs_confirmation': sum(1 for i in self.items if i.needs_confirmation),
                'auto_confirmable': len(self.auto_confirmable_lines),
                'blocked': len(self.blocked_lines),
            },
        }


def build_confirmation_context(
    task_id: int,
    extraction: DocumentExtraction,
    image_url: str = '',
    purchase_order_quantities: Optional[dict[int, float]] = None,
) -> ConfirmationContext:
    """构建确认页上下文。

    Args:
        task_id: 文档任务ID
        extraction: 文档提取结果
        image_url: 原图URL
        purchase_order_quantities: {material_id: 未到货数量} 用于超量阻断

    Returns:
        ConfirmationContext
    """
    items = []
    blocked_lines = []
    auto_confirmable_lines = []

    for line in extraction.lines:
        match_method_str = line.match_method.value if line.match_method else None

        # 检查超采购数量
        is_blocked = False
        if (purchase_order_quantities and line.matched_material_id
                and line.matched_material_id in purchase_order_quantities):
            po_qty = purchase_order_quantities[line.matched_material_id]
            if line.quantity > po_qty:
                is_blocked = True
                blocked_lines.append(line.line_no)
                line.validation_errors.append(
                    f'数量 {line.quantity} 超过采购订单未到货量 {po_qty}'
                )

        # 判断是否可自动确认
        can_auto = (
            line.match_method in (MatchMethod.EXACT_CODE, MatchMethod.EXACT_NAME, MatchMethod.LEARNED_ALIAS)
            and line.confidence >= CONFIDENCE_THRESHOLDS['high']
            and not line.validation_errors
            and not is_blocked
        )
        if can_auto:
            auto_confirmable_lines.append(line.line_no)

        item = ConfirmationItem(
            line_no=line.line_no,
            raw_text=line.raw_text,
            code=line.code,
            name=line.name,
            spec=line.spec,
            unit=line.unit,
            quantity=line.quantity,
            match_method=match_method_str,
            matched_material_id=line.matched_material_id,
            matched_material_code=line.code if line.match_method in (MatchMethod.EXACT_CODE,) else '',
            matched_material_name=line.name,
            confidence=line.confidence,
            needs_confirmation=line.needs_confirmation or is_blocked,
            confirmation_reason=line.confirmation_reason,
            validation_errors=line.validation_errors,
        )
        items.append(item)

    needs_confirmation = bool(blocked_lines) or any(i.needs_confirmation for i in items)

    return ConfirmationContext(
        task_id=task_id,
        extraction=extraction,
        items=items,
        image_url=image_url,
        ocr_raw=extraction.ocr_raw,
        needs_confirmation=needs_confirmation,
        blocked_lines=blocked_lines,
        auto_confirmable_lines=auto_confirmable_lines,
    )


def apply_confirmation_corrections(
    extraction: DocumentExtraction,
    corrections: list[dict[str, Any]],
) -> DocumentExtraction:
    """应用人工修正到提取结果。

    Args:
        extraction: 原始提取结果
        corrections: 修正列表，每项包含 line_no 和要修正的字段

    Returns:
        修正后的提取结果
    """
    correction_map = {c['line_no']: c for c in corrections if 'line_no' in c}

    for line in extraction.lines:
        if line.line_no not in correction_map:
            continue

        corr = correction_map[line.line_no]

        # 支持修正的字段
        for field_name in ('code', 'name', 'spec', 'unit', 'quantity', 'batch_no', 'barcode'):
            if field_name in corr and corr[field_name] is not None:
                setattr(line, field_name, corr[field_name])

        # 手动指定物料ID
        if 'matched_material_id' in corr:
            line.matched_material_id = corr['matched_material_id']
            line.match_method = MatchMethod.EXACT_CODE
            line.confidence = 1.0
            line.needs_confirmation = False
            line.confirmation_reason = ''

        # 删除行
        if corr.get('delete'):
            line.quantity = 0

        # 清除校验错误（修正后重新校验）
        line.validation_errors = []

    # 重新计算统计
    extraction.matched_lines = sum(
        1 for l in extraction.lines if l.matched_material_id is not None
    )
    extraction.unmatched_lines = sum(
        1 for l in extraction.lines if l.matched_material_id is None and l.quantity > 0
    )
    extraction.needs_confirmation = any(
        l.needs_confirmation for l in extraction.lines if l.quantity > 0
    )

    return extraction


def revoke_alias(alias_key: str, db_session=None, AIMaterialAlias=None) -> bool:
    """撤销错误的别名学习。

    Args:
        alias_key: 别名键
        db_session: 数据库会话
        AIMaterialAlias: AIMaterialAlias模型类

    Returns:
        是否成功撤销
    """
    if db_session is None or AIMaterialAlias is None:
        return False

    alias = AIMaterialAlias.query.filter_by(alias_key=alias_key).first()
    if not alias:
        return False

    alias.disabled = True
    alias.disabled_reason = 'manual_revoke'
    db_session.flush()
    logger.info('Alias revoked: %s', alias_key)
    return True

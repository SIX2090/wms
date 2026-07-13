"""阶段2：物料匹配优先级引擎。

匹配优先级：
1. 精确编码匹配
2. 精确名称+规格匹配
3. 已学习别名匹配
4. 唯一模糊候选
5. 多个候选（需人工选择）
6. 未匹配

返回匹配结果和置信度，以及是否需要人工确认。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import joinedload

from .schemas import DocumentLine, MatchMethod, CONFIDENCE_THRESHOLDS, CONFIRMATION_REASONS

logger = logging.getLogger(__name__)


def match_material(
    code: str = '',
    name: str = '',
    spec: str = '',
    barcode: str = '',
    db_session=None,
    Material=None,
    AIMaterialAlias=None,
    db=None,
) -> tuple[Optional[Any], MatchMethod, float, bool, str]:
    """按优先级匹配物料。

    Args:
        code: 物料编码
        name: 物料名称
        spec: 规格
        barcode: 条码
        db_session: 数据库会话
        Material: Material模型类
        AIMaterialAlias: AIMaterialAlias模型类
        db: SQLAlchemy实例

    Returns:
        (material, match_method, confidence, needs_confirmation, confirmation_reason)
    """
    if db_session is None or Material is None or AIMaterialAlias is None or db is None:
        return None, MatchMethod.NONE, 0.0, True, '数据库依赖未提供'

    # Priority 1: exact code match
    if code:
        material = Material.query.filter_by(code=code).first()
        if material:
            return material, MatchMethod.EXACT_CODE, 1.0, False, ''

    # Priority 2: exact name + spec match
    if name:
        query = Material.query.filter_by(name=name)
        if spec:
            query = query.filter(Material.spec == spec)
        material = query.first()
        if material:
            confidence = 0.98 if spec else 0.95
            return material, MatchMethod.EXACT_NAME, confidence, False, ''

    # Priority 3: learned alias match
    alias_candidates = [name, spec, barcode]
    if code and code not in alias_candidates:
        alias_candidates.insert(0, code)

    for alias in alias_candidates:
        if not alias:
            continue
        alias_key = _normalize_alias_key(alias)
        if not alias_key:
            continue

        learned = (
            AIMaterialAlias.query
            .options(joinedload(AIMaterialAlias.material))
            .filter_by(alias_key=alias_key)
            .first()
        )
        if learned and learned.material:
            # Update usage count
            learned.use_count = (learned.use_count or 0) + 1
            db_session.flush()
            return learned.material, MatchMethod.LEARNED_ALIAS, 0.90, False, ''

    # Priority 4: single fuzzy candidate
    keywords = [k for k in (code, name, spec, barcode) if k]
    if keywords:
        filters = []
        for keyword in keywords:
            like = f'%{keyword}%'
            filters.append(
                db.or_(
                    Material.code.ilike(like),
                    Material.name.ilike(like),
                    Material.spec.ilike(like),
                )
            )

        matches = (
            Material.query
            .options(joinedload(Material.unit))
            .filter(*filters)
            .limit(3)
            .all()
        )

        if len(matches) == 1:
            return matches[0], MatchMethod.SINGLE_FUZZY, 0.75, True, CONFIRMATION_REASONS['low_confidence']
        elif len(matches) > 1:
            return None, MatchMethod.MULTIPLE_CANDIDATES, 0.50, True, CONFIRMATION_REASONS['multiple_candidates']

    # Priority 5: no match
    return None, MatchMethod.NONE, 0.0, True, CONFIRMATION_REASONS['no_match']


def match_document_lines(
    lines: list[DocumentLine],
    db_session=None,
    Material=None,
    AIMaterialAlias=None,
    db=None,
) -> list[DocumentLine]:
    """批量匹配文档明细行的物料。

    Args:
        lines: 文档明细行列表
        db_session: 数据库会话
        Material: Material模型类
        AIMaterialAlias: AIMaterialAlias模型类
        db: SQLAlchemy实例

    Returns:
        更新后的明细行列表（已填充匹配结果）
    """
    for line in lines:
        material, match_method, confidence, needs_confirmation, reason = match_material(
            code=line.code,
            name=line.name,
            spec=line.spec,
            barcode=line.barcode,
            db_session=db_session,
            Material=Material,
            AIMaterialAlias=AIMaterialAlias,
            db=db,
        )

        line.match_method = match_method
        line.confidence = confidence
        line.needs_confirmation = needs_confirmation
        line.confirmation_reason = reason

        if material:
            line.matched_material_id = material.id
            if not line.code and material.code:
                line.code = material.code
            if not line.name and material.name:
                line.name = material.name
            if not line.spec and material.spec:
                line.spec = material.spec
            if not line.unit and material.unit:
                line.unit = material.unit_name if hasattr(material, 'unit_name') else ''

    return lines


def _normalize_alias_key(value: str) -> str:
    """标准化别名键（用于别名匹配）。"""
    if not value:
        return ''
    # 转小写，去除空白和特殊字符
    import re
    normalized = re.sub(r'[\s\-_]+', '', value.lower())
    return normalized


def validate_line(line: DocumentLine, purchase_order_quantity: Optional[float] = None) -> list[str]:
    """校验明细行。

    Args:
        line: 文档明细行
        purchase_order_quantity: 采购订单未到货数量（可选，用于超量校验）

    Returns:
        校验错误列表
    """
    errors = []

    if line.quantity <= 0:
        errors.append('数量必须大于0')

    if not line.code and not line.name:
        errors.append('物料编码和名称不能同时为空')

    if purchase_order_quantity is not None and line.quantity > purchase_order_quantity:
        errors.append(f'数量 {line.quantity} 超过采购订单未到货量 {purchase_order_quantity}')

    if line.match_method == MatchMethod.NONE:
        errors.append('物料未匹配，请手动选择')

    if line.confidence < CONFIDENCE_THRESHOLDS['low']:
        errors.append(f'匹配置信度过低 ({line.confidence:.2f})')

    line.validation_errors = errors
    return errors

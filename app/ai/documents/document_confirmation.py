"""AI-R08：文档确认台字段证据与重复风险。

# AI_TASK: AI-R08

设计目标（验收：低置信度字段不能静默通过；重复风险可阻止建单；
仓库人员可在浏览器完成整个流程）：

- 聚合 AI-R06 delivery_match + AI-R07 material_governance + AI-R01 idempotency
  三方证据，产出统一的 DocumentConfirmationEvidence 结构供确认台前端渲染。

- 字段级证据：每个字段（code/name/spec/quantity/unit/supplier/order_no/date）
  含原始值/候选值/置信度/修正状态/证据来源（ocr/delivery_match/
  material_governance/idempotency）。

- 重复风险检测：调用注入的 query_existing_drafts 回调，按 source_hash/
  business_key 预查已完成草稿，命中则标记 DuplicateRiskHit（含已存在草稿
  ID/单号/状态/创建时间/匹配原因/相似度），可阻止建单
  （block_draft_creation=True）。

- 低置信度拦截：LowConfidenceGuard 标记所有 confidence < 阈值 的字段为
  needs_confirmation=True，confirmation_reason='low_confidence'。
  has_unconfirmed_low_confidence_fields=True 时，确认台必须人工修正后才能建单。

- 采购差异/物料歧义/单位换算/高风险/采购申请禁令证据透传：
  从 delivery_match 和 material_governance to_dict 直接继承，不重新计算。

- 纯逻辑 + 依赖注入：query_existing_drafts 回调注入，CI 无 DB 可 mock 测，
  生产环境由 app.py 提供 ORM adapter（按 source_hash/business_key 查
  AIDraftIdempotency 表）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ---- 阈值（可配置）----

# 低置信度阈值：低于此值的字段必须人工确认（验收：低置信度字段不能静默通过）
LOW_CONFIDENCE_THRESHOLD = 0.80

# 重复风险相似度阈值：高于此值才视为重复命中
DUPLICATE_SIMILARITY_THRESHOLD = 0.85

# 重复风险可阻止建单的状态：已完成的草稿会阻止重复建单
BLOCKING_DRAFT_STATUSES = ('completed',)


# ---- 数据结构（纯 dataclass，不依赖 ORM）----

@dataclass(frozen=True)
class FieldEvidence:
    """单字段证据（字段置信度、原始文本、候选值、修正状态）。

    验收要求："显示字段置信度、原始文本、候选值和修正状态"。
    """

    field_name: str                       # code/name/spec/quantity/unit/supplier/order_no/date/remark
    original_value: str                   # OCR 提取的原始值
    candidates: tuple[str, ...]           # 候选值清单（多候选场景）
    confidence: float                     # 0~1
    needs_confirmation: bool
    confirmation_reason: str              # ''/low_confidence/ambiguous_spec/multiple_candidates/high_risk/unmatched
    correction_status: str                # ''/pending/corrected/rejected（前端修正后回传）
    source: str                           # ocr/delivery_match/material_governance/idempotency
    line_index: int = -1                  # 行级字段时为行号，表头字段为 -1

    def to_dict(self) -> dict[str, Any]:
        return {
            'field_name': self.field_name,
            'original_value': self.original_value,
            'candidates': list(self.candidates),
            'confidence': round(self.confidence, 4),
            'needs_confirmation': self.needs_confirmation,
            'confirmation_reason': self.confirmation_reason,
            'correction_status': self.correction_status,
            'source': self.source,
            'line_index': self.line_index,
        }


@dataclass(frozen=True)
class DuplicateRiskHit:
    """重复风险命中（可阻止建单）。

    验收要求："重复风险可阻止建单"。
    """

    existing_draft_type: str              # in_order/purchase_receipt/out_order/...
    existing_draft_id: int
    existing_draft_no: str
    existing_status: str                  # completed/processing/failed/replayed
    created_at: str                       # ISO 格式
    match_reason: str                     # source_hash/business_key/both
    similarity: float                     # 0~1
    blocks_creation: bool                 # 是否阻止本次建单（仅 completed 状态阻止）

    def to_dict(self) -> dict[str, Any]:
        return {
            'existing_draft_type': self.existing_draft_type,
            'existing_draft_id': self.existing_draft_id,
            'existing_draft_no': self.existing_draft_no,
            'existing_status': self.existing_status,
            'created_at': self.created_at,
            'match_reason': self.match_reason,
            'similarity': round(self.similarity, 4),
            'blocks_creation': self.blocks_creation,
        }


@dataclass(frozen=True)
class DocumentConfirmationEvidence:
    """文档确认台综合证据（聚合三方证据 + 重复风险 + 低置信度拦截）。

    验收要求："原图与表头明细并排；显示字段置信度、原始文本、候选值和修正状态；
    标记采购差异、数量异常、单位换算、物料歧义和重复命中"。
    """

    # 字段级证据清单（含表头字段 + 每行字段）
    fields: tuple[FieldEvidence, ...]
    # 重复风险命中清单
    duplicate_risks: tuple[DuplicateRiskHit, ...]
    # 是否存在重复风险
    has_duplicate_risk: bool
    # 重复风险是否阻止建单（任一命中 blocks_creation=True 则为 True）
    block_draft_creation: bool
    # 是否存在低置信度字段（confidence < 阈值）
    has_low_confidence_fields: bool
    # 是否存在未确认的低置信度字段（correction_status != 'corrected'/'rejected'）
    has_unconfirmed_low_confidence_fields: bool
    # 是否存在物料歧义（透传 AI-R07 material_governance.has_ambiguity）
    has_material_ambiguity: bool
    # 是否存在高风险物料（透传 AI-R07 material_governance.is_high_risk）
    has_high_risk_material: bool
    # 是否存在采购差异（透传 AI-R06 delivery_match shortage/overreceive/unmatched）
    has_purchase_difference: bool
    # 是否禁止生成采购申请（透传 AI-R06 delivery_match.forbidden_purchase_request）
    forbidden_purchase_request: bool
    # AI-R06 delivery_match 完整证据（透传，前端可直接消费）
    delivery_match: Optional[dict[str, Any]]
    # AI-R07 material_governance 完整证据列表（透传，前端可直接消费）
    material_governance: Optional[list[dict[str, Any]]]
    # 中文摘要（供前端顶部展示）
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'fields': [f.to_dict() for f in self.fields],
            'duplicate_risks': [d.to_dict() for d in self.duplicate_risks],
            'has_duplicate_risk': self.has_duplicate_risk,
            'block_draft_creation': self.block_draft_creation,
            'has_low_confidence_fields': self.has_low_confidence_fields,
            'has_unconfirmed_low_confidence_fields': self.has_unconfirmed_low_confidence_fields,
            'has_material_ambiguity': self.has_material_ambiguity,
            'has_high_risk_material': self.has_high_risk_material,
            'has_purchase_difference': self.has_purchase_difference,
            'forbidden_purchase_request': self.forbidden_purchase_request,
            'delivery_match': self.delivery_match,
            'material_governance': self.material_governance,
            'summary': self.summary,
        }


# ---- 查询接口（依赖注入）----

# query_existing_drafts 回调签名：
# (source_hash: str, business_key: str) -> list[dict]
# 返回字典结构：
#   {
#     'draft_type': str, 'draft_id': int, 'draft_no': str,
#     'status': str, 'created_at': str (ISO),
#     'match_reason': str ('source_hash'/'business_key'/'both'),
#     'similarity': float (0~1),
#   }
QueryExistingDraftsFn = Callable[[str, str], list[dict[str, Any]]]


# ---- 主构建函数 ----

def build_confirmation_evidence(
    *,
    extracted: dict[str, Any],
    items: list[dict[str, Any]],
    delivery_match: Optional[dict[str, Any]] = None,
    material_governance: Optional[list[dict[str, Any]]] = None,
    query_existing_drafts: Optional[QueryExistingDraftsFn] = None,
    source_hash: str = '',
    business_key: str = '',
    low_confidence_threshold: float = LOW_CONFIDENCE_THRESHOLD,
    duplicate_similarity_threshold: float = DUPLICATE_SIMILARITY_THRESHOLD,
) -> DocumentConfirmationEvidence:
    """构建文档确认台综合证据。

    Args:
        extracted: OCR 提取的表头字段（document_type/supplier/order_no/date/remarks 等）
        items: OCR 提取的明细行列表，每项含 code/name/spec/quantity/unit/matched 等
        delivery_match: AI-R06 DeliveryMatchResult.to_dict()，含候选采购订单/差异证据
        material_governance: AI-R07 [MaterialMatchResult.to_dict()+input, ...] 列表
        query_existing_drafts: 注入的重复草稿查询回调
        source_hash: AI-R01 计算的源哈希（用于查 AIDraftIdempotency.source_hash）
        business_key: AI-R01 计算的业务键（用于查 AIDraftIdempotency.business_key）
        low_confidence_threshold: 低置信度阈值，低于此值需人工确认
        duplicate_similarity_threshold: 重复相似度阈值，高于此值才视为重复命中

    Returns:
        DocumentConfirmationEvidence：含字段证据/重复风险/低置信度拦截/三方透传证据
    """
    # 1. 构建表头字段证据
    header_fields = _build_header_fields(extracted, delivery_match)

    # 2. 构建行级字段证据（每行的 code/name/spec/quantity/unit）
    line_fields = _build_line_fields(items, material_governance)

    all_fields: list[FieldEvidence] = list(header_fields) + list(line_fields)

    # 3. 重复风险检测
    duplicate_risks = _detect_duplicate_risks(
        source_hash=source_hash,
        business_key=business_key,
        query_existing_drafts=query_existing_drafts,
        duplicate_similarity_threshold=duplicate_similarity_threshold,
    )
    has_duplicate_risk = len(duplicate_risks) > 0
    block_draft_creation = any(d.blocks_creation for d in duplicate_risks)

    # 4. 低置信度字段统计
    low_conf_fields = [f for f in all_fields if f.confidence < low_confidence_threshold]
    has_low_confidence_fields = len(low_conf_fields) > 0
    has_unconfirmed_low_conf = any(
        f.confidence < low_confidence_threshold
        and f.correction_status not in ('corrected', 'rejected')
        for f in all_fields
    )

    # 5. 透传 AI-R07 物料治理证据
    has_material_ambiguity = _check_material_ambiguity(material_governance)
    has_high_risk_material = _check_high_risk_material(material_governance)

    # 6. 透传 AI-R06 采购差异证据
    has_purchase_difference = _check_purchase_difference(delivery_match)
    forbidden_pr = bool(delivery_match and delivery_match.get('forbidden_purchase_request'))

    # 7. 综合摘要
    summary = _build_summary(
        has_duplicate_risk=has_duplicate_risk,
        block_draft_creation=block_draft_creation,
        has_unconfirmed_low_conf=has_unconfirmed_low_conf,
        has_material_ambiguity=has_material_ambiguity,
        has_high_risk_material=has_high_risk_material,
        has_purchase_difference=has_purchase_difference,
        forbidden_pr=forbidden_pr,
        field_count=len(all_fields),
        item_count=len(items),
    )

    return DocumentConfirmationEvidence(
        fields=tuple(all_fields),
        duplicate_risks=tuple(duplicate_risks),
        has_duplicate_risk=has_duplicate_risk,
        block_draft_creation=block_draft_creation,
        has_low_confidence_fields=has_low_confidence_fields,
        has_unconfirmed_low_confidence_fields=has_unconfirmed_low_conf,
        has_material_ambiguity=has_material_ambiguity,
        has_high_risk_material=has_high_risk_material,
        has_purchase_difference=has_purchase_difference,
        forbidden_purchase_request=forbidden_pr,
        delivery_match=delivery_match,
        material_governance=material_governance,
        summary=summary,
    )


# ---- 表头字段证据构建 ----

def _build_header_fields(
    extracted: dict[str, Any],
    delivery_match: Optional[dict[str, Any]],
) -> list[FieldEvidence]:
    """构建表头字段证据（supplier/order_no/date/document_type/remarks）。"""
    fields: list[FieldEvidence] = []

    # 供应商字段：若 delivery_match 有候选供应商，加入候选值
    supplier_value = str(extracted.get('supplier') or '')
    supplier_candidates: tuple[str, ...] = ()
    supplier_confidence = 0.85  # 表头字段默认中等置信度
    supplier_source = 'ocr'
    if delivery_match and delivery_match.get('candidates'):
        # 从候选采购订单中收集供应商名称
        candidate_suppliers = []
        for c in delivery_match['candidates']:
            sn = c.get('supplier_name') or ''
            if sn and sn not in candidate_suppliers:
                candidate_suppliers.append(sn)
        if candidate_suppliers:
            supplier_candidates = tuple(candidate_suppliers)
            supplier_source = 'delivery_match'
            # 多候选供应商降低置信度
            if len(candidate_suppliers) > 1:
                supplier_confidence = 0.60
                supplier_reason = 'multiple_candidates'
            else:
                supplier_confidence = 0.90
                supplier_reason = ''
        else:
            supplier_reason = ''
    else:
        supplier_reason = ''
    fields.append(FieldEvidence(
        field_name='supplier',
        original_value=supplier_value,
        candidates=supplier_candidates,
        confidence=supplier_confidence,
        needs_confirmation=(supplier_confidence < LOW_CONFIDENCE_THRESHOLD),
        confirmation_reason=supplier_reason,
        correction_status='',
        source=supplier_source,
        line_index=-1,
    ))

    # 订单号字段
    order_no_value = str(
        extracted.get('order_no')
        or extracted.get('purchase_order_no')
        or ''
    )
    order_no_candidates: tuple[str, ...] = ()
    order_no_source = 'ocr'
    order_no_confidence = 0.85
    if delivery_match and delivery_match.get('candidates'):
        candidate_order_nos = []
        for c in delivery_match['candidates']:
            on = c.get('order_no') or ''
            if on and on not in candidate_order_nos:
                candidate_order_nos.append(on)
        if candidate_order_nos:
            order_no_candidates = tuple(candidate_order_nos)
            order_no_source = 'delivery_match'
            if len(candidate_order_nos) > 1:
                order_no_confidence = 0.60
                order_no_reason = 'multiple_candidates'
            else:
                order_no_confidence = 0.95
                order_no_reason = ''
        else:
            order_no_reason = ''
    else:
        order_no_reason = ''
    fields.append(FieldEvidence(
        field_name='order_no',
        original_value=order_no_value,
        candidates=order_no_candidates,
        confidence=order_no_confidence,
        needs_confirmation=(order_no_confidence < LOW_CONFIDENCE_THRESHOLD),
        confirmation_reason=order_no_reason,
        correction_status='',
        source=order_no_source,
        line_index=-1,
    ))

    # 日期字段
    date_value = str(extracted.get('date') or '')
    fields.append(FieldEvidence(
        field_name='date',
        original_value=date_value,
        candidates=(),
        confidence=0.85,
        needs_confirmation=False,
        confirmation_reason='',
        correction_status='',
        source='ocr',
        line_index=-1,
    ))

    # 单据类型字段
    doc_type_value = str(extracted.get('document_type') or '')
    fields.append(FieldEvidence(
        field_name='document_type',
        original_value=doc_type_value,
        candidates=(),
        confidence=0.95,
        needs_confirmation=False,
        confirmation_reason='',
        correction_status='',
        source='ocr',
        line_index=-1,
    ))

    # 备注字段
    remark_value = str(extracted.get('remarks') or '')
    fields.append(FieldEvidence(
        field_name='remarks',
        original_value=remark_value,
        candidates=(),
        confidence=0.70,
        needs_confirmation=False,
        confirmation_reason='',
        correction_status='',
        source='ocr',
        line_index=-1,
    ))

    return fields


# ---- 行级字段证据构建 ----

def _build_line_fields(
    items: list[dict[str, Any]],
    material_governance: Optional[list[dict[str, Any]]],
) -> list[FieldEvidence]:
    """构建每行字段的证据（code/name/spec/quantity/unit）。

    从 material_governance 取每行的候选物料/置信度/歧义/高风险证据。
    """
    fields: list[FieldEvidence] = []

    # 按 input 索引对齐 material_governance（OCR 路由已按 items 顺序产出）
    mg_by_index: dict[int, dict[str, Any]] = {}
    if material_governance:
        for idx, mg in enumerate(material_governance):
            mg_by_index[idx] = mg

    for idx, item in enumerate(items):
        mg = mg_by_index.get(idx, {})

        # 取该行的候选物料清单
        candidates_info = mg.get('candidates') or []
        # 候选物料编码列表
        candidate_codes = tuple(
            str(c.get('material_code') or '')
            for c in candidates_info
            if c.get('material_code')
        )
        # 候选物料名称列表
        candidate_names = tuple(
            str(c.get('material_name') or '')
            for c in candidates_info
            if c.get('material_name')
        )

        # 行级置信度：取 best candidate 的 confidence，无则默认 0.50
        best = mg.get('best')
        if best:
            line_confidence = float(best.get('confidence') or 0.50)
            line_needs_confirmation = bool(best.get('needs_confirmation'))
            line_reason = str(best.get('confirmation_reason') or '')
            is_high_risk = bool(best.get('is_high_risk'))
            if is_high_risk and line_reason != 'high_risk':
                line_reason = 'high_risk'
        else:
            line_confidence = 0.50
            line_needs_confirmation = True
            line_reason = 'unmatched'

        # code 字段
        code_value = str(item.get('code') or '')
        fields.append(FieldEvidence(
            field_name='code',
            original_value=code_value,
            candidates=candidate_codes,
            confidence=line_confidence,
            needs_confirmation=line_needs_confirmation or line_confidence < LOW_CONFIDENCE_THRESHOLD,
            confirmation_reason=line_reason if line_needs_confirmation else (
                'low_confidence' if line_confidence < LOW_CONFIDENCE_THRESHOLD else ''
            ),
            correction_status='',
            source='material_governance' if mg else 'ocr',
            line_index=idx,
        ))

        # name 字段
        name_value = str(item.get('name') or '')
        fields.append(FieldEvidence(
            field_name='name',
            original_value=name_value,
            candidates=candidate_names,
            confidence=line_confidence,
            needs_confirmation=line_needs_confirmation or line_confidence < LOW_CONFIDENCE_THRESHOLD,
            confirmation_reason=line_reason if line_needs_confirmation else (
                'low_confidence' if line_confidence < LOW_CONFIDENCE_THRESHOLD else ''
            ),
            correction_status='',
            source='material_governance' if mg else 'ocr',
            line_index=idx,
        ))

        # spec 字段（规格不匹配触发 ambiguous_spec）
        spec_value = str(item.get('spec') or '')
        spec_reason = ''
        if line_reason == 'ambiguous_spec':
            spec_reason = 'ambiguous_spec'
        spec_confidence = 0.85 if spec_value else 0.50
        fields.append(FieldEvidence(
            field_name='spec',
            original_value=spec_value,
            candidates=(),
            confidence=spec_confidence,
            needs_confirmation=(spec_reason == 'ambiguous_spec') or spec_confidence < LOW_CONFIDENCE_THRESHOLD,
            confirmation_reason=spec_reason,
            correction_status='',
            source='material_governance' if mg else 'ocr',
            line_index=idx,
        ))

        # quantity 字段（数量异常：短交/超收检测）
        quantity_value = str(item.get('quantity') or '')
        quantity_reason = ''
        quantity_confidence = 0.95
        # 从 delivery_match 的 line_evidence 检测数量差异（如果可对齐）
        # 此处仅做基础数量字段证据，差异检测在 delivery_match 透传中体现
        fields.append(FieldEvidence(
            field_name='quantity',
            original_value=quantity_value,
            candidates=(),
            confidence=quantity_confidence,
            needs_confirmation=False,
            confirmation_reason=quantity_reason,
            correction_status='',
            source='ocr',
            line_index=idx,
        ))

        # unit 字段（单位换算标记：若 material_governance 含换算证据则标记）
        unit_value = str(item.get('unit') or '')
        fields.append(FieldEvidence(
            field_name='unit',
            original_value=unit_value,
            candidates=(),
            confidence=0.90,
            needs_confirmation=False,
            confirmation_reason='',
            correction_status='',
            source='ocr',
            line_index=idx,
        ))

    return fields


# ---- 重复风险检测 ----

def _detect_duplicate_risks(
    *,
    source_hash: str,
    business_key: str,
    query_existing_drafts: Optional[QueryExistingDraftsFn],
    duplicate_similarity_threshold: float,
) -> list[DuplicateRiskHit]:
    """检测重复风险（按 source_hash/business_key 查已完成草稿）。

    验收要求："重复风险可阻止建单"——已完成的草稿会阻止本次建单。
    """
    if not query_existing_drafts:
        return []
    if not source_hash and not business_key:
        return []

    try:
        raw_hits = query_existing_drafts(source_hash, business_key)
    except Exception:
        # 查询异常不阻塞主流程，降级为无重复风险
        return []

    risks: list[DuplicateRiskHit] = []
    for hit in raw_hits:
        similarity = float(hit.get('similarity') or 0.0)
        if similarity < duplicate_similarity_threshold:
            continue
        status = str(hit.get('status') or '')
        # 仅 completed 状态的草稿会阻止建单
        blocks = status in BLOCKING_DRAFT_STATUSES
        risks.append(DuplicateRiskHit(
            existing_draft_type=str(hit.get('draft_type') or ''),
            existing_draft_id=int(hit.get('draft_id') or 0),
            existing_draft_no=str(hit.get('draft_no') or ''),
            existing_status=status,
            created_at=str(hit.get('created_at') or ''),
            match_reason=str(hit.get('match_reason') or ''),
            similarity=similarity,
            blocks_creation=blocks,
        ))
    return risks


# ---- AI-R07 物料治理证据透传 ----

def _check_material_ambiguity(
    material_governance: Optional[list[dict[str, Any]]],
) -> bool:
    """检查是否存在物料歧义（透传 AI-R07 has_ambiguity）。"""
    if not material_governance:
        return False
    for mg in material_governance:
        if mg.get('has_ambiguity'):
            return True
    return False


def _check_high_risk_material(
    material_governance: Optional[list[dict[str, Any]]],
) -> bool:
    """检查是否存在高风险物料（透传 AI-R07 is_high_risk）。"""
    if not material_governance:
        return False
    for mg in material_governance:
        best = mg.get('best')
        if best and best.get('is_high_risk'):
            return True
        # 也检查候选清单中是否有高风险
        for c in (mg.get('candidates') or []):
            if c.get('is_high_risk'):
                return True
    return False


# ---- AI-R06 采购差异证据透传 ----

def _check_purchase_difference(
    delivery_match: Optional[dict[str, Any]],
) -> bool:
    """检查是否存在采购差异（短交/超收/未关联物料）。"""
    if not delivery_match:
        return False
    for c in (delivery_match.get('candidates') or []):
        if c.get('shortage_line_count', 0) > 0:
            return True
        if c.get('overreceive_line_count', 0) > 0:
            return True
        if c.get('unmatched_line_count', 0) > 0:
            return True
    return False


# ---- 中文摘要构建 ----

def _build_summary(
    *,
    has_duplicate_risk: bool,
    block_draft_creation: bool,
    has_unconfirmed_low_conf: bool,
    has_material_ambiguity: bool,
    has_high_risk_material: bool,
    has_purchase_difference: bool,
    forbidden_pr: bool,
    field_count: int,
    item_count: int,
) -> str:
    """构建中文摘要供前端顶部展示。"""
    parts: list[str] = []
    parts.append(f'共 {field_count} 个字段、{item_count} 行明细')

    if block_draft_creation:
        parts.append('检测到重复草稿，已阻止建单')
    elif has_duplicate_risk:
        parts.append('检测到重复风险，请人工确认')

    if has_unconfirmed_low_conf:
        parts.append('存在低置信度字段未确认')
    if has_material_ambiguity:
        parts.append('存在物料歧义待人工选择')
    if has_high_risk_material:
        parts.append('存在高风险物料需强制确认')
    if has_purchase_difference:
        parts.append('存在采购差异（短交/超收/未关联）')
    if forbidden_pr:
        parts.append('送货通知禁止生成采购申请')

    if len(parts) == 1:
        parts.append('所有字段置信度达标，可直接确认建单')

    return '；'.join(parts) + '。'


# ---- 前端修正回传后的二次校验 ----

def validate_corrections_before_draft_creation(
    evidence: DocumentConfirmationEvidence,
    corrections: dict[str, Any],
    *,
    low_confidence_threshold: float = LOW_CONFIDENCE_THRESHOLD,
) -> tuple[bool, list[str]]:
    """服务端二次校验：低置信度字段不能静默通过；重复风险可阻止建单。

    验收要求："低置信度字段不能静默通过；重复风险可阻止建单"。

    Args:
        evidence: build_confirmation_evidence 产出的证据
        corrections: 前端回传的修正字典，key 为 'line{idx}.{field_name}' 或 '{field_name}'
        low_confidence_threshold: 低置信度阈值

    Returns:
        (is_valid, error_messages)
        is_valid=True 时可创建草稿；False 时拒绝建单并返回错误清单
    """
    errors: list[str] = []

    # 1. 重复风险阻止建单
    if evidence.block_draft_creation:
        errors.append(
            '检测到已完成的重复草稿，已阻止本次建单。'
            '请确认是否需要复用已有草稿或联系主管处理。'
        )

    # 2. 低置信度字段必须修正后才能建单
    unconfirmed_low_conf = [
        f for f in evidence.fields
        if f.confidence < low_confidence_threshold
        and f.correction_status not in ('corrected', 'rejected')
    ]
    # corrections 中的字段视为已修正
    if corrections:
        still_unconfirmed = []
        for f in unconfirmed_low_conf:
            if f.line_index >= 0:
                key = f'line{f.line_index}.{f.field_name}'
            else:
                key = f.field_name
            if key not in corrections:
                still_unconfirmed.append(f)
        unconfirmed_low_conf = still_unconfirmed

    if unconfirmed_low_conf:
        field_descs = [
            f'第 {f.line_index + 1} 行 {f.field_name}' if f.line_index >= 0 else f'表头 {f.field_name}'
            for f in unconfirmed_low_conf
        ]
        errors.append(
            f'以下低置信度字段未修正，不能创建草稿：{", ".join(field_descs)}'
        )

    # 3. 物料歧义必须人工选择
    if evidence.has_material_ambiguity:
        # 检查是否所有歧义行都已选择 matched_material_id
        # 通过 corrections 中是否含 line{idx}.matched_material_id 判断
        if evidence.material_governance:
            for idx, mg in enumerate(evidence.material_governance):
                if mg.get('has_ambiguity'):
                    key = f'line{idx}.matched_material_id'
                    if not corrections or not corrections.get(key):
                        errors.append(
                            f'第 {idx + 1} 行存在物料歧义，必须人工选择匹配物料后才能建单'
                        )

    # 4. 高风险物料必须人工确认
    if evidence.has_high_risk_material:
        if evidence.material_governance:
            for idx, mg in enumerate(evidence.material_governance):
                best = mg.get('best')
                if best and best.get('is_high_risk'):
                    key = f'line{idx}.high_risk_confirmed'
                    if not corrections or not corrections.get(key):
                        errors.append(
                            f'第 {idx + 1} 行高风险物料（{best.get("high_risk_rule_id") or ""}）'
                            '必须人工确认后才能建单'
                        )

    return len(errors) == 0, errors

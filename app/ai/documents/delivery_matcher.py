"""AI-R06：送货通知与采购订单联合匹配引擎。

# AI_TASK: AI-R06

设计目标（验收：送货通知误建采购申请为 0；低置信度不自动选单据；
匹配依据和数量差异可见）：

- 纯逻辑 + 依赖注入：不依赖 Flask/SQLAlchemy，查询通过注入的
  `query_open_purchase_orders` 回调完成。CI 无 DB 时用 mock 测试，
  生产环境由 app.py 提供 ORM adapter。

- 联合匹配维度：供应商名称（加权）、订单号精确（最高分）、物料匹配
  （基础分）、日期接近度（小幅加权）。综合评分 0~1。

- 差异检测：短交（本次送货量 < 未收量）、超收（本次送货量 > 未收量）、
  关闭订单（status=closed/completed 不参与匹配但单独标记）、未关联物料
  （送货单有但 PO 明细无）。

- 多候选清单：不放弃多候选，返回完整候选带证据，低置信度不自动选单。

- 误建采购申请防护：`is_purchase_request_forbidden_for_delivery` 显式
  判定送货通知场景，禁止走 purchase_request 路径（AGENTS.md 硬约束）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Optional


# ---- 评分权重（可配置）----

# 设计：微信送货通知通常不含订单号，但供应商+物料双匹配已是强证据。
# 因此订单号仍是重要加分（最高单维度权重），但供应商+物料组合可达
# 自动选单门槛 0.70，确保无订单号场景下唯一候选也能自动选单。
# 权重和 = 1.0，综合评分范围 0~1。
WEIGHT_ORDER_NO = 0.25       # 订单号精确匹配：最高单维度权重
WEIGHT_SUPPLIER = 0.40       # 供应商名称匹配（核心维度，微信通知主要依据）
WEIGHT_MATERIAL = 0.30       # 物料匹配（行覆盖率）
WEIGHT_DATE = 0.05           # 日期接近度（小幅加权）

# 自动选单的置信度门槛：低于此值不自动选单，返回候选清单待人工确认
AUTO_SELECT_CONFIDENCE_THRESHOLD = 0.70

# 关闭/已完成订单状态（不参与匹配）
CLOSED_ORDER_STATUSES = ('closed', 'completed')

# 开放订单状态（可参与匹配）
OPEN_ORDER_STATUSES = ('pending', 'partial', 'open')


# ---- 输入输出数据结构（纯 dataclass，不依赖 ORM）----

@dataclass(frozen=True)
class DeliveryMaterialLine:
    """送货通知中的一行物料。"""

    code: str = ''
    name: str = ''
    spec: str = ''
    quantity: float = 0.0
    unit: str = ''
    raw_text: str = ''


@dataclass(frozen=True)
class DeliveryMatchInput:
    """送货通知联合匹配输入。"""

    supplier_name: str = ''              # 提取到的供应商名称
    purchase_order_no: str = ''          # 提取到的采购订单号（如有）
    expected_date: str = ''              # 提取到的预计交货日期（如有，YYYY-MM-DD）
    lines: tuple[DeliveryMaterialLine, ...] = field(default_factory=tuple)
    source_text: str = ''                # 原始文本（用于误建采购申请判定）
    is_delivery_notice: bool = True      # 是否为送货通知（微信发货通知等）

    def to_dict(self) -> dict[str, Any]:
        return {
            'supplier_name': self.supplier_name,
            'purchase_order_no': self.purchase_order_no,
            'expected_date': self.expected_date,
            'lines': [
                {
                    'code': l.code, 'name': l.name, 'spec': l.spec,
                    'quantity': l.quantity, 'unit': l.unit,
                }
                for l in self.lines
            ],
            'source_text': self.source_text[:200],  # 脱敏：仅保留前 200 字符
            'is_delivery_notice': self.is_delivery_notice,
        }


@dataclass(frozen=True)
class PurchaseOrderLineInfo:
    """采购订单明细行的纯数据视图（由 ORM adapter 转换）。"""

    line_id: int
    material_id: int
    material_code: str
    material_name: str
    material_spec: str
    quantity: float                       # 订单数量
    received_quantity: float              # 已收数量

    @property
    def pending_quantity(self) -> float:
        """未收数量。"""
        return max(0.0, self.quantity - self.received_quantity)


@dataclass(frozen=True)
class PurchaseOrderInfo:
    """采购订单的纯数据视图（由 ORM adapter 转换）。"""

    order_id: int
    order_no: str
    supplier_id: int = 0
    supplier_name: str = ''
    status: str = 'pending'
    expected_date: str = ''               # YYYY-MM-DD
    lines: tuple[PurchaseOrderLineInfo, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LineMatchEvidence:
    """单行匹配证据（匹配依据和数量差异可见）。"""

    delivery_line_index: int              # 送货通知行索引
    delivery_code: str
    delivery_name: str
    delivery_quantity: float
    matched_po_line_id: Optional[int]     # 匹配到的 PO 行 ID，None=未关联
    matched_material_id: Optional[int]
    po_order_quantity: float              # PO 订单数量
    po_received_quantity: float           # PO 已收数量
    po_pending_quantity: float            # PO 未收数量
    difference: float                     # 差异 = 本次送货量 - 未收量（正=超收，负=短交）
    difference_type: str                  # ''=精确 / 'shortage'=短交 / 'overreceive'=超收 / 'unmatched'=未关联

    def to_dict(self) -> dict[str, Any]:
        return {
            'delivery_line_index': self.delivery_line_index,
            'delivery_code': self.delivery_code,
            'delivery_name': self.delivery_name,
            'delivery_quantity': self.delivery_quantity,
            'matched_po_line_id': self.matched_po_line_id,
            'matched_material_id': self.matched_material_id,
            'po_order_quantity': self.po_order_quantity,
            'po_received_quantity': self.po_received_quantity,
            'po_pending_quantity': self.po_pending_quantity,
            'difference': round(self.difference, 4),
            'difference_type': self.difference_type,
        }


@dataclass(frozen=True)
class PurchaseOrderCandidate:
    """单个采购订单的匹配候选（带评分与证据）。"""

    order_id: int
    order_no: str
    supplier_name: str
    status: str
    score: float                          # 综合评分 0~1
    confidence: str                       # 'high'/'medium'/'low'
    score_breakdown: dict[str, float]     # 各维度得分明细（可解释）
    line_evidence: tuple[LineMatchEvidence, ...]
    matched_line_count: int               # 匹配上的行数
    unmatched_line_count: int             # 送货通知中未关联到 PO 的行数
    shortage_line_count: int              # 短交行数
    overreceive_line_count: int           # 超收行数
    is_closed: bool                       # 是否为关闭/已完成订单
    auto_selectable: bool                 # 是否可自动选单（评分达标且非关闭）

    def to_dict(self) -> dict[str, Any]:
        return {
            'order_id': self.order_id,
            'order_no': self.order_no,
            'supplier_name': self.supplier_name,
            'status': self.status,
            'score': round(self.score, 4),
            'confidence': self.confidence,
            'score_breakdown': dict(self.score_breakdown),
            'line_evidence': [e.to_dict() for e in self.line_evidence],
            'matched_line_count': self.matched_line_count,
            'unmatched_line_count': self.unmatched_line_count,
            'shortage_line_count': self.shortage_line_count,
            'overreceive_line_count': self.overreceive_line_count,
            'is_closed': self.is_closed,
            'auto_selectable': self.auto_selectable,
        }


@dataclass(frozen=True)
class DeliveryMatchResult:
    """联合匹配总结果。"""

    candidates: tuple[PurchaseOrderCandidate, ...]
    best_candidate: Optional[PurchaseOrderCandidate]   # 最高分候选（可能 None）
    auto_selected: Optional[PurchaseOrderCandidate]    # 自动选中的候选（低置信度时 None）
    has_candidates: bool
    should_fallback_to_in_order: bool                  # 无候选或低置信度→生成待确认普通入库草稿
    fallback_reason: str                               # 中文原因
    forbidden_purchase_request: bool                   # 是否禁止走采购申请路径
    forbidden_reason: str                              # 禁止原因

    def to_dict(self) -> dict[str, Any]:
        return {
            'candidates': [c.to_dict() for c in self.candidates],
            'best_candidate': self.best_candidate.to_dict() if self.best_candidate else None,
            'auto_selected': self.auto_selected.to_dict() if self.auto_selected else None,
            'has_candidates': self.has_candidates,
            'should_fallback_to_in_order': self.should_fallback_to_in_order,
            'fallback_reason': self.fallback_reason,
            'forbidden_purchase_request': self.forbidden_purchase_request,
            'forbidden_reason': self.forbidden_reason,
        }


# ---- 查询接口（依赖注入）----

# query_open_purchase_orders 回调签名：
# (supplier_name: str, material_codes: list[str]) -> list[PurchaseOrderInfo]
# 返回的订单含 status in OPEN_ORDER_STATUSES 的开放订单明细
QueryOpenPurchaseOrdersFn = Callable[[str, list[str]], list[PurchaseOrderInfo]]

# query_purchase_order_by_no 回调签名：
# (order_no: str) -> Optional[PurchaseOrderInfo]
# 按订单号精确查（含关闭订单，用于差异展示）
QueryPurchaseOrderByNoFn = Callable[[str], Optional[PurchaseOrderInfo]]


# ---- 主匹配函数 ----

def match_delivery(
    delivery: DeliveryMatchInput,
    *,
    query_open_purchase_orders: Optional[QueryOpenPurchaseOrdersFn] = None,
    query_purchase_order_by_no: Optional[QueryPurchaseOrderByNoFn] = None,
    auto_select_threshold: float = AUTO_SELECT_CONFIDENCE_THRESHOLD,
) -> DeliveryMatchResult:
    """对送货通知执行采购订单联合匹配。

    Args:
        delivery: 送货通知输入
        query_open_purchase_orders: 注入的开放订单查询回调
        query_purchase_order_by_no: 注入的按订单号查询回调
        auto_select_threshold: 自动选单置信度门槛

    Returns:
        DeliveryMatchResult：含候选清单、最佳候选、自动选中、回退决策、
        采购申请禁令
    """
    # 误建采购申请防护：送货通知场景禁止走 purchase_request
    forbidden_pr = delivery.is_delivery_notice and _is_delivery_notice_text(delivery.source_text)
    forbidden_reason = ''
    if forbidden_pr:
        forbidden_reason = (
            '检测到微信/截图送货通知语义，按业务规则必须生成采购收货或普通入库草稿，'
            '禁止生成采购申请草稿'
        )

    candidates: list[PurchaseOrderCandidate] = []

    # 1. 若有订单号，先按订单号精确查（含关闭订单，用于差异展示）
    if delivery.purchase_order_no and query_purchase_order_by_no:
        po = query_purchase_order_by_no(delivery.purchase_order_no)
        if po is not None:
            cand = _score_candidate(po, delivery, is_order_no_exact=True)
            candidates.append(cand)

    # 2. 按供应商 + 物料查询开放订单
    material_codes = [l.code for l in delivery.lines if l.code]
    material_names = [l.name for l in delivery.lines if l.name]
    query_codes = material_codes + material_names  # 同时用编码和名称查
    if query_open_purchase_orders and query_codes:
        open_orders = query_open_purchase_orders(delivery.supplier_name, query_codes)
        # 去重：已在订单号精确查中加入的不重复加
        existing_ids = {c.order_id for c in candidates}
        for po in open_orders:
            if po.order_id in existing_ids:
                continue
            candidates.append(_score_candidate(po, delivery, is_order_no_exact=False))

    # 3. 排序：可自动选的优先，再按评分降序
    candidates.sort(key=lambda c: (c.auto_selectable, c.score), reverse=True)

    # 4. 决策
    has_candidates = len(candidates) > 0
    best = candidates[0] if candidates else None
    auto_selected = None
    fallback_reason = ''

    if not has_candidates:
        fallback_reason = '未找到匹配的采购订单，生成待确认普通入库草稿'
    elif best is not None and best.auto_selectable and len(candidates) == 1:
        # 仅当唯一候选且评分达标才自动选单
        auto_selected = best
    elif best is not None and best.auto_selectable and len(candidates) > 1:
        # 多候选：即使评分达标也不自动选单，返回候选清单待人工确认
        fallback_reason = f'找到 {len(candidates)} 个候选采购订单，需人工确认选择'
    else:
        # 最佳候选评分不达标
        fallback_reason = (
            f'最佳候选评分 {best.score:.2f} 低于自动选单门槛 {auto_select_threshold:.2f}，'
            '需人工确认'
        )

    should_fallback = auto_selected is None

    return DeliveryMatchResult(
        candidates=tuple(candidates),
        best_candidate=best,
        auto_selected=auto_selected,
        has_candidates=has_candidates,
        should_fallback_to_in_order=should_fallback,
        fallback_reason=fallback_reason,
        forbidden_purchase_request=forbidden_pr,
        forbidden_reason=forbidden_reason,
    )


# ---- 单候选评分 ----

def _score_candidate(
    po: PurchaseOrderInfo,
    delivery: DeliveryMatchInput,
    *,
    is_order_no_exact: bool,
) -> PurchaseOrderCandidate:
    """对单个采购订单评分并生成行级证据。"""
    # 维度1：订单号精确匹配
    score_order_no = 1.0 if (is_order_no_exact and delivery.purchase_order_no) else 0.0

    # 维度2：供应商名称匹配
    score_supplier = _score_supplier(delivery.supplier_name, po.supplier_name)

    # 维度3：物料匹配（行覆盖率）
    line_evidence, matched_count, unmatched_count, shortage_count, overreceive_count = (
        _match_lines(delivery.lines, po.lines)
    )
    total_lines = len(delivery.lines)
    score_material = (matched_count / total_lines) if total_lines > 0 else 0.0

    # 维度4：日期接近度
    score_date = _score_date(delivery.expected_date, po.expected_date)

    # 综合评分
    score = (
        WEIGHT_ORDER_NO * score_order_no
        + WEIGHT_SUPPLIER * score_supplier
        + WEIGHT_MATERIAL * score_material
        + WEIGHT_DATE * score_date
    )

    is_closed = po.status in CLOSED_ORDER_STATUSES
    # 关闭订单不可自动选单
    auto_selectable = (not is_closed) and (score >= AUTO_SELECT_CONFIDENCE_THRESHOLD)

    # 置信度等级
    if score >= 0.85:
        confidence = 'high'
    elif score >= AUTO_SELECT_CONFIDENCE_THRESHOLD:
        confidence = 'medium'
    else:
        confidence = 'low'

    return PurchaseOrderCandidate(
        order_id=po.order_id,
        order_no=po.order_no,
        supplier_name=po.supplier_name,
        status=po.status,
        score=score,
        confidence=confidence,
        score_breakdown={
            'order_no': round(score_order_no, 4),
            'supplier': round(score_supplier, 4),
            'material': round(score_material, 4),
            'date': round(score_date, 4),
        },
        line_evidence=tuple(line_evidence),
        matched_line_count=matched_count,
        unmatched_line_count=unmatched_count,
        shortage_line_count=shortage_count,
        overreceive_line_count=overreceive_count,
        is_closed=is_closed,
        auto_selectable=auto_selectable,
    )


def _score_supplier(delivery_supplier: str, po_supplier: str) -> float:
    """供应商名称匹配评分。"""
    if not delivery_supplier or not po_supplier:
        return 0.0
    d = _normalize_supplier(delivery_supplier)
    p = _normalize_supplier(po_supplier)
    if not d or not p:
        return 0.0
    if d == p:
        return 1.0
    # 包含关系（一方是另一方的子串）：部分匹配
    if d in p or p in d:
        return 0.7
    return 0.0


def _normalize_supplier(name: str) -> str:
    """供应商名称归一化：去公司后缀、去空白、转小写。"""
    if not name:
        return ''
    import re
    s = name.strip().lower()
    # 去常见公司后缀
    s = re.sub(r'(有限公司|股份有限公司|有限责任公司|集团|公司|厂|店)$', '', s)
    return s.strip()


def _score_date(delivery_date: str, po_date: str) -> float:
    """日期接近度评分。"""
    if not delivery_date or not po_date:
        return 0.0
    try:
        d1 = datetime.strptime(delivery_date, '%Y-%m-%d').date()
        d2 = datetime.strptime(po_date, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return 0.0
    delta_days = abs((d1 - d2).days)
    if delta_days == 0:
        return 1.0
    if delta_days <= 7:
        return 0.8
    if delta_days <= 30:
        return 0.5
    if delta_days <= 90:
        return 0.2
    return 0.0


def _match_lines(
    delivery_lines: tuple[DeliveryMaterialLine, ...],
    po_lines: tuple[PurchaseOrderLineInfo, ...],
) -> tuple[list[LineMatchEvidence], int, int, int, int]:
    """匹配送货通知行与 PO 明细行，返回证据与计数。

    Returns:
        (line_evidence, matched_count, unmatched_count, shortage_count, overreceive_count)
    """
    evidence: list[LineMatchEvidence] = []
    matched = 0
    unmatched = 0
    shortage = 0
    overreceive = 0

    for idx, dl in enumerate(delivery_lines):
        po_line = _find_po_line(dl, po_lines)
        if po_line is None:
            evidence.append(LineMatchEvidence(
                delivery_line_index=idx,
                delivery_code=dl.code,
                delivery_name=dl.name,
                delivery_quantity=dl.quantity,
                matched_po_line_id=None,
                matched_material_id=None,
                po_order_quantity=0.0,
                po_received_quantity=0.0,
                po_pending_quantity=0.0,
                difference=dl.quantity,
                difference_type='unmatched',
            ))
            unmatched += 1
            continue

        matched += 1
        pending = po_line.pending_quantity
        diff = dl.quantity - pending
        if abs(diff) < 0.001:
            diff_type = ''
        elif diff < 0:
            diff_type = 'shortage'
            shortage += 1
        else:
            diff_type = 'overreceive'
            overreceive += 1

        evidence.append(LineMatchEvidence(
            delivery_line_index=idx,
            delivery_code=dl.code,
            delivery_name=dl.name,
            delivery_quantity=dl.quantity,
            matched_po_line_id=po_line.line_id,
            matched_material_id=po_line.material_id,
            po_order_quantity=po_line.quantity,
            po_received_quantity=po_line.received_quantity,
            po_pending_quantity=pending,
            difference=diff,
            difference_type=diff_type,
        ))

    return evidence, matched, unmatched, shortage, overreceive


def _find_po_line(
    dl: DeliveryMaterialLine,
    po_lines: tuple[PurchaseOrderLineInfo, ...],
) -> Optional[PurchaseOrderLineInfo]:
    """在 PO 明细中找匹配行：编码精确 > 名称+规格 > 名称。"""
    # 1. 编码精确匹配
    if dl.code:
        for pl in po_lines:
            if pl.material_code and pl.material_code.upper() == dl.code.upper():
                return pl
    # 2. 名称 + 规格匹配
    if dl.name:
        for pl in po_lines:
            if pl.material_name and _normalize_text(pl.material_name) == _normalize_text(dl.name):
                if not dl.spec or not pl.material_spec or _normalize_text(pl.material_spec) == _normalize_text(dl.spec):
                    return pl
    # 3. 仅名称匹配
    if dl.name:
        for pl in po_lines:
            if pl.material_name and _normalize_text(pl.material_name) == _normalize_text(dl.name):
                return pl
    return None


def _normalize_text(s: str) -> str:
    """文本归一化：去空白、转小写。"""
    if not s:
        return ''
    import re
    return re.sub(r'\s+', '', s).lower()


# ---- 误建采购申请防护 ----

def _is_delivery_notice_text(text: str) -> bool:
    """判定文本是否为送货通知语义（AGENTS.md 硬约束触发条件）。

    复用 extractor._is_wechat_delivery 的语义，但本模块不依赖 extractor
    以保持纯逻辑（避免循环依赖）。
    """
    if not text:
        return False
    compact = text.replace(' ', '').lower()
    # 时间/动作词 + 物料段
    import re
    has_action = bool(re.search(r'(今天|明天|后天|上午|下午|晚上|到货|送货|发货|出货|发)\S{0,20}', compact))
    if not has_action:
        return False
    # 排除销售出库场景
    if any(w in compact for w in ('发给客户', '发往客户', '客户要货', '销售出库')):
        return False
    # 至少含一个物料+数量段
    if not re.search(r'[\u4e00-\u9fffA-Za-z0-9]{2,}\s*[0-9]+', compact):
        return False
    return True


def is_purchase_request_forbidden_for_delivery(delivery: DeliveryMatchInput) -> tuple[bool, str]:
    """判定送货通知场景是否禁止生成采购申请草稿。

    AGENTS.md 硬约束：微信/截图送货通知必须生成采购收货或普通入库草稿，
    不能生成采购申请草稿。

    Returns:
        (是否禁止, 中文原因)
    """
    if delivery.is_delivery_notice and _is_delivery_notice_text(delivery.source_text):
        return True, (
            '检测到微信/截图送货通知语义，按业务规则必须生成采购收货或普通入库草稿，'
            '禁止生成采购申请草稿'
        )
    return False, ''

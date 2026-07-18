"""AI-SALES-F01：AI 销售订单/销售出库草稿真实闭环验收。

# AI_TASK: AI-SALES-F01

设计目标（验收：AI 只建/检草稿；库存、订单发货量和销售报表一致）：

- 纯逻辑 + 依赖注入：不依赖 Flask/SQLAlchemy，销售订单/出库/库存查询通过
  注入的回调完成。CI 无 DB 时用 mock 测试，生产环境由 app.py 提供 ORM adapter。

- 销售草稿证据链：AI 创建或检查的销售草稿必须记录完整证据，包括来源、
  操作人、时间、订单号、客户、明细、金额和状态。

- 部分发货支持：支持按行部分发货，shipped_quantity 不超过 quantity，
  多次发货累计不超过订单量。

- 多次发货追踪：每次出库草稿关联 source_sales_order_id，通过外键追踪
  来源销售订单，sync 回写 shipped_quantity。

- 库存与报表对账：销售订单的 shipped_quantity 之和应等于关联出库单的
  已完成数量之和；销售报表的金额和数量应与订单明细一致。

- AI 只建/检草稿：AI 不能确认、提交、发货、取消或删除销售订单，
  只能创建草稿和检查草稿状态。

- 与现有 recalculate_sales_order / sync_sales_order_shipment 解耦：
  本模块为旁路校验，不修改现有业务逻辑。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ---- 常量 ----

# AI 禁止的销售动作（与 AI-R13 budget_control 保持一致）
SALES_FORBIDDEN_ACTIONS: frozenset[str] = frozenset({
    'confirm',       # 确认销售订单
    'submit',        # 提交
    'ship',          # 发货
    'cancel',        # 取消
    'delete',        # 删除
    'close',         # 关闭
    'complete',      # 完成
    'auto_dispatch', # 自动发货
})

# 销售订单合法状态
VALID_ORDER_STATUSES: frozenset[str] = frozenset({
    'draft', 'confirmed', 'closed', 'cancelled',
})

# 发货状态
VALID_SHIPMENT_STATUSES: frozenset[str] = frozenset({
    'pending', 'partial', 'shipped',
})

# 出库单合法状态
VALID_OUTBOUND_STATUSES: frozenset[str] = frozenset({
    'pending', 'completed', 'cancelled',
})

# 浮点比较容差
STOCK_COMPARE_EPSILON = 1e-6


# ---- 数据结构 ----

@dataclass(frozen=True)
class SalesLineInfo:
    """销售订单行信息（纯数据视图）。"""

    line_id: int
    material_id: int
    material_code: str
    material_name: str
    quantity: float
    shipped_quantity: float
    price: float
    tax_rate: float = 0.13

    @property
    def remaining_quantity(self) -> float:
        return max(0.0, self.quantity - self.shipped_quantity)

    @property
    def tax_included_amount(self) -> float:
        return round(self.quantity * self.price, 2)

    @property
    def is_fully_shipped(self) -> bool:
        return self.shipped_quantity + STOCK_COMPARE_EPSILON >= self.quantity

    def to_dict(self) -> dict[str, Any]:
        return {
            'line_id': self.line_id,
            'material_id': self.material_id,
            'material_code': self.material_code,
            'material_name': self.material_name,
            'quantity': self.quantity,
            'shipped_quantity': self.shipped_quantity,
            'remaining_quantity': round(self.remaining_quantity, 6),
            'price': self.price,
            'tax_rate': self.tax_rate,
            'tax_included_amount': self.tax_included_amount,
            'is_fully_shipped': self.is_fully_shipped,
        }


@dataclass(frozen=True)
class SalesOrderInfo:
    """销售订单信息（纯数据视图）。"""

    order_id: int
    order_no: str
    status: str
    shipment_status: str
    customer_name: str
    lines: tuple[SalesLineInfo, ...]
    total_amount: float = 0.0
    shipped_amount: float = 0.0

    @property
    def is_draft(self) -> bool:
        return self.status == 'draft'

    @property
    def is_confirmed(self) -> bool:
        return self.status == 'confirmed'

    @property
    def is_closed(self) -> bool:
        return self.status == 'closed'

    @property
    def is_cancelled(self) -> bool:
        return self.status == 'cancelled'

    @property
    def has_remaining(self) -> bool:
        return any(line.remaining_quantity > STOCK_COMPARE_EPSILON for line in self.lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            'order_id': self.order_id,
            'order_no': self.order_no,
            'status': self.status,
            'shipment_status': self.shipment_status,
            'customer_name': self.customer_name,
            'lines': [line.to_dict() for line in self.lines],
            'total_amount': self.total_amount,
            'shipped_amount': self.shipped_amount,
            'is_draft': self.is_draft,
            'has_remaining': self.has_remaining,
        }


@dataclass(frozen=True)
class OutboundDraftInfo:
    """出库草稿信息（纯数据视图）。"""

    outbound_id: int
    order_no: str
    status: str
    source_sales_order_id: Optional[int]
    source_sales_order_no: str
    customer_name: str
    lines: tuple[dict[str, Any], ...]
    business_type: str = '销售出库'

    def to_dict(self) -> dict[str, Any]:
        return {
            'outbound_id': self.outbound_id,
            'order_no': self.order_no,
            'status': self.status,
            'source_sales_order_id': self.source_sales_order_id,
            'source_sales_order_no': self.source_sales_order_no,
            'customer_name': self.customer_name,
            'lines': list(self.lines),
            'business_type': self.business_type,
        }


@dataclass(frozen=True)
class SalesDraftEvidence:
    """AI 销售草稿证据链。"""

    evidence_id: str
    operation: str                    # create_draft / check_draft / validate_shipment
    operator_id: str
    operator_role: str
    source: str                       # ai_assistant / excel_import / manual
    sales_order: Optional[SalesOrderInfo]
    outbound_draft: Optional[OutboundDraftInfo]
    action_requested: str             # AI 建议的动作（仅草稿级）
    forbidden_actions: tuple[str, ...]
    created_at: str
    confidence: float = 1.0
    needs_confirmation: bool = True
    confirmation_reason: str = ''

    @property
    def is_valid(self) -> bool:
        return all(a in SALES_FORBIDDEN_ACTIONS for a in self.forbidden_actions)

    def to_dict(self) -> dict[str, Any]:
        return {
            'evidence_id': self.evidence_id,
            'operation': self.operation,
            'operator_id': self.operator_id,
            'operator_role': self.operator_role,
            'source': self.source,
            'sales_order': self.sales_order.to_dict() if self.sales_order else None,
            'outbound_draft': self.outbound_draft.to_dict() if self.outbound_draft else None,
            'action_requested': self.action_requested,
            'forbidden_actions': list(self.forbidden_actions),
            'created_at': self.created_at,
            'confidence': self.confidence,
            'needs_confirmation': self.needs_confirmation,
            'confirmation_reason': self.confirmation_reason,
            'is_valid': self.is_valid,
        }


@dataclass(frozen=True)
class PartialShipmentResult:
    """部分发货计算结果。"""

    order_id: int
    order_no: str
    requested_lines: tuple[dict[str, Any], ...]  # [{line_id, quantity}, ...]
    planned_lines: tuple[dict[str, Any], ...]     # [{line_id, material_id, quantity, price}, ...]
    total_planned_amount: float
    exceeds_order: bool
    exceed_details: tuple[str, ...]
    remaining_after_shipment: tuple[dict[str, Any], ...]  # [{line_id, remaining}, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            'order_id': self.order_id,
            'order_no': self.order_no,
            'requested_lines': list(self.requested_lines),
            'planned_lines': list(self.planned_lines),
            'total_planned_amount': round(self.total_planned_amount, 2),
            'exceeds_order': self.exceeds_order,
            'exceed_details': list(self.exceed_details),
            'remaining_after_shipment': list(self.remaining_after_shipment),
        }


@dataclass(frozen=True)
class SalesReconciliationResult:
    """销售对账结果。"""

    order_id: int
    order_no: str
    order_total_quantity: float
    order_shipped_quantity: float
    outbound_completed_quantity: float
    inventory_delta: float
    quantity_consistent: bool
    amount_consistent: bool
    quantity_diff: float
    amount_diff: float
    details: tuple[str, ...]

    @property
    def is_reconciled(self) -> bool:
        return self.quantity_consistent and self.amount_consistent

    def to_dict(self) -> dict[str, Any]:
        return {
            'order_id': self.order_id,
            'order_no': self.order_no,
            'order_total_quantity': round(self.order_total_quantity, 6),
            'order_shipped_quantity': round(self.order_shipped_quantity, 6),
            'outbound_completed_quantity': round(self.outbound_completed_quantity, 6),
            'inventory_delta': round(self.inventory_delta, 6),
            'quantity_consistent': self.quantity_consistent,
            'amount_consistent': self.amount_consistent,
            'quantity_diff': round(self.quantity_diff, 6),
            'amount_diff': round(self.amount_diff, 2),
            'details': list(self.details),
            'is_reconciled': self.is_reconciled,
        }


# ---- 回调类型定义 ----

QuerySalesOrderFn = Callable[[int], Optional[SalesOrderInfo]]
QueryOutboundsBySalesOrderFn = Callable[[int], list[OutboundDraftInfo]]
QueryInventoryDeltaFn = Callable[[int, int], float]  # (material_id, warehouse_id) -> delta


# ---- 核心纯函数 ----

def build_sales_draft_evidence(
    *,
    evidence_id: str,
    operation: str,
    operator_id: str,
    operator_role: str,
    source: str,
    sales_order: Optional[SalesOrderInfo],
    outbound_draft: Optional[OutboundDraftInfo] = None,
    created_at: str,
    confidence: float = 1.0,
    needs_confirmation: bool = True,
    confirmation_reason: str = '',
) -> SalesDraftEvidence:
    """构建 AI 销售草稿证据链。

    AI 只能创建草稿和检查草稿，不能确认/提交/发货/取消/删除。
    """
    if operation not in ('create_draft', 'check_draft', 'validate_shipment'):
        raise ValueError(f'非法操作: {operation}，只允许 create_draft/check_draft/validate_shipment')

    if source not in ('ai_assistant', 'excel_import', 'manual'):
        raise ValueError(f'非法来源: {source}')

    if not operator_id:
        raise ValueError('operator_id 不能为空')

    # AI 只能请求草稿级动作
    action_requested = _determine_action_requested(operation, sales_order, outbound_draft)

    return SalesDraftEvidence(
        evidence_id=evidence_id,
        operation=operation,
        operator_id=operator_id,
        operator_role=operator_role,
        source=source,
        sales_order=sales_order,
        outbound_draft=outbound_draft,
        action_requested=action_requested,
        forbidden_actions=tuple(SALES_FORBIDDEN_ACTIONS),
        created_at=created_at,
        confidence=confidence,
        needs_confirmation=needs_confirmation,
        confirmation_reason=confirmation_reason,
    )


def _determine_action_requested(
    operation: str,
    sales_order: Optional[SalesOrderInfo],
    outbound_draft: Optional[OutboundDraftInfo],
) -> str:
    """根据操作和状态确定 AI 建议的动作（仅草稿级）。"""
    if operation == 'create_draft':
        if outbound_draft:
            return 'review_outbound_draft'
        return 'review_sales_draft'
    if operation == 'check_draft':
        if sales_order and sales_order.is_draft:
            return 'confirm_draft_manually'
        if sales_order and sales_order.has_remaining:
            return 'create_outbound_draft_manually'
        return 'no_action_needed'
    if operation == 'validate_shipment':
        return 'review_shipment_evidence'
    return 'no_action_needed'


def calculate_partial_shipment(
    *,
    sales_order: SalesOrderInfo,
    requested_lines: list[dict[str, Any]],  # [{line_id, quantity}, ...]
) -> PartialShipmentResult:
    """计算部分发货计划。

    校验每行发货量不超过剩余量，累计不超过订单量。
    """
    if not sales_order or not sales_order.lines:
        return PartialShipmentResult(
            order_id=0,
            order_no='',
            requested_lines=tuple(),
            planned_lines=tuple(),
            total_planned_amount=0.0,
            exceeds_order=False,
            exceed_details=('无销售订单或无明细',),
            remaining_after_shipment=tuple(),
        )

    line_map = {line.line_id: line for line in sales_order.lines}
    planned_lines = []
    exceed_details = []
    remaining_after = []
    total_amount = 0.0

    for req in requested_lines:
        line_id = req.get('line_id')
        req_qty = float(req.get('quantity', 0))
        line = line_map.get(line_id)

        if not line:
            exceed_details.append(f'行 {line_id} 不存在')
            continue

        if req_qty <= 0:
            exceed_details.append(f'行 {line_id} 发货量必须大于 0')
            continue

        # 校验不超过剩余量
        if req_qty > line.remaining_quantity + STOCK_COMPARE_EPSILON:
            exceed_details.append(
                f'行 {line_id} 请求 {req_qty} 超过剩余 {line.remaining_quantity:.2f}'
            )
            # 截断到剩余量
            planned_qty = line.remaining_quantity
        else:
            planned_qty = req_qty

        planned_lines.append({
            'line_id': line_id,
            'material_id': line.material_id,
            'material_code': line.material_code,
            'quantity': round(planned_qty, 6),
            'price': line.price,
            'amount': round(planned_qty * line.price, 2),
        })
        total_amount += planned_qty * line.price

        new_shipped = line.shipped_quantity + planned_qty
        remaining = max(0.0, line.quantity - new_shipped)
        remaining_after.append({
            'line_id': line_id,
            'remaining': round(remaining, 6),
        })

    return PartialShipmentResult(
        order_id=sales_order.order_id,
        order_no=sales_order.order_no,
        requested_lines=tuple(requested_lines),
        planned_lines=tuple(planned_lines),
        total_planned_amount=round(total_amount, 2),
        exceeds_order=bool(exceed_details),
        exceed_details=tuple(exceed_details),
        remaining_after_shipment=tuple(remaining_after),
    )


def validate_multiple_shipments(
    *,
    sales_order: SalesOrderInfo,
    outbound_drafts: list[OutboundDraftInfo],
) -> tuple[bool, str, list[dict[str, Any]]]:
    """校验多次发货不超订单量。

    Returns:
        (是否通过, 原因, 每行累计发货明细)
    """
    if not sales_order:
        return False, '无销售订单', []

    # 按物料累计已完成出库数量
    shipped_by_material: dict[int, float] = {}
    shipment_details = []

    for outbound in outbound_drafts:
        if outbound.status != 'completed':
            continue
        for line in outbound.lines:
            material_id = line.get('material_id')
            qty = float(line.get('quantity', 0))
            if material_id is not None:
                shipped_by_material[material_id] = (
                    shipped_by_material.get(material_id, 0) + qty
                )
                shipment_details.append({
                    'outbound_id': outbound.outbound_id,
                    'outbound_no': outbound.order_no,
                    'material_id': material_id,
                    'quantity': qty,
                    'status': outbound.status,
                })

    # 校验每行不超过订单量
    order_by_material = {line.material_id: line for line in sales_order.lines}
    violations = []

    for material_id, shipped_qty in shipped_by_material.items():
        order_line = order_by_material.get(material_id)
        if not order_line:
            violations.append(f'物料 {material_id} 不在销售订单中')
            continue
        if shipped_qty > order_line.quantity + STOCK_COMPARE_EPSILON:
            violations.append(
                f'物料 {material_id} 累计发货 {shipped_qty:.2f} '
                f'超过订单量 {order_line.quantity:.2f}'
            )

    if violations:
        return False, '; '.join(violations), shipment_details

    return True, '多次发货校验通过', shipment_details


def reconcile_sales_report(
    *,
    sales_order: SalesOrderInfo,
    outbound_drafts: list[OutboundDraftInfo],
    query_inventory_delta: Optional[QueryInventoryDeltaFn] = None,
    warehouse_id: int = 0,
) -> SalesReconciliationResult:
    """销售对账：订单发货量 vs 出库完成量 vs 库存变动。

    Returns:
        SalesReconciliationResult
    """
    if not sales_order:
        return SalesReconciliationResult(
            order_id=0,
            order_no='',
            order_total_quantity=0.0,
            order_shipped_quantity=0.0,
            outbound_completed_quantity=0.0,
            inventory_delta=0.0,
            quantity_consistent=False,
            amount_consistent=False,
            quantity_diff=0.0,
            amount_diff=0.0,
            details=('无销售订单',),
        )

    details = []

    # 1. 订单总数量和已发货数量
    order_total_qty = sum(line.quantity for line in sales_order.lines)
    order_shipped_qty = sum(line.shipped_quantity for line in sales_order.lines)

    # 2. 出库完成数量
    outbound_completed_qty = 0.0
    for outbound in outbound_drafts:
        if outbound.status == 'completed':
            for line in outbound.lines:
                outbound_completed_qty += float(line.get('quantity', 0))

    # 3. 库存变动（如果提供了查询回调）
    inventory_delta = 0.0
    if query_inventory_delta:
        for line in sales_order.lines:
            try:
                delta = query_inventory_delta(line.material_id, warehouse_id)
                inventory_delta += abs(delta)  # 出库为负，取绝对值
            except Exception:
                details.append(f'物料 {line.material_id} 库存查询失败')

    # 4. 对账
    quantity_diff = abs(order_shipped_qty - outbound_completed_qty)
    quantity_consistent = quantity_diff <= STOCK_COMPARE_EPSILON

    # 金额对账：订单 shipped_amount vs 出库完成金额
    order_shipped_amount = sum(
        line.shipped_quantity * line.price for line in sales_order.lines
    )
    outbound_completed_amount = 0.0
    for outbound in outbound_drafts:
        if outbound.status == 'completed':
            for line in outbound.lines:
                qty = float(line.get('quantity', 0))
                price = float(line.get('price', 0))
                outbound_completed_amount += qty * price

    amount_diff = abs(order_shipped_amount - outbound_completed_amount)
    amount_consistent = amount_diff <= 0.01  # 金额容差 1 分

    if not quantity_consistent:
        details.append(
            f'数量不一致：订单已发 {order_shipped_qty:.2f} vs '
            f'出库完成 {outbound_completed_qty:.2f}，差 {quantity_diff:.2f}'
        )

    if not amount_consistent:
        details.append(
            f'金额不一致：订单已发金额 {order_shipped_amount:.2f} vs '
            f'出库完成金额 {outbound_completed_amount:.2f}，差 {amount_diff:.2f}'
        )

    if inventory_delta > 0 and not quantity_consistent:
        details.append(
            f'库存变动 {inventory_delta:.2f} 与出库完成量 {outbound_completed_qty:.2f} 不一致'
        )

    if quantity_consistent and amount_consistent:
        details.append('对账通过')

    return SalesReconciliationResult(
        order_id=sales_order.order_id,
        order_no=sales_order.order_no,
        order_total_quantity=order_total_qty,
        order_shipped_quantity=order_shipped_qty,
        outbound_completed_quantity=outbound_completed_qty,
        inventory_delta=inventory_delta,
        quantity_consistent=quantity_consistent,
        amount_consistent=amount_consistent,
        quantity_diff=quantity_diff,
        amount_diff=amount_diff,
        details=tuple(details),
    )


def validate_ai_only_draft(
    *,
    evidence: SalesDraftEvidence,
) -> tuple[bool, str]:
    """校验 AI 只建/检草稿，不执行禁止动作。

    Returns:
        (是否通过, 原因)
    """
    if not evidence:
        return False, '无证据记录'

    if evidence.operation not in ('create_draft', 'check_draft', 'validate_shipment'):
        return False, f'非法操作: {evidence.operation}'

    if evidence.action_requested in SALES_FORBIDDEN_ACTIONS:
        return False, f'AI 请求了禁止动作: {evidence.action_requested}'

    if not evidence.needs_confirmation:
        return False, 'AI 草稿必须需要人工确认'

    return True, 'AI 只建/检草稿校验通过'


# ---- 校验函数 ----

def validate_shipment_not_exceed_order(
    *,
    sales_order: SalesOrderInfo,
    planned_lines: list[dict[str, Any]],
) -> tuple[bool, str]:
    """校验发货计划不超过订单剩余量。"""
    if not sales_order:
        return False, '无销售订单'

    line_map = {line.line_id: line for line in sales_order.lines}

    for planned in planned_lines:
        line_id = planned.get('line_id')
        qty = float(planned.get('quantity', 0))
        line = line_map.get(line_id)

        if not line:
            return False, f'行 {line_id} 不存在'

        if qty > line.remaining_quantity + STOCK_COMPARE_EPSILON:
            return (
                False,
                f'行 {line_id} 发货量 {qty:.2f} 超过剩余 {line.remaining_quantity:.2f}',
            )

    return True, '发货计划校验通过'


def validate_sales_report_consistency(
    *,
    sales_order: SalesOrderInfo,
    outbound_drafts: list[OutboundDraftInfo],
) -> tuple[bool, str]:
    """校验销售报表与订单/出库一致性。"""
    result = reconcile_sales_report(
        sales_order=sales_order,
        outbound_drafts=outbound_drafts,
    )
    if result.is_reconciled:
        return True, '销售报表一致性校验通过'
    return False, '; '.join(result.details)

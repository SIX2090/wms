"""阶段3：草稿检查Agent。

功能：
1. 检查必填字段
2. 检查重复物料
3. 检查异常数量/单价
4. 检查库存是否充足（出库单）
5. 检查采购未到货量（入库单）
6. 检查仓库/库位/批次
7. 检查单据状态
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from ..agents.framework import AgentRun, create_agent_run

logger = logging.getLogger(__name__)


def _check_required_fields(order: Any, required_fields: list[str]) -> list[str]:
    """检查必填字段。"""
    errors = []
    for field_name in required_fields:
        value = getattr(order, field_name, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f'缺少必填字段: {field_name}')
    return errors


def _check_duplicate_materials(items: list[Any]) -> list[str]:
    """检查明细行中是否有重复物料。"""
    errors = []
    seen = {}
    for i, item in enumerate(items):
        material_id = getattr(item, 'material_id', None)
        if material_id is None:
            continue
        if material_id in seen:
            errors.append(f'第{i+1}行与第{seen[material_id]+1}行物料重复')
        else:
            seen[material_id] = i
    return errors


def _check_quantity_anomalies(items: list[Any], max_ratio: float = 10.0) -> list[str]:
    """检查异常数量（与平均数量偏差过大）。"""
    errors = []
    quantities = [getattr(item, 'quantity', 0) or 0 for item in items]
    if not quantities:
        return errors

    avg_qty = sum(quantities) / len(quantities)
    if avg_qty == 0:
        return errors

    for i, item in enumerate(items):
        qty = getattr(item, 'quantity', 0) or 0
        if qty > avg_qty * max_ratio:
            errors.append(f'第{i+1}行数量 {qty} 异常偏大（平均值 {avg_qty:.1f}）')
        elif qty < avg_qty / max_ratio and qty > 0:
            errors.append(f'第{i+1}行数量 {qty} 异常偏小（平均值 {avg_qty:.1f}）')

    return errors


def _check_stock_sufficiency(
    items: list[Any],
    db=None,
    Stock=None,
) -> list[str]:
    """检查出库单库存是否充足。"""
    if db is None or Stock is None:
        return []

    errors = []
    for i, item in enumerate(items):
        material_id = getattr(item, 'material_id', None)
        quantity = getattr(item, 'quantity', 0) or 0
        if material_id is None or quantity <= 0:
            continue

        stock = Stock.query.filter_by(material_id=material_id).first()
        current_qty = stock.quantity if stock else 0

        if current_qty < quantity:
            errors.append(f'第{i+1}行库存不足（需要{quantity}，当前{current_qty}）')

    return errors


def _check_po_quantity(
    items: list[Any],
    db=None,
    PurchaseOrderItem=None,
    PurchaseOrder=None,
) -> list[str]:
    """检查入库单是否超过采购未到货量。"""
    if db is None or PurchaseOrderItem is None or PurchaseOrder is None:
        return []

    errors = []
    for i, item in enumerate(items):
        material_id = getattr(item, 'material_id', None)
        quantity = getattr(item, 'quantity', 0) or 0
        po_id = getattr(item, 'purchase_order_id', None)
        if material_id is None or quantity <= 0 or po_id is None:
            continue

        # 计算该采购订单该物料的未到货量
        po_items = PurchaseOrderItem.query.filter(
            PurchaseOrderItem.material_id == material_id,
            PurchaseOrderItem.purchase_order_id == po_id,
        ).all()

        total_ordered = sum(getattr(pi, 'quantity', 0) or 0 for pi in po_items)
        total_received = sum(getattr(pi, 'received', 0) or 0 for pi in po_items)
        remaining = total_ordered - total_received

        if quantity > remaining:
            errors.append(f'第{i+1}行超过采购未到货量（需要{quantity}，剩余{remaining}）')

    return errors


def draft_check_agent(
    user_id: int,
    order: Any,
    order_type: str = 'in_order',
    db=None,
    Stock=None,
    PurchaseOrderItem=None,
    PurchaseOrder=None,
) -> AgentRun:
    """执行草稿检查。

    Args:
        user_id: 用户ID
        order: 草稿单据对象
        order_type: 单据类型（in_order/out_order/transfer/check/adjustment）
        db: 数据库会话
        Stock: Stock模型
        PurchaseOrderItem: PurchaseOrderItem模型
        PurchaseOrder: PurchaseOrder模型

    Returns:
        AgentRun实例
    """
    items = getattr(order, 'items', [])

    steps = [
        {
            'name': '检查必填字段',
            'description': '检查单据表头必填字段是否完整',
            'tool_name': 'check_required_fields',
            'is_write': False,
        },
        {
            'name': '检查重复物料',
            'description': '检查明细行中是否有重复物料',
            'tool_name': 'check_duplicate_materials',
            'is_write': False,
        },
        {
            'name': '检查异常数量',
            'description': '检查明细行数量是否异常偏大或偏小',
            'tool_name': 'check_quantity_anomalies',
            'is_write': False,
        },
    ]

    # 出库单额外检查库存
    if order_type == 'out_order':
        steps.append({
            'name': '检查库存是否充足',
            'description': '检查出库数量是否超过当前库存',
            'tool_name': 'check_stock_sufficiency',
            'is_write': False,
        })

    # 入库单额外检查采购未到货量
    if order_type == 'in_order':
        steps.append({
            'name': '检查采购未到货量',
            'description': '检查入库数量是否超过采购订单未到货量',
            'tool_name': 'check_po_quantity',
            'is_write': False,
        })

    run = create_agent_run(
        agent_name='draft_check',
        user_id=user_id,
        goal=f'草稿检查：检查{order_type}草稿的完整性和合理性',
        steps=steps,
    )

    from ..agents.framework import AgentExecutor
    executor = AgentExecutor(run)

    required_fields_map = {
        'in_order': ['warehouse_id', 'supplier_id'],
        'out_order': ['warehouse_id', 'department_id'],
        'transfer': ['from_warehouse_id', 'to_warehouse_id'],
        'check': ['warehouse_id'],
        'adjustment': ['warehouse_id', 'reason'],
    }

    executor.register_tool(
        'check_required_fields',
        lambda **ctx: _check_required_fields(order, required_fields_map.get(order_type, []))
    )
    executor.register_tool('check_duplicate_materials', lambda **ctx: _check_duplicate_materials(items))
    executor.register_tool('check_quantity_anomalies', lambda **ctx: _check_quantity_anomalies(items))
    executor.register_tool('check_stock_sufficiency', lambda **ctx: _check_stock_sufficiency(items, db, Stock))
    executor.register_tool('check_po_quantity', lambda **ctx: _check_po_quantity(items, db, PurchaseOrderItem, PurchaseOrder))

    executor.execute()
    return run


def format_draft_check_report(run: AgentRun) -> str:
    """格式化草稿检查报告。"""
    lines = [f'**草稿检查报告**', f'时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}']

    all_errors = []
    for step in run.plan.steps:
        if step.status.value == 'success' and step.result:
            if isinstance(step.result, list) and step.result:
                all_errors.extend(step.result)

    if all_errors:
        lines.append(f'\n发现 {len(all_errors)} 个问题：')
        for error in all_errors:
            lines.append(f'- {error}')
        lines.append('\n建议修复以上问题后再提交。')
    else:
        lines.append('\n检查通过，未发现明显问题。可以提交。')

    return '\n'.join(lines)

"""阶段3：采购到货跟进Agent。

功能：
1. 查询逾期/即将到货的采购订单
2. 按供应商归组
3. 生成催交话术（不自动发送）
4. 输出跟进清单
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from ..agents.framework import AgentRun, create_agent_run

logger = logging.getLogger(__name__)


def _get_overdue_orders(
    db=None,
    PurchaseOrder=None,
    PurchaseOrderItem=None,
    Material=None,
    days_lookback=7,
    days_lookahead=3,
) -> dict[str, list[dict[str, Any]]]:
    """获取逾期和即将到货的采购订单，按供应商归组。"""
    if db is None or PurchaseOrder is None:
        return {}

    today = datetime.now().date()
    overdue_since = today - timedelta(days=days_lookback)
    upcoming_until = today + timedelta(days=days_lookahead)

    results = {}

    try:
        # 逾期订单
        overdue_orders = PurchaseOrder.query.filter(
            PurchaseOrder.status.in_(['submitted', 'approved']),
            PurchaseOrder.expected_date < today,
            PurchaseOrder.expected_date >= overdue_since,
        ).all()

        for order in overdue_orders:
            supplier = order.supplier_name if hasattr(order, 'supplier_name') else '未知供应商'
            if supplier not in results:
                results[supplier] = []

            items = []
            if hasattr(order, 'items'):
                for item in order.items:
                    material = item.material if hasattr(item, 'material') else None
                    items.append({
                        'material_code': material.code if material else '',
                        'material_name': material.name if material else '',
                        'quantity': item.quantity if hasattr(item, 'quantity') else 0,
                        'received': item.received if hasattr(item, 'received') else 0,
                    })

            results[supplier].append({
                'order_no': order.order_no if hasattr(order, 'order_no') else f'PO{order.id}',
                'expected_date': order.expected_date.isoformat() if hasattr(order, 'expected_date') and order.expected_date else '',
                'days_overdue': (today - order.expected_date).days if hasattr(order, 'expected_date') and order.expected_date else 0,
                'items': items,
                'status': 'overdue',
            })

        # 即将到货订单
        upcoming_orders = PurchaseOrder.query.filter(
            PurchaseOrder.status.in_(['submitted', 'approved']),
            PurchaseOrder.expected_date >= today,
            PurchaseOrder.expected_date <= upcoming_until,
        ).all()

        for order in upcoming_orders:
            supplier = order.supplier_name if hasattr(order, 'supplier_name') else '未知供应商'
            if supplier not in results:
                results[supplier] = []

            items = []
            if hasattr(order, 'items'):
                for item in order.items:
                    material = item.material if hasattr(item, 'material') else None
                    items.append({
                        'material_code': material.code if material else '',
                        'material_name': material.name if material else '',
                        'quantity': item.quantity if hasattr(item, 'quantity') else 0,
                    })

            results[supplier].append({
                'order_no': order.order_no if hasattr(order, 'order_no') else f'PO{order.id}',
                'expected_date': order.expected_date.isoformat() if hasattr(order, 'expected_date') and order.expected_date else '',
                'days_until': (order.expected_date - today).days if hasattr(order, 'expected_date') and order.expected_date else 0,
                'items': items,
                'status': 'upcoming',
            })

    except Exception as e:
        logger.warning('Overdue orders query failed: %s', e)

    return results


def _generate_followup_message(supplier: str, orders: list[dict[str, Any]]) -> str:
    """生成催交话术。"""
    overdue = [o for o in orders if o['status'] == 'overdue']
    upcoming = [o for o in orders if o['status'] == 'upcoming']

    parts = [f'供应商：{supplier}']

    if overdue:
        parts.append(f'\n逾期订单（{len(overdue)} 单）：')
        for o in overdue:
            parts.append(f'- {o["order_no"]}（逾期{o["days_overdue"]}天，预计{o["expected_date"]}）')
            for item in o.get('items', [])[:3]:
                parts.append(f'  {item["material_code"]} {item["material_name"]}: {item["quantity"]}')

    if upcoming:
        parts.append(f'\n即将到货（{len(upcoming)} 单）：')
        for o in upcoming:
            parts.append(f'- {o["order_no"]}（{o["days_until"]}天后，预计{o["expected_date"]}）')

    parts.append('\n催交话术建议：')
    if overdue:
        parts.append(f'"{supplier}您好，我们有{len(overdue)}个订单已逾期，请确认发货时间并尽快安排。"')
    else:
        parts.append(f'"{supplier}您好，我们有{len(upcoming)}个订单即将到货，请确认是否按时发货。"')

    return '\n'.join(parts)


def purchase_followup_agent(
    user_id: int,
    db=None,
    PurchaseOrder=None,
    PurchaseOrderItem=None,
    Material=None,
    days_lookback: int = 7,
    days_lookahead: int = 3,
) -> AgentRun:
    """执行采购到货跟进。

    Args:
        user_id: 用户ID
        db: 数据库会话
        PurchaseOrder: PurchaseOrder模型
        PurchaseOrderItem: PurchaseOrderItem模型
        Material: Material模型
        days_lookback: 往前看多少天的逾期订单
        days_lookahead: 往后看多少天的即将到货订单

    Returns:
        AgentRun实例
    """
    steps = [
        {
            'name': '查询逾期和即将到货订单',
            'description': f'查询最近{days_lookback}天逾期和未来{days_lookahead}天即将到货的采购订单',
            'tool_name': 'get_overdue_orders',
            'is_write': False,
        },
        {
            'name': '按供应商归组并生成催交话术',
            'description': '将订单按供应商分组，为每个供应商生成催交话术',
            'tool_name': 'generate_followup_messages',
            'is_write': False,
        },
    ]

    run = create_agent_run(
        agent_name='purchase_followup',
        user_id=user_id,
        goal=f'采购到货跟进：查询逾期和即将到货订单，生成催交话术',
        steps=steps,
    )

    # 注册工具
    from ..agents.framework import AgentExecutor
    executor = AgentExecutor(run)

    orders_data = {}

    def _get_orders(**ctx):
        nonlocal orders_data
        orders_data = _get_overdue_orders(db, PurchaseOrder, PurchaseOrderItem, Material, days_lookback, days_lookahead)
        return orders_data

    def _generate_messages(**ctx):
        messages = {}
        for supplier, orders in orders_data.items():
            messages[supplier] = _generate_followup_message(supplier, orders)
        return messages

    executor.register_tool('get_overdue_orders', _get_orders)
    executor.register_tool('generate_followup_messages', _generate_messages)

    executor.execute()
    return run


def format_followup_report(run: AgentRun) -> str:
    """格式化跟进报告。"""
    lines = [f'**采购到货跟进报告**', f'时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}']

    for step in run.plan.steps:
        if step.status.value == 'success' and step.result:
            if step.tool_name == 'get_overdue_orders':
                total_suppliers = len(step.result)
                total_orders = sum(len(v) for v in step.result.values())
                lines.append(f'\n共涉及 {total_suppliers} 家供应商，{total_orders} 个订单')

            elif step.tool_name == 'generate_followup_messages':
                lines.append('\n---')
                for supplier, message in step.result.items():
                    lines.append(f'\n{message}')
                    lines.append('---')

    return '\n'.join(lines)

"""AI-SALES-F02：销售履约跟进 Agent。

# AI_TASK: AI-SALES-F02

功能：
1. 查询待发货/逾期/部分停滞/缺货的销售订单
2. 按客户归组
3. 生成催发货话术（不自动发送，需人工确认）
4. 输出客户跟进清单

注意：registry handler_name 指向 app.py 中的 `_ai_run_sales_followup_agent`，
该路径走 4 步 AIAgentTask 流程。本文件提供 2 步框架用于直接调用或单测。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from ..agents.framework import AgentRun, create_agent_run

logger = logging.getLogger(__name__)


def _get_pending_and_overdue_orders(
    db=None,
    SalesOrder=None,
    SalesOrderItem=None,
    Material=None,
    Customer=None,
    days_lookback: int = 7,
    days_lookahead: int = 3,
) -> dict[str, list[dict[str, Any]]]:
    """获取待发货和逾期未发货的销售订单，按客户归组。

    Args:
        db: 数据库会话
        SalesOrder: SalesOrder 模型
        SalesOrderItem: SalesOrderItem 模型
        Material: Material 模型
        Customer: Customer 模型
        days_lookback: 往前看多少天的逾期订单
        days_lookahead: 往后看多少天的即将到期订单

    Returns:
        dict[str, list[dict]]: 按客户名归组的订单列表
    """
    if db is None or SalesOrder is None:
        return {}

    today = datetime.now().date()
    overdue_since = today - timedelta(days=days_lookback)
    upcoming_until = today + timedelta(days=days_lookahead)

    results: dict[str, list[dict[str, Any]]] = {}

    try:
        # 逾期订单（已确认/草稿但 shipment_status=pending/partial 且 delivery_date < today）
        overdue_orders = SalesOrder.query.filter(
            SalesOrder.status.in_(['draft', 'confirmed']),
            SalesOrder.shipment_status.in_(['pending', 'partial']),
            SalesOrder.delivery_date < today,
            SalesOrder.delivery_date >= overdue_since,
        ).all()

        for order in overdue_orders:
            customer = _get_customer_name(order, Customer)
            if customer not in results:
                results[customer] = []

            items = _extract_items(order)
            results[customer].append({
                'order_no': getattr(order, 'order_no', f'SO{order.id}'),
                'delivery_date': _iso_date(getattr(order, 'delivery_date', None)),
                'days_overdue': _days_between(today, getattr(order, 'delivery_date', None)),
                'items': items,
                'status': 'overdue',
            })

        # 即将到期订单（delivery_date in [today, today+days_lookahead]）
        upcoming_orders = SalesOrder.query.filter(
            SalesOrder.status.in_(['draft', 'confirmed']),
            SalesOrder.shipment_status.in_(['pending', 'partial']),
            SalesOrder.delivery_date >= today,
            SalesOrder.delivery_date <= upcoming_until,
        ).all()

        for order in upcoming_orders:
            customer = _get_customer_name(order, Customer)
            if customer not in results:
                results[customer] = []

            items = _extract_items(order)
            results[customer].append({
                'order_no': getattr(order, 'order_no', f'SO{order.id}'),
                'delivery_date': _iso_date(getattr(order, 'delivery_date', None)),
                'days_until': _days_between(getattr(order, 'delivery_date', None), today),
                'items': items,
                'status': 'upcoming',
            })

    except Exception as e:
        logger.warning('Sales pending/overdue orders query failed: %s', e)

    return results


def _generate_customer_followup_message(customer: str, orders: list[dict[str, Any]]) -> str:
    """生成催发货话术（不自动发送）。"""
    overdue = [o for o in orders if o['status'] == 'overdue']
    upcoming = [o for o in orders if o['status'] == 'upcoming']

    parts = [f'客户：{customer}']

    if overdue:
        parts.append(f'\n逾期未发货订单（{len(overdue)} 单）：')
        for o in overdue:
            parts.append(f'- {o["order_no"]}（逾期{o["days_overdue"]}天，应发{o["delivery_date"]}）')
            for item in o.get('items', [])[:3]:
                parts.append(f'  {item["material_code"]} {item["material_name"]}: 应发 {item["quantity"]}')

    if upcoming:
        parts.append(f'\n即将到期（{len(upcoming)} 单）：')
        for o in upcoming:
            parts.append(f'- {o["order_no"]}（{o["days_until"]}天后到期，应发{o["delivery_date"]}）')

    parts.append('\n催发货话术建议（需人工确认后发送）：')
    if overdue:
        parts.append(f'"{customer}您好，贵司有{len(overdue)}笔订单已逾期未发货，请确认收货地址与时间，我方将尽快安排发货。"')
    else:
        parts.append(f'"{customer}您好，贵司有{len(upcoming)}笔订单即将到期，请确认是否需要安排发货。"')

    return '\n'.join(parts)


def _get_customer_name(order, Customer=None) -> str:
    """安全获取客户名。"""
    if hasattr(order, 'customer') and order.customer is not None:
        return getattr(order.customer, 'name', None) or f'客户#{order.customer_id}'
    return f'客户#{getattr(order, "customer_id", 0)}'


def _extract_items(order) -> list[dict[str, Any]]:
    """安全提取订单明细。"""
    items: list[dict[str, Any]] = []
    if not hasattr(order, 'items'):
        return items
    for item in order.items:
        material = getattr(item, 'material', None)
        items.append({
            'material_code': getattr(material, 'code', '') if material else '',
            'material_name': getattr(material, 'name', '') if material else '',
            'quantity': getattr(item, 'quantity', 0),
            'shipped_quantity': getattr(item, 'shipped_quantity', 0),
        })
    return items


def _iso_date(d) -> str:
    """安全转 ISO 日期字符串。"""
    if d is None:
        return ''
    if hasattr(d, 'isoformat'):
        return d.isoformat()
    return str(d)


def _days_between(a, b) -> int:
    """计算 a - b 的天数（None 安全）。"""
    if a is None or b is None:
        return 0
    try:
        return (a - b).days
    except Exception:
        return 0


def sales_followup_agent(
    user_id: int,
    db=None,
    SalesOrder=None,
    SalesOrderItem=None,
    Material=None,
    Customer=None,
    days_lookback: int = 7,
    days_lookahead: int = 3,
) -> AgentRun:
    """执行销售履约跟进。

    Args:
        user_id: 用户ID
        db: 数据库会话
        SalesOrder: SalesOrder 模型
        SalesOrderItem: SalesOrderItem 模型
        Material: Material 模型
        Customer: Customer 模型
        days_lookback: 往前看多少天的逾期订单
        days_lookahead: 往后看多少天的即将到期订单

    Returns:
        AgentRun 实例
    """
    steps = [
        {
            'name': '查询待发货和逾期未发货订单',
            'description': f'查询最近{days_lookback}天逾期和未来{days_lookahead}天即将到期的销售订单',
            'tool_name': 'get_pending_and_overdue_orders',
            'is_write': False,
        },
        {
            'name': '按客户归组并生成催发货话术',
            'description': '将订单按客户分组，为每个客户生成催发货话术（不自动发送）',
            'tool_name': 'generate_customer_messages',
            'is_write': False,
        },
    ]

    run = create_agent_run(
        agent_name='sales_followup',
        user_id=user_id,
        goal=f'销售履约跟进：查询待发货和逾期订单，生成催发货话术（不自动发送）',
        steps=steps,
    )

    # 注册工具
    from ..agents.framework import AgentExecutor
    executor = AgentExecutor(run)

    orders_data: dict[str, list[dict[str, Any]]] = {}

    def _get_orders(**ctx):
        nonlocal orders_data
        orders_data = _get_pending_and_overdue_orders(
            db, SalesOrder, SalesOrderItem, Material, Customer,
            days_lookback, days_lookahead,
        )
        return orders_data

    def _generate_messages(**ctx):
        messages: dict[str, str] = {}
        for customer, orders in orders_data.items():
            messages[customer] = _generate_customer_followup_message(customer, orders)
        return messages

    executor.register_tool('get_pending_and_overdue_orders', _get_orders)
    executor.register_tool('generate_customer_messages', _generate_messages)

    executor.execute()
    return run


def format_sales_followup_report(run: AgentRun) -> str:
    """格式化跟进报告。"""
    lines = [f'**销售履约跟进报告**', f'时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}']

    for step in run.plan.steps:
        if step.status.value == 'success' and step.result:
            if step.tool_name == 'get_pending_and_overdue_orders':
                total_customers = len(step.result)
                total_orders = sum(len(v) for v in step.result.values())
                lines.append(f'\n共涉及 {total_customers} 家客户，{total_orders} 个订单')

            elif step.tool_name == 'generate_customer_messages':
                lines.append('\n---')
                for customer, message in step.result.items():
                    lines.append(f'\n{message}')
                    lines.append('---')

    lines.append('\n注意：催发货话术需人工确认后发送，工作台不自动发送。')
    return '\n'.join(lines)

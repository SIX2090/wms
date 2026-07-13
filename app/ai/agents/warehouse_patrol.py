"""阶段3：仓库主管每日巡检Agent。

检查项：
1. 负库存物料
2. 低库存预警
3. 待处理单据（入库/出库/调拨/盘点）
4. 草稿阻塞（长时间未提交的草稿）
5. 库存异常（近期大幅波动）

输出优先任务卡，指导仓库主管今日工作。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from ..agents.framework import AgentRun, create_agent_run

logger = logging.getLogger(__name__)


def _check_negative_stock(db=None, Material=None, Stock=None) -> list[dict[str, Any]]:
    """检查负库存物料。"""
    if db is None or Material is None or Stock is None:
        return []

    results = []
    try:
        materials = Material.query.all()
        for m in materials:
            stock = Stock.query.filter_by(material_id=m.id).first()
            qty = stock.quantity if stock else 0
            if qty < 0:
                results.append({
                    'material_id': m.id,
                    'code': m.code,
                    'name': m.name,
                    'quantity': qty,
                    'severity': 'high',
                })
    except Exception as e:
        logger.warning('Negative stock check failed: %s', e)

    return results


def _check_low_stock(db=None, Material=None, Stock=None) -> list[dict[str, Any]]:
    """检查低库存预警。"""
    if db is None or Material is None or Stock is None:
        return []

    results = []
    try:
        materials = Material.query.filter(Material.min_stock.isnot(None)).all()
        for m in materials:
            stock = Stock.query.filter_by(material_id=m.id).first()
            qty = stock.quantity if stock else 0
            if qty <= m.min_stock and qty >= 0:
                results.append({
                    'material_id': m.id,
                    'code': m.code,
                    'name': m.name,
                    'quantity': qty,
                    'min_stock': m.min_stock,
                    'shortage': m.min_stock - qty,
                    'severity': 'medium',
                })
    except Exception as e:
        logger.warning('Low stock check failed: %s', e)

    return results


def _check_pending_documents(
    db=None,
    InOrder=None,
    OutOrder=None,
    TransferOrder=None,
    InventoryCheck=None,
) -> dict[str, int]:
    """检查待处理单据数量。"""
    if db is None:
        return {}

    counts = {}
    try:
        if InOrder:
            counts['pending_in'] = InOrder.query.filter_by(status='pending').count()
        if OutOrder:
            counts['pending_out'] = OutOrder.query.filter_by(status='pending').count()
        if TransferOrder:
            counts['pending_transfer'] = TransferOrder.query.filter_by(status='pending').count()
        if InventoryCheck:
            counts['pending_check'] = InventoryCheck.query.filter_by(status='pending').count()
    except Exception as e:
        logger.warning('Pending documents check failed: %s', e)

    return counts


def _check_stale_drafts(db=None, InOrder=None, OutOrder=None, days=3) -> list[dict[str, Any]]:
    """检查长时间未提交的草稿。"""
    if db is None:
        return []

    results = []
    cutoff = datetime.now() - timedelta(days=days)

    try:
        if InOrder:
            stale_in = InOrder.query.filter(
                InOrder.status == 'pending',
                InOrder.created_at < cutoff,
            ).limit(10).all()
            for order in stale_in:
                results.append({
                    'type': 'in_order',
                    'order_no': order.order_no if hasattr(order, 'order_no') else f'IN{order.id}',
                    'created_at': order.created_at.isoformat() if order.created_at else '',
                    'days_pending': (datetime.now() - order.created_at).days if order.created_at else 0,
                })

        if OutOrder:
            stale_out = OutOrder.query.filter(
                OutOrder.status == 'pending',
                OutOrder.created_at < cutoff,
            ).limit(10).all()
            for order in stale_out:
                results.append({
                    'type': 'out_order',
                    'order_no': order.order_no if hasattr(order, 'order_no') else f'OUT{order.id}',
                    'created_at': order.created_at.isoformat() if order.created_at else '',
                    'days_pending': (datetime.now() - order.created_at).days if order.created_at else 0,
                })
    except Exception as e:
        logger.warning('Stale drafts check failed: %s', e)

    return results


def warehouse_patrol_agent(
    user_id: int,
    db=None,
    Material=None,
    Stock=None,
    InOrder=None,
    OutOrder=None,
    TransferOrder=None,
    InventoryCheck=None,
) -> AgentRun:
    """执行仓库主管每日巡检。

    Args:
        user_id: 用户ID
        db: 数据库会话
        Material: Material模型
        Stock: Stock模型
        InOrder: InOrder模型
        OutOrder: OutOrder模型
        TransferOrder: TransferOrder模型
        InventoryCheck: InventoryCheck模型

    Returns:
        AgentRun实例
    """
    steps = [
        {
            'name': '检查负库存',
            'description': '查找所有负库存物料，这是最高优先级问题',
            'tool_name': 'check_negative_stock',
            'is_write': False,
        },
        {
            'name': '检查低库存预警',
            'description': '查找低于安全库存的物料',
            'tool_name': 'check_low_stock',
            'is_write': False,
        },
        {
            'name': '检查待处理单据',
            'description': '统计待入库/出库/调拨/盘点单据数量',
            'tool_name': 'check_pending_documents',
            'is_write': False,
        },
        {
            'name': '检查草稿阻塞',
            'description': '查找超过3天未提交的草稿',
            'tool_name': 'check_stale_drafts',
            'is_write': False,
        },
    ]

    run = create_agent_run(
        agent_name='warehouse_patrol',
        user_id=user_id,
        goal='仓库主管每日巡检：检查负库存、低库存、待处理单据和草稿阻塞',
        steps=steps,
    )

    # 注册工具
    from ..agents.framework import AgentExecutor
    executor = AgentExecutor(run)
    executor.register_tool('check_negative_stock', lambda **ctx: _check_negative_stock(db, Material, Stock))
    executor.register_tool('check_low_stock', lambda **ctx: _check_low_stock(db, Material, Stock))
    executor.register_tool('check_pending_documents', lambda **ctx: _check_pending_documents(
        db, InOrder, OutOrder, TransferOrder, InventoryCheck
    ))
    executor.register_tool('check_stale_drafts', lambda **ctx: _check_stale_drafts(db, InOrder, OutOrder))

    # 执行
    executor.execute()

    return run


def format_patrol_report(run: AgentRun) -> str:
    """格式化巡检报告。"""
    lines = [f'**仓库主管每日巡检报告**', f'时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}']

    for step in run.plan.steps:
        if step.status.value == 'success' and step.result:
            if step.tool_name == 'check_negative_stock':
                if step.result:
                    lines.append(f'\n**负库存物料 ({len(step.result)} 项)**')
                    for item in step.result[:5]:
                        lines.append(f'- {item["code"]} {item["name"]}: {item["quantity"]}')
                else:
                    lines.append('\n**负库存物料**: 无')

            elif step.tool_name == 'check_low_stock':
                if step.result:
                    lines.append(f'\n**低库存预警 ({len(step.result)} 项)**')
                    for item in step.result[:5]:
                        lines.append(f'- {item["code"]} {item["name"]}: {item["quantity"]}/{item["min_stock"]}')
                else:
                    lines.append('\n**低库存预警**: 无')

            elif step.tool_name == 'check_pending_documents':
                lines.append('\n**待处理单据**')
                for key, count in step.result.items():
                    label = {
                        'pending_in': '待入库',
                        'pending_out': '待出库',
                        'pending_transfer': '待调拨',
                        'pending_check': '待盘点',
                    }.get(key, key)
                    if count > 0:
                        lines.append(f'- {label}: {count}')

            elif step.tool_name == 'check_stale_drafts':
                if step.result:
                    lines.append(f'\n**草稿阻塞 ({len(step.result)} 项)**')
                    for item in step.result[:5]:
                        lines.append(f'- {item["order_no"]}: {item["days_pending"]}天')
                else:
                    lines.append('\n**草稿阻塞**: 无')

    return '\n'.join(lines)

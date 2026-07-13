"""阶段3：低库存补货Agent。

功能：
1. 结合现存库存、安全库存、未到货采购量、待审批请购量
2. 计算建议补货量
3. 生成可解释的补货建议
4. 可生成请购草稿（需确认）
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from ..agents.framework import AgentRun, create_agent_run

logger = logging.getLogger(__name__)


def _get_materials_needing_replenishment(
    db=None,
    Material=None,
    Stock=None,
    PurchaseOrder=None,
    PurchaseOrderItem=None,
    PurchaseRequest=None,
    PurchaseRequestItem=None,
    limit=50,
) -> list[dict[str, Any]]:
    """获取需要补货的物料列表。"""
    if db is None or Material is None or Stock is None:
        return []

    results = []
    try:
        materials = Material.query.filter(Material.min_stock.isnot(None)).limit(limit).all()

        for m in materials:
            stock = Stock.query.filter_by(material_id=m.id).first()
            current_qty = stock.quantity if stock else 0

            # 只处理低于安全库存的物料
            if current_qty > m.min_stock:
                continue

            # 计算未到货采购量
            open_po_qty = 0
            if PurchaseOrder and PurchaseOrderItem:
                po_items = PurchaseOrderItem.query.join(PurchaseOrder).filter(
                    PurchaseOrderItem.material_id == m.id,
                    PurchaseOrder.status.in_(['submitted', 'approved']),
                ).all()
                open_po_qty = sum(
                    (item.quantity or 0) - (item.received or 0)
                    for item in po_items
                )

            # 计算待审批请购量
            pending_pr_qty = 0
            if PurchaseRequest and PurchaseRequestItem:
                pr_items = PurchaseRequestItem.query.join(PurchaseRequest).filter(
                    PurchaseRequestItem.material_id == m.id,
                    PurchaseRequest.status == 'pending',
                ).all()
                pending_pr_qty = sum(item.quantity or 0 for item in pr_items)

            # 建议补货量 = 安全库存 - 当前库存 - 未到货 + 缓冲
            shortage = m.min_stock - current_qty - open_po_qty - pending_pr_qty
            if shortage <= 0:
                continue

            suggested_qty = max(shortage, m.min_stock * 0.5)  # 至少补到安全库存的50%

            results.append({
                'material_id': m.id,
                'code': m.code,
                'name': m.name,
                'spec': m.spec or '',
                'current_qty': current_qty,
                'min_stock': m.min_stock,
                'open_po_qty': open_po_qty,
                'pending_pr_qty': pending_pr_qty,
                'shortage': shortage,
                'suggested_qty': round(suggested_qty, 2),
                'unit': m.unit.name if hasattr(m, 'unit') and m.unit else '',
            })

        # 按缺货量排序
        results.sort(key=lambda x: x['shortage'], reverse=True)

    except Exception as e:
        logger.warning('Replenishment query failed: %s', e)

    return results


def _generate_replenishment_explanation(item: dict[str, Any]) -> str:
    """生成补货建议的解释。"""
    parts = [
        f'**{item["code"]} {item["name"]}**',
        f'当前库存：{item["current_qty"]} {item["unit"]}',
        f'安全库存：{item["min_stock"]} {item["unit"]}',
    ]

    if item['open_po_qty'] > 0:
        parts.append(f'未到货采购：{item["open_po_qty"]} {item["unit"]}')
    if item['pending_pr_qty'] > 0:
        parts.append(f'待审批请购：{item["pending_pr_qty"]} {item["unit"]}')

    parts.append(f'缺口：{item["shortage"]} {item["unit"]}')
    parts.append(f'**建议补货：{item["suggested_qty"]} {item["unit"]}**')

    return '\n'.join(parts)


def replenishment_agent(
    user_id: int,
    db=None,
    Material=None,
    Stock=None,
    PurchaseOrder=None,
    PurchaseOrderItem=None,
    PurchaseRequest=None,
    PurchaseRequestItem=None,
    limit: int = 50,
) -> AgentRun:
    """执行低库存补货分析。

    Args:
        user_id: 用户ID
        db: 数据库会话
        Material: Material模型
        Stock: Stock模型
        PurchaseOrder: PurchaseOrder模型
        PurchaseOrderItem: PurchaseOrderItem模型
        PurchaseRequest: PurchaseRequest模型
        PurchaseRequestItem: PurchaseRequestItem模型
        limit: 返回物料数量限制

    Returns:
        AgentRun实例
    """
    steps = [
        {
            'name': '查询需要补货的物料',
            'description': f'查询低于安全库存且有缺口的物料（最多{limit}项）',
            'tool_name': 'get_materials_needing_replenishment',
            'is_write': False,
        },
        {
            'name': '生成补货建议和解释',
            'description': '为每个物料生成可解释的补货建议',
            'tool_name': 'generate_replenishment_explanations',
            'is_write': False,
        },
    ]

    run = create_agent_run(
        agent_name='replenishment',
        user_id=user_id,
        goal=f'低库存补货分析：查询缺口物料并生成补货建议',
        steps=steps,
    )

    from ..agents.framework import AgentExecutor
    executor = AgentExecutor(run)

    materials_data = []

    def _get_materials(**ctx):
        nonlocal materials_data
        materials_data = _get_materials_needing_replenishment(
            db, Material, Stock, PurchaseOrder, PurchaseOrderItem,
            PurchaseRequest, PurchaseRequestItem, limit
        )
        return materials_data

    def _generate_explanations(**ctx):
        explanations = []
        for item in materials_data:
            explanations.append({
                'material': item,
                'explanation': _generate_replenishment_explanation(item),
            })
        return explanations

    executor.register_tool('get_materials_needing_replenishment', _get_materials)
    executor.register_tool('generate_replenishment_explanations', _generate_explanations)

    executor.execute()
    return run


def format_replenishment_report(run: AgentRun) -> str:
    """格式化补货报告。"""
    lines = [f'**低库存补货建议报告**', f'时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}']

    for step in run.plan.steps:
        if step.status.value == 'success' and step.result:
            if step.tool_name == 'get_materials_needing_replenishment':
                lines.append(f'\n共 {len(step.result)} 项物料需要补货')

            elif step.tool_name == 'generate_replenishment_explanations':
                lines.append('\n---')
                for item_data in step.result:
                    lines.append(f'\n{item_data["explanation"]}')
                    lines.append('---')

    return '\n'.join(lines)

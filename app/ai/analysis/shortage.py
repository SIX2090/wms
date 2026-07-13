"""阶段4：缺料分析工具。

识别当前库存不足且有未满足需求的物料。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


def shortage_analysis(
    db=None,
    Material=None,
    Stock=None,
    OutOrder=None,
    OutOrderItem=None,
    PurchaseOrder=None,
    PurchaseOrderItem=None,
    limit: int = 50,
) -> dict[str, Any]:
    """缺料分析。

    Args:
        db: 数据库会话
        Material: Material模型
        Stock: Stock模型
        OutOrder: OutOrder模型
        OutOrderItem: OutOrderItem模型
        PurchaseOrder: PurchaseOrder模型
        PurchaseOrderItem: PurchaseOrderItem模型
        limit: 返回物料数量限制

    Returns:
        包含 shortage_count / materials 的字典
    """
    if db is None or Material is None or Stock is None:
        return {
            'shortage_count': 0,
            'materials': [],
        }

    result = {
        'shortage_count': 0,
        'materials': [],
    }

    try:
        materials = Material.query.filter(Material.min_stock.isnot(None)).limit(limit).all()

        for m in materials:
            stock = Stock.query.filter_by(material_id=m.id).first()
            current_qty = stock.quantity if stock else 0

            # 只处理低于安全库存的物料
            if current_qty >= m.min_stock:
                continue

            # 计算待出库量
            pending_out = 0
            if OutOrder and OutOrderItem:
                pending_out = db.session.query(
                    db.func.coalesce(db.func.sum(OutOrderItem.quantity), 0)
                ).join(OutOrder).filter(
                    OutOrderItem.material_id == m.id,
                    OutOrder.status == 'pending',
                ).scalar() or 0

            # 计算未到货采购量
            open_po = 0
            if PurchaseOrder and PurchaseOrderItem:
                po_items = PurchaseOrderItem.query.join(PurchaseOrder).filter(
                    PurchaseOrderItem.material_id == m.id,
                    PurchaseOrder.status.in_(['submitted', 'approved']),
                ).all()
                open_po = sum(
                    (item.quantity or 0) - (item.received or 0)
                    for item in po_items
                )

            # 净缺口 = 安全库存 - 当前库存 - 未到货 + 待出库
            net_shortage = m.min_stock - current_qty - open_po + pending_out

            if net_shortage > 0:
                result['shortage_count'] += 1
                result['materials'].append({
                    'material_id': m.id,
                    'code': m.code,
                    'name': m.name,
                    'current_qty': current_qty,
                    'min_stock': m.min_stock,
                    'pending_out': pending_out,
                    'open_po': open_po,
                    'net_shortage': round(net_shortage, 2),
                    'unit': m.unit.name if hasattr(m, 'unit') and m.unit else '',
                })

        # 按净缺口降序排序
        result['materials'].sort(key=lambda x: x['net_shortage'], reverse=True)

    except Exception as e:
        logger.warning('Shortage analysis failed: %s', e)

    return result

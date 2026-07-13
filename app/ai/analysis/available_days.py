"""阶段4：预计可用天数分析工具。

根据当前库存和近期消耗速度，计算物料预计可用天数。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


def available_days_analysis(
    db=None,
    Material=None,
    Stock=None,
    StockTransaction=None,
    days: int = 30,
    limit: int = 100,
) -> dict[str, Any]:
    """预计可用天数分析。

    Args:
        db: 数据库会话
        Material: Material模型
        Stock: Stock模型
        StockTransaction: StockTransaction模型
        days: 消耗速度计算天数
        limit: 返回物料数量限制

    Returns:
        包含 critical_count / low_count / materials 的字典
    """
    if db is None or Material is None or Stock is None or StockTransaction is None:
        return {
            'critical_count': 0,
            'low_count': 0,
            'materials': [],
        }

    result = {
        'critical_count': 0,
        'low_count': 0,
        'materials': [],
    }

    try:
        cutoff = datetime.now() - timedelta(days=days)
        materials = Material.query.limit(limit).all()

        for m in materials:
            stock = Stock.query.filter_by(material_id=m.id).first()
            current_qty = stock.quantity if stock else 0

            # 跳过零库存
            if current_qty <= 0:
                continue

            # 计算日均消耗量
            out_qty = db.session.query(
                db.func.coalesce(db.func.sum(db.func.abs(StockTransaction.quantity)), 0)
            ).filter(
                StockTransaction.material_id == m.id,
                StockTransaction.transaction_type == 'out',
                StockTransaction.created_at >= cutoff,
            ).scalar() or 0

            daily_consumption = out_qty / days if days > 0 else 0

            # 预计可用天数 = 当前库存 / 日均消耗
            available_days = current_qty / daily_consumption if daily_consumption > 0 else 999

            material_data = {
                'material_id': m.id,
                'code': m.code,
                'name': m.name,
                'current_qty': current_qty,
                'daily_consumption': round(daily_consumption, 2),
                'available_days': round(available_days, 1),
                'unit': m.unit.name if hasattr(m, 'unit') and m.unit else '',
            }

            result['materials'].append(material_data)

            # 分类
            if available_days <= 7:
                result['critical_count'] += 1
            elif available_days <= 30:
                result['low_count'] += 1

        # 按可用天数升序排序（最紧急的在前）
        result['materials'].sort(key=lambda x: x['available_days'])

    except Exception as e:
        logger.warning('Available days analysis failed: %s', e)

    return result

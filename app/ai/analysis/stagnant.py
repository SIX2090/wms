"""阶段4：呆滞物料分析工具。

识别长期无出库记录的物料，计算呆滞天数和呆滞金额。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


def stagnant_material_analysis(
    db=None,
    Material=None,
    Stock=None,
    StockTransaction=None,
    stagnant_days: int = 180,
    limit: int = 100,
) -> dict[str, Any]:
    """呆滞物料分析。

    Args:
        db: 数据库会话
        Material: Material模型
        Stock: Stock模型
        StockTransaction: StockTransaction模型
        stagnant_days: 呆滞天数阈值（默认180天）
        limit: 返回物料数量限制

    Returns:
        包含 stagnant_count / stagnant_value / materials 的字典
    """
    if db is None or Material is None or Stock is None or StockTransaction is None:
        return {
            'stagnant_count': 0,
            'stagnant_value': 0.0,
            'materials': [],
        }

    result = {
        'stagnant_count': 0,
        'stagnant_value': 0.0,
        'materials': [],
    }

    try:
        cutoff = datetime.now() - timedelta(days=stagnant_days)
        materials = Material.query.limit(limit).all()

        for m in materials:
            stock = Stock.query.filter_by(material_id=m.id).first()
            current_qty = stock.quantity if stock else 0

            # 跳过零库存物料
            if current_qty <= 0:
                continue

            # 查找最近一次出库时间
            last_out = StockTransaction.query.filter(
                StockTransaction.material_id == m.id,
                StockTransaction.transaction_type == 'out',
            ).order_by(StockTransaction.created_at.desc()).first()

            if last_out and last_out.created_at:
                days_since_last_out = (datetime.now() - last_out.created_at).days
            else:
                days_since_last_out = stagnant_days + 1  # 从未出库

            # 判断是否呆滞
            if days_since_last_out >= stagnant_days:
                value = current_qty * (m.price or 0)
                result['stagnant_count'] += 1
                result['stagnant_value'] += value

                result['materials'].append({
                    'material_id': m.id,
                    'code': m.code,
                    'name': m.name,
                    'spec': m.spec or '',
                    'current_qty': current_qty,
                    'unit_price': m.price or 0,
                    'value': round(value, 2),
                    'days_since_last_out': days_since_last_out,
                    'last_out_date': last_out.created_at.strftime('%Y-%m-%d') if last_out and last_out.created_at else '从未出库',
                })

        # 按呆滞金额降序排序
        result['materials'].sort(key=lambda x: x['value'], reverse=True)

    except Exception as e:
        logger.warning('Stagnant material analysis failed: %s', e)

    return result

"""阶段4：库存周转分析工具。

计算物料库存周转率、周转天数，识别快周转和慢周转物料。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


def inventory_turnover_analysis(
    db=None,
    Material=None,
    Stock=None,
    StockTransaction=None,
    days: int = 90,
    limit: int = 50,
) -> dict[str, Any]:
    """库存周转分析。

    Args:
        db: 数据库会话
        Material: Material模型
        Stock: Stock模型
        StockTransaction: StockTransaction模型
        days: 分析天数
        limit: 返回物料数量限制

    Returns:
        包含 turnover_rate / turnover_days / fast_moving / slow_moving / materials 的字典
    """
    if db is None or Material is None or Stock is None or StockTransaction is None:
        return {
            'turnover_rate': 0.0,
            'turnover_days': 0.0,
            'fast_moving': [],
            'slow_moving': [],
            'materials': [],
        }

    result = {
        'turnover_rate': 0.0,
        'turnover_days': 0.0,
        'fast_moving': [],
        'slow_moving': [],
        'materials': [],
    }

    try:
        cutoff = datetime.now() - timedelta(days=days)
        materials = Material.query.limit(limit).all()

        total_turnover = 0.0
        material_count = 0

        for m in materials:
            stock = Stock.query.filter_by(material_id=m.id).first()
            current_qty = stock.quantity if stock else 0

            # 计算期间出库总量
            out_qty = db.session.query(
                db.func.coalesce(db.func.sum(db.func.abs(StockTransaction.quantity)), 0)
            ).filter(
                StockTransaction.material_id == m.id,
                StockTransaction.transaction_type == 'out',
                StockTransaction.created_at >= cutoff,
            ).scalar() or 0

            # 计算期间入库总量
            in_qty = db.session.query(
                db.func.coalesce(db.func.sum(db.func.abs(StockTransaction.quantity)), 0)
            ).filter(
                StockTransaction.material_id == m.id,
                StockTransaction.transaction_type == 'in',
                StockTransaction.created_at >= cutoff,
            ).scalar() or 0

            # 平均库存 = (期初 + 期末) / 2
            opening_qty = current_qty - in_qty + out_qty
            avg_qty = (opening_qty + current_qty) / 2 if (opening_qty + current_qty) > 0 else 0

            # 周转率 = 出库量 / 平均库存
            turnover_rate = out_qty / avg_qty if avg_qty > 0 else 0

            # 周转天数 = 分析天数 / 周转率
            turnover_days = days / turnover_rate if turnover_rate > 0 else 999

            material_data = {
                'material_id': m.id,
                'code': m.code,
                'name': m.name,
                'current_qty': current_qty,
                'out_qty': out_qty,
                'in_qty': in_qty,
                'turnover_rate': round(turnover_rate, 2),
                'turnover_days': round(turnover_days, 1),
            }

            result['materials'].append(material_data)

            if turnover_rate > 0:
                total_turnover += turnover_rate
                material_count += 1

            # 分类
            if turnover_days <= 30:
                result['fast_moving'].append(material_data)
            elif turnover_days >= 180:
                result['slow_moving'].append(material_data)

        # 整体周转率
        result['turnover_rate'] = round(total_turnover / material_count, 2) if material_count > 0 else 0
        result['turnover_days'] = round(days / result['turnover_rate'], 1) if result['turnover_rate'] > 0 else 999

    except Exception as e:
        logger.warning('Inventory turnover analysis failed: %s', e)

    return result

"""阶段1：库存查询工具模块。

从 app.py 中抽离的库存相关查询函数：
- material_query: 物料库存查询
- stock_transactions: 物料流水查询
- inventory_health: 库存健康分析
- low_stock_report: 低库存报告
- stock_value: 库存价值分析
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _escape_like_pattern(pattern: str) -> str:
    """转义 SQL LIKE 模式中的通配符。

    用户输入的关键字会直接拼到 ``ilike('%{keyword}%')`` 中，如果关键字包含
    ``%`` 或 ``_``，会被 SQL 当作通配符匹配意外范围（如 ``100%`` 会匹配
    ``1000``/``1009`` 等），属于数据泄露风险。这里把 ``%`` 和 ``_`` 转义为
    字面量，并使用 ``escape='\\'`` 让 SQLAlchemy 生成 ``ILIKE ... ESCAPE '\\'``
    子句识别转义。
    """
    if not pattern:
        return ''
    # 反斜杠必须先转义，否则会被当作 SQL 转义字符
    return pattern.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def material_query(keyword: str, limit: int = 8) -> list[dict[str, Any]]:
    """查询物料库存信息。

    Args:
        keyword: 物料编码或名称关键词
        limit: 返回数量限制

    Returns:
        物料列表，每项包含 id/code/name/spec/warehouse/quantity/alert_status
    """
    from app import db, Material, Stock

    results = []
    try:
        # 按编码或名称模糊匹配
        # 关键字中的 %/_ 必须转义为字面量，避免被 SQL LIKE 当作通配符
        escaped = _escape_like_pattern(keyword)
        materials = Material.query.filter(
            db.or_(
                Material.code.ilike(f'%{escaped}%', escape='\\'),
                Material.name.ilike(f'%{escaped}%', escape='\\'),
            )
        ).limit(limit).all()

        for m in materials:
            # 获取当前库存
            stock = Stock.query.filter_by(material_id=m.id).first()
            qty = stock.quantity if stock else 0

            # 判断预警状态
            alert_status = 'normal'
            if m.min_stock and qty <= m.min_stock:
                alert_status = 'low'
            if qty < 0:
                alert_status = 'negative'

            results.append({
                'id': m.id,
                'code': m.code,
                'name': m.name,
                'spec': m.spec or '',
                'warehouse': m.warehouse_name if hasattr(m, 'warehouse_name') else '',
                'quantity': qty,
                'alert_status': alert_status,
            })
    except Exception as exc:
        logger.warning('material_query failed: %s', exc)

    return results


def stock_transactions(material_id: int, limit: int = 8) -> list[dict[str, Any]]:
    """查询物料库存流水。

    Args:
        material_id: 物料ID
        limit: 返回数量限制

    Returns:
        流水列表，每项包含 date/type/quantity/related_order/remark
    """
    from app import db, StockTransaction

    results = []
    try:
        transactions = StockTransaction.query.filter_by(
            material_id=material_id
        ).order_by(StockTransaction.created_at.desc()).limit(limit).all()

        for t in transactions:
            results.append({
                'id': t.id,
                'date': t.created_at.strftime('%Y-%m-%d %H:%M') if t.created_at else '',
                'type': t.transaction_type,
                'quantity': t.quantity,
                'related_order': t.related_order_no or '',
                'remark': t.remark or '',
            })
    except Exception as exc:
        logger.warning('stock_transactions failed: %s', exc)

    return results


def inventory_health(days: int = 30, limit: int = 200) -> dict[str, Any]:
    """库存健康分析。

    Args:
        days: 分析天数
        limit: 返回物料数量限制

    Returns:
        包含 health_score / low_stock_count / negative_stock_count / slow_moving_count / materials 的字典
    """
    from app import db, Material, Stock, StockTransaction

    result = {
        'health_score': 100,
        'low_stock_count': 0,
        'negative_stock_count': 0,
        'slow_moving_count': 0,
        'materials': [],
    }

    try:
        materials = Material.query.limit(limit).all()
        cutoff_date = datetime.now() - timedelta(days=days)

        for m in materials:
            stock = Stock.query.filter_by(material_id=m.id).first()
            qty = stock.quantity if stock else 0

            # 检查负库存
            if qty < 0:
                result['negative_stock_count'] += 1
                result['health_score'] -= 5

            # 检查低库存
            if m.min_stock and qty <= m.min_stock:
                result['low_stock_count'] += 1
                result['health_score'] -= 2

            # 检查滞销（最近N天无出库记录）
            recent_out = StockTransaction.query.filter(
                StockTransaction.material_id == m.id,
                StockTransaction.transaction_type == 'out',
                StockTransaction.created_at >= cutoff_date,
            ).count()

            if recent_out == 0 and qty > 0:
                result['slow_moving_count'] += 1
                result['health_score'] -= 1

            # 记录异常物料
            if qty < 0 or (m.min_stock and qty <= m.min_stock) or (recent_out == 0 and qty > 0):
                result['materials'].append({
                    'id': m.id,
                    'code': m.code,
                    'name': m.name,
                    'quantity': qty,
                    'min_stock': m.min_stock or 0,
                    'recent_out_count': recent_out,
                    'issues': [
                        'negative_stock' if qty < 0 else None,
                        'low_stock' if m.min_stock and qty <= m.min_stock else None,
                        'slow_moving' if recent_out == 0 and qty > 0 else None,
                    ]
                })

        result['health_score'] = max(0, min(100, result['health_score']))
    except Exception as exc:
        logger.warning('inventory_health failed: %s', exc)

    return result


def low_stock_report() -> list[dict[str, Any]]:
    """低库存报告。

    Returns:
        低库存物料列表
    """
    from app import db, Material, Stock

    results = []
    try:
        materials = Material.query.filter(Material.min_stock.isnot(None)).all()

        for m in materials:
            stock = Stock.query.filter_by(material_id=m.id).first()
            qty = stock.quantity if stock else 0

            if qty <= m.min_stock:
                results.append({
                    'id': m.id,
                    'code': m.code,
                    'name': m.name,
                    'spec': m.spec or '',
                    'quantity': qty,
                    'min_stock': m.min_stock,
                    'shortage': m.min_stock - qty,
                })
    except Exception as exc:
        logger.warning('low_stock_report failed: %s', exc)

    return results


def stock_value_analysis(category: Optional[str] = None) -> dict[str, Any]:
    """库存价值分析。

    Args:
        category: 物料分类（可选）

    Returns:
        包含 total_value / material_count / by_category 的字典
    """
    from app import db, Material, Stock

    result = {
        'total_value': 0.0,
        'material_count': 0,
        'by_category': {},
    }

    try:
        query = Material.query
        if category:
            query = query.filter_by(category=category)

        materials = query.all()
        for m in materials:
            stock = Stock.query.filter_by(material_id=m.id).first()
            qty = stock.quantity if stock else 0
            value = qty * (m.price or 0)

            result['total_value'] += value
            result['material_count'] += 1

            cat = m.category or '未分类'
            if cat not in result['by_category']:
                result['by_category'][cat] = {'value': 0.0, 'count': 0}
            result['by_category'][cat]['value'] += value
            result['by_category'][cat]['count'] += 1
    except Exception as exc:
        logger.warning('stock_value_analysis failed: %s', exc)

    return result

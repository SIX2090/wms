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


def _ai_inventory_alert_status(material, qty: int, use_switch: bool = False) -> str:
    """AI 库存工具共用的两级告警判定（low / danger / normal / disabled）。

    BUG-2026-10-06-002：与 app.py 的 ``_alert_status_for`` 保持同一口径
    （AI-CI-GREEN-005-F05 唯一实现的调用方）。低库存语义统一为
    low（≤min_stock）+ danger（≤reorder_point/safety_stock）两级，
    避免 AI 工具与 dashboard / alert 页对同一数据给出不同答案。
    此处不直接 import app.py 的函数（避免循环依赖），逻辑等价复制并
    以单元测试锁同步（见 test_bug_2026_10_06_002_ai_tools_alert_status.py）。

    use_switch：是否读取 inventory_alert_enabled 开关。material_query 的
    ``alert_status`` 字段是纯展示字段（不驱动告警页/计数），历史行为从未受
    开关影响；low_stock_report / inventory_health 驱动低库存统计，与
    dashboard/alert 页同语义，须读开关（关闭时统计口径同 dashboard=disabled）。
    """
    if use_switch:
        from app import inventory_alert_enabled
        if not inventory_alert_enabled():
            return 'disabled'
    min_stock = material.min_stock or 0
    safety_stock = max(material.reorder_point or 0, min_stock)
    if min_stock <= 0 and safety_stock <= 0:
        return 'disabled'
    if qty <= min_stock:
        return 'low'
    if qty <= safety_stock:
        return 'danger'
    return 'normal'


def material_query(keyword: str, limit: int = 8) -> list[dict[str, Any]]:
    """查询物料库存信息。

    Args:
        keyword: 物料编码或名称关键词
        limit: 返回数量限制

    Returns:
        物料列表，每项包含 id/code/name/spec/warehouse/quantity/alert_status
    """
    from app import db, Material, get_all_warehouses_stock_quantities

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

        # BUG-2026-10-05-003：库存查询改全仓汇总（Σ②库位账）口径，
        # 不回退全局 Material.stock（A11/R2，与告警页 stock_query 同源）。
        all_wh_stock = get_all_warehouses_stock_quantities()

        for m in materials:
            # 获取当前库存：全仓仓库级口径（A11），非校验语境亦不回退总账
            qty = all_wh_stock.get(m.id, 0)

            # BUG-2026-10-06-002：对齐 _alert_status_for 两级口径（low/danger），
            # 原实现只判 min_stock，reorder_point 档物料会误报 normal。
            # alert_status 为纯展示字段（不驱动告警页），不读告警开关（use_switch=False）
            alert_status = _ai_inventory_alert_status(m, qty, use_switch=False)
            if qty < 0:
                alert_status = 'negative'

            results.append({
                'id': m.id,
                'code': m.code,
                'name': m.name,
                'spec': m.spec or '',
                'category': m.category.name if m.category else '',
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
    from app import (db, Material, StockTransaction,
                     get_all_warehouses_stock_quantities)

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

        # BUG-2026-10-05-003：健康度判定改全仓汇总（Σ②库位账）口径（A11/R2）。
        all_wh_stock = get_all_warehouses_stock_quantities()

        for m in materials:
            # 获取当前库存：全仓仓库级口径（A11），低库存/负库存判定不回退总账
            qty = all_wh_stock.get(m.id, 0)

            # 检查负库存
            if qty < 0:
                result['negative_stock_count'] += 1
                result['health_score'] -= 5

            # 检查低库存（BUG-2026-10-06-002：对齐 _alert_status_for 两级口径，
            # low（≤min_stock）+ danger（≤reorder_point/safety_stock）都算低库存；
            # 原实现只判 min_stock，漏 danger 档，与 dashboard/alert 页口径不一致）
            alert_status = _ai_inventory_alert_status(m, qty, use_switch=True)
            if alert_status in ('low', 'danger'):
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
            if qty < 0 or alert_status in ('low', 'danger') or (recent_out == 0 and qty > 0):
                result['materials'].append({
                    'id': m.id,
                    'code': m.code,
                    'name': m.name,
                    'quantity': qty,
                    'min_stock': m.min_stock or 0,
                    'recent_out_count': recent_out,
                    'issues': [
                        'negative_stock' if qty < 0 else None,
                        alert_status if alert_status in ('low', 'danger') else None,
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
    from app import db, Material, get_all_warehouses_stock_quantities

    results = []
    try:
        materials = Material.query.filter(Material.min_stock.isnot(None)).all()

        # BUG-2026-10-05-003：低库存判定改全仓汇总（Σ②库位账）口径（A11/R2）。
        all_wh_stock = get_all_warehouses_stock_quantities()

        for m in materials:
            # 获取当前库存：全仓仓库级口径（A11），低库存判定不回退总账
            qty = all_wh_stock.get(m.id, 0)

            # BUG-2026-10-06-002：对齐 _alert_status_for 两级口径，danger 档也进报告；
            # 原实现只判 qty <= m.min_stock，漏 reorder_point 档
            alert_status = _ai_inventory_alert_status(m, qty, use_switch=True)
            if alert_status in ('low', 'danger'):
                results.append({
                    'id': m.id,
                    'code': m.code,
                    'name': m.name,
                    'spec': m.spec or '',
                    'quantity': qty,
                    'min_stock': m.min_stock,
                    'alert_status': alert_status,
                    'shortage': max(
                        (m.reorder_point or m.min_stock or 0), m.min_stock or 0,
                    ) - qty,
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
    from app import db, Material, MaterialCategory

    result = {
        'total_value': 0.0,
        'material_count': 0,
        'by_category': {},
    }

    try:
        query = Material.query
        if category:
            # BUG-2026-10-06-002 附属修复：Material.category 是 relationship
            # （MaterialCategory 对象），按分类名过滤应走 name 或外键 category_id
            query = query.join(Material.category).filter(
                MaterialCategory.name == category)

        materials = query.all()
        for m in materials:
            # stock-truth:reason=库存价值分析为纯展示聚合（乘价格求和），无比较/校验语境，按 INVENTORY_TRUTH.md §5 允许使用全局总账
            qty = m.stock or 0
            value = qty * (m.price or 0)

            result['total_value'] += value
            result['material_count'] += 1

            cat = m.category.name if m.category else '未分类'
            if cat not in result['by_category']:
                result['by_category'][cat] = {'value': 0.0, 'count': 0}
            result['by_category'][cat]['value'] += value
            result['by_category'][cat]['count'] += 1
    except Exception as exc:
        logger.warning('stock_value_analysis failed: %s', exc)

    return result

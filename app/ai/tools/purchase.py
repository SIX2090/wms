"""阶段1：采购查询工具模块。

从 app.py 中抽离的采购相关查询函数：
- purchase_insights: 采购工作台
- supplier_analysis: 供应商分析
- pending_purchase_orders: 待处理采购单
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


def purchase_insights(days: int = 30) -> dict[str, Any]:
    """采购工作台概览。

    Args:
        days: 统计天数

    Returns:
        包含 pending_count / completed_count / total_amount / suppliers 的字典
    """
    from app import db, PurchaseOrder

    result = {
        'pending_count': 0,
        'completed_count': 0,
        'total_amount': 0.0,
        'suppliers': {},
    }

    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        orders = PurchaseOrder.query.filter(
            PurchaseOrder.created_at >= cutoff_date
        ).all()

        for order in orders:
            if order.status == 'pending':
                result['pending_count'] += 1
            elif order.status in ('completed', 'received'):
                result['completed_count'] += 1

            result['total_amount'] += order.total_amount or 0

            supplier = order.supplier_name or '未知供应商'
            if supplier not in result['suppliers']:
                result['suppliers'][supplier] = {'count': 0, 'amount': 0.0}
            result['suppliers'][supplier]['count'] += 1
            result['suppliers'][supplier]['amount'] += order.total_amount or 0
    except Exception as exc:
        logger.warning('purchase_insights failed: %s', exc)

    return result


def supplier_analysis(days: int = 90, limit: int = 12) -> list[dict[str, Any]]:
    """供应商分析。

    Args:
        days: 分析天数
        limit: 返回供应商数量限制

    Returns:
        供应商列表，包含 name/order_count/total_amount/avg_lead_time
    """
    from app import db, PurchaseOrder

    results = []
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        orders = PurchaseOrder.query.filter(
            PurchaseOrder.created_at >= cutoff_date
        ).all()

        supplier_stats = {}
        for order in orders:
            supplier = order.supplier_name or '未知供应商'
            if supplier not in supplier_stats:
                supplier_stats[supplier] = {
                    'name': supplier,
                    'order_count': 0,
                    'total_amount': 0.0,
                    'lead_times': [],
                }
            supplier_stats[supplier]['order_count'] += 1
            supplier_stats[supplier]['total_amount'] += order.total_amount or 0

            if order.lead_time_days:
                supplier_stats[supplier]['lead_times'].append(order.lead_time_days)

        # 计算平均交期
        for stats in supplier_stats.values():
            if stats['lead_times']:
                stats['avg_lead_time'] = sum(stats['lead_times']) / len(stats['lead_times'])
            else:
                stats['avg_lead_time'] = None
            del stats['lead_times']
            results.append(stats)

        # 按订单数排序
        results.sort(key=lambda x: x['order_count'], reverse=True)
        results = results[:limit]
    except Exception as exc:
        logger.warning('supplier_analysis failed: %s', exc)

    return results


def pending_purchase_orders(limit: int = 12) -> list[dict[str, Any]]:
    """待处理采购单。

    Args:
        limit: 返回数量限制

    Returns:
        待处理采购单列表
    """
    from app import db, PurchaseOrder

    results = []
    try:
        orders = PurchaseOrder.query.filter_by(status='pending').order_by(
            PurchaseOrder.created_at.asc()
        ).limit(limit).all()

        for order in orders:
            results.append({
                'id': order.id,
                'order_no': order.order_no,
                'supplier': order.supplier_name or '',
                'total_amount': order.total_amount or 0,
                'created_at': order.created_at.strftime('%Y-%m-%d') if order.created_at else '',
                'days_pending': (datetime.now() - order.created_at).days if order.created_at else 0,
            })
    except Exception as exc:
        logger.warning('pending_purchase_orders failed: %s', exc)

    return results

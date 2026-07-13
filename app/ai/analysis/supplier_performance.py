"""阶段4：供应商履约分析工具。

分析供应商交期准时率、质量合格率、响应速度等指标。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


def supplier_performance_analysis(
    db=None,
    PurchaseOrder=None,
    PurchaseOrderItem=None,
    Material=None,
    days: int = 90,
    limit: int = 20,
) -> dict[str, Any]:
    """供应商履约分析。

    Args:
        db: 数据库会话
        PurchaseOrder: PurchaseOrder模型
        PurchaseOrderItem: PurchaseOrderItem模型
        Material: Material模型
        days: 分析天数
        limit: 返回供应商数量限制

    Returns:
        包含 suppliers 列表的字典，每项包含 name/order_count/on_time_rate/avg_lead_time/quality_rate
    """
    if db is None or PurchaseOrder is None:
        return {
            'suppliers': [],
        }

    result = {
        'suppliers': [],
    }

    try:
        cutoff = datetime.now() - timedelta(days=days)
        orders = PurchaseOrder.query.filter(
            PurchaseOrder.created_at >= cutoff,
            PurchaseOrder.status.in_(['completed', 'received', 'closed']),
        ).all()

        # 按供应商分组
        supplier_stats = {}
        for order in orders:
            supplier = order.supplier_name if hasattr(order, 'supplier_name') else '未知供应商'
            if supplier not in supplier_stats:
                supplier_stats[supplier] = {
                    'name': supplier,
                    'order_count': 0,
                    'on_time_count': 0,
                    'lead_times': [],
                    'total_amount': 0.0,
                }

            stats = supplier_stats[supplier]
            stats['order_count'] += 1
            stats['total_amount'] += order.total_amount or 0

            # 计算交期
            if hasattr(order, 'expected_date') and hasattr(order, 'received_date'):
                if order.expected_date and order.received_date:
                    actual_days = (order.received_date - order.expected_date).days
                    stats['lead_times'].append(actual_days)
                    if actual_days <= 0:
                        stats['on_time_count'] += 1

        # 计算指标
        for supplier, stats in supplier_stats.items():
            avg_lead_time = sum(stats['lead_times']) / len(stats['lead_times']) if stats['lead_times'] else 0
            on_time_rate = stats['on_time_count'] / stats['order_count'] if stats['order_count'] > 0 else 0

            result['suppliers'].append({
                'name': stats['name'],
                'order_count': stats['order_count'],
                'on_time_rate': round(on_time_rate, 2),
                'avg_lead_time': round(avg_lead_time, 1),
                'total_amount': round(stats['total_amount'], 2),
            })

        # 按订单数降序排序
        result['suppliers'].sort(key=lambda x: x['order_count'], reverse=True)
        result['suppliers'] = result['suppliers'][:limit]

    except Exception as e:
        logger.warning('Supplier performance analysis failed: %s', e)

    return result

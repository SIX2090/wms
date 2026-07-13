"""AI巡检调度器 - 定时执行巡检规则并生成告警"""
from __future__ import annotations

import json
import logging
from datetime import datetime, date, timedelta
from typing import Any

from flask import current_app
from sqlalchemy import func, or_


logger = logging.getLogger(__name__)


# 巡检规则类型常量
RULE_TYPE_NEGATIVE_STOCK = 'negative_stock'
RULE_TYPE_LOW_STOCK = 'low_stock'
RULE_TYPE_OVERDUE_ORDER = 'overdue_order'
RULE_TYPE_PENDING_DRAFT = 'pending_draft'
RULE_TYPE_PURCHASE_DELAY = 'purchase_delay'
RULE_TYPE_SLOW_MOVING = 'slow_moving'


def run_patrol(app, db, models: dict[str, Any]) -> dict[str, Any]:
    """执行一次完整巡检，返回巡检结果摘要"""
    from app import AIPatrolRule, AIPatrolAlert

    started_at = datetime.now()
    summary = {
        'started_at': started_at.isoformat(),
        'rules_evaluated': 0,
        'alerts_created': 0,
        'alerts_by_severity': {'critical': 0, 'warning': 0, 'info': 0},
        'errors': [],
    }

    with app.app_context():
        rules = AIPatrolRule.query.filter_by(enabled=True).all()
        summary['rules_evaluated'] = len(rules)

        for rule in rules:
            try:
                alerts = _evaluate_rule(rule, db, models)
                for alert_data in alerts:
                    alert = _create_alert(rule, alert_data)
                    if alert:
                        summary['alerts_created'] += 1
                        severity = alert_data.get('severity', rule.severity)
                        summary['alerts_by_severity'][severity] = summary['alerts_by_severity'].get(severity, 0) + 1
            except Exception as exc:
                logger.exception('Patrol rule %s failed: %s', rule.id, exc)
                summary['errors'].append({'rule_id': rule.id, 'rule_name': rule.name, 'error': str(exc)})

        summary['completed_at'] = datetime.now().isoformat()
        summary['duration_ms'] = int((datetime.now() - started_at).total_seconds() * 1000)

    return summary


def _evaluate_rule(rule, db, models: dict[str, Any]) -> list[dict[str, Any]]:
    """评估单条巡检规则，返回告警数据列表"""
    Material = models['Material']
    PurchaseOrder = models['PurchaseOrder']
    InOrder = models['InOrder']
    OutOrder = models['OutOrder']
    TransferOrder = models['TransferOrder']
    InventoryCheck = models['InventoryCheck']
    AdjustmentOrder = models['AdjustmentOrder']

    alerts = []

    if rule.rule_type == RULE_TYPE_NEGATIVE_STOCK:
        negative_materials = Material.query.filter(Material.stock < 0).all()
        if negative_materials:
            alerts.append({
                'title': f'发现 {len(negative_materials)} 项负库存物料',
                'message': f'以下物料库存为负数，需要立即处理：{", ".join(m.code or m.name for m in negative_materials[:10])}',
                'severity': 'critical',
                'data_context': {
                    'material_ids': [m.id for m in negative_materials],
                    'count': len(negative_materials),
                },
            })

    elif rule.rule_type == RULE_TYPE_LOW_STOCK:
        threshold = rule.threshold_value or 0
        low_stock_materials = Material.query.filter(
            Material.stock <= Material.min_stock,
            Material.min_stock > threshold,
        ).all()
        if low_stock_materials:
            alerts.append({
                'title': f'发现 {len(low_stock_materials)} 项低库存物料',
                'message': f'以下物料库存低于安全库存：{", ".join(m.code or m.name for m in low_stock_materials[:10])}',
                'severity': 'warning',
                'data_context': {
                    'material_ids': [m.id for m in low_stock_materials],
                    'count': len(low_stock_materials),
                },
            })

    elif rule.rule_type == RULE_TYPE_OVERDUE_ORDER:
        threshold_days = rule.threshold_days or 0
        cutoff_date = date.today() - timedelta(days=threshold_days)
        overdue_orders = PurchaseOrder.query.filter(
            PurchaseOrder.status.in_(['pending', 'partial']),
            PurchaseOrder.expected_date < cutoff_date,
        ).all()
        if overdue_orders:
            alerts.append({
                'title': f'发现 {len(overdue_orders)} 张采购订单逾期超过 {threshold_days} 天',
                'message': f'以下采购订单已逾期：{", ".join(o.order_no for o in overdue_orders[:10])}',
                'severity': 'warning',
                'data_context': {
                    'order_ids': [o.id for o in overdue_orders],
                    'count': len(overdue_orders),
                },
            })

    elif rule.rule_type == RULE_TYPE_PENDING_DRAFT:
        threshold_days = rule.threshold_days or 7
        cutoff_date = datetime.now() - timedelta(days=threshold_days)
        pending_drafts = (
            InOrder.query.filter(InOrder.status == 'pending', InOrder.created_at < cutoff_date).count()
            + OutOrder.query.filter(OutOrder.status == 'pending', OutOrder.created_at < cutoff_date).count()
            + TransferOrder.query.filter(TransferOrder.status == 'pending', TransferOrder.created_at < cutoff_date).count()
            + InventoryCheck.query.filter(InventoryCheck.status == 'pending', InventoryCheck.created_at < cutoff_date).count()
            + AdjustmentOrder.query.filter(AdjustmentOrder.status == 'pending', AdjustmentOrder.created_at < cutoff_date).count()
        )
        if pending_drafts > 0:
            alerts.append({
                'title': f'发现 {pending_drafts} 张草稿超过 {threshold_days} 天未处理',
                'message': f'有 {pending_drafts} 张单据草稿长时间未提交或处理，建议检查并清理。',
                'severity': 'info',
                'data_context': {
                    'count': pending_drafts,
                    'threshold_days': threshold_days,
                },
            })

    elif rule.rule_type == RULE_TYPE_PURCHASE_DELAY:
        threshold_days = rule.threshold_days or 30
        cutoff_date = date.today() - timedelta(days=threshold_days)
        delayed_materials = (
            db.session.query(Material)
            .join(PurchaseOrder)
            .filter(
                PurchaseOrder.date >= cutoff_date,
                PurchaseOrder.status.in_(['pending', 'partial']),
            )
            .group_by(Material.id)
            .having(func.count(PurchaseOrder.id) >= 3)
            .all()
        )
        if delayed_materials:
            alerts.append({
                'title': f'发现 {len(delayed_materials)} 项物料采购延迟',
                'message': f'以下物料近 {threshold_days} 天内有3次以上未完成采购：{", ".join(m.code or m.name for m in delayed_materials[:10])}',
                'severity': 'warning',
                'data_context': {
                    'material_ids': [m.id for m in delayed_materials],
                    'count': len(delayed_materials),
                },
            })

    elif rule.rule_type == RULE_TYPE_SLOW_MOVING:
        threshold_days = rule.threshold_days or 90
        cutoff_date = datetime.now() - timedelta(days=threshold_days)
        StockTransaction = models['StockTransaction']
        slow_materials = (
            db.session.query(Material)
            .outerjoin(StockTransaction, (StockTransaction.material_id == Material.id) & (StockTransaction.created_at >= cutoff_date))
            .group_by(Material.id)
            .having(func.count(StockTransaction.id) == 0)
            .filter(Material.stock > 0)
            .all()
        )
        if slow_materials:
            alerts.append({
                'title': f'发现 {len(slow_materials)} 项呆滞物料（{threshold_days}天无出库）',
                'message': f'以下物料超过 {threshold_days} 天无出库记录：{", ".join(m.code or m.name for m in slow_materials[:10])}',
                'severity': 'info',
                'data_context': {
                    'material_ids': [m.id for m in slow_materials],
                    'count': len(slow_materials),
                },
            })

    return alerts


def _create_alert(rule, alert_data: dict[str, Any]):
    """创建告警记录"""
    from app import AIPatrolAlert

    # 检查是否已存在相同规则的活跃告警（避免重复）
    existing = AIPatrolAlert.query.filter_by(
        rule_id=rule.id,
        status='active',
    ).first()

    if existing:
        # 更新现有告警
        existing.title = alert_data['title']
        existing.message = alert_data['message']
        existing.data_context = json.dumps(alert_data.get('data_context', {}), ensure_ascii=False)
        existing.severity = alert_data.get('severity', rule.severity)
        return existing

    # 创建新告警
    alert = AIPatrolAlert(
        rule_id=rule.id,
        alert_type=rule.rule_type,
        severity=alert_data.get('severity', rule.severity),
        title=alert_data['title'],
        message=alert_data['message'],
        data_context=json.dumps(alert_data.get('data_context', {}), ensure_ascii=False),
        status='active',
    )
    db.session.add(alert)
    db.session.commit()
    return alert


def get_default_rules() -> list[dict[str, Any]]:
    """返回默认巡检规则配置"""
    return [
        {
            'name': '负库存检测',
            'description': '检测库存为负的物料，需要立即处理',
            'rule_type': RULE_TYPE_NEGATIVE_STOCK,
            'severity': 'critical',
            'enabled': True,
        },
        {
            'name': '低库存预警',
            'description': '检测库存低于安全库存的物料',
            'rule_type': RULE_TYPE_LOW_STOCK,
            'threshold_value': 0,
            'severity': 'warning',
            'enabled': True,
        },
        {
            'name': '采购订单逾期检测',
            'description': '检测超过预期日期未完成的采购订单',
            'rule_type': RULE_TYPE_OVERDUE_ORDER,
            'threshold_days': 0,
            'severity': 'warning',
            'enabled': True,
        },
        {
            'name': '草稿长时间未处理',
            'description': '检测超过指定天数未处理的草稿单据',
            'rule_type': RULE_TYPE_PENDING_DRAFT,
            'threshold_days': 7,
            'severity': 'info',
            'enabled': True,
        },
        {
            'name': '采购延迟检测',
            'description': '检测近期多次采购未完成的物料',
            'rule_type': RULE_TYPE_PURCHASE_DELAY,
            'threshold_days': 30,
            'severity': 'warning',
            'enabled': True,
        },
        {
            'name': '呆滞物料检测',
            'description': '检测长时间无出库记录的物料',
            'rule_type': RULE_TYPE_SLOW_MOVING,
            'threshold_days': 90,
            'severity': 'info',
            'enabled': True,
        },
    ]


def initialize_default_rules(db, admin_user_id: int) -> None:
    """初始化默认巡检规则（如果不存在）"""
    from app import AIPatrolRule

    existing_count = AIPatrolRule.query.count()
    if existing_count > 0:
        return

    default_rules = get_default_rules()
    for rule_data in default_rules:
        rule = AIPatrolRule(
            name=rule_data['name'],
            description=rule_data['description'],
            rule_type=rule_data['rule_type'],
            threshold_value=rule_data.get('threshold_value'),
            threshold_days=rule_data.get('threshold_days'),
            severity=rule_data['severity'],
            enabled=rule_data['enabled'],
            notify_roles=json.dumps(['admin', 'warehouse'], ensure_ascii=False),
            created_by=admin_user_id,
        )
        db.session.add(rule)

    db.session.commit()
    logger.info('Initialized %d default patrol rules', len(default_rules))

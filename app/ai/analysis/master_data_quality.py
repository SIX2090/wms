"""阶段4：主数据质量评分工具。

评估物料、供应商、客户等基础资料的完整性和准确性。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def master_data_quality_score(
    db=None,
    Material=None,
    Supplier=None,
    Customer=None,
    limit: int = 200,
) -> dict[str, Any]:
    """主数据质量评分。

    Args:
        db: 数据库会话
        Material: Material模型
        Supplier: Supplier模型
        Customer: Customer模型
        limit: 分析物料数量限制

    Returns:
        包含 overall_score / material_score / supplier_score / customer_score / issues 的字典
    """
    if db is None or Material is None:
        return {
            'overall_score': 0,
            'material_score': 0,
            'supplier_score': 0,
            'customer_score': 0,
            'issues': [],
        }

    result = {
        'overall_score': 0,
        'material_score': 0,
        'supplier_score': 0,
        'customer_score': 0,
        'issues': [],
    }

    try:
        # 物料质量评分
        materials = Material.query.limit(limit).all()
        material_issues = []
        material_score = 100

        for m in materials:
            issues = []

            # 检查必填字段
            if not m.code:
                issues.append('缺少编码')
                material_score -= 5
            if not m.name:
                issues.append('缺少名称')
                material_score -= 5
            if not m.spec:
                issues.append('缺少规格')
                material_score -= 2
            if not m.unit:
                issues.append('缺少单位')
                material_score -= 3
            if m.min_stock is None:
                issues.append('未设置安全库存')
                material_score -= 2
            if not m.price or m.price <= 0:
                issues.append('未设置参考价格')
                material_score -= 1

            if issues:
                material_issues.append({
                    'material_id': m.id,
                    'code': m.code or '未知',
                    'name': m.name or '未知',
                    'issues': issues,
                })

        result['material_score'] = max(0, min(100, material_score))
        result['issues'].extend(material_issues[:20])  # 最多返回20个问题

        # 供应商质量评分（简化）
        supplier_score = 80  # 默认分数
        if Supplier:
            suppliers = Supplier.query.all()
            supplier_issues_count = 0
            for s in suppliers:
                if not s.name:
                    supplier_issues_count += 1
                    supplier_score -= 5
                if not s.contact:
                    supplier_score -= 2
            result['supplier_score'] = max(0, min(100, supplier_score))

        # 客户质量评分（简化）
        customer_score = 80  # 默认分数
        if Customer:
            customers = Customer.query.all()
            for c in customers:
                if not c.name:
                    customer_score -= 5
                if not c.contact:
                    customer_score -= 2
            result['customer_score'] = max(0, min(100, customer_score))

        # 整体评分 = 加权平均
        result['overall_score'] = round(
            result['material_score'] * 0.6 +
            result['supplier_score'] * 0.2 +
            result['customer_score'] * 0.2,
            1
        )

    except Exception as e:
        logger.warning('Master data quality score failed: %s', e)

    return result

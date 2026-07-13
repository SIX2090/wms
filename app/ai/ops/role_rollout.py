"""阶段5：分角色灰度发布模块。

根据用户角色控制AI功能的可见性和可用性：
- 管理员：全部功能
- 仓库主管：仓库巡检/库存分析/文档识别
- 采购员：采购跟进/供应商分析/文档识别
- 生产人员：领料草稿/库存查询
- 普通用户：只读查询+知识库
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from .feature_flags import FeatureFlagManager, RolloutMode, get_feature_manager

logger = logging.getLogger(__name__)


# 角色-功能映射
ROLE_FEATURE_MAP: dict[str, list[str]] = {
    'admin': [
        'ai_chat', 'ai_vision', 'ai_drafts', 'ai_agents', 'ai_analysis',
        'warehouse_insights', 'purchase_insights', 'inventory_health',
        'master_data_insights', 'admin_insights', 'knowledge_base',
        'in_order_draft', 'out_order_draft', 'transfer_draft',
        'check_draft', 'adjustment_draft', 'purchase_receive_draft',
        'warehouse_patrol_agent', 'purchase_followup_agent',
        'replenishment_planning', 'replenishment_smart',
        'alias_management', 'usage_help',
    ],
    'warehouse_manager': [
        'ai_chat', 'ai_vision', 'ai_drafts',
        'warehouse_insights', 'inventory_health', 'knowledge_base',
        'in_order_draft', 'out_order_draft', 'transfer_draft',
        'check_draft', 'adjustment_draft',
        'warehouse_patrol_agent', 'usage_help',
    ],
    'purchase': [
        'ai_chat', 'ai_vision', 'ai_drafts',
        'purchase_insights', 'knowledge_base',
        'purchase_receive_draft', 'purchase_request_draft',
        'purchase_followup_agent', 'replenishment_planning',
        'usage_help',
    ],
    'production': [
        'ai_chat', 'ai_drafts',
        'warehouse_insights', 'knowledge_base',
        'out_order_draft', 'usage_help',
    ],
    'viewer': [
        'ai_chat',
        'warehouse_insights', 'purchase_insights', 'knowledge_base',
        'usage_help',
    ],
}


def get_allowed_features(user_role: str) -> list[str]:
    """获取角色允许的功能列表。"""
    return ROLE_FEATURE_MAP.get(user_role, ROLE_FEATURE_MAP.get('viewer', []))


def is_feature_allowed(
    feature_name: str,
    user_role: str = '',
    user_id: int = 0,
) -> bool:
    """检查功能是否对指定角色允许。

    Args:
        feature_name: 功能名称
        user_role: 用户角色
        user_id: 用户ID

    Returns:
        是否允许
    """
    # 管理员全部允许
    if user_role == 'admin':
        return True

    # 角色功能映射检查
    allowed = get_allowed_features(user_role)
    if feature_name not in allowed:
        return False

    # Feature Flag检查
    fm = get_feature_manager()
    return fm.is_feature_available(feature_name, user_id, user_role)


def get_role_capabilities(user_role: str) -> dict[str, Any]:
    """获取角色能力概览。"""
    features = get_allowed_features(user_role)

    capabilities = {
        'role': user_role,
        'total_features': len(features),
        'chat': 'ai_chat' in features,
        'vision': 'ai_vision' in features,
        'drafts': any(f.endswith('_draft') for f in features),
        'agents': any('agent' in f for f in features),
        'analysis': any('insights' in f or 'health' in f for f in features),
        'features': features,
    }

    return capabilities


def get_role_comparison() -> dict[str, dict]:
    """获取所有角色能力对比。"""
    comparison = {}
    for role in ROLE_FEATURE_MAP:
        comparison[role] = get_role_capabilities(role)
    return comparison

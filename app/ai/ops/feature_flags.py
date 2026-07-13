"""阶段5：Feature Flags灰度发布模块。

控制AI功能的灰度发布：
- 全局开关
- 发布模式（全部/只读/草稿/管理员）
- 分角色灰度
- 分用户灰度
- 功能级别开关
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RolloutMode(str, Enum):
    """发布模式。"""
    ALL = 'all'  # 全部用户
    READ_ONLY = 'read_only'  # 只读模式（查询+知识）
    READ_DRAFT = 'read_draft'  # 只读+草稿
    ADMIN_ONLY = 'admin_only'  # 仅管理员
    DISABLED = 'disabled'  # 完全关闭


class FeatureFlag:
    """单个Feature Flag。"""

    def __init__(
        self,
        name: str,
        enabled: bool = True,
        rollout_percentage: int = 100,
        allowed_roles: Optional[list[str]] = None,
        allowed_users: Optional[list[int]] = None,
        description: str = '',
    ):
        self.name = name
        self.enabled = enabled
        self.rollout_percentage = rollout_percentage
        self.allowed_roles = allowed_roles or []
        self.allowed_users = allowed_users or []
        self.description = description
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def is_enabled_for(self, user_id: int = 0, user_role: str = '') -> bool:
        """检查功能是否对指定用户启用。"""
        if not self.enabled:
            return False

        # 管理员始终可用
        if user_role == 'admin':
            return True

        # 用户白名单
        if self.allowed_users and user_id in self.allowed_users:
            return True

        # 角色白名单
        if self.allowed_roles and user_role in self.allowed_roles:
            return True

        # 百分比灰度
        if self.rollout_percentage < 100:
            return (user_id % 100) < self.rollout_percentage

        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'enabled': self.enabled,
            'rollout_percentage': self.rollout_percentage,
            'allowed_roles': self.allowed_roles,
            'allowed_users': self.allowed_users,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class FeatureFlagManager:
    """Feature Flag管理器。"""

    def __init__(self):
        self._flags: dict[str, FeatureFlag] = {}
        self._rollout_mode = RolloutMode.ALL

    def register_flag(self, flag: FeatureFlag) -> None:
        """注册Feature Flag。"""
        self._flags[flag.name] = flag

    def get_flag(self, name: str) -> Optional[FeatureFlag]:
        """获取Feature Flag。"""
        return self._flags.get(name)

    def set_flag(self, name: str, **kwargs) -> Optional[FeatureFlag]:
        """更新Feature Flag。"""
        flag = self._flags.get(name)
        if not flag:
            return None

        if 'enabled' in kwargs:
            flag.enabled = kwargs['enabled']
        if 'rollout_percentage' in kwargs:
            flag.rollout_percentage = kwargs['rollout_percentage']
        if 'allowed_roles' in kwargs:
            flag.allowed_roles = kwargs['allowed_roles']
        if 'allowed_users' in kwargs:
            flag.allowed_users = kwargs['allowed_users']
        flag.updated_at = datetime.now()

        return flag

    def set_rollout_mode(self, mode: RolloutMode) -> None:
        """设置发布模式。"""
        self._rollout_mode = mode

    def get_rollout_mode(self) -> RolloutMode:
        """获取当前发布模式。"""
        return self._rollout_mode

    def is_feature_available(
        self,
        feature_name: str,
        user_id: int = 0,
        user_role: str = '',
    ) -> bool:
        """检查功能是否可用。"""
        # 全局发布模式检查
        if self._rollout_mode == RolloutMode.DISABLED:
            return False

        if self._rollout_mode == RolloutMode.ADMIN_ONLY and user_role != 'admin':
            return False

        # 只读模式：只允许查询类功能
        if self._rollout_mode == RolloutMode.READ_ONLY:
            read_only_features = {
                'warehouse_insights', 'purchase_insights', 'knowledge_base',
                'inventory_health', 'master_data_insights', 'admin_insights',
            }
            if feature_name not in read_only_features:
                return False

        # 草稿模式：允许查询+草稿
        if self._rollout_mode == RolloutMode.READ_DRAFT:
            draft_features = {
                'warehouse_insights', 'purchase_insights', 'knowledge_base',
                'inventory_health', 'master_data_insights', 'admin_insights',
                'in_order_draft', 'out_order_draft', 'transfer_draft',
                'check_draft', 'adjustment_draft', 'purchase_receive_draft',
            }
            if feature_name not in draft_features:
                return False

        # Feature Flag检查
        flag = self._flags.get(feature_name)
        if flag:
            return flag.is_enabled_for(user_id, user_role)

        return True

    def get_all_flags(self) -> dict[str, dict]:
        """获取所有Feature Flags。"""
        return {
            name: flag.to_dict()
            for name, flag in self._flags.items()
        }

    def get_rollout_status(self) -> dict[str, Any]:
        """获取发布状态。"""
        return {
            'rollout_mode': self._rollout_mode.value,
            'total_flags': len(self._flags),
            'enabled_flags': sum(1 for f in self._flags.values() if f.enabled),
            'flags': self.get_all_flags(),
        }


# 全局管理器实例
_feature_manager = FeatureFlagManager()

# 注册默认Feature Flags
_feature_manager.register_flag(FeatureFlag(
    name='ai_chat',
    enabled=True,
    description='AI对话功能',
))
_feature_manager.register_flag(FeatureFlag(
    name='ai_vision',
    enabled=True,
    description='AI图片识别功能',
))
_feature_manager.register_flag(FeatureFlag(
    name='ai_drafts',
    enabled=True,
    description='AI草稿生成功能',
))
_feature_manager.register_flag(FeatureFlag(
    name='ai_agents',
    enabled=True,
    description='AI Agent功能',
))
_feature_manager.register_flag(FeatureFlag(
    name='ai_analysis',
    enabled=True,
    description='AI分析功能',
))


def get_feature_manager() -> FeatureFlagManager:
    """获取全局Feature Flag管理器。"""
    return _feature_manager

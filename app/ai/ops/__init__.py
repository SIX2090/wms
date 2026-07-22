"""阶段5：ops包初始化。"""

# 核心模块（无外部依赖）
from .monitor import OpsMonitor, get_ops_monitor, HealthStatus, AIMetrics, AlertRule
from .feature_flags import FeatureFlagManager, FeatureFlag, RolloutMode, get_feature_manager

# 可选模块（依赖requests）
try:
    from .fallback import FallbackChain, FallbackLevel, get_fallback_chain
    _HAS_FALLBACK = True
except ImportError:
    _HAS_FALLBACK = False

try:
    from .role_rollout import get_allowed_features, is_feature_allowed, get_role_capabilities
    _HAS_ROLE_ROLLOUT = True
except ImportError:
    _HAS_ROLE_ROLLOUT = False

__all__ = [
    'OpsMonitor', 'get_ops_monitor', 'HealthStatus', 'AIMetrics', 'AlertRule',
    'FeatureFlagManager', 'FeatureFlag', 'RolloutMode', 'get_feature_manager',
]

if _HAS_FALLBACK:
    __all__.extend(['FallbackChain', 'FallbackLevel', 'get_fallback_chain'])

if _HAS_ROLE_ROLLOUT:
    __all__.extend(['get_allowed_features', 'is_feature_allowed', 'get_role_capabilities'])

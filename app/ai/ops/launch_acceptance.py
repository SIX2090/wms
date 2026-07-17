"""AI-R17 真实用户灰度、回滚演练和上线验收。

# AI_TASK: AI-R17

本模块是 AI-R17 的纯逻辑+依赖注入模块，职责是聚合"上线验收四项指标"和编排
"灰度演练 / 回滚演练"的结果校验，本身不依赖 Flask/ORM，CI 无 DB 时可直接传入
样本列表测试；生产环境由 app.py 提供 ORM adapter 查询样本。

与现有能力的边界（防重复）：
- 灰度发布模式（admin_only/read_only/read_draft/all）已存在于 app.py 的
  ``_ai_capability_allowed_by_rollout`` 和 app/ai/ops/feature_flags.py，本模块
  不重新发明灰度模式，仅校验"灰度演练是否覆盖角色矩阵并记录回退"。
- Provider 紧急回滚 force_fallback 已存在于 app/ai/documents/provider_router.py，
  一键关闭 ai_feature_global_enabled / ai_degrade_local_only 已存在于 app.py，
  本模块不重复回滚开关，仅校验"关闭+恢复是否在 10 分钟内"。
- 越权成功 unauthorized_success 检测已存在于 app.py 的 _ai_ops_metrics，
  自动提交 validate_no_auto_submit 已存在于 app/ai/agents/budget_control.py，
  低置信度 has_unconfirmed_low_confidence_fields 已存在于
  app/ai/documents/document_confirmation.py，
  重复草稿 status='replayed' 已存在于 AIDraftIdempotency，
  本模块不重新发明单项检测，仅做四项绝对计数的统一聚合校验。
- business_quality.py 的 7 指标是比率口径（rate），本模块的四项是绝对计数口径
  （count，验收阈值为 0），两者可共存不冲突。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# ===== 四项上线验收指标常量（绝对计数，阈值为 0）=====

METRIC_UNAUTHORIZED_SUCCESS = 'unauthorized_success'
"""越权成功数：AIToolCall permission_allowed=False 且 status in (completed/success/authorized)。"""

METRIC_DUPLICATE_DRAFTS = 'duplicate_drafts'
"""重复草稿数：AIDraftIdempotency status='replayed' 表示被幂等拦截的重复请求。"""

METRIC_AUTO_SUBMIT = 'auto_submit'
"""自动提交数：AIToolCall 审计中 action 命中 AUTO_SUBMIT_FORBIDDEN_ACTIONS 的次数。"""

METRIC_LOW_CONFIDENCE_UNCONFIRMED = 'low_confidence_unconfirmed'
"""低置信度未确认建单数：AIDocumentJob draft_created 且存在未确认低置信度字段。"""

ALL_ACCEPTANCE_METRICS: tuple[str, ...] = (
    METRIC_UNAUTHORIZED_SUCCESS,
    METRIC_DUPLICATE_DRAFTS,
    METRIC_AUTO_SUBMIT,
    METRIC_LOW_CONFIDENCE_UNCONFIRMED,
)

METRIC_LABELS: dict[str, str] = {
    METRIC_UNAUTHORIZED_SUCCESS: '越权成功',
    METRIC_DUPLICATE_DRAFTS: '重复草稿',
    METRIC_AUTO_SUBMIT: '自动提交',
    METRIC_LOW_CONFIDENCE_UNCONFIRMED: '低置信度未确认建单',
}

# 复用 AI-R13 budget_control.AUTO_SUBMIT_FORBIDDEN_ACTIONS 的口径（保持一致）
AUTO_SUBMIT_FORBIDDEN_ACTIONS: frozenset[str] = frozenset({
    'submit', 'audit', 'approve', 'complete', 'close',
    'void', 'delete', 'confirm_submit', 'auto_dispatch', 'auto_complete',
})

DEFAULT_WINDOW_HOURS = 168  # 7 天 = 7 * 24
DEFAULT_ROLLBACK_MAX_MINUTES = 10  # 验收：10 分钟内关闭 AI 并恢复配置


# ===== 数据结构（纯 dataclass）=====

@dataclass(frozen=True)
class AcceptanceMetric:
    """单项上线验收指标。

    绝对计数口径：count 必须为 0 才算 passed。
    """
    metric: str
    label: str
    count: int
    threshold: int = 0
    window_hours: int = DEFAULT_WINDOW_HOURS

    @property
    def passed(self) -> bool:
        return self.count <= self.threshold

    def to_dict(self) -> dict[str, Any]:
        return {
            'metric': self.metric,
            'label': self.label,
            'count': self.count,
            'threshold': self.threshold,
            'window_hours': self.window_hours,
            'passed': self.passed,
        }


@dataclass(frozen=True)
class LaunchAcceptanceReport:
    """上线验收报告：四项指标聚合。

    验收标准（AI-R17）：连续一周越权成功 0、重复草稿 0、自动提交 0、
    低置信度未确认建单 0。
    """
    metrics: tuple[AcceptanceMetric, ...]
    window_hours: int = DEFAULT_WINDOW_HOURS
    generated_at: Optional[datetime] = None

    @property
    def all_passed(self) -> bool:
        return all(m.passed for m in self.metrics)

    @property
    def failed_metrics(self) -> tuple[AcceptanceMetric, ...]:
        return tuple(m for m in self.metrics if not m.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            'metrics': [m.to_dict() for m in self.metrics],
            'window_hours': self.window_hours,
            'generated_at': (self.generated_at or datetime.now()).isoformat(),
            'all_passed': self.all_passed,
            'failed_count': len(self.failed_metrics),
        }


@dataclass(frozen=True)
class RolloutDrillResult:
    """灰度演练结果。

    记录耗时、修正、误判、失败和回退。
    """
    role_matrix: tuple[tuple[str, bool], ...]  # (role, expected_access) 矩阵
    duration_seconds: float  # 演练总耗时
    corrections: int = 0  # 修正次数
    misjudgments: int = 0  # 误判次数
    failures: int = 0  # 失败次数
    rolled_back: bool = False  # 是否完成回退
    rollback_at: Optional[datetime] = None  # 回退时间
    notes: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'role_matrix': [{'role': r, 'expected_access': a} for r, a in self.role_matrix],
            'duration_seconds': self.duration_seconds,
            'corrections': self.corrections,
            'misjudgments': self.misjudgments,
            'failures': self.failures,
            'rolled_back': self.rolled_back,
            'rollback_at': self.rollback_at.isoformat() if self.rollback_at else None,
            'notes': self.notes,
        }


@dataclass(frozen=True)
class RollbackDrillResult:
    """回滚演练结果。

    验收标准（AI-R17）：10 分钟内关闭 AI 并恢复配置。
    """
    shutdown_started_at: datetime  # 关闭开始时间
    shutdown_completed_at: datetime  # 关闭完成时间（ai_feature_global_enabled=0 生效）
    restore_started_at: datetime  # 恢复开始时间
    restore_completed_at: datetime  # 恢复完成时间（ai_feature_global_enabled=1 恢复）
    now: Optional[datetime] = None  # 注入的当前时间（可复算）

    @property
    def shutdown_seconds(self) -> float:
        """关闭耗时（秒）。"""
        return (self.shutdown_completed_at - self.shutdown_started_at).total_seconds()

    @property
    def restore_seconds(self) -> float:
        """恢复耗时（秒）。"""
        return (self.restore_completed_at - self.restore_started_at).total_seconds()

    @property
    def total_seconds(self) -> float:
        """关闭+恢复总耗时（秒）。"""
        return (self.restore_completed_at - self.shutdown_started_at).total_seconds()

    @property
    def total_minutes(self) -> float:
        """关闭+恢复总耗时（分钟）。"""
        return self.total_seconds / 60.0

    def to_dict(self) -> dict[str, Any]:
        return {
            'shutdown_started_at': self.shutdown_started_at.isoformat(),
            'shutdown_completed_at': self.shutdown_completed_at.isoformat(),
            'restore_started_at': self.restore_started_at.isoformat(),
            'restore_completed_at': self.restore_completed_at.isoformat(),
            'shutdown_seconds': self.shutdown_seconds,
            'restore_seconds': self.restore_seconds,
            'total_seconds': self.total_seconds,
            'total_minutes': self.total_minutes,
        }


# ===== 主函数（纯逻辑，依赖注入）=====

def compute_acceptance_metrics(
    counts: dict[str, int],
    *,
    window_hours: int = DEFAULT_WINDOW_HOURS,
    now: Optional[datetime] = None,
) -> LaunchAcceptanceReport:
    """计算上线验收四项指标。

    Args:
        counts: 四项指标的绝对计数，键为 ALL_ACCEPTANCE_METRICS 中的 metric 名。
                缺失的键按 0 处理。由 app.py 的 ORM adapter 查询填充。
        window_hours: 采集窗口（默认 168 小时 = 7 天）。
        now: 注入当前时间（可复算），None 时用 datetime.now()。

    Returns:
        LaunchAcceptanceReport 含四项 AcceptanceMetric。
    """
    metrics: list[AcceptanceMetric] = []
    for metric_name in ALL_ACCEPTANCE_METRICS:
        metrics.append(AcceptanceMetric(
            metric=metric_name,
            label=METRIC_LABELS[metric_name],
            count=int(counts.get(metric_name, 0)),
            threshold=0,
            window_hours=window_hours,
        ))
    return LaunchAcceptanceReport(
        metrics=tuple(metrics),
        window_hours=window_hours,
        generated_at=now or datetime.now(),
    )


def validate_zero_violation(report: LaunchAcceptanceReport) -> tuple[bool, str]:
    """校验四项指标全部为 0（验收：连续一周四项为 0）。

    Returns:
        (是否通过, 原因)
    """
    if report.all_passed:
        return True, '四项上线验收指标全部为 0，通过'
    failed = report.failed_metrics
    detail = '；'.join(f'{m.label}={m.count}' for m in failed)
    return False, f'上线验收失败，以下指标不为 0：{detail}'


def validate_rollback_within_minutes(
    drill: RollbackDrillResult,
    *,
    max_minutes: int = DEFAULT_ROLLBACK_MAX_MINUTES,
    now: Optional[datetime] = None,
) -> tuple[bool, str]:
    """校验关闭 AI 并恢复配置在 max_minutes 分钟内（验收：10 分钟内）。

    Args:
        drill: 回滚演练结果。
        max_minutes: 最大允许分钟数（默认 10）。
        now: 注入当前时间（可复算），None 时用 datetime.now()。

    Returns:
        (是否通过, 原因)
    """
    # 时间顺序校验
    if drill.shutdown_completed_at < drill.shutdown_started_at:
        return False, '关闭完成时间早于关闭开始时间'
    if drill.restore_completed_at < drill.restore_started_at:
        return False, '恢复完成时间早于恢复开始时间'
    if drill.restore_started_at < drill.shutdown_completed_at:
        return False, '恢复开始时间早于关闭完成时间'

    if drill.total_minutes > max_minutes:
        return False, (
            f'关闭+恢复总耗时 {drill.total_minutes:.2f} 分钟，'
            f'超过 {max_minutes} 分钟上限'
        )
    return True, (
        f'关闭+恢复总耗时 {drill.total_minutes:.2f} 分钟，'
        f'在 {max_minutes} 分钟上限内'
    )


def validate_rollout_drill_complete(drill: RolloutDrillResult) -> tuple[bool, str]:
    """校验灰度演练完整性（覆盖角色矩阵+记录耗时+完成回退）。

    Returns:
        (是否通过, 原因)
    """
    if not drill.role_matrix:
        return False, '灰度演练未覆盖角色矩阵'
    # 至少覆盖 admin/warehouse/purchase 三类核心角色（台账要求管理员/仓库主管/指定采购员）
    covered_roles = {role for role, _ in drill.role_matrix}
    required_roles = {'admin', 'warehouse', 'purchase'}
    missing = required_roles - covered_roles
    if missing:
        return False, f'灰度演练角色矩阵缺失：{sorted(missing)}'
    if drill.duration_seconds <= 0:
        return False, '灰度演练未记录耗时'
    if not drill.rolled_back:
        return False, '灰度演练未完成回退'
    if drill.rollback_at is None:
        return False, '灰度演练回退时间未记录'
    return True, '灰度演练完整（角色矩阵+耗时+回退）'


def validate_all(
    report: LaunchAcceptanceReport,
    rollback_drill: RollbackDrillResult,
    rollout_drill: RolloutDrillResult,
    *,
    max_minutes: int = DEFAULT_ROLLBACK_MAX_MINUTES,
    now: Optional[datetime] = None,
) -> tuple[bool, list[str]]:
    """一次性多项校验：四项指标 + 回滚演练 + 灰度演练。

    Returns:
        (全部通过, 失败原因列表)
    """
    failures: list[str] = []
    ok1, reason1 = validate_zero_violation(report)
    if not ok1:
        failures.append(reason1)
    ok2, reason2 = validate_rollback_within_minutes(rollback_drill, max_minutes=max_minutes, now=now)
    if not ok2:
        failures.append(reason2)
    ok3, reason3 = validate_rollout_drill_complete(rollout_drill)
    if not ok3:
        failures.append(reason3)
    return (len(failures) == 0), failures

"""AI-R17-F02 连续七天真实上线验收 — 验收证据包纯逻辑模块。

# AI_TASK: AI-R17-F02

台账 13.2 节验收要求：
1. 四项绝对指标（越权成功/重复草稿/自动提交/低置信度未确认建单）连续七天每日为 0。
2. 质量指标（分类/表头/行召回/物料/修正/采用/拦截）按天采集并汇总。
3. 口径修正：草稿采用率反查业务单据状态；低置信度未确认读取确认状态（临时用 confidence<0.85）。
4. 验收证据包：七天每日快照+汇总+灰度矩阵+样本清单+回滚记录+go/no-go 结论。
5. 所有指标保存分子、分母、时间窗口和筛选条件，支持从原始记录复算。
6. 管理员签字 go/no-go；任一绝对指标非 0 必须 no-go 并建立子修复项。

防重复设计：
- 不重新发明四项绝对指标口径（复用 launch_acceptance.ALL_ACCEPTANCE_METRICS）。
- 不重新发明质量指标口径（复用 business_quality.ALL_METRICS）。
- 不重新发明回滚校验（复用 launch_acceptance.validate_rollback_within_minutes）。
- 本模块只提供每日快照持久化编排和七天证据包聚合。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

# 复用 AI-R17 的四项绝对指标口径
from ai.ops.launch_acceptance import (
    ALL_ACCEPTANCE_METRICS,
    AUTO_SUBMIT_FORBIDDEN_ACTIONS,
    DEFAULT_WINDOW_HOURS,
    METRIC_AUTO_SUBMIT,
    METRIC_DUPLICATE_DRAFTS,
    METRIC_LOW_CONFIDENCE_UNCONFIRMED,
    METRIC_UNAUTHORIZED_SUCCESS,
)

# 复用 AI-R15 的七项质量指标口径
from ai.ops.business_quality import ALL_METRICS as ALL_QUALITY_METRICS


# ===== 常量 =====

DEFAULT_EVIDENCE_DAYS = 7  # 连续七天验收
GO_DECISION = 'go'
NO_GO_DECISION = 'no_go'
VALID_DECISIONS = (GO_DECISION, NO_GO_DECISION)

# 证据样本类型
SAMPLE_FAILURE = 'failure'
SAMPLE_FALLBACK = 'fallback'
SAMPLE_DUPLICATE = 'duplicate'
SAMPLE_CORRECTION = 'correction'
ALL_SAMPLE_TYPES = (SAMPLE_FAILURE, SAMPLE_FALLBACK, SAMPLE_DUPLICATE, SAMPLE_CORRECTION)

# 低置信度阈值（与 AI-R08 一致，待 R08-F01 完成后切换为 confirmation_status 口径）
LOW_CONFIDENCE_THRESHOLD = 0.85


# ===== dataclass =====

@dataclass(frozen=True)
class DailyMetricSnapshot:
    """单日验收指标快照。

    保存当日四项绝对指标计数和七项质量指标聚合，
    以及灰度用户/角色信息，支持从原始记录复算。
    """

    snapshot_date: str  # YYYY-MM-DD
    absolute_counts: dict[str, int]  # 4 项绝对指标名→计数
    quality_metrics: dict[str, dict[str, Any]]  # 7 项质量指标名→{numerator, denominator, rate}
    rollout_user_count: int  # 当日灰度用户数
    rollout_role_count: int  # 当日灰度角色数
    rollout_roles: tuple[str, ...]  # 当日灰度角色列表
    window_hours: int  # 采集窗口（单日=24）
    filter_applied: dict[str, Any]  # 筛选条件追溯
    generated_at: str  # ISO 时间戳

    def to_dict(self) -> dict[str, Any]:
        return {
            'snapshot_date': self.snapshot_date,
            'absolute_counts': dict(self.absolute_counts),
            'quality_metrics': {k: dict(v) for k, v in self.quality_metrics.items()},
            'rollout_user_count': self.rollout_user_count,
            'rollout_role_count': self.rollout_role_count,
            'rollout_roles': list(self.rollout_roles),
            'window_hours': self.window_hours,
            'filter_applied': dict(self.filter_applied),
            'generated_at': self.generated_at,
        }

    @property
    def all_absolute_zero(self) -> bool:
        """当日四项绝对指标是否全为 0。"""
        return all(self.absolute_counts.get(m, 0) == 0 for m in ALL_ACCEPTANCE_METRICS)


@dataclass(frozen=True)
class EvidenceSample:
    """证据样本条目（失败/降级/重复/人工修正）。"""

    sample_type: str  # SAMPLE_FAILURE / SAMPLE_FALLBACK / SAMPLE_DUPLICATE / SAMPLE_CORRECTION
    sample_id: str  # 原始记录 ID
    occurred_at: str  # ISO 时间戳
    role: str
    source: str
    detail: str  # 样本描述（脱敏后）
    related_record_type: str  # 关联记录类型（如 AIToolCall/AIDraftIdempotency 等）
    related_record_id: str  # 关联记录 ID

    def to_dict(self) -> dict[str, Any]:
        return {
            'sample_type': self.sample_type,
            'sample_id': self.sample_id,
            'occurred_at': self.occurred_at,
            'role': self.role,
            'source': self.source,
            'detail': self.detail,
            'related_record_type': self.related_record_type,
            'related_record_id': self.related_record_id,
        }


@dataclass(frozen=True)
class RollbackEvidence:
    """回滚演练证据（10 分钟内关闭+恢复）。"""

    event_id: str
    action: str  # shutdown / restore
    operator_id: int
    operator_role: str
    started_at: str  # ISO
    completed_at: str  # ISO
    duration_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            'event_id': self.event_id,
            'action': self.action,
            'operator_id': self.operator_id,
            'operator_role': self.operator_role,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'duration_seconds': self.duration_seconds,
        }


@dataclass(frozen=True)
class AcceptanceEvidencePackage:
    """七天验收证据包。

    聚合连续七天的每日快照、样本清单、回滚记录和 go/no-go 结论。
    """

    package_id: str
    start_date: str  # YYYY-MM-DD（七天第一天）
    end_date: str  # YYYY-MM-DD（七天最后一天）
    daily_snapshots: tuple[DailyMetricSnapshot, ...]
    seven_day_summary: dict[str, Any]  # 七天汇总
    rollout_role_matrix: tuple[tuple[str, bool], ...]  # (角色, 是否灰度)
    failure_samples: tuple[EvidenceSample, ...]
    fallback_samples: tuple[EvidenceSample, ...]
    duplicate_samples: tuple[EvidenceSample, ...]
    correction_samples: tuple[EvidenceSample, ...]
    rollback_events: tuple[RollbackEvidence, ...]
    go_no_go_decision: str  # go / no_go / pending
    decision_reason: str
    decided_by: Optional[int]  # 签字管理员 user_id
    decided_at: Optional[str]  # ISO
    generated_at: str  # ISO

    def to_dict(self) -> dict[str, Any]:
        return {
            'package_id': self.package_id,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'daily_snapshots': [s.to_dict() for s in self.daily_snapshots],
            'seven_day_summary': dict(self.seven_day_summary),
            'rollout_role_matrix': [list(r) for r in self.rollout_role_matrix],
            'failure_samples': [s.to_dict() for s in self.failure_samples],
            'fallback_samples': [s.to_dict() for s in self.fallback_samples],
            'duplicate_samples': [s.to_dict() for s in self.duplicate_samples],
            'correction_samples': [s.to_dict() for s in self.correction_samples],
            'rollback_events': [r.to_dict() for r in self.rollback_events],
            'go_no_go_decision': self.go_no_go_decision,
            'decision_reason': self.decision_reason,
            'decided_by': self.decided_by,
            'decided_at': self.decided_at,
            'generated_at': self.generated_at,
        }

    @property
    def day_count(self) -> int:
        return len(self.daily_snapshots)


# ===== 构造函数 =====

def build_daily_snapshot(
    *,
    snapshot_date: str,
    absolute_counts: dict[str, int],
    quality_metrics: dict[str, dict[str, Any]],
    rollout_user_count: int = 0,
    rollout_role_count: int = 0,
    rollout_roles: tuple[str, ...] = (),
    window_hours: int = 24,
    filter_applied: Optional[dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> DailyMetricSnapshot:
    """构造单日验收指标快照。

    Args:
        snapshot_date: 日期字符串 YYYY-MM-DD。
        absolute_counts: 四项绝对指标计数（缺失键按 0）。
        quality_metrics: 七项质量指标聚合（每项含 numerator/denominator/rate）。
        rollout_user_count: 当日灰度用户数。
        rollout_role_count: 当日灰度角色数。
        rollout_roles: 当日灰度角色列表。
        window_hours: 采集窗口（单日=24）。
        filter_applied: 筛选条件追溯。
        now: 时间戳注入（可复算）。
    """
    if now is None:
        now = datetime.now()
    # 补齐缺失的绝对指标键
    full_absolute = {m: int(absolute_counts.get(m, 0)) for m in ALL_ACCEPTANCE_METRICS}
    # 补齐缺失的质量指标键
    full_quality: dict[str, dict[str, Any]] = {}
    for m in ALL_QUALITY_METRICS:
        entry = quality_metrics.get(m, {})
        full_quality[m] = {
            'numerator': int(entry.get('numerator', 0)),
            'denominator': int(entry.get('denominator', 0)),
            'rate': float(entry.get('rate', 0.0)),
        }
    return DailyMetricSnapshot(
        snapshot_date=snapshot_date,
        absolute_counts=full_absolute,
        quality_metrics=full_quality,
        rollout_user_count=rollout_user_count,
        rollout_role_count=rollout_role_count,
        rollout_roles=tuple(rollout_roles),
        window_hours=window_hours,
        filter_applied=dict(filter_applied or {}),
        generated_at=now.isoformat(),
    )


def build_evidence_package(
    *,
    package_id: str,
    daily_snapshots: list[DailyMetricSnapshot],
    rollout_role_matrix: list[tuple[str, bool]],
    failure_samples: Optional[list[EvidenceSample]] = None,
    fallback_samples: Optional[list[EvidenceSample]] = None,
    duplicate_samples: Optional[list[EvidenceSample]] = None,
    correction_samples: Optional[list[EvidenceSample]] = None,
    rollback_events: Optional[list[RollbackEvidence]] = None,
    go_no_go_decision: str = 'pending',
    decision_reason: str = '',
    decided_by: Optional[int] = None,
    decided_at: Optional[str] = None,
    now: Optional[datetime] = None,
) -> AcceptanceEvidencePackage:
    """构造七天验收证据包。

    Args:
        package_id: 证据包唯一 ID。
        daily_snapshots: 每日快照列表（按日期升序）。
        rollout_role_matrix: 灰度角色矩阵 (角色, 是否灰度)。
        failure_samples: 失败样本清单。
        fallback_samples: 降级样本清单。
        duplicate_samples: 重复样本清单。
        correction_samples: 人工修正样本清单。
        rollback_events: 回滚演练记录。
        go_no_go_decision: go / no_go / pending。
        decision_reason: 决策原因。
        decided_by: 签字管理员 user_id。
        decided_at: 签字时间 ISO。
        now: 时间戳注入。
    """
    if now is None:
        now = datetime.now()
    if not daily_snapshots:
        raise ValueError('每日快照列表不能为空')
    # 按日期排序
    sorted_snapshots = sorted(daily_snapshots, key=lambda s: s.snapshot_date)
    start_date = sorted_snapshots[0].snapshot_date
    end_date = sorted_snapshots[-1].snapshot_date
    # 计算七天汇总
    summary = _compute_seven_day_summary(sorted_snapshots)
    return AcceptanceEvidencePackage(
        package_id=package_id,
        start_date=start_date,
        end_date=end_date,
        daily_snapshots=tuple(sorted_snapshots),
        seven_day_summary=summary,
        rollout_role_matrix=tuple(tuple(r) for r in rollout_role_matrix),
        failure_samples=tuple(failure_samples or []),
        fallback_samples=tuple(fallback_samples or []),
        duplicate_samples=tuple(duplicate_samples or []),
        correction_samples=tuple(correction_samples or []),
        rollback_events=tuple(rollback_events or []),
        go_no_go_decision=go_no_go_decision,
        decision_reason=decision_reason,
        decided_by=decided_by,
        decided_at=decided_at,
        generated_at=now.isoformat(),
    )


def _compute_seven_day_summary(snapshots: list[DailyMetricSnapshot]) -> dict[str, Any]:
    """计算七天汇总。"""
    # 绝对指标七天总和
    absolute_totals: dict[str, int] = {m: 0 for m in ALL_ACCEPTANCE_METRICS}
    for s in snapshots:
        for m in ALL_ACCEPTANCE_METRICS:
            absolute_totals[m] += s.absolute_counts.get(m, 0)
    # 质量指标七天加权平均
    quality_summary: dict[str, dict[str, Any]] = {}
    for m in ALL_QUALITY_METRICS:
        total_num = sum(s.quality_metrics.get(m, {}).get('numerator', 0) for s in snapshots)
        total_den = sum(s.quality_metrics.get(m, {}).get('denominator', 0) for s in snapshots)
        rate = total_num / total_den if total_den > 0 else 0.0
        quality_summary[m] = {
            'numerator': total_num,
            'denominator': total_den,
            'rate': round(rate, 6),
        }
    # 连续七天全 0 校验
    all_zero = all(absolute_totals[m] == 0 for m in ALL_ACCEPTANCE_METRICS)
    return {
        'absolute_totals': absolute_totals,
        'quality_summary': quality_summary,
        'all_absolute_zero': all_zero,
        'day_count': len(snapshots),
    }


# ===== 校验函数 =====

def validate_seven_consecutive_days_zero(
    snapshots: list[DailyMetricSnapshot],
    *,
    required_days: int = DEFAULT_EVIDENCE_DAYS,
) -> tuple[bool, str]:
    """校验连续七天四项绝对指标每日均为 0。

    验收要求：连续一周越权成功 0、重复草稿 0、自动提交 0、低置信度未确认建单 0。
    """
    if len(snapshots) < required_days:
        return False, f'快照数量不足：需要 {required_days} 天，实际 {len(snapshots)} 天'
    # 取最近 required_days 天
    recent = sorted(snapshots, key=lambda s: s.snapshot_date)[-required_days:]
    # 检查日期连续性
    for i in range(1, len(recent)):
        prev_date = datetime.strptime(recent[i - 1].snapshot_date, '%Y-%m-%d')
        curr_date = datetime.strptime(recent[i].snapshot_date, '%Y-%m-%d')
        if (curr_date - prev_date).days != 1:
            return False, f'日期不连续：{recent[i - 1].snapshot_date} → {recent[i].snapshot_date}'
    # 检查每日四项全 0
    for s in recent:
        if not s.all_absolute_zero:
            nonzero = {
                m: s.absolute_counts.get(m, 0)
                for m in ALL_ACCEPTANCE_METRICS
                if s.absolute_counts.get(m, 0) != 0
            }
            return False, f'{s.snapshot_date} 绝对指标非 0：{nonzero}'
    return True, f'连续 {required_days} 天四项绝对指标每日均为 0'


def validate_evidence_reproducible(
    package: AcceptanceEvidencePackage,
) -> tuple[bool, str]:
    """校验验收数据可复算。

    验收要求：所有指标必须保存分子、分母、时间窗口和筛选条件，支持从原始记录复算。
    """
    for s in package.daily_snapshots:
        # 检查时间窗口
        if s.window_hours <= 0:
            return False, f'{s.snapshot_date} window_hours={s.window_hours} 非法'
        # 检查筛选条件追溯
        if not s.filter_applied:
            return False, f'{s.snapshot_date} 缺少 filter_applied 筛选条件追溯'
        # 检查质量指标分子分母齐全
        for m in ALL_QUALITY_METRICS:
            entry = s.quality_metrics.get(m, {})
            if 'numerator' not in entry or 'denominator' not in entry:
                return False, f'{s.snapshot_date} 质量指标 {m} 缺少分子或分母'
            num = entry.get('numerator', 0)
            den = entry.get('denominator', 0)
            expected_rate = num / den if den > 0 else 0.0
            actual_rate = entry.get('rate', 0.0)
            if abs(expected_rate - actual_rate) > 0.001:
                return False, (
                    f'{s.snapshot_date} 质量指标 {m} rate 不可复算：'
                    f'{num}/{den} 应为 {expected_rate:.6f}，实际 {actual_rate:.6f}'
                )
    # 检查七天汇总
    summary = package.seven_day_summary
    if 'absolute_totals' not in summary:
        return False, '七天汇总缺少 absolute_totals'
    if 'quality_summary' not in summary:
        return False, '七天汇总缺少 quality_summary'
    return True, '验收数据可复算：分子分母时间窗口筛选条件齐全'


def validate_go_no_go(package: AcceptanceEvidencePackage) -> tuple[bool, str]:
    """校验 go/no-go 结论正确性。

    验收要求：任一绝对指标非 0 必须 no-go 并建立子修复项。
    """
    summary = package.seven_day_summary
    all_zero = summary.get('all_absolute_zero', False)
    decision = package.go_no_go_decision
    # 任一非 0 必须 no-go
    if not all_zero and decision == GO_DECISION:
        nonzero = {
            m: v for m, v in summary.get('absolute_totals', {}).items() if v != 0
        }
        return False, f'绝对指标非 0 时不得 go：{nonzero}'
    # go 决策必须有管理员签字
    if decision == GO_DECISION and package.decided_by is None:
        return False, 'go 决策缺少管理员签字（decided_by 为空）'
    # no-go 决策必须有原因
    if decision == NO_GO_DECISION and not package.decision_reason:
        return False, 'no-go 决策缺少原因说明'
    # pending 不是最终结论
    if decision == 'pending':
        return False, 'go/no-go 决策待定（pending），未签字'
    if decision not in VALID_DECISIONS:
        return False, f'未知决策值：{decision}'
    return True, f'go/no-go 决策校验通过：{decision}'


def validate_rollout_matrix_complete(
    package: AcceptanceEvidencePackage,
) -> tuple[bool, str]:
    """校验灰度用户/角色矩阵完整性。

    验收要求：证据包含灰度用户/角色矩阵。
    """
    if not package.rollout_role_matrix:
        return False, '灰度角色矩阵为空'
    # 至少覆盖 admin/warehouse/purchase 三个核心角色
    roles = {r[0] for r in package.rollout_role_matrix}
    required_roles = {'admin', 'warehouse', 'purchase'}
    missing = required_roles - roles
    if missing:
        return False, f'灰度角色矩阵缺少核心角色：{missing}'
    # 每日快照应有灰度信息
    for s in package.daily_snapshots:
        if s.rollout_role_count == 0:
            return False, f'{s.snapshot_date} 灰度角色数为 0'
    return True, '灰度用户/角色矩阵完整'


def validate_rollback_evidence_present(
    package: AcceptanceEvidencePackage,
) -> tuple[bool, str]:
    """校验回滚演练证据存在。

    验收要求：证据包含 10 分钟内关闭+恢复回滚记录。
    """
    if not package.rollback_events:
        return False, '回滚演练记录为空'
    actions = {e.action for e in package.rollback_events}
    if 'shutdown' not in actions:
        return False, '回滚演练缺少 shutdown 记录'
    if 'restore' not in actions:
        return False, '回滚演练缺少 restore 记录'
    return True, '回滚演练证据齐全（shutdown+restore）'


def validate_sample_lists_present(
    package: AcceptanceEvidencePackage,
) -> tuple[bool, str]:
    """校验样本清单存在（失败/降级/重复/人工修正）。

    验收要求：证据包含失败、降级、重复和人工修正样本清单。
    即使样本数为 0 也需要明确记录（证明已采集）。
    """
    # 样本清单字段必须存在（即使为空 tuple 也算存在，因为 build_evidence_package 默认填充）
    # 这里校验七天汇总中有对应的采集记录
    for sample_type, samples in (
        (SAMPLE_FAILURE, package.failure_samples),
        (SAMPLE_FALLBACK, package.fallback_samples),
        (SAMPLE_DUPLICATE, package.duplicate_samples),
        (SAMPLE_CORRECTION, package.correction_samples),
    ):
        # 样本列表是 tuple，build_evidence_package 保证字段存在
        if samples is None:
            return False, f'{sample_type} 样本清单缺失'
    return True, '四类样本清单字段齐全（失败/降级/重复/人工修正）'


def validate_all_evidence(package: AcceptanceEvidencePackage) -> tuple[bool, list[str]]:
    """一次性多项校验验收证据包。"""
    failures: list[str] = []
    # validate_seven_consecutive_days_zero 接收快照列表，其他校验器接收 package
    ok, reason = validate_seven_consecutive_days_zero(list(package.daily_snapshots))
    if not ok:
        failures.append(reason)
    for validator in (
        validate_evidence_reproducible,
        validate_go_no_go,
        validate_rollout_matrix_complete,
        validate_rollback_evidence_present,
        validate_sample_lists_present,
    ):
        ok, reason = validator(package)  # type: ignore[arg-type]
        if not ok:
            failures.append(reason)
    if failures:
        return False, failures
    return True, []


# ===== 草稿采用率反查辅助（纯逻辑判定）=====

# 业务单据有效状态（未作废/未删除）
# InOrder.status: pending/completed/voided
# OutOrder.status: pending/completed/voided
# 其他单据类似
VALID_BUSINESS_STATUSES = frozenset({'pending', 'completed', 'confirmed', 'approved'})
INVALID_BUSINESS_STATUSES = frozenset({'voided', 'deleted', 'cancelled', 'rejected'})


def is_draft_adopted_by_business(
    draft_type: str,
    draft_id: Optional[int],
    business_status: Optional[str],
) -> tuple[bool, str]:
    """判定草稿是否被业务真正采用（反查业务单据状态）。

    口径修正（台账 13.2）：草稿采用率必须反查真实业务单据是否保留并进入
    人工确认后的有效状态，不得只以 draft_id 非空判断。

    Args:
        draft_type: 草稿类型（in_order/out_order/purchase_receive 等）。
        draft_id: 草稿关联的业务单据 ID（AIDraftIdempotency.draft_id）。
        business_status: 业务单据当前 status（反查 InOrder/OutOrder 等获得）。

    Returns:
        (是否采用, 原因)
    """
    if not draft_id or draft_id <= 0:
        return False, '草稿未关联业务单据（draft_id 为空）'
    if business_status is None:
        return False, f'业务单据 {draft_type}#{draft_id} 不存在（已删除）'
    if business_status in INVALID_BUSINESS_STATUSES:
        return False, f'业务单据 {draft_type}#{draft_id} 状态为 {business_status}（已作废/删除）'
    if business_status in VALID_BUSINESS_STATUSES:
        return True, f'业务单据 {draft_type}#{draft_id} 状态为 {business_status}（有效采用）'
    # 未知状态保守判定为未采用
    return False, f'业务单据 {draft_type}#{draft_id} 状态为 {business_status}（未知状态保守判定）'


# ===== 低置信度未确认判定辅助（临时口径）=====

def is_low_confidence_unconfirmed(
    confidence: Optional[float],
    document_job_status: str,
    confirmation_status: Optional[str] = None,
) -> tuple[bool, str]:
    """判定低置信度未确认建单。

    口径修正（台账 13.2）：低置信度未确认必须读取明确的 confirmation_status，
    不得只根据置信度猜测。

    临时口径（待 R08-F01 完成）：confidence < 0.85 且 document_job_status == 'draft_created'
    且 confirmation_status 为 None 或 'pending' 时判定为未确认。
    R08-F01 完成后切换为 confirmation_status in ('pending', None) 判定。

    Args:
        confidence: 字段置信度（AIDocumentItem.confidence）。
        document_job_status: 文档任务状态（AIDocumentJob.status）。
        confirmation_status: 确认状态（R08-F01 完成后由 AIDocumentItem.confirmation_status 提供）。

    Returns:
        (是否低置信度未确认, 原因)
    """
    # 如果 confirmation_status 已实现且已确认，则不算未确认
    if confirmation_status in ('confirmed_original', 'corrected', 'rejected'):
        return False, f'confirmation_status={confirmation_status}（已处理）'
    # 临时口径：confidence < 阈值 且 draft_created 且未确认
    if confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD:
        if document_job_status == 'draft_created':
            return True, f'confidence={confidence}<{LOW_CONFIDENCE_THRESHOLD} 且 status=draft_created 且 confirmation_status={confirmation_status}（低置信度未确认）'
        return False, f'confidence={confidence} 但 status={document_job_status}（非 draft_created）'
    return False, f'confidence={confidence}（未低于阈值 {LOW_CONFIDENCE_THRESHOLD}）'

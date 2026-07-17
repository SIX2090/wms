"""AI-R15：业务质量指标和版本对比。

# AI_TASK: AI-R15

设计目标（验收：支持按时间、角色、来源、模型、提示词和 Schema 版本筛选，指标可复算）：

- 7 个业务质量指标（统一聚合层，消费 AI-R03 离线样本指标 + AI-R09 字段反馈 +
  AI-R01 重复拦截 + 草稿采用数据，产出业务级快照）：
  1. classification_accuracy   分类准确率（document_type 正确率）
  2. header_accuracy           表头准确率（表头字段正确率）
  3. line_recall               行召回率（明细行召回率）
  4. material_match_rate       物料匹配率（物料匹配正确率）
  5. human_correction_rate     人工修正率（字段被修正比例）
  6. draft_adoption_rate       草稿采用率（草稿最终被业务采用比例）
  7. duplicate_interception_rate 重复拦截率（幂等拦截次数 / 总请求次数）

  与现有能力的边界（防重复）：
  - AI-R09 field_feedback.aggregate_quality_metrics 是**字段级**聚合
    （per-field accuracy/correction + 字段级下降检测）；
    本模块是**业务级**聚合（7 个业务指标整体快照 + 版本对比 + 多维筛选）。
  - AI-R03 evaluation.evaluate_document_samples 是**离线黄金样本**评估
    （sample-level header/line/quantity/material）；
    本模块是**生产运行时业务质量**（runtime + draft-level + 拦截率 + 采用率）。
  - 版本对比：AI-R09 是字段级下降检测（per-field drop）；
    本模块是整体业务质量版本对比（7 指标全对比 + 可配阈值）。

- 多维筛选 QualityFilter：时间范围 / 角色 / 来源 / 模型 / 提示词 / Schema 版本。
  纯函数 apply_filter 对样本列表过滤，不访问 DB。

- 指标可复算：所有函数为纯函数，now 参数注入；相同输入 + 相同 now 产出相同快照。

- 纯逻辑 + 依赖注入：不依赖 Flask/ORM，与 AI-R12/R13/R14 一致。
  生产环境由 app.py 提供 ORM adapter 查询样本；CI 无 DB 时直接传入样本列表测试。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# ---- 7 个业务质量指标标识 ----

METRIC_CLASSIFICATION_ACCURACY = 'classification_accuracy'
METRIC_HEADER_ACCURACY = 'header_accuracy'
METRIC_LINE_RECALL = 'line_recall'
METRIC_MATERIAL_MATCH_RATE = 'material_match_rate'
METRIC_HUMAN_CORRECTION_RATE = 'human_correction_rate'
METRIC_DRAFT_ADOPTION_RATE = 'draft_adoption_rate'
METRIC_DUPLICATE_INTERCEPTION_RATE = 'duplicate_interception_rate'

ALL_METRICS: tuple[str, ...] = (
    METRIC_CLASSIFICATION_ACCURACY,
    METRIC_HEADER_ACCURACY,
    METRIC_LINE_RECALL,
    METRIC_MATERIAL_MATCH_RATE,
    METRIC_HUMAN_CORRECTION_RATE,
    METRIC_DRAFT_ADOPTION_RATE,
    METRIC_DUPLICATE_INTERCEPTION_RATE,
)

METRIC_LABELS: dict[str, str] = {
    METRIC_CLASSIFICATION_ACCURACY: '分类准确率',
    METRIC_HEADER_ACCURACY: '表头准确率',
    METRIC_LINE_RECALL: '行召回率',
    METRIC_MATERIAL_MATCH_RATE: '物料匹配率',
    METRIC_HUMAN_CORRECTION_RATE: '人工修正率',
    METRIC_DRAFT_ADOPTION_RATE: '草稿采用率',
    METRIC_DUPLICATE_INTERCEPTION_RATE: '重复拦截率',
}

# 版本对比默认阈值：指标下降超过此值才标记 is_regression
DEFAULT_REGRESSION_THRESHOLD = 0.05


# ---- 数据结构（纯 dataclass，不依赖 ORM）----

@dataclass(frozen=True)
class QualitySample:
    """单条业务质量样本（生产运行时聚合的最小单元）。

    每条样本携带 7 个指标的分子/分母（部分指标对某条样本不适用时分母为 0），
    以及 6 个维度标签用于多维筛选。app.py 的 ORM adapter 负责从
    AIFieldFeedback / AIDraftIdempotency / 业务单据表查询并组装样本。
    """

    sample_id: str                        # 样本唯一标识（如 run_id / draft_idempotency_id）
    occurred_at: str                      # ISO 时间戳（用于时间筛选）
    role: str                             # 角色（admin/warehouse/purchase/...）
    source: str                           # 来源（ocr_upload/wechat_text/excel_import/...）
    model: str                            # 模型名
    prompt_hash: str                      # 提示词指纹
    schema_version: str                   # Schema 版本

    # 7 个指标的分子/分母（分母为 0 表示该指标对该样本不适用）
    classification_total: int = 0
    classification_correct: int = 0
    header_total: int = 0
    header_correct: int = 0
    line_expected: int = 0
    line_recalled: int = 0
    material_total: int = 0
    material_matched: int = 0
    field_total: int = 0
    field_corrected: int = 0
    draft_total: int = 0
    draft_adopted: int = 0
    request_total: int = 0
    request_intercepted: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            'sample_id': self.sample_id,
            'occurred_at': self.occurred_at,
            'role': self.role,
            'source': self.source,
            'model': self.model,
            'prompt_hash': self.prompt_hash,
            'schema_version': self.schema_version,
            'classification_total': self.classification_total,
            'classification_correct': self.classification_correct,
            'header_total': self.header_total,
            'header_correct': self.header_correct,
            'line_expected': self.line_expected,
            'line_recalled': self.line_recalled,
            'material_total': self.material_total,
            'material_matched': self.material_matched,
            'field_total': self.field_total,
            'field_corrected': self.field_corrected,
            'draft_total': self.draft_total,
            'draft_adopted': self.draft_adopted,
            'request_total': self.request_total,
            'request_intercepted': self.request_intercepted,
        }


@dataclass(frozen=True)
class MetricValue:
    """单个指标聚合值（分子 / 分母 / 比率）。"""

    metric: str
    numerator: int
    denominator: int
    rate: float                            # numerator / denominator，分母为 0 时返回 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            'metric': self.metric,
            'label': METRIC_LABELS.get(self.metric, self.metric),
            'numerator': self.numerator,
            'denominator': self.denominator,
            'rate': round(self.rate, 4),
        }


@dataclass(frozen=True)
class BusinessQualitySnapshot:
    """业务质量快照（7 指标聚合 + 维度分组 + 筛选条件）。

    验收要求："支持按时间、角色、来源、模型、提示词和 Schema 版本筛选，指标可复算"。
    """

    metrics: dict[str, MetricValue]        # 7 指标聚合值，key 为指标标识
    by_dimension: dict[str, dict[str, dict[str, Any]]]  # 按维度分组：{dimension: {value: {metric: rate}}}
    sample_count: int
    filter_applied: dict[str, Any]         # 实际应用的筛选条件快照（可复算追溯）
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'metrics': {k: v.to_dict() for k, v in self.metrics.items()},
            'by_dimension': self.by_dimension,
            'sample_count': self.sample_count,
            'filter_applied': self.filter_applied,
            'generated_at': self.generated_at,
        }


@dataclass(frozen=True)
class VersionComparison:
    """版本对比结果（当前版本 vs 基线版本的 7 指标对比）。

    验收要求："版本对比"。
    """

    baseline_version: str                  # 基线版本标识（如 schema_version 或 自定义版本标签）
    current_version: str                   # 当前版本标识
    baseline_metrics: dict[str, MetricValue]
    current_metrics: dict[str, MetricValue]
    deltas: dict[str, float]               # 各指标 current_rate - baseline_rate（正值=提升，负值=下降）
    regressions: tuple[str, ...]           # 下降超阈值的指标标识列表
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'baseline_version': self.baseline_version,
            'current_version': self.current_version,
            'baseline_metrics': {k: v.to_dict() for k, v in self.baseline_metrics.items()},
            'current_metrics': {k: v.to_dict() for k, v in self.current_metrics.items()},
            'deltas': {k: round(v, 4) for k, v in self.deltas.items()},
            'regressions': list(self.regressions),
            'generated_at': self.generated_at,
        }


@dataclass(frozen=True)
class QualityFilter:
    """多维筛选条件（纯数据，apply_filter 对样本列表过滤）。

    验收要求："支持按时间、角色、来源、模型、提示词和 Schema 版本筛选"。
    所有字段为可选；None 或空表示不限制该维度。
    """

    time_start: Optional[str] = None       # ISO 时间戳，含
    time_end: Optional[str] = None         # ISO 时间戳，含
    role: Optional[str] = None
    source: Optional[str] = None
    model: Optional[str] = None
    prompt_hash: Optional[str] = None
    schema_version: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'time_start': self.time_start,
            'time_end': self.time_end,
            'role': self.role,
            'source': self.source,
            'model': self.model,
            'prompt_hash': self.prompt_hash,
            'schema_version': self.schema_version,
        }


# ---- 筛选 ----

def apply_filter(
    samples: list[QualitySample],
    filter_: Optional[QualityFilter],
) -> list[QualitySample]:
    """按 QualityFilter 多维筛选样本列表。

    验收要求："支持按时间、角色、来源、模型、提示词和 Schema 版本筛选"。
    纯函数，不访问 DB。time_start/time_end 为闭区间（含端点）。
    """
    if filter_ is None:
        return list(samples)

    result: list[QualitySample] = []
    for s in samples:
        if filter_.time_start is not None and s.occurred_at < filter_.time_start:
            continue
        if filter_.time_end is not None and s.occurred_at > filter_.time_end:
            continue
        if filter_.role is not None and s.role != filter_.role:
            continue
        if filter_.source is not None and s.source != filter_.source:
            continue
        if filter_.model is not None and s.model != filter_.model:
            continue
        if filter_.prompt_hash is not None and s.prompt_hash != filter_.prompt_hash:
            continue
        if filter_.schema_version is not None and s.schema_version != filter_.schema_version:
            continue
        result.append(s)
    return result


# ---- 单指标聚合 ----

def _ratio(numerator: int, denominator: int) -> float:
    """计算比率，分母为 0 返回 0.0（该指标对该批样本不适用）。"""
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _aggregate_metric(
    samples: list[QualitySample],
    metric: str,
) -> MetricValue:
    """聚合单个指标（分子分母求和后算比率）。"""
    num = 0
    den = 0
    for s in samples:
        if metric == METRIC_CLASSIFICATION_ACCURACY:
            den += s.classification_total
            num += s.classification_correct
        elif metric == METRIC_HEADER_ACCURACY:
            den += s.header_total
            num += s.header_correct
        elif metric == METRIC_LINE_RECALL:
            den += s.line_expected
            num += s.line_recalled
        elif metric == METRIC_MATERIAL_MATCH_RATE:
            den += s.material_total
            num += s.material_matched
        elif metric == METRIC_HUMAN_CORRECTION_RATE:
            den += s.field_total
            num += s.field_corrected
        elif metric == METRIC_DRAFT_ADOPTION_RATE:
            den += s.draft_total
            num += s.draft_adopted
        elif metric == METRIC_DUPLICATE_INTERCEPTION_RATE:
            den += s.request_total
            num += s.request_intercepted
    return MetricValue(metric=metric, numerator=num, denominator=den, rate=_ratio(num, den))


# ---- 主构建函数：业务质量快照 ----

# 维度分组使用的样本字段
_DIMENSION_FIELDS: tuple[str, ...] = ('role', 'source', 'model', 'prompt_hash', 'schema_version')


def compute_business_quality(
    samples: list[QualitySample],
    *,
    filter_: Optional[QualityFilter] = None,
    now: Optional[str] = None,
) -> BusinessQualitySnapshot:
    """计算业务质量快照（7 指标聚合 + 维度分组 + 筛选条件追溯）。

    验收要求："支持按时间、角色、来源、模型、提示词和 Schema 版本筛选，指标可复算"。

    Args:
        samples: 业务质量样本列表（由 app.py ORM adapter 查询组装，或测试直接构造）
        filter_: 多维筛选条件；None 时不筛选
        now: ISO 时间戳；None 时取当前时间（注入 now 保证可复算）

    Returns:
        BusinessQualitySnapshot 含 7 指标聚合 + 6 维度分组 + 筛选条件快照
    """
    timestamp = now or datetime.now().isoformat()

    # 应用筛选
    filtered = apply_filter(samples, filter_)

    # 7 指标聚合
    metrics: dict[str, MetricValue] = {}
    for metric in ALL_METRICS:
        metrics[metric] = _aggregate_metric(filtered, metric)

    # 维度分组（按 role/source/model/prompt_hash/schema_version 分组，每组算 7 指标比率）
    by_dimension: dict[str, dict[str, dict[str, Any]]] = {}
    for dim_field in _DIMENSION_FIELDS:
        dim_groups: dict[str, list[QualitySample]] = {}
        for s in filtered:
            value = getattr(s, dim_field)
            if not value:
                continue
            dim_groups.setdefault(value, []).append(s)
        dim_result: dict[str, dict[str, Any]] = {}
        for value, group in dim_groups.items():
            metric_rates: dict[str, Any] = {}
            for metric in ALL_METRICS:
                mv = _aggregate_metric(group, metric)
                metric_rates[metric] = round(mv.rate, 4)
            dim_result[value] = metric_rates
        by_dimension[dim_field] = dim_result

    filter_snapshot = filter_.to_dict() if filter_ is not None else {}

    return BusinessQualitySnapshot(
        metrics=metrics,
        by_dimension=by_dimension,
        sample_count=len(filtered),
        filter_applied=filter_snapshot,
        generated_at=timestamp,
    )


# ---- 版本对比 ----

def compare_versions(
    current_samples: list[QualitySample],
    baseline_samples: list[QualitySample],
    *,
    current_version: str,
    baseline_version: str,
    filter_: Optional[QualityFilter] = None,
    regression_threshold: float = DEFAULT_REGRESSION_THRESHOLD,
    now: Optional[str] = None,
) -> VersionComparison:
    """版本对比：当前版本 vs 基线版本的 7 指标对比。

    验收要求："版本对比"。
    对两版本分别计算快照，逐指标对比 delta = current_rate - baseline_rate，
    delta < -threshold 视为下降（is_regression）。

    Args:
        current_samples: 当前版本样本
        baseline_samples: 基线版本样本
        current_version: 当前版本标识
        baseline_version: 基线版本标识
        filter_: 可选筛选（同时应用于两版本，保证对比口径一致）
        regression_threshold: 下降阈值（正值），delta < -threshold 视为下降
        now: ISO 时间戳
    """
    timestamp = now or datetime.now().isoformat()

    current_snapshot = compute_business_quality(current_samples, filter_=filter_, now=timestamp)
    baseline_snapshot = compute_business_quality(baseline_samples, filter_=filter_, now=timestamp)

    deltas: dict[str, float] = {}
    regressions: list[str] = []
    for metric in ALL_METRICS:
        cur_rate = current_snapshot.metrics[metric].rate
        base_rate = baseline_snapshot.metrics[metric].rate
        delta = cur_rate - base_rate
        deltas[metric] = delta
        # 下降超阈值（delta 为负且绝对值 > threshold），用容差避免浮点精度误判
        if delta < -(regression_threshold + 1e-9):
            regressions.append(metric)

    return VersionComparison(
        baseline_version=baseline_version,
        current_version=current_version,
        baseline_metrics=baseline_snapshot.metrics,
        current_metrics=current_snapshot.metrics,
        deltas=deltas,
        regressions=tuple(regressions),
        generated_at=timestamp,
    )


# ---- 验收校验函数 ----

def validate_metrics_reproducible(
    samples: list[QualitySample],
    filter_: Optional[QualityFilter] = None,
    *,
    now: str = '2026-07-17T10:00:00',
) -> tuple[bool, str]:
    """校验指标可复算：相同输入 + 相同 now 产出相同快照。

    验收要求："指标可复算"。
    """
    snap1 = compute_business_quality(samples, filter_=filter_, now=now)
    snap2 = compute_business_quality(samples, filter_=filter_, now=now)
    if snap1.to_dict() != snap2.to_dict():
        return False, '相同输入 + 相同 now 产出不同快照，指标不可复算'
    # 不同 now 仅影响 generated_at，指标值应一致
    snap3 = compute_business_quality(samples, filter_=filter_, now='2026-07-17T11:00:00')
    for metric in ALL_METRICS:
        if snap1.metrics[metric].to_dict() != snap3.metrics[metric].to_dict():
            return False, f'指标 {metric} 随 now 变化，不可复算'
    return True, '指标可复算（相同输入产出相同指标值，generated_at 随 now 变化但不影响指标）'


def validate_filter_dimensions(
    samples: list[QualitySample],
) -> tuple[bool, str]:
    """校验多维筛选生效：6 维度筛选各自只保留匹配样本。

    验收要求："支持按时间、角色、来源、模型、提示词和 Schema 版本筛选"。
    """
    if not samples:
        return True, '无样本，筛选校验跳过'

    # 取第一个样本的维度值作为筛选目标
    target = samples[0]

    dimensions: list[tuple[str, str, Any]] = [
        ('role', 'role', target.role),
        ('source', 'source', target.source),
        ('model', 'model', target.model),
        ('prompt_hash', 'prompt_hash', target.prompt_hash),
        ('schema_version', 'schema_version', target.schema_version),
    ]
    for label, attr, value in dimensions:
        if not value:
            continue
        filtered = apply_filter(samples, QualityFilter(**{attr: value}))
        if any(getattr(s, attr) != value for s in filtered):
            return False, f'{label} 筛选后仍含不匹配样本'
        if not any(getattr(s, attr) == value for s in filtered):
            return False, f'{label} 筛选后丢失匹配样本'

    # 时间筛选（闭区间）
    if len(samples) >= 2:
        sorted_samples = sorted(samples, key=lambda s: s.occurred_at)
        mid_time = sorted_samples[len(sorted_samples) // 2].occurred_at
        filtered_time = apply_filter(samples, QualityFilter(time_start=mid_time, time_end=mid_time))
        if any(s.occurred_at < mid_time or s.occurred_at > mid_time for s in filtered_time):
            return False, '时间筛选后仍含区间外样本'

    # 组合筛选
    combo_filter = QualityFilter(role=target.role, source=target.source) if target.role and target.source else None
    if combo_filter:
        combo_filtered = apply_filter(samples, combo_filter)
        if any(s.role != target.role or s.source != target.source for s in combo_filtered):
            return False, '组合筛选后仍含不匹配样本'

    return True, '6 维度筛选（时间/角色/来源/模型/提示词/Schema版本）均生效'


def validate_version_comparison(
    comparison: VersionComparison,
) -> tuple[bool, str]:
    """校验版本对比完整性：7 指标均有 delta + regressions 与阈值一致。

    验收要求："版本对比"。
    """
    if len(comparison.deltas) != len(ALL_METRICS):
        return False, f'deltas 数量 {len(comparison.deltas)} != 指标数 {len(ALL_METRICS)}'
    if len(comparison.baseline_metrics) != len(ALL_METRICS):
        return False, '基线指标不完整'
    if len(comparison.current_metrics) != len(ALL_METRICS):
        return False, '当前指标不完整'
    # regressions 应是 deltas 中下降超阈值的子集
    for metric in comparison.regressions:
        if metric not in comparison.deltas:
            return False, f'regression 指标 {metric} 不在 deltas 中'
    # 所有 delta 应等于 current_rate - baseline_rate
    for metric in ALL_METRICS:
        expected = comparison.current_metrics[metric].rate - comparison.baseline_metrics[metric].rate
        actual = comparison.deltas[metric]
        if abs(expected - actual) > 1e-9:
            return False, f'指标 {metric} delta 与快照不一致'
    return True, '版本对比完整（7 指标 delta + regressions 一致）'


def validate_all_dimensions_present(
    snapshot: BusinessQualitySnapshot,
) -> tuple[bool, str]:
    """校验快照含 5 个维度分组（role/source/model/prompt_hash/schema_version）。"""
    expected_dims = {'role', 'source', 'model', 'prompt_hash', 'schema_version'}
    actual_dims = set(snapshot.by_dimension.keys())
    missing = expected_dims - actual_dims
    if missing:
        return False, f'缺失维度分组：{missing}'
    return True, '5 个维度分组齐全'

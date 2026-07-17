"""AI-R09：字段级反馈和文档质量指标。

# AI_TASK: AI-R09

设计目标（验收：可定位质量下降的字段和版本，不保存不必要的敏感原文）：

- 记录字段级反馈：字段名/原值/新值/修正原因/是否采纳/模型/提示词/Schema 版本/来源/行号。
  从 AI-R08 DocumentConfirmationEvidence 的 fields + 用户提交的 corrections 产出
  FieldCorrectionRecord 列表，是生产运行时的逐字段反馈闭环（区别于 AI-R03 离线样本
  聚合评估）。

- 按来源与版本聚合准确率和修正率：aggregate_quality_metrics 按
  (source, model, schema_version, field_name) 分组，产出 accuracy_rate /
  correction_rate / top_reasons，供运维页和 AI-R15 业务质量指标消费。

- 质量下降定位：detect_quality_regressions 对比当前版本与基线版本的 per-field
  accuracy，下降超阈值（默认 0.10）标记 is_regression=True，可定位到具体字段和版本。

- 不保存不必要的敏感原文：mask_sensitive_value 内置脱敏（手机号/身份证/地址/联系人），
  空值不存；save 回调由调用方注入，CI 无 DB 可 mock 测，生产由 app.py 提供 ORM adapter
  写入 AIFieldFeedback 表。

- 纯逻辑 + 依赖注入：不依赖 Flask/ORM，与 AI-R06/R07/R08 一致。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional


# ---- 阈值（可配置）----

# 质量下降阈值：当前版本 accuracy 低于基线 accuracy 超过此值才视为下降
QUALITY_REGRESSION_THRESHOLD = 0.10

# Schema 版本（与 AI-R05 provider_evaluation.SCHEMA_VERSION 对齐）
DEFAULT_SCHEMA_VERSION = 'document-extraction-v1'


# ---- 数据结构（纯 dataclass，不依赖 ORM）----

@dataclass(frozen=True)
class FieldCorrectionRecord:
    """单字段修正记录（生产运行时逐字段反馈）。

    验收要求："记录字段名、原值、新值、修正原因、是否采纳、模型、提示词和 Schema 版本"。
    敏感原文经 mask_sensitive_value 脱敏后存储，不保存不必要的敏感原文。
    """

    field_name: str                       # code/name/spec/quantity/unit/supplier/order_no/date/...
    line_index: int                       # 行级字段为行号，表头字段为 -1
    original_value: str                   # OCR 提取的原始值（已脱敏）
    corrected_value: str                  # 用户修正后的新值（已脱敏）
    correction_reason: str                # low_confidence/ambiguous_spec/multiple_candidates/high_risk/user_override/...
    adopted: bool                         # 是否采纳修正（True=采用新值，False=拒绝修正保留原值）
    model: str                            # 模型名（gpt-5.6-sol/...）
    prompt_hash: str                      # 提示词指纹（复用 AI-R05 compute_prompt_hash）
    schema_version: str                   # Schema 版本（document-extraction-v1）
    source: str                           # 来源（ocr_upload/wechat_text/excel_import/...）
    created_at: str                       # ISO 格式时间戳

    def to_dict(self) -> dict[str, Any]:
        return {
            'field_name': self.field_name,
            'line_index': self.line_index,
            'original_value': self.original_value,
            'corrected_value': self.corrected_value,
            'correction_reason': self.correction_reason,
            'adopted': self.adopted,
            'model': self.model,
            'prompt_hash': self.prompt_hash,
            'schema_version': self.schema_version,
            'source': self.source,
            'created_at': self.created_at,
        }


@dataclass(frozen=True)
class FieldQualityMetrics:
    """单字段聚合质量指标（按 source/model/schema_version/field_name 分组）。

    验收要求："按来源与版本聚合准确率和修正率"。
    """

    field_name: str
    source: str
    model: str
    schema_version: str
    total_count: int                      # 该字段出现的总次数（含未修正）
    corrected_count: int                  # 被修正的次数
    adopted_count: int                    # 修正被采纳的次数
    accuracy_rate: float                  # 1 - correction_rate
    correction_rate: float                # corrected_count / total_count
    top_reasons: tuple[tuple[str, int], ...]  # 修正原因分布（原因, 次数）按次数降序

    def to_dict(self) -> dict[str, Any]:
        return {
            'field_name': self.field_name,
            'source': self.source,
            'model': self.model,
            'schema_version': self.schema_version,
            'total_count': self.total_count,
            'corrected_count': self.corrected_count,
            'adopted_count': self.adopted_count,
            'accuracy_rate': round(self.accuracy_rate, 4),
            'correction_rate': round(self.correction_rate, 4),
            'top_reasons': [{'reason': r, 'count': c} for r, c in self.top_reasons],
        }


@dataclass(frozen=True)
class QualityRegression:
    """质量下降定位（当前版本 vs 基线版本的 per-field accuracy 对比）。

    验收要求："可定位质量下降的字段和版本"。
    """

    field_name: str
    source: str
    model: str
    baseline_schema_version: str
    current_schema_version: str
    baseline_accuracy: float
    current_accuracy: float
    drop_amount: float                    # baseline_accuracy - current_accuracy（正值=下降）
    is_regression: bool                   # drop_amount > 阈值才为 True

    def to_dict(self) -> dict[str, Any]:
        return {
            'field_name': self.field_name,
            'source': self.source,
            'model': self.model,
            'baseline_schema_version': self.baseline_schema_version,
            'current_schema_version': self.current_schema_version,
            'baseline_accuracy': round(self.baseline_accuracy, 4),
            'current_accuracy': round(self.current_accuracy, 4),
            'drop_amount': round(self.drop_amount, 4),
            'is_regression': self.is_regression,
        }


@dataclass(frozen=True)
class QualityMetricsSnapshot:
    """聚合质量指标快照（含按字段/来源/模型/Schema版本分组 + 质量下降定位）。"""

    by_field: tuple[FieldQualityMetrics, ...]
    regressions: tuple[QualityRegression, ...]
    total_records: int
    overall_accuracy_rate: float          # 全字段综合准确率
    overall_correction_rate: float        # 全字段综合修正率
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'by_field': [m.to_dict() for m in self.by_field],
            'regressions': [r.to_dict() for r in self.regressions],
            'total_records': self.total_records,
            'overall_accuracy_rate': round(self.overall_accuracy_rate, 4),
            'overall_correction_rate': round(self.overall_correction_rate, 4),
            'generated_at': self.generated_at,
        }


# ---- 保存接口（依赖注入）----

# save_feedback_record 回调签名：
# (record: FieldCorrectionRecord) -> None
# 生产环境由 app.py 提供写入 AIFieldFeedback ORM 的 adapter；CI 无 DB 时传 None。
SaveFeedbackRecordFn = Callable[[FieldCorrectionRecord], None]


# ---- 敏感原文脱敏 ----

# 手机号：1 开头 11 位
_PHONE_RE = re.compile(r'1[3-9]\d{9}')
# 身份证：18 位（最后一位可能是 X）
_ID_CARD_RE = re.compile(r'\d{17}[\dXx]')
# 邮箱
_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
# 需要整体脱敏的字段名（不存原值，只存 ***）
_FULL_MASK_FIELDS = ('id_card', 'phone', 'mobile', 'email', 'contact', 'contact_phone')


def mask_sensitive_value(value: str, field_name: str) -> str:
    """脱敏敏感原文。

    验收要求："不保存不必要的敏感原文"。
    - 空值返回空（不存）。
    - 整体脱敏字段（id_card/phone/email/contact）：返回 '***'。
    - 其他字段：对值中的手机号/身份证/邮箱做局部脱敏。
    """
    if not value:
        return ''
    fname = (field_name or '').lower()
    # 整体脱敏字段
    for sensitive in _FULL_MASK_FIELDS:
        if sensitive in fname:
            return '***'
    # 局部脱敏：手机号保留前3后4，身份证保留前6后4，邮箱打码
    result = value
    result = _PHONE_RE.sub(lambda m: m.group()[:3] + '****' + m.group()[-4:], result)
    result = _ID_CARD_RE.sub(lambda m: m.group()[:6] + '********' + m.group()[-4:], result)
    result = _EMAIL_RE.sub(lambda m: m.group()[:2] + '***@' + m.group().split('@')[1], result)
    return result


# ---- 主构建函数 ----

def build_field_correction_records(
    *,
    evidence_fields: list[dict[str, Any]],
    corrections: dict[str, Any],
    model: str,
    prompt_hash: str,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
    source: str = 'ocr_upload',
    save_feedback_record: Optional[SaveFeedbackRecordFn] = None,
    now: Optional[str] = None,
) -> list[FieldCorrectionRecord]:
    """从 R08 evidence.fields + 用户 corrections 产出字段修正记录。

    Args:
        evidence_fields: AI-R08 DocumentConfirmationEvidence.to_dict()['fields'] 列表，
                         每项含 field_name/line_index/original_value/confidence/
                         needs_confirmation/confirmation_reason/correction_status
        corrections: 用户提交的修正字典，key 为 'line{idx}.{field_name}' 或 '{field_name}'，
                     value 为修正后的新值
        model: 模型名（来自 _ai_llm_model()）
        prompt_hash: 提示词指纹（来自 AI-R05 compute_prompt_hash）
        schema_version: Schema 版本（默认 document-extraction-v1）
        source: 来源（ocr_upload/wechat_text/excel_import/...）
        save_feedback_record: 注入的保存回调；None 时不持久化（仅返回记录供测试/聚合）
        now: ISO 时间戳；None 时取当前时间

    Returns:
        FieldCorrectionRecord 列表（仅对发生修正或确认的字段产出）

    说明：
        - 仅当字段 needs_confirmation=True 或 corrections 中有覆盖时才产出记录
          （未触发确认流程的字段不产生反馈记录，避免噪音）。
        - corrections 中的字段视为"已修正"，adopted=True；
          needs_confirmation=True 但 corrections 中无覆盖视为"未修正拒绝"，adopted=False。
        - original_value/corrected_value 经 mask_sensitive_value 脱敏后存储。
    """
    if not evidence_fields:
        return []

    timestamp = now or datetime.now().isoformat()
    records: list[FieldCorrectionRecord] = []

    for f in evidence_fields:
        field_name = str(f.get('field_name') or '')
        line_index = int(f.get('line_index') or -1)
        needs_confirmation = bool(f.get('needs_confirmation'))
        confirmation_reason = str(f.get('confirmation_reason') or '')
        original_value = str(f.get('original_value') or '')

        # 构造 corrections key
        if line_index >= 0:
            key = f'line{line_index}.{field_name}'
        else:
            key = field_name

        # 仅对触发确认流程的字段产出记录
        if not needs_confirmation and key not in (corrections or {}):
            continue

        # 判断是否被用户修正
        corrected_value_raw = ''
        adopted = False
        correction_reason = ''

        if corrections and key in corrections:
            # 用户提交了修正
            corrected_value_raw = str(corrections.get(key) or '')
            if corrected_value_raw and corrected_value_raw != original_value:
                adopted = True
                correction_reason = confirmation_reason or 'user_override'
            elif corrected_value_raw == original_value:
                # 用户确认原值正确（保留原值），视为"拒绝修正"
                adopted = False
                correction_reason = confirmation_reason or 'user_confirmed_original'
            else:
                # 空修正，视为未处理
                adopted = False
                correction_reason = confirmation_reason or 'unhandled'
        else:
            # needs_confirmation=True 但用户未提交修正，视为"未修正拒绝"
            adopted = False
            correction_reason = confirmation_reason or 'unhandled'

        # 脱敏后存储
        original_masked = mask_sensitive_value(original_value, field_name)
        corrected_masked = mask_sensitive_value(corrected_value_raw, field_name)

        record = FieldCorrectionRecord(
            field_name=field_name,
            line_index=line_index,
            original_value=original_masked,
            corrected_value=corrected_masked,
            correction_reason=correction_reason,
            adopted=adopted,
            model=model,
            prompt_hash=prompt_hash,
            schema_version=schema_version,
            source=source,
            created_at=timestamp,
        )
        records.append(record)

        # 注入保存回调
        if save_feedback_record is not None:
            try:
                save_feedback_record(record)
            except Exception:
                # 保存失败不阻塞主流程（反馈记录是旁路，不影响业务）
                pass

    return records


# ---- 聚合质量指标 ----

def aggregate_quality_metrics(
    records: list[FieldCorrectionRecord],
    *,
    baseline_records: Optional[list[FieldCorrectionRecord]] = None,
    regression_threshold: float = QUALITY_REGRESSION_THRESHOLD,
    now: Optional[str] = None,
) -> QualityMetricsSnapshot:
    """按来源/模型/Schema版本/字段名聚合准确率和修正率，并检测质量下降。

    验收要求："按来源与版本聚合准确率和修正率" + "可定位质量下降的字段和版本"。

    Args:
        records: 当前版本的字段修正记录列表
        baseline_records: 基线版本记录（用于质量下降对比）；None 时跳过下降检测
        regression_threshold: 质量下降阈值，accuracy 下降超过此值才标记 is_regression
        now: ISO 时间戳

    Returns:
        QualityMetricsSnapshot 含 by_field 聚合 + regressions 下降定位
    """
    timestamp = now or datetime.now().isoformat()

    # 按 (source, model, schema_version, field_name) 分组聚合
    groups: dict[tuple[str, str, str, str], list[FieldCorrectionRecord]] = {}
    for r in records:
        group_key = (r.source, r.model, r.schema_version, r.field_name)
        groups.setdefault(group_key, []).append(r)

    by_field: list[FieldQualityMetrics] = []
    total_records = 0
    total_corrected = 0

    for (source, model, schema_version, field_name), group in groups.items():
        # total_count: 该字段被记录的总次数（含未修正的拒绝记录）
        total_count = len(group)
        # corrected_count: adopted=True 的次数（实际修正了值）
        corrected_count = sum(1 for r in group if r.adopted)
        # adopted_count 同 corrected_count（保留语义清晰）
        adopted_count = corrected_count

        correction_rate = corrected_count / total_count if total_count > 0 else 0.0
        accuracy_rate = 1.0 - correction_rate

        # 修正原因分布
        reason_counts: dict[str, int] = {}
        for r in group:
            reason = r.correction_reason or 'unknown'
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        top_reasons = tuple(
            sorted(reason_counts.items(), key=lambda x: (-x[1], x[0]))[:5]
        )

        by_field.append(FieldQualityMetrics(
            field_name=field_name,
            source=source,
            model=model,
            schema_version=schema_version,
            total_count=total_count,
            corrected_count=corrected_count,
            adopted_count=adopted_count,
            accuracy_rate=accuracy_rate,
            correction_rate=correction_rate,
            top_reasons=top_reasons,
        ))

        total_records += total_count
        total_corrected += corrected_count

    # 按 total_count 降序排序（高频字段在前）
    by_field.sort(key=lambda m: (-m.total_count, m.field_name))

    overall_correction_rate = total_corrected / total_records if total_records > 0 else 0.0
    overall_accuracy_rate = 1.0 - overall_correction_rate

    # 质量下降检测
    regressions: list[QualityRegression] = []
    if baseline_records:
        regressions = detect_quality_regressions(
            current_records=records,
            baseline_records=baseline_records,
            threshold=regression_threshold,
        )

    return QualityMetricsSnapshot(
        by_field=tuple(by_field),
        regressions=tuple(regressions),
        total_records=total_records,
        overall_accuracy_rate=overall_accuracy_rate,
        overall_correction_rate=overall_correction_rate,
        generated_at=timestamp,
    )


# ---- 质量下降定位 ----

def detect_quality_regressions(
    *,
    current_records: list[FieldCorrectionRecord],
    baseline_records: list[FieldCorrectionRecord],
    threshold: float = QUALITY_REGRESSION_THRESHOLD,
) -> list[QualityRegression]:
    """检测质量下降：对比当前版本与基线版本的 per-field accuracy。

    验收要求："可定位质量下降的字段和版本"。
    当前版本某字段 accuracy 低于基线版本 accuracy 超过阈值时标记 is_regression=True。

    按 (source, model, field_name) 对齐，schema_version 作为版本标识。
    """
    baseline_metrics = _compute_per_field_accuracy(baseline_records)
    current_metrics = _compute_per_field_accuracy(current_records)

    regressions: list[QualityRegression] = []
    # 遍历当前版本所有 (source, model, field_name) 组合
    seen_keys: set[tuple[str, str, str]] = set()
    for (b_source, b_model, b_schema, b_field), b_acc in baseline_metrics.items():
        align_key = (b_source, b_model, b_field)
        if align_key in seen_keys:
            continue
        seen_keys.add(align_key)
        # 找当前版本同 (source, model, field_name) 的指标
        for (c_source, c_model, c_schema, c_field), c_acc in current_metrics.items():
            if c_source == b_source and c_model == b_model and c_field == b_field:
                drop = b_acc - c_acc
                # 用容差避免浮点精度误判（如 0.8-0.7=0.1000...09 不应 > 0.10）
                is_reg = drop > threshold + 1e-9
                # 仅当版本不同或确实下降时记录（版本相同时无意义）
                if c_schema != b_schema or is_reg:
                    regressions.append(QualityRegression(
                        field_name=b_field,
                        source=b_source,
                        model=b_model,
                        baseline_schema_version=b_schema,
                        current_schema_version=c_schema,
                        baseline_accuracy=b_acc,
                        current_accuracy=c_acc,
                        drop_amount=drop,
                        is_regression=is_reg,
                    ))
                break

    # 也检查当前版本有但基线无的新字段（无基线不算下降）
    # 按 drop_amount 降序排序，is_regression 优先
    regressions.sort(key=lambda r: (-r.drop_amount, r.field_name))
    return regressions


def _compute_per_field_accuracy(
    records: list[FieldCorrectionRecord],
) -> dict[tuple[str, str, str, str], float]:
    """计算每 (source, model, schema_version, field_name) 的准确率。"""
    groups: dict[tuple[str, str, str, str], list[FieldCorrectionRecord]] = {}
    for r in records:
        key = (r.source, r.model, r.schema_version, r.field_name)
        groups.setdefault(key, []).append(r)
    result: dict[tuple[str, str, str, str], float] = {}
    for key, group in groups.items():
        total = len(group)
        corrected = sum(1 for r in group if r.adopted)
        accuracy = 1.0 - (corrected / total if total > 0 else 0.0)
        result[key] = accuracy
    return result


# ---- 质量下降是否阻止建单（可选，默认不阻止，仅告警）----

def should_warn_quality_regression(
    snapshot: QualityMetricsSnapshot,
) -> tuple[bool, list[str]]:
    """检查质量下降是否需要告警（不阻止建单，仅返回告警信息）。

    Returns:
        (has_warning, warning_messages)
    """
    warnings: list[str] = []
    for r in snapshot.regressions:
        if r.is_regression:
            warnings.append(
                f'字段 {r.field_name}（来源 {r.source}，模型 {r.model}）'
                f'准确率从 {r.baseline_schema_version} 版本的 '
                f'{r.baseline_accuracy:.2%} 下降到 {r.current_schema_version} 版本的 '
                f'{r.current_accuracy:.2%}（下降 {r.drop_amount:.2%}），'
                f'请检查该字段的提示词或 Schema 变更。'
            )
    return len(warnings) > 0, warnings

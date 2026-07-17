"""AI-R05：视觉/OCR Provider 评测框架。

# AI_TASK: AI-R05

设计目标（验收：达到质量门槛后才允许试点；记录模型/提示词/Schema/耗时/错误率/调用量）：

- 注入式记录，不真调外部 API：
  生产环境（有 API Key）由调用方注入 EvaluationRecord；CI 用 mock 记录验证框架。
  这避免在日志/CI 中泄露密钥，符合 AI-R05"日志不得泄露密钥"硬性约束。

- 质量门槛（QualityGate）：定义 min_header_accuracy / min_line_recall /
  max_error_rate 等阈值；is_passed 判定是否达到试点标准。

- 可复算聚合：aggregate 对一批 EvaluationRecord 计算调用量、错误率、
  各项准确率，支持按 provider/model/prompt_hash/schema_version 分组比对。

- 持久化：serialize_run 输出 JSON，避免新增 DB 迁移；落盘路径由调用方决定。

评测维度对齐 AI-R03 黄金样本指标：
header_accuracy / line_recall / material_match_accuracy / quantity_accuracy。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


# ---- Schema 版本 ----

SCHEMA_VERSION = 'document-extraction-v1'


def compute_prompt_hash(prompt: str) -> str:
    """计算提示词指纹，用于按提示词版本分组评测。"""
    return hashlib.sha256((prompt or '').encode('utf-8')).hexdigest()[:12]


def compute_schema_version() -> str:
    """返回当前文档提取 Schema 版本。"""
    return SCHEMA_VERSION


# ---- 数据结构 ----

@dataclass(frozen=True)
class EvaluationRecord:
    """单次评测记录（一个样本对一个 Provider 的结果）。

    不含 API Key、不含完整敏感原文；extracted_summary 仅存字段命中计数，
    不存原始图片或完整回复，符合"日志不得泄露完整敏感原文"约束。
    """

    sample_id: str
    provider_name: str
    model: str
    prompt_hash: str
    schema_version: str
    duration_ms: float
    error_type: str = ''                 # 空=成功；timeout/invalid_json/unavailable/other
    header_accuracy: float = 0.0         # 0~1
    line_recall: float = 0.0             # 0~1
    material_match_accuracy: float = 0.0  # 0~1
    quantity_accuracy: float = 0.0       # 0~1
    extracted_field_count: int = 0       # 提取出的字段数（不含敏感原文）
    created_at: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'sample_id': self.sample_id,
            'provider_name': self.provider_name,
            'model': self.model,
            'prompt_hash': self.prompt_hash,
            'schema_version': self.schema_version,
            'duration_ms': self.duration_ms,
            'error_type': self.error_type,
            'header_accuracy': self.header_accuracy,
            'line_recall': self.line_recall,
            'material_match_accuracy': self.material_match_accuracy,
            'quantity_accuracy': self.quantity_accuracy,
            'extracted_field_count': self.extracted_field_count,
            'created_at': self.created_at,
        }


@dataclass(frozen=True)
class AggregatedMetrics:
    """一批评测记录的聚合指标。"""

    provider_name: str
    model: str
    prompt_hash: str
    schema_version: str
    sample_count: int
    call_count: int                      # = sample_count（每样本一次调用）
    error_count: int
    error_rate: float                    # error_count / call_count
    success_count: int
    avg_duration_ms: float
    avg_header_accuracy: float           # 仅成功样本
    avg_line_recall: float
    avg_material_match_accuracy: float
    avg_quantity_accuracy: float

    def to_dict(self) -> dict[str, Any]:
        return {
            'provider_name': self.provider_name,
            'model': self.model,
            'prompt_hash': self.prompt_hash,
            'schema_version': self.schema_version,
            'sample_count': self.sample_count,
            'call_count': self.call_count,
            'error_count': self.error_count,
            'error_rate': round(self.error_rate, 4),
            'success_count': self.success_count,
            'avg_duration_ms': round(self.avg_duration_ms, 2),
            'avg_header_accuracy': round(self.avg_header_accuracy, 4),
            'avg_line_recall': round(self.avg_line_recall, 4),
            'avg_material_match_accuracy': round(self.avg_material_match_accuracy, 4),
            'avg_quantity_accuracy': round(self.avg_quantity_accuracy, 4),
        }


@dataclass(frozen=True)
class QualityGate:
    """质量门槛：达到后才允许试点。

    所有阈值均为"下限"（error_rate 为上限）。任一不达标即 is_passed=False。
    """

    min_header_accuracy: float = 0.85
    min_line_recall: float = 0.80
    min_material_match_accuracy: float = 0.80
    min_quantity_accuracy: float = 0.80
    max_error_rate: float = 0.10
    min_sample_count: int = 20           # 样本数不足不判达标（统计意义）

    def is_passed(self, metrics: AggregatedMetrics) -> tuple[bool, list[str]]:
        """判定聚合指标是否达到试点门槛。

        Returns:
            (是否达标, 未达标原因列表)
        """
        failures: list[str] = []
        if metrics.sample_count < self.min_sample_count:
            failures.append(
                f'样本数 {metrics.sample_count} 不足 {self.min_sample_count}，无统计意义'
            )
        if metrics.error_rate > self.max_error_rate:
            failures.append(
                f'错误率 {metrics.error_rate:.2%} 超过上限 {self.max_error_rate:.2%}'
            )
        if metrics.avg_header_accuracy < self.min_header_accuracy:
            failures.append(
                f'表头准确率 {metrics.avg_header_accuracy:.2%} 低于下限 {self.min_header_accuracy:.2%}'
            )
        if metrics.avg_line_recall < self.min_line_recall:
            failures.append(
                f'行召回率 {metrics.avg_line_recall:.2%} 低于下限 {self.min_line_recall:.2%}'
            )
        if metrics.avg_material_match_accuracy < self.min_material_match_accuracy:
            failures.append(
                f'物料匹配率 {metrics.avg_material_match_accuracy:.2%} 低于下限 '
                f'{self.min_material_match_accuracy:.2%}'
            )
        if metrics.avg_quantity_accuracy < self.min_quantity_accuracy:
            failures.append(
                f'数量准确率 {metrics.avg_quantity_accuracy:.2%} 低于下限 '
                f'{self.min_quantity_accuracy:.2%}'
            )
        return (len(failures) == 0, failures)


@dataclass(frozen=True)
class EvaluationRun:
    """一次完整评测运行（可序列化持久化）。"""

    run_id: str
    created_at: str
    provider_name: str
    model: str
    prompt_hash: str
    schema_version: str
    records: tuple[EvaluationRecord, ...]
    aggregated: AggregatedMetrics
    gate: QualityGate
    gate_passed: bool
    gate_failures: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            'run_id': self.run_id,
            'created_at': self.created_at,
            'provider_name': self.provider_name,
            'model': self.model,
            'prompt_hash': self.prompt_hash,
            'schema_version': self.schema_version,
            'records': [r.to_dict() for r in self.records],
            'aggregated': self.aggregated.to_dict(),
            'gate': {
                'min_header_accuracy': self.gate.min_header_accuracy,
                'min_line_recall': self.gate.min_line_recall,
                'min_material_match_accuracy': self.gate.min_material_match_accuracy,
                'min_quantity_accuracy': self.gate.min_quantity_accuracy,
                'max_error_rate': self.gate.max_error_rate,
                'min_sample_count': self.gate.min_sample_count,
            },
            'gate_passed': self.gate_passed,
            'gate_failures': list(self.gate_failures),
        }

    def to_json(self) -> str:
        """序列化为 JSON 字符串（落盘持久化，避免新增 DB 迁移）。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ---- 评测器 ----

class ProviderEvaluator:
    """Provider 评测器：聚合记录、判定门槛、生成可持久化运行结果。

    不调用外部 API。记录由调用方注入（生产环境注入真实结果，CI 注入 mock）。
    """

    def __init__(self, gate: Optional[QualityGate] = None) -> None:
        self.gate = gate or QualityGate()

    def aggregate(self, records: list[EvaluationRecord]) -> Optional[AggregatedMetrics]:
        """聚合一批记录为指标。空列表返回 None。"""
        if not records:
            return None
        first = records[0]
        call_count = len(records)
        error_count = sum(1 for r in records if r.error_type)
        success = [r for r in records if not r.error_type]
        success_count = len(success)

        def _avg(items: list[EvaluationRecord], attr: str) -> float:
            if not items:
                return 0.0
            return sum(getattr(r, attr) for r in items) / len(items)

        return AggregatedMetrics(
            provider_name=first.provider_name,
            model=first.model,
            prompt_hash=first.prompt_hash,
            schema_version=first.schema_version,
            sample_count=call_count,
            call_count=call_count,
            error_count=error_count,
            error_rate=error_count / call_count if call_count else 0.0,
            success_count=success_count,
            avg_duration_ms=_avg(records, 'duration_ms'),
            avg_header_accuracy=_avg(success, 'header_accuracy'),
            avg_line_recall=_avg(success, 'line_recall'),
            avg_material_match_accuracy=_avg(success, 'material_match_accuracy'),
            avg_quantity_accuracy=_avg(success, 'quantity_accuracy'),
        )

    def evaluate_run(
        self,
        records: list[EvaluationRecord],
        run_id: Optional[str] = None,
    ) -> Optional[EvaluationRun]:
        """对一批记录执行完整评测：聚合 + 门槛判定 + 生成可持久化运行。

        records 必须来自同一 provider/model/prompt_hash/schema_version（自动取首条）。
        """
        if not records:
            return None
        metrics = self.aggregate(records)
        if metrics is None:
            return None
        passed, failures = self.gate.is_passed(metrics)
        # 校验记录同质性（防混入不同 provider 的记录导致聚合失真）
        first = records[0]
        for r in records[1:]:
            if (r.provider_name != first.provider_name
                    or r.model != first.model
                    or r.prompt_hash != first.prompt_hash
                    or r.schema_version != first.schema_version):
                raise ValueError(
                    f'评测记录必须同质：期望 provider={first.provider_name}/'
                    f'model={first.model}/prompt={first.prompt_hash}/'
                    f'schema={first.schema_version}，实际 provider={r.provider_name}/'
                    f'model={r.model}/prompt={r.prompt_hash}/schema={r.schema_version}'
                )
        return EvaluationRun(
            run_id=run_id or _gen_run_id(first),
            created_at=datetime.now(timezone.utc).isoformat(),
            provider_name=first.provider_name,
            model=first.model,
            prompt_hash=first.prompt_hash,
            schema_version=first.schema_version,
            records=tuple(records),
            aggregated=metrics,
            gate=self.gate,
            gate_passed=passed,
            gate_failures=tuple(failures),
        )


def _gen_run_id(first: EvaluationRecord) -> str:
    """生成运行 ID：provider-model-prompt-timestamp 短指纹。"""
    payload = f'{first.provider_name}|{first.model}|{first.prompt_hash}|{first.schema_version}'
    short = hashlib.sha256(payload.encode('utf-8')).hexdigest()[:8]
    return f'eval-{short}'


def make_record(
    *,
    sample_id: str,
    provider_name: str,
    model: str,
    prompt: str,
    duration_ms: float,
    error_type: str = '',
    header_accuracy: float = 0.0,
    line_recall: float = 0.0,
    material_match_accuracy: float = 0.0,
    quantity_accuracy: float = 0.0,
    extracted_field_count: int = 0,
    schema_version: Optional[str] = None,
    created_at: str = '',
) -> EvaluationRecord:
    """便捷构造 EvaluationRecord（自动算 prompt_hash/schema_version）。"""
    return EvaluationRecord(
        sample_id=sample_id,
        provider_name=provider_name,
        model=model,
        prompt_hash=compute_prompt_hash(prompt),
        schema_version=schema_version or compute_schema_version(),
        duration_ms=duration_ms,
        error_type=error_type,
        header_accuracy=header_accuracy,
        line_recall=line_recall,
        material_match_accuracy=material_match_accuracy,
        quantity_accuracy=quantity_accuracy,
        extracted_field_count=extracted_field_count,
        created_at=created_at or datetime.now(timezone.utc).isoformat(),
    )

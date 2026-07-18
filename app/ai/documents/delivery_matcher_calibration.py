"""AI-R06-F01：送货通知匹配权重校准与错误样本回灌。

# AI_TASK: AI-R06-F01

设计目标（验收：权重可动态调整；错误样本可收集并回灌；多候选不自动选单；
误建采购申请为 0）：

- 权重可配置：MatcherWeights 替代硬编码常量，支持从配置源（JSON/DB/注入）
  加载。默认值与 delivery_matcher 模块常量一致，保证向后兼容。

- 错误样本收集：当人工修正了自动匹配结果（选择了非 auto_selected 的候选、
  或从候选清单中手动指定了不同订单），记录 MatchErrorSample 含输入摘要、
  系统选择、人工选择、修正原因。

- 权重校准：calibrate_weights 基于错误样本分析各维度误判分布，输出建议权重
  （不直接修改运行时权重，需管理员确认后注入）。校准算法：统计每个维度
  在错误样本中的"贡献缺失"频率，降低高频误判维度权重，提升低频维度权重。

- 纯逻辑 + 依赖注入：不依赖 Flask/ORM，save_error_sample 回调由调用方注入。
  CI 无 DB 时用 mock 测试，生产环境由 app.py 提供 ORM adapter。

- 安全约束：校准不改变多候选不自动选单规则、不改变误建采购申请防护。
  仅调整评分权重和自动选单阈值。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional


# ---- 默认权重（与 delivery_matcher 模块常量一致）----

DEFAULT_WEIGHT_ORDER_NO = 0.25
DEFAULT_WEIGHT_SUPPLIER = 0.40
DEFAULT_WEIGHT_MATERIAL = 0.30
DEFAULT_WEIGHT_DATE = 0.05
DEFAULT_AUTO_SELECT_THRESHOLD = 0.70

# 校准安全边界：权重调整幅度不得超过此值（防止单次校准剧烈波动）
MAX_WEIGHT_DELTA_PER_CALIBRATION = 0.10

# 最小错误样本数：低于此数不执行校准（样本不足）
MIN_ERROR_SAMPLES_FOR_CALIBRATION = 5

# 权重最小值：任何维度权重不得低于此值（防止完全忽略某维度）
MIN_WEIGHT_VALUE = 0.05


# ---- 数据结构 ----

@dataclass(frozen=True)
class MatcherWeights:
    """匹配评分权重配置。

    权重和必须 = 1.0。各维度含义：
    - order_no: 订单号精确匹配
    - supplier: 供应商名称匹配
    - material: 物料匹配（行覆盖率）
    - date: 日期接近度
    - auto_select_threshold: 自动选单置信度门槛
    """

    order_no: float = DEFAULT_WEIGHT_ORDER_NO
    supplier: float = DEFAULT_WEIGHT_SUPPLIER
    material: float = DEFAULT_WEIGHT_MATERIAL
    date: float = DEFAULT_WEIGHT_DATE
    auto_select_threshold: float = DEFAULT_AUTO_SELECT_THRESHOLD

    def __post_init__(self) -> None:
        # 使用 object.__setattr__ 因为 frozen=True
        total = self.order_no + self.supplier + self.material + self.date
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f'权重和必须为 1.0，实际为 {total:.4f} '
                f'(order_no={self.order_no}, supplier={self.supplier}, '
                f'material={self.material}, date={self.date})'
            )
        if self.auto_select_threshold <= 0 or self.auto_select_threshold > 1.0:
            raise ValueError(
                f'自动选单阈值必须在 (0, 1.0] 范围，实际为 {self.auto_select_threshold}'
            )
        for name in ('order_no', 'supplier', 'material', 'date'):
            val = getattr(self, name)
            if val < MIN_WEIGHT_VALUE:
                raise ValueError(
                    f'维度 {name} 权重 {val} 低于最小值 {MIN_WEIGHT_VALUE}'
                )

    def to_dict(self) -> dict[str, float]:
        return {
            'order_no': self.order_no,
            'supplier': self.supplier,
            'material': self.material,
            'date': self.date,
            'auto_select_threshold': self.auto_select_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MatcherWeights:
        return cls(
            order_no=float(data.get('order_no', DEFAULT_WEIGHT_ORDER_NO)),
            supplier=float(data.get('supplier', DEFAULT_WEIGHT_SUPPLIER)),
            material=float(data.get('material', DEFAULT_WEIGHT_MATERIAL)),
            date=float(data.get('date', DEFAULT_WEIGHT_DATE)),
            auto_select_threshold=float(
                data.get('auto_select_threshold', DEFAULT_AUTO_SELECT_THRESHOLD)
            ),
        )

    @classmethod
    def from_json(cls, json_str: str) -> MatcherWeights:
        """从 JSON 字符串加载权重。"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def to_json(self) -> str:
        """序列化为 JSON 字符串。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ---- 错误样本 ----

@dataclass(frozen=True)
class MatchErrorSample:
    """匹配错误样本（人工修正记录）。

    当人工选择了与系统 auto_selected 不同的候选，或从候选清单中手动指定了
    不同订单时，记录此样本用于后续权重校准。

    - sample_id: 唯一标识
    - created_at: 记录时间
    - delivery_summary: 送货通知输入摘要（脱敏）
    - system_selected_order_id: 系统自动选中的订单 ID（None=系统未自动选）
    - system_best_order_id: 系统最高分候选订单 ID（None=无候选）
    - human_selected_order_id: 人工最终选择的订单 ID
    - correction_reason: 人工修正原因（如 '供应商名称别名未识别'）
    - score_breakdown: 系统选中候选的各维度评分
    - weights_version: 匹配时使用的权重版本/指纹
    """

    sample_id: str
    created_at: str                     # ISO 8601
    delivery_summary: dict[str, Any]
    system_selected_order_id: Optional[int]
    system_best_order_id: Optional[int]
    human_selected_order_id: int
    correction_reason: str = ''
    score_breakdown: dict[str, float] = field(default_factory=dict)
    weights_version: str = 'default'

    def to_dict(self) -> dict[str, Any]:
        return {
            'sample_id': self.sample_id,
            'created_at': self.created_at,
            'delivery_summary': dict(self.delivery_summary),
            'system_selected_order_id': self.system_selected_order_id,
            'system_best_order_id': self.system_best_order_id,
            'human_selected_order_id': self.human_selected_order_id,
            'correction_reason': self.correction_reason,
            'score_breakdown': dict(self.score_breakdown),
            'weights_version': self.weights_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MatchErrorSample:
        return cls(
            sample_id=str(data['sample_id']),
            created_at=str(data.get('created_at', datetime.utcnow().isoformat())),
            delivery_summary=dict(data.get('delivery_summary', {})),
            system_selected_order_id=data.get('system_selected_order_id'),
            system_best_order_id=data.get('system_best_order_id'),
            human_selected_order_id=int(data['human_selected_order_id']),
            correction_reason=str(data.get('correction_reason', '')),
            score_breakdown=dict(data.get('score_breakdown', {})),
            weights_version=str(data.get('weights_version', 'default')),
        )


@dataclass(frozen=True)
class CalibrationResult:
    """权重校准结果。

    - suggested_weights: 建议的新权重（需管理员确认后注入）
    - current_weights: 当前权重
    - error_sample_count: 参与校准的错误样本数
    - dimension_error_rates: 各维度在错误样本中的误判率
    - calibration_notes: 校准说明（中文）
    - is_safe: 校准结果是否在安全边界内（所有维度调整幅度 <= MAX_WEIGHT_DELTA）
    """

    suggested_weights: MatcherWeights
    current_weights: MatcherWeights
    error_sample_count: int
    dimension_error_rates: dict[str, float]
    calibration_notes: str
    is_safe: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            'suggested_weights': self.suggested_weights.to_dict(),
            'current_weights': self.current_weights.to_dict(),
            'error_sample_count': self.error_sample_count,
            'dimension_error_rates': dict(self.dimension_error_rates),
            'calibration_notes': self.calibration_notes,
            'is_safe': self.is_safe,
        }


# ---- 回调签名 ----

# save_error_sample 回调：(sample: MatchErrorSample) -> None
# 生产环境由 app.py 提供 ORM adapter 写入数据库
SaveErrorSampleFn = Callable[[MatchErrorSample], None]

# load_error_samples 回调：() -> list[MatchErrorSample]
# 返回所有可用于校准的错误样本
LoadErrorSamplesFn = Callable[[], list[MatchErrorSample]]

# load_weights 回调：() -> MatcherWeights
# 从配置源加载当前权重
LoadWeightsFn = Callable[[], MatcherWeights]


# ---- 错误样本收集 ----

def collect_error_sample(
    *,
    sample_id: str,
    delivery_summary: dict[str, Any],
    system_selected_order_id: Optional[int],
    system_best_order_id: Optional[int],
    human_selected_order_id: int,
    correction_reason: str = '',
    score_breakdown: dict[str, float] | None = None,
    weights_version: str = 'default',
    save_callback: Optional[SaveErrorSampleFn] = None,
) -> MatchErrorSample:
    """收集一条匹配错误样本。

    当人工修正了自动匹配结果时调用。样本经 save_callback 持久化。

    Args:
        sample_id: 唯一标识
        delivery_summary: 送货通知输入摘要（脱敏后）
        system_selected_order_id: 系统自动选中的订单 ID
        system_best_order_id: 系统最高分候选订单 ID
        human_selected_order_id: 人工最终选择的订单 ID
        correction_reason: 人工修正原因
        score_breakdown: 系统选中候选的各维度评分
        weights_version: 匹配时使用的权重版本
        save_callback: 持久化回调（注入）

    Returns:
        MatchErrorSample：构造的样本记录
    """
    sample = MatchErrorSample(
        sample_id=sample_id,
        created_at=datetime.utcnow().isoformat(),
        delivery_summary=delivery_summary,
        system_selected_order_id=system_selected_order_id,
        system_best_order_id=system_best_order_id,
        human_selected_order_id=human_selected_order_id,
        correction_reason=correction_reason,
        score_breakdown=score_breakdown or {},
        weights_version=weights_version,
    )

    if save_callback is not None:
        save_callback(sample)

    return sample


# ---- 权重校准 ----

def calibrate_weights(
    *,
    current_weights: MatcherWeights,
    error_samples: list[MatchErrorSample],
    max_delta: float = MAX_WEIGHT_DELTA_PER_CALIBRATION,
    min_samples: int = MIN_ERROR_SAMPLES_FOR_CALIBRATION,
) -> CalibrationResult:
    """基于错误样本校准匹配权重。

    校准算法：
    1. 统计每个维度在错误样本中的"贡献缺失"频率：
       - 系统选中了候选但人工选了另一个 → 检查系统选中候选的各维度评分
       - 若某维度在系统选中候选中评分高（>0.5）但人工不认可 → 该维度"误判"
       - 若某维度在系统选中候选中评分低（<=0.5）但人工认可的目标该维度应高
         → 该维度"贡献不足"
    2. 计算各维度误判率 = 误判次数 / 样本数
    3. 降低高误判率维度权重，提升低误判率维度权重
    4. 调整幅度限制在 max_delta 内，保证权重和 = 1.0

    安全约束：
    - 样本数 < min_samples 时不校准
    - 单维度调整幅度 <= max_delta
    - 不改变多候选不自动选单规则
    - 不改变误建采购申请防护

    Args:
        current_weights: 当前权重
        error_samples: 错误样本列表
        max_delta: 单维度最大调整幅度
        min_samples: 最小样本数

    Returns:
        CalibrationResult：含建议权重、误判率、安全标记
    """
    dimensions = ('order_no', 'supplier', 'material', 'date')

    # 样本不足
    if len(error_samples) < min_samples:
        return CalibrationResult(
            suggested_weights=current_weights,
            current_weights=current_weights,
            error_sample_count=len(error_samples),
            dimension_error_rates={d: 0.0 for d in dimensions},
            calibration_notes=f'错误样本数 {len(error_samples)} 不足最小要求 {min_samples}，未执行校准',
            is_safe=True,
        )

    # 统计各维度误判次数
    dimension_misjudge_count = {d: 0 for d in dimensions}
    total_effective = 0

    for sample in error_samples:
        if not sample.score_breakdown:
            continue
        total_effective += 1

        # 系统选中候选 vs 人工选择不同 → 分析维度贡献
        system_selected = sample.system_selected_order_id
        human_selected = sample.human_selected_order_id

        if system_selected is not None and system_selected != human_selected:
            # 系统选错了：检查系统选中候选的各维度评分
            for dim in dimensions:
                dim_score = sample.score_breakdown.get(dim, 0.0)
                # 若该维度评分高（>0.5）但系统仍选错 → 该维度权重过高导致误判
                if dim_score > 0.5:
                    dimension_misjudge_count[dim] += 1

    # 计算误判率
    dimension_error_rates = {
        dim: (dimension_misjudge_count[dim] / total_effective)
        if total_effective > 0 else 0.0
        for dim in dimensions
    }

    # 调整权重：降低高误判率维度，提升低误判率维度
    current_vals = {dim: getattr(current_weights, dim) for dim in dimensions}
    suggested_vals = dict(current_vals)

    # 平均误判率
    avg_error_rate = (
        sum(dimension_error_rates.values()) / len(dimensions)
        if dimensions else 0.0
    )

    # 计算原始调整量（带方向：正=提升，负=降低）
    raw_deltas: dict[str, float] = {}
    for dim in dimensions:
        error_rate = dimension_error_rates[dim]
        if error_rate > avg_error_rate + 0.1:
            # 高误判率：降低权重
            raw_deltas[dim] = -(error_rate - avg_error_rate) * 0.5
        elif error_rate < avg_error_rate - 0.1:
            # 低误判率：提升权重
            raw_deltas[dim] = (avg_error_rate - error_rate) * 0.5
        else:
            raw_deltas[dim] = 0.0

    # 限制单维度调整幅度在 max_delta 内
    clamped_deltas = {dim: max(-max_delta, min(max_delta, d)) for dim, d in raw_deltas.items()}

    # 应用调整
    for dim in dimensions:
        suggested_vals[dim] = current_vals[dim] + clamped_deltas[dim]

    # 确保不低于最小值
    for dim in dimensions:
        suggested_vals[dim] = max(MIN_WEIGHT_VALUE, suggested_vals[dim])

    # 归一化：确保权重和 = 1.0，同时保持调整幅度约束
    total = sum(suggested_vals.values())
    if total > 0 and abs(total - 1.0) > 0.001:
        # 按比例缩放，但检查缩放后的 delta 是否超限
        scale = 1.0 / total
        for dim in dimensions:
            scaled_val = suggested_vals[dim] * scale
            delta = abs(scaled_val - current_vals[dim])
            if delta > max_delta:
                # 缩放后超限，改用截断方式归一化
                # 将超出部分按比例分配给其他维度
                suggested_vals[dim] = current_vals[dim] + (
                    max_delta if scaled_val > current_vals[dim] else -max_delta
                )
                # 重新计算剩余需要分配的量
                remaining = 1.0 - sum(suggested_vals.values())
                other_dims = [d for d in dimensions if d != dim]
                if other_dims and abs(remaining) > 0.001:
                    per_other = remaining / len(other_dims)
                    for od in other_dims:
                        new_val = suggested_vals[od] + per_other
                        od_delta = abs(new_val - current_vals[od])
                        if od_delta > max_delta:
                            suggested_vals[od] = current_vals[od] + (
                                max_delta if new_val > current_vals[od] else -max_delta
                            )
                        else:
                            suggested_vals[od] = new_val
                break
            else:
                suggested_vals[dim] = scaled_val

    # 最终确保权重和精确为 1.0（微调最大维度）
    total = sum(suggested_vals.values())
    if abs(total - 1.0) > 0.0001:
        # 找调整幅度最小的维度进行微调
        min_delta_dim = min(dimensions, key=lambda d: abs(suggested_vals[d] - current_vals[d]))
        suggested_vals[min_delta_dim] += 1.0 - total

    # 检查安全边界
    is_safe = True
    for dim in dimensions:
        delta = abs(suggested_vals[dim] - current_vals[dim])
        if delta > max_delta + 0.001:  # 容差
            is_safe = False
            break

    suggested_weights = MatcherWeights(
        order_no=suggested_vals['order_no'],
        supplier=suggested_vals['supplier'],
        material=suggested_vals['material'],
        date=suggested_vals['date'],
        auto_select_threshold=current_weights.auto_select_threshold,
    )

    notes_parts = [
        f'基于 {len(error_samples)} 条错误样本校准',
        f'（有效样本 {total_effective} 条）',
    ]
    for dim in dimensions:
        old_val = current_vals[dim]
        new_val = suggested_vals[dim]
        if abs(new_val - old_val) > 0.001:
            direction = '↑' if new_val > old_val else '↓'
            notes_parts.append(
                f'{dim}: {old_val:.3f}→{new_val:.3f} ({direction}{abs(new_val-old_val):.3f})'
            )

    return CalibrationResult(
        suggested_weights=suggested_weights,
        current_weights=current_weights,
        error_sample_count=len(error_samples),
        dimension_error_rates=dimension_error_rates,
        calibration_notes='；'.join(notes_parts),
        is_safe=is_safe,
    )


# ---- 权重加载 ----

def load_weights_from_config(
    load_callback: Optional[LoadWeightsFn] = None,
    *,
    default_weights: Optional[MatcherWeights] = None,
) -> MatcherWeights:
    """从配置源加载权重。

    若 load_callback 提供，使用回调加载（生产环境从 DB/配置文件加载）。
    否则使用 default_weights 或默认权重。

    Args:
        load_callback: 加载回调（注入）
        default_weights: 默认权重（覆盖模块默认值）

    Returns:
        MatcherWeights：加载的权重配置
    """
    if load_callback is not None:
        return load_callback()
    return default_weights or MatcherWeights()


def weights_fingerprint(weights: MatcherWeights) -> str:
    """计算权重指纹（用于审计和版本追踪）。

    Returns:
        权重指纹字符串，如 'w-0.25-0.40-0.30-0.05-t0.70'
    """
    return (
        f'w-{weights.order_no:.2f}-{weights.supplier:.2f}'
        f'-{weights.material:.2f}-{weights.date:.2f}'
        f'-t{weights.auto_select_threshold:.2f}'
    )

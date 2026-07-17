"""AI-R03 黄金样本库验证脚本。
# AI_TASK: AI-R03

校验 samples/ai_documents/ 下黄金样本库的完整性与覆盖度，并验证评估指标可计算。

检查项：
1. Schema 校验：所有样本符合 golden_samples.GoldenSample 结构（硬要求）
2. 场景覆盖率：9 大必备场景 100% 覆盖（硬要求）
3. 来源类别覆盖率：5 大必备来源 100% 覆盖（硬要求）
4. 图片介质样本的 image_path 文件实际存在（硬要求）
5. 评估指标可计算：evaluate_document_samples 对样本返回有效指标（硬要求）
6. 脱敏标记：所有样本 desensitization_applied=True（硬要求）
7. 样本数量门槛：≥ MIN_SAMPLE_COUNT（100）
   - 默认渐进式：未达标警告但不失败
   - AI_GOLDEN_SAMPLE_ENFORCE=strict 时强制失败

退出码 0=通过，1=失败。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
SAMPLE_DIR = ROOT / 'samples' / 'ai_documents'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ai.documents.golden_samples import (  # noqa: E402
    MIN_SAMPLE_COUNT,
    REQUIRED_SCENARIOS,
    REQUIRED_SOURCE_CATEGORIES,
    compute_scenario_coverage,
    compute_source_category_coverage,
    load_sample_dir,
)
from ai.documents.evaluation import evaluate_document_samples  # noqa: E402


def main() -> int:
    if not SAMPLE_DIR.exists():
        print(f'FAIL AI-GOLDEN-SAMPLES: 样本目录不存在 {SAMPLE_DIR}')
        return 1

    load_result = load_sample_dir(SAMPLE_DIR)
    samples = load_result.samples
    issues = load_result.issues

    failures: list[str] = []
    warnings: list[str] = []

    # 1. Schema 校验
    if issues:
        for issue in issues:
            failures.append(f'Schema 校验失败: {issue}')

    # 2. 场景覆盖率（硬要求 100%）
    covered_scenarios, missing_scenarios = compute_scenario_coverage(samples)
    if missing_scenarios:
        failures.append(
            f'场景覆盖率 {len(covered_scenarios)}/{len(REQUIRED_SCENARIOS)}：'
            f'缺失必备场景 {sorted(missing_scenarios)}'
        )

    # 3. 来源类别覆盖率（硬要求 100%）
    covered_src, missing_src = compute_source_category_coverage(samples)
    if missing_src:
        failures.append(
            f'来源类别覆盖率 {len(covered_src)}/{len(REQUIRED_SOURCE_CATEGORIES)}：'
            f'缺失必备来源 {sorted(missing_src)}'
        )

    # 4. 图片介质样本 image_path 文件存在
    for sample in samples:
        if not sample.image_path:
            continue
        image_abs = SAMPLE_DIR / sample.image_path
        if not image_abs.exists():
            failures.append(
                f'{sample.sample_id}: image_path={sample.image_path} 指向的文件不存在'
            )

    # 5. 评估指标可计算（用样本自身 expected 作为 actual，验证指标函数可运行）
    eval_input = []
    for sample in samples:
        sample_dict = sample.to_dict()
        # 用 expected 作为 actual，模拟完美识别，验证评估函数可运行
        sample_dict['actual'] = sample.expected
        eval_input.append(sample_dict)
    try:
        result = evaluate_document_samples(eval_input)
    except Exception as exc:  # noqa: BLE001
        failures.append(f'评估指标计算失败: {exc}')
        result = None

    # 6. 脱敏标记
    undesisitized = [s.sample_id for s in samples if not s.desensitization_applied]
    if undesisitized:
        failures.append(
            f'未脱敏样本 {len(undesisitized)} 份: {undesisitized[:5]}...'
        )

    # 7. 样本数量门槛（渐进式）
    if len(samples) < MIN_SAMPLE_COUNT:
        msg = (
            f'样本数量 {len(samples)} < 门槛 {MIN_SAMPLE_COUNT}，'
            f'需补充真实脱敏样本至 {MIN_SAMPLE_COUNT} 份'
        )
        if os.environ.get('AI_GOLDEN_SAMPLE_ENFORCE') == 'strict':
            failures.append(msg)
        else:
            warnings.append(msg)

    # 输出
    print(f'AI-R03 黄金样本库验证: 样本数={len(samples)}')
    print(f'  场景覆盖: {len(covered_scenarios)}/{len(REQUIRED_SCENARIOS)} '
          f'(missing={sorted(missing_scenarios) if missing_scenarios else "无"})')
    print(f'  来源覆盖: {len(covered_src)}/{len(REQUIRED_SOURCE_CATEGORIES)} '
          f'(missing={sorted(missing_src) if missing_src else "无"})')
    if result is not None:
        print(f'  表头准确率: {result.header_accuracy}')
        print(f'  行召回率: {result.line_recall}')
        print(f'  物料匹配率: {result.material_match_accuracy}')
        print(f'  数量准确率: {result.quantity_accuracy}')
        print(f'  场景覆盖率指标: {result.scenario_coverage}')
        print(f'  来源覆盖率指标: {result.source_category_coverage}')

    if warnings:
        print('警告（渐进式，不阻塞）:')
        for w in warnings:
            print(f'  - {w}')

    if failures:
        print('FAIL AI-GOLDEN-SAMPLES:')
        for f in failures:
            print(f'  - {f}')
        return 1

    enforce_note = ' (strict)' if os.environ.get('AI_GOLDEN_SAMPLE_ENFORCE') == 'strict' else ' (progressive)'
    print(f'PASS AI-GOLDEN-SAMPLES: {len(samples)} 份样本，场景/来源全覆盖，'
          f'评估指标可计算，脱敏标记完整{enforce_note}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""AI-R03 黄金样本 Schema 与加载校验。
# AI_TASK: AI-R03

定义真实中文文档黄金样本库的统一结构、来源类别、场景标签和加载校验逻辑。
黄金样本用于衡量文档识别质量（表头准确率、行召回率、物料匹配率、数量准确率、场景覆盖率）。

设计要点：
- 样本 JSON 同时承载期望结果（expected）和元数据（来源类别、场景标签、脱敏标记、授权）。
- 与 schemas.py 的 DocumentExtraction 解耦：黄金样本是测试数据契约，DocumentExtraction 是运行时提取结果。
- 旧样本（仅有 expected/actual 两段）通过 upgrade_legacy_sample 自动升级为新 Schema。
- 验收门槛：MIN_SAMPLE_COUNT=100、9 大场景全覆盖、5 大来源类别全覆盖。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = '1.0'
SAMPLE_VERSION = '1.0'

# 首批目标样本数（验收门槛）
MIN_SAMPLE_COUNT = 100

# 必须覆盖的场景标签（验收门槛）
REQUIRED_SCENARIOS: frozenset[str] = frozenset({
    'normal',        # 正常清晰
    'blurry',        # 模糊
    'tilted',        # 倾斜
    'shadow',        # 阴影
    'handwritten',   # 手写
    'multipage',     # 多页
    'merged_cell',   # 合并单元格
    'duplicate',     # 重复行
    'unit_mixed',    # 单位混用
})

# 必须覆盖的来源类别（验收门槛）
REQUIRED_SOURCE_CATEGORIES: frozenset[str] = frozenset({
    'photo',             # 送货单照片
    'scanned',           # 扫描件
    'wechat_screenshot', # 微信截图
    'wechat_text',       # 微信文字
    'excel',             # Excel 表格
})

# 合法的场景标签全集（超出 REQUIRED 也允许，用于扩展）
ALL_SCENARIO_TAGS: frozenset[str] = REQUIRED_SCENARIOS | frozenset({
    'low_light',      # 低光
    'folded',         # 折痕
    'stamp_overlap',  # 印章遮挡
    'partial_match',  # 部分匹配
    'multi_supplier', # 多供应商合并
})

# 合法的来源类别全集
ALL_SOURCE_CATEGORIES: frozenset[str] = REQUIRED_SOURCE_CATEGORIES | frozenset({
    'pdf',   # PDF（扩展用）
    'email', # 邮件（扩展用）
})

# 合法的期望草稿类型（与 AI_TOOL_REGISTRY 草稿工具对齐）
VALID_DRAFT_TYPES: frozenset[str] = frozenset({
    'in_order_draft',
    'purchase_receive_draft',
    'out_order_draft',
    'sales_out_draft',
    # 新增（AI-SALES-F01-FIX-02）：拆分 sales_out_draft
    'after_sale_out_draft',
    'sales_outbound_draft',
    'transfer_draft',
    'check_draft',
    'adjustment_draft',
    'purchase_request_draft',
    'none',  # 无法生成草稿（识别失败用例）
})

# 合法的物料匹配方式（与 schemas.MatchMethod 对齐）
VALID_MATCH_METHODS: frozenset[str] = frozenset({
    'exact_code',
    'exact_name',
    'learned_alias',
    'single_fuzzy',
    'multiple',
    'none',
})

# 合法的期望文档类型（与 schemas.DocumentType 对齐）
VALID_DOCUMENT_TYPES: frozenset[str] = frozenset({
    'in_order',
    'out_order',
    'sales_out_order',
    'transfer',
    'check',
    'adjustment',
    'purchase_request',
    'other',
})

# 合法的使用授权类别
VALID_USAGE_CONSENT: frozenset[str] = frozenset({
    'synthetic',    # 合成数据（无真实个人信息）
    'authorized',   # 已获授权的真实脱敏数据
    'public',       # 公开样本
    'restricted',   # 仅内部测试，不得外传
})


@dataclass
class GoldenSample:
    """黄金样本结构。

    每份样本描述一份真实/合成中文单据文档及其期望识别结果。
    """
    sample_id: str                      # 唯一标识，如 GS-001
    source_category: str                # 来源类别（photo/scanned/wechat_screenshot/wechat_text/excel）
    scenario_tags: list[str]            # 场景标签（normal/blurry/...）
    expected: dict[str, Any]            # 期望识别结果（document_type/supplier/order_no/items）
    expected_draft_type: str = 'none'   # 期望草稿类型
    expected_material_matches: list[dict[str, Any]] = field(default_factory=list)
    description: str = ''
    sample_version: str = SAMPLE_VERSION
    schema_version: str = SCHEMA_VERSION
    usage_consent: str = 'synthetic'
    desensitization_applied: bool = True
    image_path: str = ''                # 图片介质相对路径（photo/scanned/wechat_screenshot）
    source_text: str = ''               # 文本介质原始内容（wechat_text/excel）
    actual: dict[str, Any] | None = None  # 可选：回归模式下模型实际识别结果

    def to_dict(self) -> dict[str, Any]:
        return {
            'sample_id': self.sample_id,
            'sample_version': self.sample_version,
            'schema_version': self.schema_version,
            'source_category': self.source_category,
            'scenario_tags': list(self.scenario_tags),
            'usage_consent': self.usage_consent,
            'desensitization_applied': self.desensitization_applied,
            'description': self.description,
            'image_path': self.image_path,
            'source_text': self.source_text,
            'expected': self.expected,
            'expected_draft_type': self.expected_draft_type,
            'expected_material_matches': list(self.expected_material_matches),
            'actual': self.actual,
        }


@dataclass
class SampleValidationIssue:
    """样本校验问题。"""
    sample_id: str
    field: str
    message: str

    def __str__(self) -> str:
        return f'{self.sample_id}.{self.field}: {self.message}'


@dataclass
class SampleLoadResult:
    """样本加载结果。"""
    samples: list[GoldenSample]
    issues: list[SampleValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def upgrade_legacy_sample(raw: Mapping[str, Any]) -> dict[str, Any]:
    """把旧格式样本（仅 expected/actual）升级为新黄金样本 Schema。

    旧样本缺 sample_id/source_category/scenario_tags 等字段时填默认值，
    使现有 3 份样本无需手工改写即可纳入新框架。
    """
    sample_id = raw.get('sample_id') or _derive_sample_id(raw)
    return {
        'sample_id': sample_id,
        'sample_version': raw.get('sample_version', SAMPLE_VERSION),
        'schema_version': raw.get('schema_version', SCHEMA_VERSION),
        'source_category': raw.get('source_category', _derive_source_category(raw)),
        'scenario_tags': list(raw.get('scenario_tags') or ['normal']),
        'usage_consent': raw.get('usage_consent', 'synthetic'),
        'desensitization_applied': raw.get('desensitization_applied', True),
        'description': raw.get('description', ''),
        'image_path': raw.get('image_path', ''),
        'source_text': raw.get('source_text', ''),
        'expected': raw.get('expected') or {},
        'expected_draft_type': raw.get('expected_draft_type', 'in_order_draft'),
        'expected_material_matches': list(raw.get('expected_material_matches') or []),
        'actual': raw.get('actual'),
    }


def load_sample_file(path: Path) -> GoldenSample:
    """加载单个样本 JSON 文件为 GoldenSample（自动升级旧格式）。"""
    raw = json.loads(path.read_text(encoding='utf-8'))
    upgraded = upgrade_legacy_sample(raw)
    return GoldenSample(**upgraded)


def load_sample_dir(sample_dir: Path) -> SampleLoadResult:
    """加载样本目录下所有 *.json 样本并校验。"""
    samples: list[GoldenSample] = []
    issues: list[SampleValidationIssue] = []

    if not sample_dir.exists():
        return SampleLoadResult(samples=samples)

    for path in sorted(sample_dir.glob('*.json')):
        try:
            sample = load_sample_file(path)
        except Exception as exc:  # noqa: BLE001 - 加载错误需收集而非中断
            issues.append(SampleValidationIssue(
                sample_id=path.name,
                field='__load__',
                message=f'加载失败: {exc}',
            ))
            continue
        samples.append(sample)

    # 唯一性校验
    seen_ids: set[str] = set()
    for sample in samples:
        if sample.sample_id in seen_ids:
            issues.append(SampleValidationIssue(
                sample_id=sample.sample_id,
                field='sample_id',
                message='样本 ID 重复',
            ))
        seen_ids.add(sample.sample_id)

    # 字段合法性校验
    for sample in samples:
        if sample.source_category not in ALL_SOURCE_CATEGORIES:
            issues.append(SampleValidationIssue(
                sample_id=sample.sample_id,
                field='source_category',
                message=f'非法来源类别 {sample.source_category!r}',
            ))
        for tag in sample.scenario_tags:
            if tag not in ALL_SCENARIO_TAGS:
                issues.append(SampleValidationIssue(
                    sample_id=sample.sample_id,
                    field='scenario_tags',
                    message=f'非法场景标签 {tag!r}',
                ))
        if sample.expected_draft_type not in VALID_DRAFT_TYPES:
            issues.append(SampleValidationIssue(
                sample_id=sample.sample_id,
                field='expected_draft_type',
                message=f'非法草稿类型 {sample.expected_draft_type!r}',
            ))
        if sample.usage_consent not in VALID_USAGE_CONSENT:
            issues.append(SampleValidationIssue(
                sample_id=sample.sample_id,
                field='usage_consent',
                message=f'非法使用授权 {sample.usage_consent!r}',
            ))
        expected_doc_type = (sample.expected or {}).get('document_type', '')
        if expected_doc_type and expected_doc_type not in VALID_DOCUMENT_TYPES:
            issues.append(SampleValidationIssue(
                sample_id=sample.sample_id,
                field='expected.document_type',
                message=f'非法文档类型 {expected_doc_type!r}',
            ))
        for idx, match in enumerate(sample.expected_material_matches):
            method = match.get('match_method')
            if method and method not in VALID_MATCH_METHODS:
                issues.append(SampleValidationIssue(
                    sample_id=sample.sample_id,
                    field=f'expected_material_matches[{idx}].match_method',
                    message=f'非法匹配方式 {method!r}',
                ))
        # 图片介质样本要求 image_path 非空
        if sample.source_category in {'photo', 'scanned', 'wechat_screenshot'} and not sample.image_path:
            issues.append(SampleValidationIssue(
                sample_id=sample.sample_id,
                field='image_path',
                message=f'来源类别 {sample.source_category!r} 要求 image_path 非空',
            ))
        # 文本介质样本要求 source_text 非空
        if sample.source_category in {'wechat_text', 'excel'} and not sample.source_text:
            issues.append(SampleValidationIssue(
                sample_id=sample.sample_id,
                field='source_text',
                message=f'来源类别 {sample.source_category!r} 要求 source_text 非空',
            ))

    return SampleLoadResult(samples=samples, issues=issues)


def compute_scenario_coverage(samples: Iterable[GoldenSample]) -> tuple[set[str], set[str]]:
    """计算场景覆盖率。

    Returns:
        (covered_scenarios, missing_scenarios)
    """
    covered: set[str] = set()
    for sample in samples:
        for tag in sample.scenario_tags:
            if tag in REQUIRED_SCENARIOS:
                covered.add(tag)
    missing = set(REQUIRED_SCENARIOS) - covered
    return covered, missing


def compute_source_category_coverage(samples: Iterable[GoldenSample]) -> tuple[set[str], set[str]]:
    """计算来源类别覆盖率。

    Returns:
        (covered_categories, missing_categories)
    """
    covered: set[str] = set()
    for sample in samples:
        if sample.source_category in REQUIRED_SOURCE_CATEGORIES:
            covered.add(sample.source_category)
    missing = set(REQUIRED_SOURCE_CATEGORIES) - covered
    return covered, missing


def _derive_sample_id(raw: Mapping[str, Any]) -> str:
    """旧样本无 sample_id 时从 description 或文件特征派生。"""
    desc = raw.get('description') or ''
    if desc:
        # 取前 12 字符做哈希
        import hashlib
        return f'LEGACY-{hashlib.sha1(desc.encode("utf-8")).hexdigest()[:8]}'
    return 'LEGACY-UNKNOWN'


def _derive_source_category(raw: Mapping[str, Any]) -> str:
    """旧样本无 source_category 时根据 description 推断。"""
    desc = (raw.get('description') or '').lower()
    if '微信' in desc or 'wechat' in desc:
        return 'wechat_text'
    if 'ocr' in desc or '识别' in desc:
        return 'photo'
    return 'photo'

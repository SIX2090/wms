"""AI-R07：物料歧义、别名和单位换算治理。

# AI_TASK: AI-R07

设计目标（验收：歧义行 100% 人工确认；高风险物料错误自动确认数为 0；
换算依据可追溯）：

- 纯逻辑 + 依赖注入：不依赖 Flask/SQLAlchemy，物料/别名查询通过注入的
  回调完成。CI 无 DB 时用 mock 测试，生产环境由 app.py 提供 ORM adapter。

- 中文归一化：全角/半角统一、繁简转换（简化版常见字）、同义词归一化、
  去多余空白与标点，为物料匹配提供稳定的归一化基础。

- 编码/名称/规格三维加权评分（权重和=1.0）：编码匹配权重最高（0.50），
  名称次之（0.35），规格最低（0.15）。综合评分 0~1。

- 多候选清单：不放弃多候选，返回完整候选带评分与证据，
  `has_ambiguity=True` 标记歧义，前端可展示候选清单供人工选择。

- 高风险物料规则引擎：可注入规则集合（编码前缀/正则），命中即强制
  `needs_confirmation=True`，不论 confidence 多高，确保高风险物料错误
  自动确认数为 0。

- 包装单位换算：内置标准换算因子表（箱/包/盒/打 ↔ 个/只/件/套/m/kg），
  支持注入自定义换算回调；`UnitConversionEvidence` 记录换算因子、规则
  来源、原始量与基本量，换算依据可追溯。

- 一物多码：通过别名机制扩展（同一物料多个供应商编码/旧编码），
  `query_aliases` 回调返回多个别名键指向同一物料的候选。

- 与生产匹配函数 `_ai_material_match_one` 解耦：本模块为旁路调用，
  结果存 flask.g 供前端展示候选清单和证据，不破坏现有 OCR 草稿路径。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ---- 评分权重（可配置）----

# 设计：编码是物料主数据唯一键，权重最高；名称是识别主要依据；
# 规格是辅助区分维度。权重和 = 1.0，综合评分范围 0~1。
WEIGHT_CODE = 0.50          # 编码匹配：最高权重
WEIGHT_NAME = 0.35          # 名称匹配
WEIGHT_SPEC = 0.15          # 规格匹配

# 自动选中的置信度门槛：唯一候选且评分 >= 此值且非高风险才自动选中
AUTO_SELECT_CONFIDENCE_THRESHOLD = 0.85

# 多候选阈值：模糊查询返回 >1 条即视为歧义
AMBIGUITY_CANDIDATE_LIMIT = 3


# ---- 中文归一化 ----

# 全角→半角映射表（数字、字母、常用标点）
_FULLWIDTH_DIGITS = str.maketrans('０１２３４５６７８９', '0123456789')
_FULLWIDTH_UPPER = str.maketrans('ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')
_FULLWIDTH_LOWER = str.maketrans('ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ', 'abcdefghijklmnopqrstuvwxyz')
# 全角标点用 dict 形式 maketrans 避免引号转义问题
_FULLWIDTH_PUNCT = str.maketrans({
    '\u3000': ' ',   # 全角空格
    '\uff08': '(',
    '\uff09': ')',
    '\uff0d': '-',
    '\uff3f': '_',
    '\uff0c': ',',
    '\u3002': '.',
    '\uff1a': ':',
    '\uff1b': ';',
    '\uff01': '!',
    '\uff1f': '?',
    '\uff07': "'",
    '\uff02': '"',
})

# 繁简转换（简化版，仅覆盖常见物料相关单字）
_TRAD_SIMPL = str.maketrans({
    '軸': '轴', '釘': '钉', '彈': '弹', '齒': '齿', '輪': '轮',
    '電': '电', '機': '机', '動': '动', '車': '车', '鋼': '钢',
    '鐵': '铁', '銅': '铜', '鋁': '铝', '閥': '阀', '泵': '泵',
    '墊': '垫', '彈': '弹', '鏈': '链', '條': '条', '桿': '杆',
})

# 同义词归一化（仅常见行业术语）
_SYNONYM_MAP = {
    '轴承': '轴承', '轴承座': '轴承座', '轴承箱': '轴承座',
    '螺母': '螺母', '螺帽': '螺母', '螺丝帽': '螺母',
    '螺栓': '螺栓', '螺丝': '螺栓', '螺杆': '螺栓',
    '垫圈': '垫圈', '垫片': '垫圈', '介子': '垫圈',
    '电机': '电机', '马达': '电机', '电动机': '电机',
    '齿轮': '齿轮', '牙轮': '齿轮',
    '钢管': '钢管', '铁管': '钢管',
}


def normalize_chinese_text(text: str) -> str:
    """中文归一化：全角→半角、繁简转换、同义词归一化、去多余空白与标点。

    Args:
        text: 原始文本

    Returns:
        归一化后的文本（小写、无多余空白、同义词统一）

    例：
        "ＡＢＣ-１２３ 軸承" -> "abc-123 轴承"
        "马达 6204" -> "电机 6204"
    """
    if not text:
        return ''
    s = text
    # 全角→半角
    s = s.translate(_FULLWIDTH_DIGITS)
    s = s.translate(_FULLWIDTH_UPPER)
    s = s.translate(_FULLWIDTH_LOWER)
    s = s.translate(_FULLWIDTH_PUNCT)
    # 繁简转换
    s = s.translate(_TRAD_SIMPL)
    # 同义词归一化（按词替换，长词优先）
    for trad in sorted(_SYNONYM_MAP.keys(), key=len, reverse=True):
        if trad in s:
            s = s.replace(trad, _SYNONYM_MAP[trad])
    # 去多余空白
    s = re.sub(r'\s+', ' ', s).strip()
    # 转小写（保留中文）
    return s.lower()


def normalize_match_key(text: str) -> str:
    """匹配键归一化：在 normalize_chinese_text 基础上去除所有空白与分隔符。

    用于精确匹配比对（如编码、别名键），消除格式差异。
    """
    s = normalize_chinese_text(text)
    # 去除所有空白、连字符、下划线、斜杠、冒号、中文标点
    return re.sub(r'[\s\-_/#:：，,;；]+', '', s)


# ---- 输入输出数据结构（纯 dataclass，不依赖 ORM）----

@dataclass(frozen=True)
class MaterialInfo:
    """物料主数据的纯数据视图（由 ORM adapter 转换）。"""

    material_id: int
    code: str = ''
    name: str = ''
    spec: str = ''
    unit_code: str = ''
    aliases: tuple[str, ...] = field(default_factory=tuple)  # 别名键列表


@dataclass(frozen=True)
class MaterialMatchCandidate:
    """单个物料匹配候选（带评分与证据）。"""

    material_id: int
    material_code: str
    material_name: str
    material_spec: str
    match_method: str                # exact_code / exact_name / alias / fuzzy / none
    confidence: float                # 综合评分 0~1
    score_breakdown: dict[str, float]
    needs_confirmation: bool
    confirmation_reason: str         # '' / multiple_candidates / low_confidence / ambiguous_spec / high_risk
    is_high_risk: bool
    high_risk_rule_id: str           # 命中的高风险规则 ID，无则 ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'material_id': self.material_id,
            'material_code': self.material_code,
            'material_name': self.material_name,
            'material_spec': self.material_spec,
            'match_method': self.match_method,
            'confidence': round(self.confidence, 4),
            'score_breakdown': dict(self.score_breakdown),
            'needs_confirmation': self.needs_confirmation,
            'confirmation_reason': self.confirmation_reason,
            'is_high_risk': self.is_high_risk,
            'high_risk_rule_id': self.high_risk_rule_id,
        }


@dataclass(frozen=True)
class MaterialMatchResult:
    """物料匹配总结果。"""

    candidates: tuple[MaterialMatchCandidate, ...]
    best: Optional[MaterialMatchCandidate]           # 最高分候选
    auto_selected: Optional[MaterialMatchCandidate]  # 自动选中的候选
    needs_confirmation: bool
    confirmation_reason: str
    has_ambiguity: bool                              # 多候选歧义
    fallback_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'candidates': [c.to_dict() for c in self.candidates],
            'best': self.best.to_dict() if self.best else None,
            'auto_selected': self.auto_selected.to_dict() if self.auto_selected else None,
            'needs_confirmation': self.needs_confirmation,
            'confirmation_reason': self.confirmation_reason,
            'has_ambiguity': self.has_ambiguity,
            'fallback_reason': self.fallback_reason,
        }


# ---- 单位换算 ----

@dataclass(frozen=True)
class UnitConversionEvidence:
    """单位换算证据（换算依据可追溯）。"""

    from_unit: str
    to_unit: str
    factor: float                    # 换算因子：base_quantity = original_quantity * factor
    rule_source: str                 # 'builtin' / 'custom' / 'identity'
    original_quantity: float
    base_quantity: float

    def to_dict(self) -> dict[str, Any]:
        return {
            'from_unit': self.from_unit,
            'to_unit': self.to_unit,
            'factor': self.factor,
            'rule_source': self.rule_source,
            'original_quantity': self.original_quantity,
            'base_quantity': round(self.base_quantity, 6),
        }


# 内置标准换算因子表：单位 -> (基本单位, 因子)
# 基本单位：个/只/件/套/m/kg/升
# 包装单位：箱/包/盒/打/捆
_BUILTIN_CONVERSIONS: dict[str, tuple[str, float]] = {
    # 箱 → 个
    '箱': ('个', 100.0),
    '包': ('个', 10.0),
    '盒': ('个', 10.0),
    '打': ('个', 12.0),
    '捆': ('个', 50.0),
    # 同义单位归一（只/件/套 → 个，按数量等价）
    '只': ('个', 1.0),
    '件': ('个', 1.0),
    '套': ('个', 1.0),
    'pcs': ('个', 1.0),
    'pc': ('个', 1.0),
    # 长度单位
    '米': ('m', 1.0),
    '公尺': ('m', 1.0),
    '厘米': ('m', 0.01),
    '毫米': ('m', 0.001),
    # 重量单位
    '千克': ('kg', 1.0),
    '公斤': ('kg', 1.0),
    '克': ('kg', 0.001),
    '吨': ('kg', 1000.0),
    # 容量单位
    '升': ('升', 1.0),
    '毫升': ('升', 0.001),
}


def convert_quantity(
    quantity: float,
    from_unit: str,
    to_unit: str = '',
    *,
    query_custom_conversions: Optional[Callable[[str, str], Optional[float]]] = None,
) -> Optional[UnitConversionEvidence]:
    """单位换算：将 quantity 从 from_unit 换算到 to_unit。

    Args:
        quantity: 原始数量
        from_unit: 原始单位
        to_unit: 目标单位（基本单位），留空则换算到内置基本单位
        query_custom_conversions: 注入的自定义换算因子查询回调，
            签名 (from_unit, to_unit) -> Optional[float]，返回因子或 None

    Returns:
        UnitConversionEvidence：换算证据，含因子、规则来源、原始量、基本量。
        无法换算时返回 None。
    """
    if quantity is None or from_unit is None:
        return None

    from_u = normalize_chinese_text(from_unit).strip()
    if not from_u:
        return None

    # 目标单位为空时，按内置表换算到基本单位
    target = normalize_chinese_text(to_unit).strip() if to_unit else ''

    # 同单位：身份换算
    if target and from_u == target:
        return UnitConversionEvidence(
            from_unit=from_unit,
            to_unit=to_unit,
            factor=1.0,
            rule_source='identity',
            original_quantity=float(quantity),
            base_quantity=float(quantity),
        )

    # 1. 优先查自定义换算（生产环境可注入物料专属换算因子）
    if query_custom_conversions and target:
        try:
            custom_factor = query_custom_conversions(from_u, target)
        except Exception:  # noqa: BLE001
            custom_factor = None
        if custom_factor is not None and custom_factor > 0:
            return UnitConversionEvidence(
                from_unit=from_unit,
                to_unit=to_unit,
                factor=float(custom_factor),
                rule_source='custom',
                original_quantity=float(quantity),
                base_quantity=float(quantity) * float(custom_factor),
            )

    # 2. 内置换算表
    builtin = _BUILTIN_CONVERSIONS.get(from_u)
    if builtin is None:
        # 尝试英文小写
        builtin = _BUILTIN_CONVERSIONS.get(from_u.lower())
    if builtin is None:
        return None

    base_unit, factor = builtin
    # 若 target 指定，需与内置基本单位一致才换算
    if target and normalize_match_key(target) != normalize_match_key(base_unit):
        # 尝试 target 也是包装单位，二次换算
        target_builtin = _BUILTIN_CONVERSIONS.get(target) or _BUILTIN_CONVERSIONS.get(target.lower())
        if target_builtin and target_builtin[0] == base_unit:
            # from -> base -> target 反向
            if target_builtin[1] > 0:
                final_factor = factor / target_builtin[1]
                return UnitConversionEvidence(
                    from_unit=from_unit,
                    to_unit=to_unit,
                    factor=final_factor,
                    rule_source='builtin',
                    original_quantity=float(quantity),
                    base_quantity=float(quantity) * final_factor,
                )
        return None

    return UnitConversionEvidence(
        from_unit=from_unit,
        to_unit=to_unit or base_unit,
        factor=factor,
        rule_source='builtin',
        original_quantity=float(quantity),
        base_quantity=float(quantity) * factor,
    )


# ---- 高风险物料规则 ----

@dataclass(frozen=True)
class HighRiskRule:
    """高风险物料规则定义。"""

    rule_id: str
    pattern: str                     # 物料编码前缀或正则
    description: str
    is_regex: bool = False           # True=正则匹配，False=前缀匹配


# 默认高风险物料规则（生产环境可注入覆盖）
DEFAULT_HIGH_RISK_RULES: tuple[HighRiskRule, ...] = (
    HighRiskRule('HR-ELECTRONICS', 'IC-', '高价值电子元器件（IC/CPU 类）'),
    HighRiskRule('HR-HAZARDOUS', 'HZ-', '危险品（易燃易爆有毒）'),
    HighRiskRule('HR-PRECIOUS', 'PM-', '贵金属（金/银/铂）'),
    HighRiskRule('HR-PRECISION', 'BRG-PRECISION-', '精密轴承（高精度）'),
)


def is_high_risk_material(
    material_code: str,
    material_name: str = '',
    *,
    rules: Optional[tuple[HighRiskRule, ...]] = None,
) -> tuple[bool, str, str]:
    """判定物料是否为高风险。

    Args:
        material_code: 物料编码
        material_name: 物料名称（用于正则匹配）
        rules: 注入的规则集合，留空则用 DEFAULT_HIGH_RISK_RULES

    Returns:
        (是否高风险, 命中的规则 ID, 中文描述)
    """
    if not material_code:
        return False, '', ''
    applied_rules = rules if rules is not None else DEFAULT_HIGH_RISK_RULES
    code_upper = material_code.upper()
    for rule in applied_rules:
        if rule.is_regex:
            try:
                if re.search(rule.pattern, material_code) or (
                    material_name and re.search(rule.pattern, material_name)
                ):
                    return True, rule.rule_id, rule.description
            except re.error:
                continue
        else:
            pattern_upper = rule.pattern.upper()
            if code_upper.startswith(pattern_upper):
                return True, rule.rule_id, rule.description
    return False, '', ''


# ---- 查询接口（依赖注入）----

# 按编码列表查物料：([code1, code2, ...]) -> list[MaterialInfo]
QueryMaterialsByCodesFn = Callable[[list[str]], list[MaterialInfo]]

# 按名称查物料：(name: str, limit: int) -> list[MaterialInfo]
QueryMaterialsByNameFn = Callable[[str, int], list[MaterialInfo]]

# 按别名键列表查物料：([alias_key1, alias_key2, ...]) -> list[MaterialInfo]
QueryAliasesFn = Callable[[list[str]], list[MaterialInfo]]


# ---- 主匹配函数 ----

def match_material_governance(
    code: str,
    name: str,
    spec: str = '',
    barcode: str = '',
    *,
    query_materials_by_codes: Optional[QueryMaterialsByCodesFn] = None,
    query_materials_by_name: Optional[QueryMaterialsByNameFn] = None,
    query_aliases: Optional[QueryAliasesFn] = None,
    high_risk_rules: Optional[tuple[HighRiskRule, ...]] = None,
    auto_select_threshold: float = AUTO_SELECT_CONFIDENCE_THRESHOLD,
) -> MaterialMatchResult:
    """对送货通知/OCR 提取的物料执行加权评分匹配。

    匹配流程：
    1. 编码精确匹配（normalize_match_key 比对）
    2. 名称+规格精确匹配
    3. 别名匹配（多别名键查询，支持一物多码）
    4. 名称模糊匹配（ilike 等效，limit 3）
    5. 去重 + 评分 + 排序
    6. 决策：唯一候选+评分达标+非高风险→自动选中；多候选→歧义；低置信度→待确认

    Args:
        code: 提取的物料编码
        name: 提取的物料名称
        spec: 提取的规格
        barcode: 条码（作为别名候选）
        query_materials_by_codes: 按编码列表查物料回调
        query_materials_by_name: 按名称查物料回调
        query_aliases: 按别名键列表查物料回调
        high_risk_rules: 高风险物料规则集合
        auto_select_threshold: 自动选中置信度门槛

    Returns:
        MaterialMatchResult：含候选清单、最佳候选、自动选中、歧义标记、
        人工确认决策
    """
    candidates: list[MaterialMatchCandidate] = []
    seen_ids: set[int] = set()

    # 归一化输入
    norm_code = normalize_match_key(code) if code else ''
    norm_name = normalize_chinese_text(name) if name else ''
    norm_spec = normalize_match_key(spec) if spec else ''
    norm_barcode = normalize_match_key(barcode) if barcode else ''

    # 1. 编码精确匹配
    if norm_code and query_materials_by_codes:
        try:
            code_matches = query_materials_by_codes([code, norm_code])
        except Exception:  # noqa: BLE001
            code_matches = []
        for m in code_matches:
            if m.material_id in seen_ids:
                continue
            if normalize_match_key(m.code) == norm_code:
                seen_ids.add(m.material_id)
                candidates.append(_score_candidate(
                    m, code, name, spec,
                    match_method='exact_code',
                    is_code_exact=True,
                    high_risk_rules=high_risk_rules,
                ))

    # 2. 名称+规格精确匹配（通过 query_materials_by_name）
    if norm_name and query_materials_by_name and not candidates:
        try:
            name_matches = query_materials_by_name(name, AMBIGUITY_CANDIDATE_LIMIT)
        except Exception:  # noqa: BLE001
            name_matches = []
        for m in name_matches:
            if m.material_id in seen_ids:
                continue
            m_name = normalize_chinese_text(m.name)
            if m_name == norm_name:
                seen_ids.add(m.material_id)
                candidates.append(_score_candidate(
                    m, code, name, spec,
                    match_method='exact_name',
                    is_name_exact=True,
                    high_risk_rules=high_risk_rules,
                ))

    # 3. 别名匹配（一物多码：多个别名键指向同一物料）
    alias_keys: list[str] = []
    if norm_name:
        alias_keys.append(name)
        alias_keys.append(norm_name)
    if norm_spec:
        alias_keys.append(spec)
    if norm_barcode:
        alias_keys.append(barcode)
    if norm_name and norm_spec:
        alias_keys.append(f'{name} {spec}')
    # 去重
    alias_keys = list(dict.fromkeys(alias_keys))

    if alias_keys and query_aliases and not candidates:
        try:
            alias_matches = query_aliases(alias_keys)
        except Exception:  # noqa: BLE001
            alias_matches = []
        for m in alias_matches:
            if m.material_id in seen_ids:
                continue
            seen_ids.add(m.material_id)
            candidates.append(_score_candidate(
                m, code, name, spec,
                match_method='alias',
                is_alias_match=True,
                high_risk_rules=high_risk_rules,
            ))

    # 4. 名称模糊匹配（仅当前 3 步无命中时）
    if norm_name and query_materials_by_name and not candidates:
        try:
            fuzzy_matches = query_materials_by_name(name, AMBIGUITY_CANDIDATE_LIMIT)
        except Exception:  # noqa: BLE001
            fuzzy_matches = []
        for m in fuzzy_matches:
            if m.material_id in seen_ids:
                continue
            seen_ids.add(m.material_id)
            candidates.append(_score_candidate(
                m, code, name, spec,
                match_method='fuzzy',
                high_risk_rules=high_risk_rules,
            ))

    # 5. 排序：可自动选的优先，再按 confidence 降序
    candidates.sort(key=lambda c: (not c.is_high_risk, c.confidence), reverse=True)

    # 6. 决策
    has_candidates = len(candidates) > 0
    has_ambiguity = len(candidates) > 1
    best = candidates[0] if candidates else None
    auto_selected: Optional[MaterialMatchCandidate] = None
    needs_confirmation = False
    confirmation_reason = ''
    fallback_reason = ''

    if not has_candidates:
        needs_confirmation = True
        confirmation_reason = 'no_match'
        fallback_reason = '未匹配到物料，需人工确认或新建物料'
    elif has_ambiguity:
        # 多候选歧义：100% 人工确认
        needs_confirmation = True
        confirmation_reason = 'multiple_candidates'
        fallback_reason = f'找到 {len(candidates)} 个候选物料，需人工确认选择'
    elif best is not None:
        # 唯一候选
        if best.is_high_risk:
            # 高风险物料强制人工确认
            needs_confirmation = True
            confirmation_reason = 'high_risk'
            fallback_reason = f'命中高风险物料规则 {best.high_risk_rule_id}，需人工确认'
        elif best.needs_confirmation:
            # 候选自身标记需确认（如规格不明确 ambiguous_spec）
            needs_confirmation = True
            confirmation_reason = best.confirmation_reason
            fallback_reason = (
                f'候选需人工确认（{best.confirmation_reason}），'
                f'评分 {best.confidence:.2f}'
            )
        elif best.confidence >= auto_select_threshold:
            # 唯一候选+评分达标+非高风险+无需确认→自动选中
            auto_selected = best
        else:
            # 低置信度
            needs_confirmation = True
            confirmation_reason = 'low_confidence'
            fallback_reason = (
                f'候选评分 {best.confidence:.2f} 低于自动选中门槛 '
                f'{auto_select_threshold:.2f}，需人工确认'
            )

    return MaterialMatchResult(
        candidates=tuple(candidates),
        best=best,
        auto_selected=auto_selected,
        needs_confirmation=needs_confirmation,
        confirmation_reason=confirmation_reason,
        has_ambiguity=has_ambiguity,
        fallback_reason=fallback_reason,
    )


# ---- 单候选评分 ----

def _score_candidate(
    material: MaterialInfo,
    input_code: str,
    input_name: str,
    input_spec: str,
    *,
    match_method: str,
    is_code_exact: bool = False,
    is_name_exact: bool = False,
    is_alias_match: bool = False,
    high_risk_rules: Optional[tuple[HighRiskRule, ...]] = None,
) -> MaterialMatchCandidate:
    """对单个物料候选评分并生成证据。"""
    # 维度1：编码匹配
    if is_code_exact:
        score_code = 1.0
    elif input_code and material.code:
        # 模糊匹配编码（归一化后包含关系）
        nc_input = normalize_match_key(input_code)
        nc_mat = normalize_match_key(material.code)
        if nc_input and nc_mat:
            if nc_input == nc_mat:
                score_code = 1.0
            elif nc_input in nc_mat or nc_mat in nc_input:
                score_code = 0.7
            else:
                score_code = 0.0
        else:
            score_code = 0.0
    else:
        score_code = 0.0

    # 维度2：名称匹配
    if is_name_exact:
        score_name = 1.0
    elif input_name and material.name:
        nn_input = normalize_chinese_text(input_name)
        nn_mat = normalize_chinese_text(material.name)
        if nn_input and nn_mat:
            if nn_input == nn_mat:
                score_name = 1.0
            elif nn_input in nn_mat or nn_mat in nn_input:
                score_name = 0.7
            else:
                # 词级重合度
                score_name = _word_overlap(nn_input, nn_mat)
        else:
            score_name = 0.0
    else:
        score_name = 0.0

    # 维度3：规格匹配
    if input_spec and material.spec:
        ns_input = normalize_match_key(input_spec)
        ns_mat = normalize_match_key(material.spec)
        if ns_input and ns_mat:
            if ns_input == ns_mat:
                score_spec = 1.0
            elif ns_input in ns_mat or ns_mat in ns_input:
                score_spec = 0.7
            else:
                score_spec = 0.0
        else:
            score_spec = 0.0
    elif not input_spec and not material.spec:
        # 双方都无规格：视为中性，给 0.5
        score_spec = 0.5
    else:
        # 一方有一方无：规格不明确
        score_spec = 0.0

    # 综合评分
    confidence = (
        WEIGHT_CODE * score_code
        + WEIGHT_NAME * score_name
        + WEIGHT_SPEC * score_spec
    )

    # 高风险物料判定
    is_hr, hr_rule_id, hr_desc = is_high_risk_material(
        material.code, material.name, rules=high_risk_rules,
    )

    # 确认原因（不含多候选决策，多候选由 match_material_governance 决定）
    # 规格不明确：输入和物料都有规格但不匹配，即使 confidence 达标也需确认
    spec_mismatch = (
        score_spec == 0.0
        and bool(input_spec)
        and bool(material.spec)
    )
    if is_hr:
        confirmation_reason = 'high_risk'
        needs_confirmation = True
    elif spec_mismatch:
        # 规格不明确：触发 ambiguous_spec
        confirmation_reason = 'ambiguous_spec'
        needs_confirmation = True
    elif confidence < AUTO_SELECT_CONFIDENCE_THRESHOLD:
        confirmation_reason = 'low_confidence'
        needs_confirmation = True
    else:
        confirmation_reason = ''
        needs_confirmation = False

    return MaterialMatchCandidate(
        material_id=material.material_id,
        material_code=material.code,
        material_name=material.name,
        material_spec=material.spec,
        match_method=match_method,
        confidence=confidence,
        score_breakdown={
            'code': round(score_code, 4),
            'name': round(score_name, 4),
            'spec': round(score_spec, 4),
        },
        needs_confirmation=needs_confirmation,
        confirmation_reason=confirmation_reason,
        is_high_risk=is_hr,
        high_risk_rule_id=hr_rule_id,
    )


def _word_overlap(s1: str, s2: str) -> float:
    """计算两个字符串的词级重合度（0~1）。

    简化实现：按 2-gram 字符重合度。
    """
    if not s1 or not s2:
        return 0.0
    # 2-gram
    grams1 = {s1[i:i + 2] for i in range(len(s1) - 1)} if len(s1) > 1 else {s1}
    grams2 = {s2[i:i + 2] for i in range(len(s2) - 1)} if len(s2) > 1 else {s2}
    if not grams1 or not grams2:
        return 0.0
    overlap = len(grams1 & grams2)
    return overlap / max(len(grams1 | grams2), 1)

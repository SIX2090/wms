"""AI-R07 物料歧义、别名和单位换算治理验证脚本。

# AI_TASK: AI-R07

验证内容：
1. 中文归一化：全角/半角、繁简、同义词、空白
2. 编码精确匹配：最高分自动选
3. 名称+规格加权匹配
4. 别名候选命中（一物多码）
5. 多候选返回清单不自动选（has_ambiguity=True，歧义行 100% 人工确认）
6. 低置信度人工确认（ambiguous_spec 触发）
7. 单位换算正确（含证据可追溯）
8. 高风险物料强制人工确认（不论 confidence 多高，错误自动确认数为 0）

退出码 0=通过，1=失败。
"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ai.documents.material_governance import (  # noqa: E402
    AUTO_SELECT_CONFIDENCE_THRESHOLD,
    DEFAULT_HIGH_RISK_RULES,
    HighRiskRule,
    MaterialInfo,
    convert_quantity,
    is_high_risk_material,
    match_material_governance,
    normalize_chinese_text,
    normalize_match_key,
)


def _make_material(
    mid, code, name, spec='', unit_code='个', aliases=(),
):
    """构造测试用 MaterialInfo。"""
    return MaterialInfo(
        material_id=mid,
        code=code,
        name=name,
        spec=spec,
        unit_code=unit_code,
        aliases=tuple(aliases),
    )


def test_chinese_normalization() -> None:
    """测试1：中文归一化（全角/半角/繁简/同义词/空白）。"""
    # 全角→半角
    assert normalize_chinese_text('ＡＢＣ-１２３') == 'abc-123', \
        f'全角应转半角, got {normalize_chinese_text("ＡＢＣ-１２３")!r}'
    # 繁简转换
    assert normalize_chinese_text('軸承齒輪') == '轴承齿轮', \
        f'繁体应转简体, got {normalize_chinese_text("軸承齒輪")!r}'
    # 同义词归一化
    assert normalize_chinese_text('马达 6204') == '电机 6204', \
        f'马达应归一为电机, got {normalize_chinese_text("马达 6204")!r}'
    assert normalize_chinese_text('螺帽 M8') == '螺母 m8', \
        f'螺帽应归一为螺母, got {normalize_chinese_text("螺帽 M8")!r}'
    # 多余空白
    assert normalize_chinese_text('  轴承   6204  ') == '轴承 6204', \
        f'多余空白应合并, got {normalize_chinese_text("  轴承   6204  ")!r}'
    # 全角空格
    fullwidth_space_input = '轴承\u30006204'
    assert normalize_chinese_text(fullwidth_space_input) == '轴承 6204', \
        f'全角空格应转半角, got {normalize_chinese_text(fullwidth_space_input)!r}'
    # 空字符串
    assert normalize_chinese_text('') == ''
    assert normalize_chinese_text(None) == ''  # type: ignore[arg-type]

    # 匹配键归一化：去除所有分隔符
    assert normalize_match_key(' ABC-123 軸承 ') == 'abc123轴承', \
        f'匹配键应去除分隔符, got {normalize_match_key(" ABC-123 軸承 ")!r}'

    print('测试1 通过: 中文归一化（全角/半角/繁简/同义词/空白/匹配键）')


def test_exact_code_match() -> None:
    """测试2：编码精确匹配最高分自动选。"""
    mat = _make_material(1, '6204', '轴承', '25x52x15')

    def query_by_codes(codes):
        # 模拟按编码列表查询返回物料
        return [mat] if '6204' in codes or normalize_match_key('6204') in codes else []

    result = match_material_governance(
        code='6204', name='轴承', spec='25x52x15',
        query_materials_by_codes=query_by_codes,
    )

    assert len(result.candidates) == 1
    cand = result.candidates[0]
    assert cand.match_method == 'exact_code', f'应 exact_code, got {cand.match_method}'
    assert cand.confidence >= AUTO_SELECT_CONFIDENCE_THRESHOLD, \
        f'编码精确匹配应 >= {AUTO_SELECT_CONFIDENCE_THRESHOLD}, got {cand.confidence}'
    assert cand.score_breakdown['code'] == 1.0
    assert cand.score_breakdown['name'] == 1.0
    assert cand.score_breakdown['spec'] == 1.0
    assert cand.is_high_risk is False
    assert cand.needs_confirmation is False, '编码精确匹配不应需确认'
    # 唯一候选+高分+非高风险 → 自动选中
    assert result.auto_selected is not None, '应自动选中'
    assert result.auto_selected.material_id == 1
    assert result.has_ambiguity is False

    print('测试2 通过: 编码精确匹配最高分自动选')


def test_name_spec_weighted_match() -> None:
    """测试3：名称+规格加权匹配。"""
    mat = _make_material(2, 'M8-NUT', '螺母', 'M8')

    def query_by_name(name, limit):
        return [mat] if '螺母' in name else []

    result = match_material_governance(
        code='', name='螺母', spec='M8',
        query_materials_by_name=query_by_name,
    )

    assert len(result.candidates) == 1
    cand = result.candidates[0]
    assert cand.match_method == 'exact_name', f'应 exact_name, got {cand.match_method}'
    # 名称精确=1.0，规格精确=1.0，编码无=0
    assert cand.score_breakdown['name'] == 1.0
    assert cand.score_breakdown['spec'] == 1.0
    assert cand.score_breakdown['code'] == 0.0
    # 综合 confidence = 0.5*0 + 0.35*1.0 + 0.15*1.0 = 0.50，低于门槛
    expected = 0.50
    assert abs(cand.confidence - expected) < 0.001, \
        f'名称+规格匹配 confidence 应 {expected}, got {cand.confidence}'
    # 低置信度不自动选
    assert cand.needs_confirmation is True
    assert cand.confirmation_reason == 'low_confidence'
    assert result.auto_selected is None

    print('测试3 通过: 名称+规格加权匹配（confidence=0.50 低置信度不自动选）')


def test_alias_match_one_code_multiple() -> None:
    """测试4：别名候选命中（一物多码）。"""
    mat = _make_material(3, 'BRG-6204', '轴承', '25x52x15')

    def query_aliases(alias_keys):
        # 别名 '6204-轴承' 命中物料 BRG-6204
        if any('6204' in k for k in alias_keys):
            return [mat]
        return []

    result = match_material_governance(
        code='', name='6204-轴承', spec='',
        query_aliases=query_aliases,
    )

    assert len(result.candidates) == 1
    cand = result.candidates[0]
    assert cand.match_method == 'alias', f'应 alias, got {cand.match_method}'
    # 别名命中时，名称匹配可能部分匹配
    assert cand.confidence > 0.0, '别名命中 confidence 应 > 0'

    print('测试4 通过: 别名候选命中（一物多码）')


def test_multiple_candidates_ambiguity() -> None:
    """测试5：多候选返回清单不自动选（歧义行 100% 人工确认）。"""
    mat1 = _make_material(1, '6204-2RS', '轴承', '25x52x15')
    mat2 = _make_material(2, '6204-ZZ', '轴承', '25x52x15')
    mat3 = _make_material(3, '6204-OPEN', '轴承', '25x52x15')

    def query_by_name(name, limit):
        return [mat1, mat2, mat3] if '轴承' in name else []

    result = match_material_governance(
        code='', name='轴承', spec='25x52x15',
        query_materials_by_name=query_by_name,
    )

    assert len(result.candidates) == 3, f'应有 3 候选, got {len(result.candidates)}'
    assert result.has_ambiguity is True, '多候选应标记歧义'
    assert result.auto_selected is None, '多候选不自动选'
    assert result.needs_confirmation is True, '歧义行 100% 人工确认'
    assert result.confirmation_reason == 'multiple_candidates'
    assert '3 个候选' in result.fallback_reason
    # 候选清单完整（带证据）
    for c in result.candidates:
        assert c.material_id in (1, 2, 3)
        assert 'code' in c.score_breakdown
        assert 'name' in c.score_breakdown
        assert 'spec' in c.score_breakdown

    print('测试5 通过: 多候选返回清单不自动选（歧义行 100% 人工确认）')


def test_ambiguous_spec_confirmation() -> None:
    """测试6：低置信度人工确认（ambiguous_spec 触发）。"""
    # 输入有规格，物料有规格，但规格不匹配
    mat = _make_material(1, '6204', '轴承', '25x52x15')

    def query_by_codes(codes):
        return [mat]

    result = match_material_governance(
        code='6204', name='轴承', spec='30x60x20',  # 规格不匹配
        query_materials_by_codes=query_by_codes,
    )

    assert len(result.candidates) == 1
    cand = result.candidates[0]
    # 编码精确=1.0，名称精确=1.0，规格不匹配=0.0
    # confidence = 0.5*1 + 0.35*1 + 0.15*0 = 0.85
    assert cand.score_breakdown['spec'] == 0.0, '规格不匹配应为 0'
    assert cand.confirmation_reason == 'ambiguous_spec', \
        f'规格不明确应触发 ambiguous_spec, got {cand.confirmation_reason}'
    assert cand.needs_confirmation is True
    assert result.auto_selected is None, '规格不明确不自动选'

    print('测试6 通过: 低置信度人工确认（ambiguous_spec 触发）')


def test_unit_conversion_evidence() -> None:
    """测试7：单位换算正确（含证据可追溯）。"""
    # 箱 → 个（内置换算）
    ev = convert_quantity(2, '箱')
    assert ev is not None
    assert ev.factor == 100.0, f'箱→个因子应 100, got {ev.factor}'
    assert ev.base_quantity == 200.0, f'2 箱应 200 个, got {ev.base_quantity}'
    assert ev.rule_source == 'builtin', '应 builtin 规则'
    assert ev.from_unit == '箱'
    assert ev.to_unit == '个'

    # 包 → 个
    ev2 = convert_quantity(5, '包')
    assert ev2 is not None
    assert ev2.base_quantity == 50.0, f'5 包应 50 个, got {ev2.base_quantity}'

    # 米 → 毫米（包装单位间的二次换算）
    ev3 = convert_quantity(1, '米', '毫米')
    assert ev3 is not None
    assert ev3.factor == 1000.0, f'米→毫米因子应 1000, got {ev3.factor}'
    assert ev3.base_quantity == 1000.0, f'1 米应 1000 毫米, got {ev3.base_quantity}'

    # 同单位身份换算
    ev4 = convert_quantity(10, '个', '个')
    assert ev4 is not None
    assert ev4.factor == 1.0
    assert ev4.rule_source == 'identity'

    # 自定义换算（注入回调）
    def custom_lookup(from_u, to_u):
        if from_u == '托盘' and to_u == '个':
            return 500.0  # 1 托盘 = 500 个
        return None

    ev5 = convert_quantity(3, '托盘', '个', query_custom_conversions=custom_lookup)
    assert ev5 is not None
    assert ev5.factor == 500.0
    assert ev5.base_quantity == 1500.0
    assert ev5.rule_source == 'custom', '应标记 custom 规则来源'

    # 无法换算
    ev6 = convert_quantity(1, '未知单位')
    assert ev6 is None, '未知单位应返回 None'

    # 证据可追溯：to_dict 含所有字段
    ev_dict = ev.to_dict()
    assert set(ev_dict.keys()) == {
        'from_unit', 'to_unit', 'factor', 'rule_source',
        'original_quantity', 'base_quantity',
    }, f'证据字段不完整: {ev_dict.keys()}'

    print('测试7 通过: 单位换算正确（内置/自定义/身份/无法换算/证据可追溯）')


def test_high_risk_material_forced_confirmation() -> None:
    """测试8：高风险物料强制人工确认（错误自动确认数为 0）。"""
    # 高风险物料：IC- 开头
    mat = _make_material(1, 'IC-001-CPU', 'CPU 处理器', 'i7-13700K')

    def query_by_codes(codes):
        return [mat]

    result = match_material_governance(
        code='IC-001-CPU', name='CPU 处理器', spec='i7-13700K',
        query_materials_by_codes=query_by_codes,
    )

    assert len(result.candidates) == 1
    cand = result.candidates[0]
    # 即使编码+名称+规格全部精确匹配，confidence=1.0
    assert cand.confidence == 1.0, f'应满分, got {cand.confidence}'
    # 高风险物料强制人工确认
    assert cand.is_high_risk is True, '应判定为高风险'
    assert cand.high_risk_rule_id == 'HR-ELECTRONICS', \
        f'应命中 HR-ELECTRONICS, got {cand.high_risk_rule_id}'
    assert cand.needs_confirmation is True, '高风险物料必须人工确认'
    assert cand.confirmation_reason == 'high_risk'
    # 即使 confidence=1.0，高风险物料也不自动选
    assert result.auto_selected is None, '高风险物料错误自动确认数应为 0'
    assert '高风险' in result.fallback_reason

    # 直接调用 is_high_risk_material 验证所有默认规则
    assert is_high_risk_material('IC-anything')[0] is True
    assert is_high_risk_material('HZ-危险品')[0] is True
    assert is_high_risk_material('PM-GOLD-001')[0] is True
    assert is_high_risk_material('BRG-PRECISION-001')[0] is True
    assert is_high_risk_material('NORMAL-001')[0] is False
    assert is_high_risk_material('')[0] is False

    # 注入自定义规则
    custom_rules = (
        HighRiskRule('HR-CUSTOM', 'MED-', '医疗高值耗材'),
    )
    assert is_high_risk_material('MED-001', rules=custom_rules)[0] is True
    assert is_high_risk_material('IC-001', rules=custom_rules)[0] is False, \
        '自定义规则应覆盖默认规则'

    # 正则规则
    regex_rules = (
        HighRiskRule('HR-REGEX', r'金|银|铂', '贵金属（正则）', is_regex=True),
    )
    assert is_high_risk_material('GOLD-001', '金币', rules=regex_rules)[0] is True
    assert is_high_risk_material('XXX-001', '普通物料', rules=regex_rules)[0] is False

    print('测试8 通过: 高风险物料强制人工确认（不论 confidence 多高，错误自动确认数为 0）')


def main() -> int:
    try:
        test_chinese_normalization()
        test_exact_code_match()
        test_name_spec_weighted_match()
        test_alias_match_one_code_multiple()
        test_multiple_candidates_ambiguity()
        test_ambiguous_spec_confirmation()
        test_unit_conversion_evidence()
        test_high_risk_material_forced_confirmation()
    except AssertionError as exc:
        print(f'FAIL AI-MATERIAL-GOVERNANCE: {exc}')
        return 1
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f'FAIL AI-MATERIAL-GOVERNANCE: 异常 {exc}')
        return 1

    print('PASS AI-MATERIAL-GOVERNANCE: 物料歧义/别名/单位换算/高风险规则 8 项测试全部通过')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

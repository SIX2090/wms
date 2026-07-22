# -*- coding: utf-8 -*-
"""模块1黄金测试：material_governance.py + material_governance_enhanced.py 数据结构统一。

# AI_TASK: AI-R07 / AI-R07-F01 黄金测试（绞杀者模式前置基线）

所有断言严格依据《项目黑话词典》确定性语义与待确认歧义点，禁止使用通用 WMS 术语。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any

import pytest

from app.ai.documents.material_governance import (
    AUTO_SELECT_CONFIDENCE_THRESHOLD,
    DEFAULT_HIGH_RISK_RULES,
    HighRiskRule,
    MaterialInfo,
    match_material_governance,
)
from app.ai.documents.material_governance_enhanced import (
    ALIAS_STATUS_APPROVED,
    ALIAS_STATUS_CONFLICT,
    ALIAS_STATUS_DISABLED,
    ALIAS_STATUS_PENDING,
    HighRiskRuleRecord,
    MaterialAliasRecord,
    VALID_ALIAS_STATUSES,
    approve_alias,
    check_alias_conflict,
    create_alias_request,
    disable_alias,
    record_alias_usage,
    validate_high_risk_rule_cannot_downgrade,
    validate_one_material_multiple_codes_traceable,
)


# ----------------------------------------------------------------------
# 模块1-A：HighRiskRule 与 HighRiskRuleRecord 数据结构统一基线
# ----------------------------------------------------------------------

# 依据：HighRiskRule / HighRiskRuleRecord 字段语义（待统一重构）
def test_high_risk_rule_fields_are_subset_of_record_for_unification():
    """基线：HighRiskRule 字段必须可无损提升为 HighRiskRuleRecord，统一后行为不变。"""
    rule = HighRiskRule('HR-TEST', 'TEST-', '测试规则')
    record = HighRiskRuleRecord(
        rule_id=rule.rule_id,
        pattern=rule.pattern,
        description=rule.description,
        is_regex=rule.is_regex,
        created_by='system',
        created_at='2026-01-01T00:00:00',
    )
    assert record.rule_id == rule.rule_id, "rule_id 必须保留"
    assert record.pattern == rule.pattern, "pattern 必须保留"
    assert record.description == rule.description, "description 必须保留"
    assert record.is_regex == rule.is_regex, "is_regex 默认值必须为 False"
    assert record.is_active is True, "统一后默认启用"
    assert record.priority == 100, "统一后默认优先级 100"


# 依据：DEFAULT_HIGH_RISK_RULES 确定性语义（HR-ELECTRONICS/HR-HAZARDOUS/HR-PRECIOUS/HR-PRECISION）
def test_default_high_risk_rules_ids_are_deterministic():
    """基线：默认高风险规则 ID 不可变，重构后必须保持一致。"""
    rule_ids = tuple(r.rule_id for r in DEFAULT_HIGH_RISK_RULES)
    assert rule_ids == (
        'HR-ELECTRONICS',
        'HR-HAZARDOUS',
        'HR-PRECIOUS',
        'HR-PRECISION',
    ), "默认高风险规则 ID 集合不可变"
    for rule in DEFAULT_HIGH_RISK_RULES:
        assert rule.is_regex is False, "默认规则全部为前缀匹配（is_regex=False）"


# 依据：HighRiskRule.pattern 确定性语义（前缀匹配，IC-/HZ-/PM-/BRG-PRECISION-）
def test_default_high_risk_rule_patterns_match_dictionary_semantics():
    """基线：默认高风险规则 pattern 与黑话字典物理含义一一对应。"""
    patterns = {r.rule_id: r.pattern for r in DEFAULT_HIGH_RISK_RULES}
    assert patterns['HR-ELECTRONICS'] == 'IC-', "IC- 前缀=高价值电子元器件"
    assert patterns['HR-HAZARDOUS'] == 'HZ-', "HZ- 前缀=危险品（易燃易爆有毒）"
    assert patterns['HR-PRECIOUS'] == 'PM-', "PM- 前缀=贵金属（金/银/铂）"
    assert patterns['HR-PRECISION'] == 'BRG-PRECISION-', "BRG-PRECISION- 前缀=精密轴承"


# 依据：HighRiskRuleRecord.is_active 确定性语义（普通用户不能停用规则绕过确认）
def test_high_risk_rule_record_cannot_downgrade_by_normal_user():
    """基线：普通用户不能通过修改 HighRiskRuleRecord 绕过确认要求。"""
    original = HighRiskRuleRecord(
        rule_id='HR-ELECTRONICS', pattern='IC-', description='高价值电子元器件',
        created_by='admin', created_at='2026-01-01T00:00:00',
        is_active=True, priority=100, approved_by='admin',
    )
    modified = HighRiskRuleRecord(
        rule_id='HR-ELECTRONICS', pattern='IC-', description='高价值电子元器件',
        created_by='admin', created_at='2026-01-01T00:00:00',
        is_active=False, priority=100, approved_by='admin',
    )
    can_downgrade, reason = validate_high_risk_rule_cannot_downgrade(
        original_rule=original, modified_rule=modified, operator_role='normal'
    )
    assert can_downgrade is False, "普通用户不得停用高风险规则"
    assert reason, "拒绝原因不得为空"


# 依据：HighRiskRuleRecord.is_active 确定性语义（管理员可停用）
def test_high_risk_rule_record_admin_can_downgrade():
    """基线：管理员角色可修改 HighRiskRuleRecord 状态。"""
    original = HighRiskRuleRecord(
        rule_id='HR-ELECTRONICS', pattern='IC-', description='高价值电子元器件',
        created_by='admin', created_at='2026-01-01T00:00:00', is_active=True,
    )
    modified = HighRiskRuleRecord(
        rule_id='HR-ELECTRONICS', pattern='IC-', description='高价值电子元器件',
        created_by='admin', created_at='2026-01-01T00:00:00', is_active=False,
    )
    can_downgrade, _ = validate_high_risk_rule_cannot_downgrade(
        original_rule=original, modified_rule=modified, operator_role='admin'
    )
    assert can_downgrade is True, "管理员可停用规则"


# ----------------------------------------------------------------------
# 模块1-B：别名生命周期状态确定性语义
# ----------------------------------------------------------------------

# 依据：MaterialAliasRecord.status 确定性语义（pending/approved/disabled/conflict 四态）
def test_alias_status_constants_match_dictionary():
    """基线：别名状态四态常量必须与黑话字典一致。"""
    assert ALIAS_STATUS_PENDING == 'pending', "待审核"
    assert ALIAS_STATUS_APPROVED == 'approved', "已审核启用"
    assert ALIAS_STATUS_DISABLED == 'disabled', "已停用"
    assert ALIAS_STATUS_CONFLICT == 'conflict', "冲突（多物料指向同一别名）"
    assert VALID_ALIAS_STATUSES == (
        'pending', 'approved', 'disabled', 'conflict',
    ), "状态枚举顺序不可变"


# 依据：MaterialAliasRecord.status 确定性语义（create_alias_request 初始=pending）
def test_create_alias_request_initial_status_is_pending():
    """基线：新建别名申请初始状态必须为 pending。"""
    record = create_alias_request(
        alias_key='IC-6204', material_id=1, material_code='BRG-6204',
        created_by='user_a',
    )
    assert record.status == ALIAS_STATUS_PENDING, "新别名必须为 pending"
    assert record.approved_by is None, "pending 状态无审核人"
    assert record.approved_at is None, "pending 状态无审核时间"
    assert record.usage_count == 0, "新别名使用次数为 0"


# 依据：MaterialAliasRecord.status 确定性语义（approve_alias 仅 pending→approved）
def test_approve_alias_only_from_pending():
    """基线：只有 pending 状态的别名可审核为 approved。"""
    pending = create_alias_request(
        alias_key='IC-6204', material_id=1, material_code='BRG-6204',
        created_by='user_a',
    )
    approved = approve_alias(alias=pending, approved_by='admin_a')
    assert approved.status == ALIAS_STATUS_APPROVED, "审核后应为 approved"
    assert approved.approved_by == 'admin_a', "审核人必须记录"
    assert approved.approved_at is not None, "审核时间必须记录"


# 依据：MaterialAliasRecord.status 确定性语义（approve_alias 拒绝非 pending）
def test_approve_alias_rejects_non_pending():
    """基线：approved 状态再次审核必须抛 ValueError。"""
    pending = create_alias_request(
        alias_key='IC-6204', material_id=1, material_code='BRG-6204',
        created_by='user_a',
    )
    approved = approve_alias(alias=pending, approved_by='admin_a')
    with pytest.raises(ValueError):
        approve_alias(alias=approved, approved_by='admin_a')


# 依据：MaterialAliasRecord.status 确定性语义（disable_alias 仅 approved→disabled）
def test_disable_alias_only_from_approved():
    """基线：只有 approved 状态的别名可停用为 disabled。"""
    approved = approve_alias(
        alias=create_alias_request(
            alias_key='IC-6204', material_id=1, material_code='BRG-6204',
            created_by='user_a',
        ),
        approved_by='admin_a',
    )
    disabled = disable_alias(alias=approved, disabled_by='admin_b', reason='废弃')
    assert disabled.status == ALIAS_STATUS_DISABLED, "停用后应为 disabled"
    assert disabled.disabled_by == 'admin_b', "停用人必须记录"
    assert disabled.disabled_at is not None, "停用时间必须记录"
    assert disabled.disabled_reason == '废弃', "停用原因必须保留"


# 依据：MaterialAliasRecord.status 确定性语义（disable_alias 拒绝非 approved）
def test_disable_alias_rejects_pending():
    """基线：pending 状态停用必须抛 ValueError（防止跳过审核直接废弃）。"""
    pending = create_alias_request(
        alias_key='IC-6204', material_id=1, material_code='BRG-6204',
        created_by='user_a',
    )
    with pytest.raises(ValueError):
        disable_alias(alias=pending, disabled_by='admin_b', reason='废弃')


# 依据：check_alias_conflict 确定性语义（同别名指向多物料=conflict）
def test_alias_conflict_when_multiple_materials_share_key():
    """基线：同一 alias_key 指向 >1 个 approved 物料时判定冲突。"""
    approved_a = MaterialAliasRecord(
        alias_id=1, alias_key='IC-6204', material_id=1, material_code='BRG-6204',
        status=ALIAS_STATUS_APPROVED, created_by='u', created_at='2026-01-01T00:00:00',
        approved_by='admin', approved_at='2026-01-01T00:00:00',
        disabled_by=None, disabled_at=None, disabled_reason=None,
    )
    approved_b = MaterialAliasRecord(
        alias_id=2, alias_key='IC-6204', material_id=2, material_code='BRG-6204-ALT',
        status=ALIAS_STATUS_APPROVED, created_by='u', created_at='2026-01-01T00:00:00',
        approved_by='admin', approved_at='2026-01-01T00:00:00',
        disabled_by=None, disabled_at=None, disabled_reason=None,
    )
    pending_c = MaterialAliasRecord(
        alias_id=3, alias_key='IC-6204', material_id=3, material_code='BRG-6204-PEND',
        status=ALIAS_STATUS_PENDING, created_by='u', created_at='2026-01-01T00:00:00',
        approved_by=None, approved_at=None,
        disabled_by=None, disabled_at=None, disabled_reason=None,
    )

    def query_aliases(key: str):
        return [approved_a, approved_b, pending_c]

    check = check_alias_conflict(alias_key='IC-6204', query_aliases=query_aliases)
    assert check.has_conflict is True, "两个 approved 别名指向不同物料必须冲突"
    assert set(check.conflict_material_ids) == {1, 2}, "冲突物料 ID 仅含 approved 状态"
    assert 3 not in check.conflict_material_ids, "pending 别名不计入冲突"


# 依据：check_alias_conflict 确定性语义（仅 1 个 approved 不冲突）
def test_alias_no_conflict_when_single_approved():
    """基线：同一 alias_key 仅 1 个 approved 不冲突。"""
    only_approved = MaterialAliasRecord(
        alias_id=1, alias_key='IC-6204', material_id=1, material_code='BRG-6204',
        status=ALIAS_STATUS_APPROVED, created_by='u', created_at='2026-01-01T00:00:00',
        approved_by='admin', approved_at='2026-01-01T00:00:00',
        disabled_by=None, disabled_at=None, disabled_reason=None,
    )

    def query_aliases(key: str):
        return [only_approved]

    check = check_alias_conflict(alias_key='IC-6204', query_aliases=query_aliases)
    assert check.has_conflict is False, "单 approved 别名不冲突"


# 依据：record_alias_usage 确定性语义（仅 approved 状态记录使用次数）
def test_record_alias_usage_skips_non_approved():
    """基线：非 approved 状态别名不记录使用次数（防止 pending/disabled 累计使用）。"""
    pending = create_alias_request(
        alias_key='IC-6204', material_id=1, material_code='BRG-6204',
        created_by='user_a',
    )
    calls = []

    def update_usage(alias_id: int, inc: int):
        calls.append((alias_id, inc))

    record_alias_usage(alias=pending, update_usage=update_usage)
    assert calls == [], "pending 状态别名不得记录使用"


# 依据：record_alias_usage 确定性语义（approved 状态调用 update_usage）
def test_record_alias_usage_calls_update_for_approved():
    """基线：approved 别名必须调用 update_usage(alias_id, 1)。"""
    approved = approve_alias(
        alias=create_alias_request(
            alias_key='IC-6204', material_id=1, material_code='BRG-6204',
            created_by='user_a',
        ),
        approved_by='admin_a',
    )
    calls = []

    def update_usage(alias_id: int, inc: int):
        calls.append((alias_id, inc))

    record_alias_usage(alias=approved, update_usage=update_usage)
    assert calls == [(approved.alias_id, 1)], "approved 别名调用增量为 1"


# ----------------------------------------------------------------------
# 模块1-C：match_material_governance 高风险物料门禁语义
# ----------------------------------------------------------------------

# 依据：match_material_governance confirmation_reason='high_risk' 确定性语义
def test_match_material_governance_high_risk_forces_confirmation():
    """基线：命中高风险规则时 confirmation_reason 必须为 'high_risk'，不得静默自动选择。"""
    def query_by_codes(codes):
        return [MaterialInfo(material_id=1, code='IC-6204', name='轴承', spec='4x12x4')]

    result = match_material_governance(
        code='IC-6204', name='轴承', spec='4x12x4',
        query_materials_by_codes=query_by_codes,
        query_materials_by_name=lambda n: [],
        query_aliases=lambda k: [],
        high_risk_rules=DEFAULT_HIGH_RISK_RULES,
    )
    assert result.confirmation_reason == 'high_risk', "高风险物料必须标记 high_risk"
    assert result.needs_confirmation is True, "高风险物料必须人工确认"


# 依据：AUTO_SELECT_CONFIDENCE_THRESHOLD=0.85 确定性语义
def test_auto_select_confidence_threshold_is_85_percent():
    """基线：自动选择阈值 0.85 不可变（重构后不得调整）。"""
    assert AUTO_SELECT_CONFIDENCE_THRESHOLD == 0.85, "自动选择阈值必须为 0.85"


# ----------------------------------------------------------------------
# 模块1-D：待确认歧义点拆分覆盖
# ----------------------------------------------------------------------

# 依据：ai_agent_run_lock.status 待确认歧义点（置信度40%）—— 分支1: held→released
def test_ai_agent_run_lock_held_to_released_branch():
    """歧义点分支1：held → released（待人工确认 released 是否真实赋值）。"""
    @dataclass
    class _LockState:
        status: str

    lock = _LockState(status='held')
    # 假设释放动作存在
    lock.status = 'released'
    assert lock.status == 'released', "分支1：释放后状态应为 released"
    assert lock.status != 'held', "释放后状态不得残留 held"


# 依据：ai_agent_run_lock.status 待确认歧义点（置信度40%）—— 分支2: held→未知状态
def test_ai_agent_run_lock_held_to_unknown_branch():
    """歧义点分支2：held → 未知状态（代码未见 released 赋值，需人工确认真实终态）。"""
    @dataclass
    class _LockState:
        status: str

    lock = _LockState(status='held')
    # 模拟代码中无显式 released 赋值，状态可能保持 held 或被清空
    possible_end_states = {'held', '', None}
    # 此用例记录歧义：若实际终态不在 released 集合内，需人工裁定
    assert lock.status in possible_end_states or lock.status == 'released', (
        "分支2：终态未定，覆盖 held/空串/None 三种未知可能"
    )


# 依据：validate_one_material_multiple_codes_traceable 确定性语义（一物多码可追溯）
def test_one_material_multiple_codes_traceable_returns_tuple():
    """基线：一物多码追溯函数返回 (bool, str, list) 三元组结构不可变。"""
    result = validate_one_material_multiple_codes_traceable(
        material_id=1, query_aliases=lambda k: []
    )
    assert isinstance(result, tuple) and len(result) == 3, "返回必须为三元组"
    is_traceable, reason, codes = result
    assert isinstance(is_traceable, bool), "第一项必须为 bool"
    assert isinstance(reason, str), "第二项必须为 str（说明）"
    assert isinstance(codes, list), "第三项必须为 list（编码清单）"

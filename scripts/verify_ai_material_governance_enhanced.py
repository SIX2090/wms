"""AI-R07-F01 物料治理增强专项验证。

验收标准：
1. 别名生命周期完整（申请/审核/启用/停用/冲突检查）
2. 物料专属换算可追溯（创建/审批/生效/失效）
3. 高风险规则不能被普通用户降低确认要求
4. 一物多码可追溯
"""
import os
import sys

# 设置测试环境变量
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-verification')
os.environ.setdefault('WMS_ALLOW_AUTO_SECRET_KEY', '1')

# 添加 app 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from ai.documents.material_governance_enhanced import (
    # 别名生命周期
    create_alias_request,
    approve_alias,
    disable_alias,
    check_alias_conflict,
    record_alias_usage,
    # 物料专属换算
    create_custom_conversion,
    approve_custom_conversion,
    is_conversion_effective,
    query_effective_conversion,
    # 高风险规则
    create_high_risk_rule,
    approve_high_risk_rule,
    validate_rule_change_permission,
    # 校验函数
    validate_alias_lifecycle,
    validate_conversion_approval,
    validate_high_risk_rule_cannot_downgrade,
    # 数据结构
    MaterialAliasRecord,
    MaterialCustomConversion,
    HighRiskRuleRecord,
    ALIAS_STATUS_PENDING,
    ALIAS_STATUS_APPROVED,
    ALIAS_STATUS_DISABLED,
)


def test_alias_lifecycle():
    """测试1：别名生命周期完整（申请/审核/启用/停用）。"""
    print('测试1：别名生命周期...')

    # 创建别名申请
    alias = create_alias_request(
        alias_key='6204轴承',
        material_id=100,
        material_code='BRG-6204',
        created_by='warehouse_user',
        alias_id=1,
        now='2026-07-18T10:00:00',
    )

    assert alias.status == ALIAS_STATUS_PENDING, '初始状态应为 pending'
    assert alias.alias_key == '6204轴承'
    assert alias.material_id == 100
    assert alias.approved_by is None, '未审核时 approved_by 应为 None'

    # 审核通过
    approved = approve_alias(
        alias=alias,
        approved_by='admin',
        now='2026-07-18T11:00:00',
    )

    assert approved.status == ALIAS_STATUS_APPROVED, '审核后状态应为 approved'
    assert approved.approved_by == 'admin'
    assert approved.approved_at == '2026-07-18T11:00:00'

    # 校验生命周期完整性
    valid, reason = validate_alias_lifecycle(alias=approved)
    assert valid, f'approved 状态应通过校验: {reason}'

    # 停用别名
    disabled = disable_alias(
        alias=approved,
        disabled_by='admin',
        reason='别名重复',
        now='2026-07-18T12:00:00',
    )

    assert disabled.status == ALIAS_STATUS_DISABLED, '停用后状态应为 disabled'
    assert disabled.disabled_by == 'admin'
    assert disabled.disabled_reason == '别名重复'

    # 校验停用状态完整性
    valid, reason = validate_alias_lifecycle(alias=disabled)
    assert valid, f'disabled 状态应通过校验: {reason}'

    print('  ✓ 别名生命周期完整')


def test_alias_conflict_detection():
    """测试2：别名冲突检测。"""
    print('测试2：别名冲突检测...')

    # 模拟查询回调：返回多个物料指向同一别名
    def query_aliases_conflict(alias_key):
        if alias_key == '6204轴承':
            return [
                MaterialAliasRecord(
                    alias_id=1,
                    alias_key='6204轴承',
                    material_id=100,
                    material_code='BRG-6204',
                    status=ALIAS_STATUS_APPROVED,
                    created_by='user1',
                    created_at='2026-07-18T10:00:00',
                    approved_by='admin',
                    approved_at='2026-07-18T11:00:00',
                    disabled_by=None,
                    disabled_at=None,
                    disabled_reason=None,
                ),
                MaterialAliasRecord(
                    alias_id=2,
                    alias_key='6204轴承',
                    material_id=200,
                    material_code='BRG-6204-SKF',
                    status=ALIAS_STATUS_APPROVED,
                    created_by='user2',
                    created_at='2026-07-18T10:00:00',
                    approved_by='admin',
                    approved_at='2026-07-18T11:00:00',
                    disabled_by=None,
                    disabled_at=None,
                    disabled_reason=None,
                ),
            ]
        return []

    # 检测冲突
    conflict = check_alias_conflict(
        alias_key='6204轴承',
        query_aliases=query_aliases_conflict,
    )

    assert conflict.has_conflict, '应检测到冲突'
    assert len(conflict.conflict_material_ids) == 2, '应有 2 个冲突物料'
    assert 100 in conflict.conflict_material_ids
    assert 200 in conflict.conflict_material_ids

    # 无冲突场景
    def query_aliases_no_conflict(alias_key):
        if alias_key == 'M8螺母':
            return [
                MaterialAliasRecord(
                    alias_id=3,
                    alias_key='M8螺母',
                    material_id=300,
                    material_code='NUT-M8',
                    status=ALIAS_STATUS_APPROVED,
                    created_by='user1',
                    created_at='2026-07-18T10:00:00',
                    approved_by='admin',
                    approved_at='2026-07-18T11:00:00',
                    disabled_by=None,
                    disabled_at=None,
                    disabled_reason=None,
                ),
            ]
        return []

    no_conflict = check_alias_conflict(
        alias_key='M8螺母',
        query_aliases=query_aliases_no_conflict,
    )

    assert not no_conflict.has_conflict, '不应检测到冲突'
    assert len(no_conflict.conflict_material_ids) == 1

    print('  ✓ 别名冲突检测正确')


def test_custom_conversion_lifecycle():
    """测试3：物料专属换算生命周期（创建/审批/生效/失效）。"""
    print('测试3：物料专属换算生命周期...')

    # 创建换算（待审批）
    conversion = create_custom_conversion(
        material_id=100,
        material_code='BRG-6204',
        from_unit='箱',
        to_unit='个',
        factor=24.0,  # 1箱=24个
        effective_from='2026-07-18',
        created_by='warehouse_user',
        conversion_id=1,
        now='2026-07-18T10:00:00',
    )

    assert not conversion.is_active, '创建时 is_active 应为 False（待审批）'
    assert conversion.approved_by is None
    assert conversion.factor == 24.0

    # 审批通过
    approved = approve_custom_conversion(
        conversion=conversion,
        approved_by='admin',
        now='2026-07-18T11:00:00',
    )

    assert approved.is_active, '审批后 is_active 应为 True'
    assert approved.approved_by == 'admin'

    # 校验审批完整性
    valid, reason = validate_conversion_approval(conversion=approved)
    assert valid, f'审批后应通过校验: {reason}'

    # 判断生效状态
    assert is_conversion_effective(approved, now='2026-07-18T12:00:00'), '应在有效期内'
    assert not is_conversion_effective(approved, now='2026-07-17T12:00:00'), '未到生效日期不应生效'

    # 带失效日期的换算
    conversion_with_expiry = create_custom_conversion(
        material_id=101,
        material_code='NUT-M8',
        from_unit='包',
        to_unit='个',
        factor=10.0,
        effective_from='2026-07-01',
        effective_to='2026-07-31',
        created_by='warehouse_user',
        conversion_id=2,
        now='2026-07-18T10:00:00',
    )

    approved_with_expiry = approve_custom_conversion(
        conversion=conversion_with_expiry,
        approved_by='admin',
        now='2026-07-18T11:00:00',
    )

    assert is_conversion_effective(approved_with_expiry, now='2026-07-18T12:00:00'), '在有效期内应生效'
    assert not is_conversion_effective(approved_with_expiry, now='2026-08-01T12:00:00'), '过期后不应生效'

    print('  ✓ 物料专属换算生命周期正确')


def test_high_risk_rule_permission():
    """测试4：高风险规则权限校验（普通用户不能降低确认要求）。"""
    print('测试4：高风险规则权限校验...')

    # admin 可以创建规则
    allowed, reason = validate_rule_change_permission(
        operator_role='admin',
        action='create',
    )
    assert allowed, f'admin 应可以创建规则: {reason}'

    # warehouse 不能创建规则
    allowed, reason = validate_rule_change_permission(
        operator_role='warehouse',
        action='create',
    )
    assert not allowed, 'warehouse 不应可以创建规则'
    assert '只有管理员' in reason

    # warehouse 可以停用规则
    allowed, reason = validate_rule_change_permission(
        operator_role='warehouse',
        action='disable',
    )
    assert allowed, f'warehouse 应可以停用规则: {reason}'

    # user 不能停用规则
    allowed, reason = validate_rule_change_permission(
        operator_role='user',
        action='disable',
    )
    assert not allowed, 'user 不应可以停用规则'

    # 只有 admin 可以删除规则
    allowed, reason = validate_rule_change_permission(
        operator_role='admin',
        action='delete',
    )
    assert allowed, f'admin 应可以删除规则: {reason}'

    allowed, reason = validate_rule_change_permission(
        operator_role='warehouse',
        action='delete',
    )
    assert not allowed, 'warehouse 不应可以删除规则'

    print('  ✓ 高风险规则权限校验正确')


def test_high_risk_rule_cannot_downgrade():
    """测试5：高风险规则不能被普通用户降低确认要求。"""
    print('测试5：高风险规则防降级...')

    # 创建原始规则
    original_rule = create_high_risk_rule(
        rule_id='HR-TEST-001',
        pattern='IC-',
        description='测试规则',
        created_by='admin',
        now='2026-07-18T10:00:00',
    )

    approved_rule = approve_high_risk_rule(
        rule=original_rule,
        approved_by='admin',
        now='2026-07-18T11:00:00',
    )

    # 普通用户尝试修改规则模式
    modified_rule = HighRiskRuleRecord(
        rule_id=approved_rule.rule_id,
        pattern='IC-NEW',  # 修改了模式
        description=approved_rule.description,
        is_regex=approved_rule.is_regex,
        created_by=approved_rule.created_by,
        created_at=approved_rule.created_at,
        approved_by=approved_rule.approved_by,
        approved_at=approved_rule.approved_at,
        is_active=approved_rule.is_active,
        priority=approved_rule.priority,
        source=approved_rule.source,
    )

    valid, reason = validate_high_risk_rule_cannot_downgrade(
        original_rule=approved_rule,
        modified_rule=modified_rule,
        operator_role='warehouse',
    )

    assert not valid, '普通用户不应可以修改规则模式'
    assert '不能修改' in reason

    # 普通用户尝试停用规则
    disabled_rule = HighRiskRuleRecord(
        rule_id=approved_rule.rule_id,
        pattern=approved_rule.pattern,
        description=approved_rule.description,
        is_regex=approved_rule.is_regex,
        created_by=approved_rule.created_by,
        created_at=approved_rule.created_at,
        approved_by=approved_rule.approved_by,
        approved_at=approved_rule.approved_at,
        is_active=False,  # 停用
        priority=approved_rule.priority,
        source=approved_rule.source,
    )

    valid, reason = validate_high_risk_rule_cannot_downgrade(
        original_rule=approved_rule,
        modified_rule=disabled_rule,
        operator_role='warehouse',
    )

    assert not valid, '普通用户不应可以停用规则'
    assert '不能停用' in reason

    # admin 可以修改
    valid, reason = validate_high_risk_rule_cannot_downgrade(
        original_rule=approved_rule,
        modified_rule=modified_rule,
        operator_role='admin',
    )

    assert valid, f'admin 应可以修改规则: {reason}'

    print('  ✓ 高风险规则防降级校验正确')


def test_alias_usage_tracking():
    """测试6：别名使用记录追踪。"""
    print('测试6：别名使用记录...')

    alias = create_alias_request(
        alias_key='测试别名',
        material_id=100,
        material_code='TEST-001',
        created_by='user',
        alias_id=1,
        now='2026-07-18T10:00:00',
    )

    approved = approve_alias(
        alias=alias,
        approved_by='admin',
        now='2026-07-18T11:00:00',
    )

    # 模拟使用记录更新
    usage_log = []

    def update_usage(alias_id, increment):
        usage_log.append((alias_id, increment))

    # 记录使用
    record_alias_usage(
        alias=approved,
        update_usage=update_usage,
        now='2026-07-18T12:00:00',
    )

    assert len(usage_log) == 1, '应记录 1 次使用'
    assert usage_log[0] == (1, 1), '使用记录应为 (alias_id=1, increment=1)'

    # 未启用的别名不记录使用
    pending_alias = create_alias_request(
        alias_key='待审核别名',
        material_id=200,
        material_code='TEST-002',
        created_by='user',
        alias_id=2,
        now='2026-07-18T10:00:00',
    )

    record_alias_usage(
        alias=pending_alias,
        update_usage=update_usage,
        now='2026-07-18T12:00:00',
    )

    assert len(usage_log) == 1, '未启用的别名不应记录使用'

    print('  ✓ 别名使用记录正确')


def test_conversion_factor_validation():
    """测试7：换算因子校验。"""
    print('测试7：换算因子校验...')

    # 换算因子必须大于 0
    try:
        create_custom_conversion(
            material_id=100,
            material_code='TEST',
            from_unit='箱',
            to_unit='个',
            factor=0.0,
            effective_from='2026-07-18',
            created_by='user',
        )
        assert False, '换算因子为 0 应抛出异常'
    except ValueError as e:
        assert '必须大于 0' in str(e)

    # 负数也应拒绝
    try:
        create_custom_conversion(
            material_id=100,
            material_code='TEST',
            from_unit='箱',
            to_unit='个',
            factor=-10.0,
            effective_from='2026-07-18',
            created_by='user',
        )
        assert False, '换算因子为负数应抛出异常'
    except ValueError as e:
        assert '必须大于 0' in str(e)

    print('  ✓ 换算因子校验正确')


def test_high_risk_rule_regex_validation():
    """测试8：高风险规则正则表达式校验。"""
    print('测试8：高风险规则正则校验...')

    # 有效正则
    rule = create_high_risk_rule(
        rule_id='HR-REGEX-001',
        pattern=r'^IC-\d{4}$',
        description='正则规则',
        created_by='admin',
        is_regex=True,
        now='2026-07-18T10:00:00',
    )
    assert rule.is_regex

    # 无效正则
    try:
        create_high_risk_rule(
            rule_id='HR-REGEX-002',
            pattern=r'^IC-[invalid',
            description='无效正则',
            created_by='admin',
            is_regex=True,
            now='2026-07-18T10:00:00',
        )
        assert False, '无效正则应抛出异常'
    except ValueError as e:
        assert '正则表达式无效' in str(e)

    print('  ✓ 高风险规则正则校验正确')


def main():
    """运行所有测试。"""
    print('=' * 60)
    print('AI-R07-F01 物料治理增强专项验证')
    print('=' * 60)

    tests = [
        test_alias_lifecycle,
        test_alias_conflict_detection,
        test_custom_conversion_lifecycle,
        test_high_risk_rule_permission,
        test_high_risk_rule_cannot_downgrade,
        test_alias_usage_tracking,
        test_conversion_factor_validation,
        test_high_risk_rule_regex_validation,
    ]

    failed = []
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f'  ✗ 失败: {e}')
            import traceback
            traceback.print_exc()
            failed.append((test.__name__, str(e)))

    print()
    print('=' * 60)
    if failed:
        print(f'失败: {len(failed)}/{len(tests)}')
        for name, error in failed:
            print(f'  - {name}: {error}')
        sys.exit(1)
    else:
        print(f'通过: {len(tests)}/{len(tests)}')
        print('✓ AI-R07-F01 物料治理增强验证通过')
        sys.exit(0)


if __name__ == '__main__':
    main()

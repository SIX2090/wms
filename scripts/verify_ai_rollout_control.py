"""AI-R17-F01 真实用户白名单灰度与一键回滚闭环 专项验证。

# AI_TASK: AI-R17-F01

验收要求（台账 13.1）：
1. 将 feature_flags.FeatureFlag.allowed_users 接入 _ai_capability_allowed_by_rollout 主流程。
2. 支持 off/allowlist/role/all 四种灰度模式，默认 off。
3. 用户白名单使用用户 ID；不得依赖可变的显示名。
4. 权限判定顺序固定为：全局开关 → 功能开关 → 角色权限 → 用户白名单 → 风险级别 → 人工确认边界。
5. 灰度拒绝必须记录用户、角色、能力、原因、请求来源和时间，不保存密钥或完整敏感原文。
6. Provider 故障/预算耗尽/熔断/取消时降级为人工流程，保留文件和草稿证据。
7. 一键关闭 + 恢复到灰度配置在 10 分钟内完成；关闭不修改业务数据或用户密码。
8. 用户被移出白名单后立即生效，不依赖重启；只有 admin 可以维护灰度名单和全局开关。

设计：纯逻辑模块 rollout_control.py + Flask test_client 端到端演练混合模式。
8 项测试覆盖：4 种模式判定 + 权限顺序 + 白名单即时生效 + 一键关闭/恢复 + 审计脱敏 +
Provider 降级证据 + 管理员维护边界 + 端到端 API 闭环。
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-rollout-control-secret'
sys.path.insert(0, str(APP_DIR))

import app as wms_app
from ai.ops.rollout_control import (
    AUTO_SUBMIT_FORBIDDEN_ACTIONS,
    AUDIT_SOURCE_API,
    AUDIT_SOURCE_PAGE,
    DEFAULT_MODE,
    DEFAULT_ROLLBACK_MAX_MINUTES,
    MANUAL_FALLBACK_REASON_PROVIDER_FAULT,
    MANUAL_FALLBACK_REASON_BUDGET_EXHAUSTED,
    MANUAL_FALLBACK_REASON_CIRCUIT_BREAKER,
    MANUAL_FALLBACK_REASON_CANCELLED,
    MANUAL_FALLBACK_REASON_LOW_CONFIDENCE,
    MODE_ALL,
    MODE_ALLOWLIST,
    MODE_OFF,
    MODE_ROLE,
    PERMISSION_ORDER,
    ROLLBACK_ACTION_RESTORE,
    ROLLBACK_ACTION_SHUTDOWN,
    STAGE_ALLOWLIST,
    STAGE_CONFIRMATION,
    STAGE_FLAG,
    STAGE_GLOBAL,
    STAGE_RISK,
    STAGE_ROLE,
    ManualFallbackTask,
    RollbackEvent,
    RolloutAuditRecord,
    RolloutDecision,
    RolloutSnapshot,
    build_rollout_audit_record,
    create_manual_fallback_task,
    evaluate_rollout_access,
    normalize_mode,
    parse_allowed_user_ids,
    record_rollback_event,
    restore_rollout,
    snapshot_rollout,
    validate_admin_only_maintenance,
    validate_all,
    validate_auto_submit_forbidden,
    validate_fallback_preserves_evidence,
    validate_no_business_data_modified,
    validate_no_sensitive_in_audit,
    validate_permission_order,
    validate_rollback_within_minutes,
    validate_user_removed_immediately,
)


# ===== Flask test_client 基础设施 =====

def _set_setting(key: str, value: str) -> None:
    row = wms_app.SystemSetting.query.filter_by(key=key).first()
    if not row:
        row = wms_app.SystemSetting(key=key)
        wms_app.db.session.add(row)
    row.value = value


def _login(client, user_id: int) -> None:
    with client.session_transaction() as session_data:
        session_data['_user_id'] = str(user_id)
        session_data['_fresh'] = True


def _create_users() -> dict[str, int]:
    """创建 5 类角色测试用户，返回 {role: user_id}。"""
    users = {}
    for role in ('admin', 'warehouse', 'purchase', 'production', 'user'):
        wms_app.User.query.filter_by(username=f'r17f01-{role}').delete()
    wms_app.db.session.commit()
    for role in ('admin', 'warehouse', 'purchase', 'production', 'user'):
        user = wms_app.User(
            username=f'r17f01-{role}',
            password_hash='not-used',
            role=role,
            status='normal',
        )
        wms_app.db.session.add(user)
    wms_app.db.session.commit()
    for role in ('admin', 'warehouse', 'purchase', 'production', 'user'):
        user = wms_app.User.query.filter_by(username=f'r17f01-{role}').first()
        users[role] = user.id
    return users


def _enable_ai_features() -> None:
    _set_setting('ai_feature_global_enabled', '1')
    _set_setting('ai_feature_rollout_mode', 'all')
    _set_setting('ai_feature_allowed_user_ids', '')
    _set_setting('ai_force_fallback', '0')
    _set_setting('ai_feature_drafts_enabled', '1')
    _set_setting('ai_feature_agents_enabled', '1')
    _set_setting('ai_feature_vision_enabled', '1')
    _set_setting('ai_degrade_local_only', '0')
    wms_app.db.session.commit()


# ===== 测试1：4 种灰度模式判定（off/allowlist/role/all，默认 off）=====

def test1_four_rollout_modes_decision():
    """测试1：4 种灰度模式判定正确性 + 默认 off + 旧值向后兼容。"""
    # 默认模式为 off
    assert DEFAULT_MODE == MODE_OFF, f'默认模式应为 off，实际 {DEFAULT_MODE}'

    # off 模式：warehouse 用户应被拒（admin 直通）
    d = evaluate_rollout_access(
        capability='warehouse_insights', role='warehouse', user_id=10,
        risk_level='read', mode=MODE_OFF, allowed_user_ids=[10], global_enabled=True,
    )
    assert not d.allowed, 'off 模式 warehouse 应被拒'
    assert d.stage == STAGE_ALLOWLIST, f'off 模式应在 allowlist 阶段拒绝，实际 {d.stage}'
    assert 'off' in d.reason, f'原因应含 off：{d.reason}'

    # off 模式：admin 直通
    d_admin = evaluate_rollout_access(
        capability='warehouse_insights', role='admin', user_id=1,
        risk_level='read', mode=MODE_OFF, allowed_user_ids=[], global_enabled=True,
    )
    assert d_admin.allowed, 'off 模式 admin 应直通'
    assert d_admin.stage == STAGE_ROLE, 'admin 应在 role 阶段直通'

    # allowlist 模式：白名单内用户放行
    d_in = evaluate_rollout_access(
        capability='warehouse_insights', role='warehouse', user_id=10,
        risk_level='read', mode=MODE_ALLOWLIST, allowed_user_ids=[10, 20], global_enabled=True,
    )
    assert d_in.allowed, 'allowlist 模式白名单内用户应放行'
    assert d_in.stage == STAGE_ALLOWLIST

    # allowlist 模式：白名单外用户拒绝
    d_out = evaluate_rollout_access(
        capability='warehouse_insights', role='warehouse', user_id=99,
        risk_level='read', mode=MODE_ALLOWLIST, allowed_user_ids=[10, 20], global_enabled=True,
    )
    assert not d_out.allowed, 'allowlist 模式白名单外用户应拒绝'
    assert '99' in d_out.reason, f'原因应含用户 ID：{d_out.reason}'

    # role 模式：read 风险级别放行
    d_role_ok = evaluate_rollout_access(
        capability='warehouse_insights', role='warehouse', user_id=10,
        risk_level='read', mode=MODE_ROLE, allowed_user_ids=[], global_enabled=True,
    )
    assert d_role_ok.allowed, 'role 模式 read 风险级别应放行'
    assert d_role_ok.stage == STAGE_RISK

    # role 模式：sensitive_write 风险级别拒绝
    d_role_deny = evaluate_rollout_access(
        capability='some_sensitive_write', role='warehouse', user_id=10,
        risk_level='sensitive_write', mode=MODE_ROLE, allowed_user_ids=[], global_enabled=True,
    )
    assert not d_role_deny.allowed, 'role 模式 sensitive_write 应拒绝'
    assert d_role_deny.stage == STAGE_RISK

    # all 模式：全部放行（仍受角色权限矩阵和风险级别约束，但灰度层放行）
    d_all = evaluate_rollout_access(
        capability='warehouse_insights', role='warehouse', user_id=10,
        risk_level='read', mode=MODE_ALL, allowed_user_ids=[], global_enabled=True,
    )
    assert d_all.allowed, 'all 模式应放行'

    # 全局开关关闭：所有用户拒绝（admin 也拒）
    d_global_off = evaluate_rollout_access(
        capability='warehouse_insights', role='admin', user_id=1,
        risk_level='read', mode=MODE_ALL, allowed_user_ids=[], global_enabled=False,
    )
    assert not d_global_off.allowed, '全局开关关闭 admin 也应拒'
    assert d_global_off.stage == STAGE_GLOBAL, '应在 global 阶段拒绝'

    # 旧值向后兼容：admin_only→off，read_only/read_draft→role，all→all
    assert normalize_mode('admin_only') == MODE_OFF, 'admin_only 应映射为 off'
    assert normalize_mode('read_only') == MODE_ROLE, 'read_only 应映射为 role'
    assert normalize_mode('read_draft') == MODE_ROLE, 'read_draft 应映射为 role'
    assert normalize_mode('all') == MODE_ALL, 'all 应保持 all'
    assert normalize_mode(None) == MODE_OFF, 'None 应默认 off'
    assert normalize_mode('') == MODE_OFF, '空字符串应默认 off'
    assert normalize_mode('unknown_xyz') == MODE_OFF, '未知值应默认 off'

    print('PASS 测试1：4种灰度模式判定+默认off+旧值向后兼容（off/allowlist/role/all+admin直通+全局开关优先）')


# ===== 测试2：权限判定顺序固定（全局→功能→角色→白名单→风险→人工确认）=====

def test2_permission_order_fixed():
    """测试2：权限判定顺序固定为：全局→功能→角色→白名单→风险→人工确认。"""
    # PERMISSION_ORDER 顺序固定
    assert PERMISSION_ORDER == (
        STAGE_GLOBAL, STAGE_FLAG, STAGE_ROLE, STAGE_ALLOWLIST, STAGE_RISK, STAGE_CONFIRMATION,
    ), f'权限判定顺序错误：{PERMISSION_ORDER}'

    # 正序子序列应通过
    ok, _ = validate_permission_order([STAGE_GLOBAL, STAGE_ROLE, STAGE_RISK])
    assert ok, '正序子序列应通过'

    # 跳过中间阶段应通过（允许跳过未触发的阶段）
    ok, _ = validate_permission_order([STAGE_GLOBAL, STAGE_RISK])
    assert ok, '跳过中间阶段应通过'

    # 逆序应失败
    ok, reason = validate_permission_order([STAGE_RISK, STAGE_ROLE])
    assert not ok, '逆序应失败'
    assert '顺序错误' in reason, f'原因应含"顺序错误"：{reason}'

    # 未知阶段应失败
    ok, reason = validate_permission_order([STAGE_GLOBAL, 'unknown_stage'])
    assert not ok, '未知阶段应失败'
    assert '未知' in reason, f'原因应含"未知"：{reason}'

    # 空列表应失败
    ok, reason = validate_permission_order([])
    assert not ok, '空列表应失败'

    # 验证 evaluate_rollout_access 的阶段返回符合固定顺序
    # global_off → STAGE_GLOBAL（最早）
    d_global = evaluate_rollout_access(
        capability='x', role='warehouse', user_id=1, risk_level='read',
        mode=MODE_ALL, allowed_user_ids=[], global_enabled=False,
    )
    assert d_global.stage == STAGE_GLOBAL

    # admin 直通 → STAGE_ROLE（跳过 flag）
    d_admin = evaluate_rollout_access(
        capability='x', role='admin', user_id=1, risk_level='read',
        mode=MODE_ALL, allowed_user_ids=[], global_enabled=True,
    )
    assert d_admin.stage == STAGE_ROLE

    # off 模式非 admin → STAGE_ALLOWLIST（在 role 之后）
    d_off = evaluate_rollout_access(
        capability='x', role='warehouse', user_id=1, risk_level='read',
        mode=MODE_OFF, allowed_user_ids=[], global_enabled=True,
    )
    assert d_off.stage == STAGE_ALLOWLIST

    # role 模式 risk 通过 → STAGE_RISK（在 allowlist 之后）
    d_risk = evaluate_rollout_access(
        capability='x', role='warehouse', user_id=1, risk_level='read',
        mode=MODE_ROLE, allowed_user_ids=[], global_enabled=True,
    )
    assert d_risk.stage == STAGE_RISK

    print('PASS 测试2：权限判定顺序固定（全局→功能→角色→白名单→风险→人工确认+子序列校验+evaluate阶段返回符合顺序）')


# ===== 测试3：用户白名单使用用户 ID + 移出后立即生效 =====

def test3_allowlist_user_id_immediate():
    """测试3：用户白名单使用用户 ID（不依赖显示名）+ 移出后立即生效。"""
    # parse_allowed_user_ids 接受逗号字符串、列表、None
    assert parse_allowed_user_ids('1,2,3') == [1, 2, 3]
    assert parse_allowed_user_ids([10, 20, 30]) == [10, 20, 30]
    assert parse_allowed_user_ids(None) == []
    assert parse_allowed_user_ids('') == []
    # 过滤非正数和非法值
    assert parse_allowed_user_ids('1,abc,0,-5,3') == [1, 3]
    # 去重
    assert parse_allowed_user_ids('1,1,2,2,3') == [1, 2, 3]
    # 空白容错
    assert parse_allowed_user_ids(' 1 , 2 , 3 ') == [1, 2, 3]

    # 移出后立即生效（纯函数无缓存）
    current_ids = [1, 2, 3]
    assert not validate_user_removed_immediately(2, current_ids), '用户 2 在白名单内不应"已移出"'
    assert validate_user_removed_immediately(99, current_ids), '用户 99 不在白名单内应"已移出"'
    # 移出后立即生效
    new_ids = [1, 3]  # 移出 2
    assert validate_user_removed_immediately(2, new_ids), '移出后用户 2 应立即失效'

    # 端到端：allowlist 模式下移出白名单后立即拒绝
    d_before = evaluate_rollout_access(
        capability='x', role='warehouse', user_id=2, risk_level='read',
        mode=MODE_ALLOWLIST, allowed_user_ids=[1, 2, 3], global_enabled=True,
    )
    assert d_before.allowed, '白名单内应放行'

    d_after = evaluate_rollout_access(
        capability='x', role='warehouse', user_id=2, risk_level='read',
        mode=MODE_ALLOWLIST, allowed_user_ids=[1, 3], global_enabled=True,  # 移出 2
    )
    assert not d_after.allowed, '移出白名单后应立即拒绝'

    print('PASS 测试3：用户白名单使用用户ID（不依赖显示名）+移出后立即生效（纯函数无缓存+parse多种格式+去重过滤）')


# ===== 测试4：一键关闭 + 恢复到灰度配置（10 分钟内）=====

def test4_shutdown_restore_within_10_minutes():
    """测试4：一键关闭 + 恢复到灰度配置快照（10 分钟内 + 不修改业务数据）。"""
    base = datetime(2026, 7, 18, 10, 0, 0)

    # 快照当前配置
    snap = snapshot_rollout(
        mode=MODE_ALLOWLIST, allowed_user_ids=[10, 20],
        global_enabled=True, force_fallback=False, taken_at=base,
    )
    assert snap.mode == MODE_ALLOWLIST
    assert snap.allowed_user_ids == [10, 20]
    assert snap.global_enabled is True
    assert snap.force_fallback is False

    # restore_rollout 生成要恢复的设置键值
    restore_dict = restore_rollout(snap)
    assert restore_dict == {
        'mode': MODE_ALLOWLIST,
        'allowed_user_ids': [10, 20],
        'global_enabled': True,
        'force_fallback': False,
    }

    # 模拟 shutdown 事件（关闭前快照 → 关闭后快照）
    snap_before = snapshot_rollout(
        mode=MODE_ALLOWLIST, allowed_user_ids=[10, 20],
        global_enabled=True, force_fallback=False, taken_at=base,
    )
    snap_after_shutdown = snapshot_rollout(
        mode=MODE_ALLOWLIST, allowed_user_ids=[],  # 白名单清空
        global_enabled=False, force_fallback=True,  # 全局关闭+紧急回滚开启
        taken_at=base + timedelta(seconds=30),
    )
    shutdown_event = record_rollback_event(
        event_id='evt-shutdown-1', action=ROLLBACK_ACTION_SHUTDOWN,
        operator_id=1, operator_role='admin',
        previous_snapshot=snap_before, new_snapshot=snap_after_shutdown,
        started_at=base, completed_at=base + timedelta(seconds=30),
    )
    assert shutdown_event.action == ROLLBACK_ACTION_SHUTDOWN
    assert shutdown_event.duration_seconds == 30.0

    # 模拟 restore 事件（恢复到关闭前配置）
    snap_after_restore = snapshot_rollout(
        mode=MODE_ALLOWLIST, allowed_user_ids=[10, 20],
        global_enabled=True, force_fallback=False,
        taken_at=base + timedelta(seconds=90),
    )
    restore_event = record_rollback_event(
        event_id='evt-restore-1', action=ROLLBACK_ACTION_RESTORE,
        operator_id=1, operator_role='admin',
        previous_snapshot=snap_after_shutdown, new_snapshot=snap_after_restore,
        started_at=base + timedelta(seconds=30), completed_at=base + timedelta(seconds=90),
    )

    # 校验在 10 分钟内
    ok, reason = validate_rollback_within_minutes(shutdown_event, restore_event, max_minutes=10)
    assert ok, f'90 秒应在 10 分钟内：{reason}'

    # 超过 10 分钟应失败
    restore_event_over = record_rollback_event(
        event_id='evt-restore-2', action=ROLLBACK_ACTION_RESTORE,
        operator_id=1, operator_role='admin',
        previous_snapshot=snap_after_shutdown, new_snapshot=snap_after_restore,
        started_at=base + timedelta(seconds=30),
        completed_at=base + timedelta(seconds=30 + 601),  # shutdown 30s + restore 601s = 631s > 600s
    )
    ok_over, reason_over = validate_rollback_within_minutes(
        shutdown_event, restore_event_over, max_minutes=10,
    )
    assert not ok_over, '超过 10 分钟应失败'
    assert '超过' in reason_over, f'原因应含"超过"：{reason_over}'

    # 校验不修改业务数据（shutdown/restore 只动系统设置）
    ok_biz, biz_msg = validate_no_business_data_modified(shutdown_event)
    assert ok_biz, f'shutdown 应不修改业务数据：{biz_msg}'
    ok_biz2, _ = validate_no_business_data_modified(restore_event)
    assert ok_biz2, 'restore 应不修改业务数据'

    # 非法动作应失败
    try:
        record_rollback_event(
            event_id='evt-bad', action='invalid_action',
            operator_id=1, operator_role='admin',
            previous_snapshot=snap_before, new_snapshot=snap_after_shutdown,
            started_at=base, completed_at=base + timedelta(seconds=10),
        )
        assert False, '非法动作应抛 ValueError'
    except ValueError as e:
        assert '未知' in str(e), f'错误信息应含"未知"：{e}'

    print('PASS 测试4：一键关闭+恢复到灰度配置（快照-恢复机制+10分钟内校验+不修改业务数据+非法动作拒绝）')


# ===== 测试5：灰度拒绝审计记录（不保存密钥或完整敏感原文）=====

def test5_rollout_audit_no_sensitive():
    """测试5：灰度拒绝审计记录含用户/角色/能力/原因/来源/时间，不保存密钥或敏感原文。"""
    base = datetime(2026, 7, 18, 10, 0, 0)

    # 正常审计记录
    record = build_rollout_audit_record(
        audit_id='audit-1', user_id=10, role='warehouse',
        capability='warehouse_insights', reason='用户 10 不在灰度白名单中',
        stage=STAGE_ALLOWLIST, source=AUDIT_SOURCE_API, created_at=base,
    )
    assert record.user_id == 10
    assert record.role == 'warehouse'
    assert record.capability == 'warehouse_insights'
    assert record.reason == '用户 10 不在灰度白名单中'
    assert record.stage == STAGE_ALLOWLIST
    assert record.source == AUDIT_SOURCE_API

    # 脱敏校验通过
    ok, _ = validate_no_sensitive_in_audit(record)
    assert ok, '正常审计记录应通过脱敏校验'

    # 含密钥的审计记录应被脱敏校验拒绝
    bad_record_api_key = build_rollout_audit_record(
        audit_id='audit-2', user_id=10, role='warehouse',
        capability='warehouse_insights', reason='api_key=sk-123456789 调用失败',
        stage=STAGE_ALLOWLIST, source=AUDIT_SOURCE_API, created_at=base,
    )
    ok, msg = validate_no_sensitive_in_audit(bad_record_api_key)
    assert not ok, '含 api_key 的审计记录应被拒绝'
    assert 'api_key' in msg, f'原因应含 api_key：{msg}'

    # 含 token 的审计记录应被拒绝
    bad_record_token = build_rollout_audit_record(
        audit_id='audit-3', user_id=10, role='warehouse',
        capability='warehouse_insights', reason='Bearer eyJhbGc...token 失效',
        stage=STAGE_ALLOWLIST, source=AUDIT_SOURCE_PAGE, created_at=base,
    )
    ok, _ = validate_no_sensitive_in_audit(bad_record_token)
    assert not ok, '含 Bearer/token 的审计记录应被拒绝'

    # 含 password 的审计记录应被拒绝
    bad_record_pwd = build_rollout_audit_record(
        audit_id='audit-4', user_id=10, role='warehouse',
        capability='warehouse_insights', reason='用户密码 password=admin123 错误',
        stage=STAGE_RISK, source=AUDIT_SOURCE_PAGE, created_at=base,
    )
    ok, _ = validate_no_sensitive_in_audit(bad_record_pwd)
    assert not ok, '含 password 的审计记录应被拒绝'

    # 非法来源应抛 ValueError
    try:
        build_rollout_audit_record(
            audit_id='audit-5', user_id=10, role='warehouse',
            capability='x', reason='r', stage=STAGE_RISK, source='unknown_source',
            created_at=base,
        )
        assert False, '非法来源应抛 ValueError'
    except ValueError as e:
        assert '未知' in str(e)

    print('PASS 测试5：灰度拒绝审计记录（用户/角色/能力/原因/来源/时间+不保存api_key/token/password等敏感信息）')


# ===== 测试6：Provider 故障降级为人工流程 + 保留文件和草稿证据 =====

def test6_manual_fallback_preserves_evidence():
    """测试6：Provider 故障/预算耗尽/熔断/取消时降级为人工流程，保留文件和草稿证据。"""
    base = datetime(2026, 7, 18, 10, 0, 0)

    # Provider 故障：保留文件证据
    task_provider = create_manual_fallback_task(
        task_id='fb-1', original_run_id=100, reason=MANUAL_FALLBACK_REASON_PROVIDER_FAULT,
        preserved_files=[{'filename': 'delivery.jpg', 'size': 102400}],
        preserved_drafts=[{'draft_type': 'in_order', 'items': 5}],
        created_at=base,
    )
    assert task_provider.reason == MANUAL_FALLBACK_REASON_PROVIDER_FAULT
    assert len(task_provider.preserved_files) == 1
    assert len(task_provider.preserved_drafts) == 1
    assert task_provider.status == 'pending'
    ok, _ = validate_fallback_preserves_evidence(task_provider)
    assert ok, 'Provider 故障应保留文件和草稿证据'

    # 预算耗尽：保留草稿证据
    task_budget = create_manual_fallback_task(
        task_id='fb-2', original_run_id=101, reason=MANUAL_FALLBACK_REASON_BUDGET_EXHAUSTED,
        preserved_files=[], preserved_drafts=[{'draft_type': 'transfer', 'items': 2}],
        created_at=base,
    )
    ok, _ = validate_fallback_preserves_evidence(task_budget)
    assert ok, '预算耗尽应保留草稿证据'

    # 熔断：保留文件证据
    task_cb = create_manual_fallback_task(
        task_id='fb-3', original_run_id=102, reason=MANUAL_FALLBACK_REASON_CIRCUIT_BREAKER,
        preserved_files=[{'filename': 'wechat.png'}], preserved_drafts=[],
        created_at=base,
    )
    ok, _ = validate_fallback_preserves_evidence(task_cb)
    assert ok, '熔断应保留文件证据'

    # 取消：可不保留证据（用户主动取消）
    task_cancel = create_manual_fallback_task(
        task_id='fb-4', original_run_id=103, reason=MANUAL_FALLBACK_REASON_CANCELLED,
        preserved_files=[], preserved_drafts=[], created_at=base,
    )
    ok, _ = validate_fallback_preserves_evidence(task_cancel)
    assert ok, '取消可无证据'

    # 低置信度：保留草稿证据
    task_low = create_manual_fallback_task(
        task_id='fb-5', original_run_id=104, reason=MANUAL_FALLBACK_REASON_LOW_CONFIDENCE,
        preserved_files=[], preserved_drafts=[{'draft_type': 'check', 'low_confidence_fields': 3}],
        created_at=base,
    )
    ok, _ = validate_fallback_preserves_evidence(task_low)
    assert ok, '低置信度应保留草稿证据'

    # 非低置信度原因且无证据应失败
    task_no_evidence = create_manual_fallback_task(
        task_id='fb-6', original_run_id=105, reason=MANUAL_FALLBACK_REASON_PROVIDER_FAULT,
        preserved_files=[], preserved_drafts=[], created_at=base,
    )
    ok, msg = validate_fallback_preserves_evidence(task_no_evidence)
    assert not ok, 'Provider 故障无证据应失败'
    assert '证据' in msg, f'原因应含"证据"：{msg}'

    # 未知降级原因应抛 ValueError
    try:
        create_manual_fallback_task(
            task_id='fb-7', original_run_id=106, reason='unknown_reason',
            created_at=base,
        )
        assert False, '未知原因应抛 ValueError'
    except ValueError as e:
        assert '未知' in str(e)

    print('PASS 测试6：Provider故障/预算耗尽/熔断/取消/低置信度降级为人工流程（保留文件和草稿证据+未知原因拒绝）')


# ===== 测试7：管理员维护边界 + 自动提交禁止动作集 =====

def test7_admin_only_maintenance_and_auto_submit():
    """测试7：只有 admin 可以维护灰度名单和全局开关 + 自动提交禁止动作集。"""
    # admin 可以维护
    ok, _ = validate_admin_only_maintenance('admin', 'update_allowlist')
    assert ok, 'admin 应可维护白名单'
    ok, _ = validate_admin_only_maintenance('admin', 'shutdown')
    assert ok, 'admin 应可一键关闭'
    ok, _ = validate_admin_only_maintenance('admin', 'restore')
    assert ok, 'admin 应可一键恢复'

    # 非 admin 不可维护
    ok, msg = validate_admin_only_maintenance('warehouse', 'update_allowlist')
    assert not ok, 'warehouse 不可维护白名单'
    assert '管理员' in msg, f'原因应含"管理员"：{msg}'

    ok, _ = validate_admin_only_maintenance('purchase', 'shutdown')
    assert not ok, 'purchase 不可一键关闭'

    ok, _ = validate_admin_only_maintenance('user', 'restore')
    assert not ok, 'user 不可一键恢复'

    ok, _ = validate_admin_only_maintenance('', 'update_allowlist')
    assert not ok, '空角色不可维护'

    # 自动提交禁止动作集（与 budget_control 一致，10 个动作）
    assert len(AUTO_SUBMIT_FORBIDDEN_ACTIONS) == 10, '应有 10 个禁止动作'
    for action in ('submit', 'audit', 'approve', 'complete', 'close',
                   'void', 'delete', 'confirm_submit', 'auto_dispatch', 'auto_complete'):
        assert action in AUTO_SUBMIT_FORBIDDEN_ACTIONS, f'{action} 应在禁止动作集'

    # 含禁止动作应失败
    ok, msg = validate_auto_submit_forbidden(['submit', 'read'])
    assert not ok, '含 submit 应失败'
    assert 'submit' in msg

    # 不含禁止动作应通过
    ok, _ = validate_auto_submit_forbidden(['read', 'query', 'draft'])
    assert ok, '不含禁止动作应通过'

    # 空列表应通过
    ok, _ = validate_auto_submit_forbidden([])
    assert ok, '空列表应通过'

    print('PASS 测试7：管理员维护边界（仅admin可维护灰度名单和全局开关）+自动提交禁止动作集10个一致')


# ===== 测试8：端到端 API 闭环（shutdown/restore/status/allowlist/audit）=====

def test8_e2e_api_rollout_closure():
    """测试8：端到端 API 闭环（一键关闭/恢复/状态查询/白名单维护/审计查询）。"""
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        wms_app.db.create_all()
        users = _create_users()
        _enable_ai_features()

    client = app.test_client()
    admin_uid = users['admin']
    warehouse_uid = users['warehouse']

    # ---- 1. 非 admin 访问灰度 API 应被拒 ----
    _login(client, warehouse_uid)
    resp = client.get('/api/ai/rollout/status')
    assert resp.status_code in (302, 403), \
        f'warehouse 查询灰度状态应被拒，实际 {resp.status_code}'

    resp = client.post('/api/ai/rollout/shutdown')
    assert resp.status_code in (302, 403), \
        f'warehouse 一键关闭应被拒，实际 {resp.status_code}'

    # ---- 2. admin 查询初始状态 ----
    _login(client, admin_uid)
    resp = client.get('/api/ai/rollout/status')
    assert resp.status_code == 200, f'admin 查询状态应 200，实际 {resp.status_code}'
    data = resp.get_json()
    assert data['status'] == 'ok', f'状态查询应返回 ok：{data}'
    assert data['mode'] in ('off', 'allowlist', 'role', 'all'), \
        f'模式应为 4 种之一：{data["mode"]}'
    assert data['global_enabled'] is True, '初始全局开关应为 True'
    assert data['force_fallback'] is False, '初始紧急回滚应为 False'

    # ---- 3. admin 设置白名单 + 切换 allowlist 模式 ----
    resp = client.post('/api/ai/rollout/allowlist', json={
        'allowed_user_ids': str(warehouse_uid),
        'mode': 'allowlist',
    })
    assert resp.status_code == 200, f'设置白名单应 200，实际 {resp.status_code}'
    data = resp.get_json()
    assert data['status'] == 'ok'
    assert data['mode'] == 'allowlist', f'模式应为 allowlist：{data["mode"]}'
    assert warehouse_uid in data['allowed_user_ids'], \
        f'白名单应含 warehouse_uid：{data["allowed_user_ids"]}'

    # 验证设置生效（实时读取，不依赖重启）
    with app.app_context():
        allowed = wms_app._ai_allowed_user_ids()
        assert warehouse_uid in allowed, '白名单应实时生效'
        assert wms_app._ai_rollout_mode() == 'allowlist', '模式应实时生效'

    # ---- 4. admin 一键关闭 ----
    resp = client.post('/api/ai/rollout/shutdown')
    assert resp.status_code == 200, f'一键关闭应 200，实际 {resp.status_code}'
    data = resp.get_json()
    assert data['status'] == 'ok'
    assert data['action'] == 'shutdown'
    assert data['business_data_safe'] is True, '关闭不应修改业务数据'
    assert data['previous_snapshot']['global_enabled'] is True, '关闭前全局开关应为 True'
    assert data['new_snapshot']['global_enabled'] is False, '关闭后全局开关应为 False'
    assert data['new_snapshot']['force_fallback'] is True, '关闭后紧急回滚应为 True'
    assert data['new_snapshot']['allowed_user_ids'] == [], '关闭后白名单应清空'

    # 验证关闭生效
    with app.app_context():
        assert not wms_app._ai_global_enabled(), '关闭后全局开关应为 False'
        assert wms_app._ai_force_fallback(), '关闭后紧急回滚应为 True'
        assert wms_app._ai_allowed_user_ids() == [], '关闭后白名单应为空'

    # 验证 AIRollbackEvent 已记录
    with app.app_context():
        shutdown_events = wms_app.AIRollbackEvent.query.filter_by(action='shutdown').all()
        assert len(shutdown_events) >= 1, '应记录 shutdown 事件'

    # ---- 5. admin 一键恢复 ----
    resp = client.post('/api/ai/rollout/restore')
    assert resp.status_code == 200, f'一键恢复应 200，实际 {resp.status_code}'
    data = resp.get_json()
    assert data['status'] == 'ok'
    assert data['action'] == 'restore'
    assert data['restored_snapshot']['global_enabled'] is True, '恢复后全局开关应为 True'
    assert data['restored_snapshot']['mode'] == 'allowlist', '恢复后模式应为 allowlist'
    assert warehouse_uid in data['restored_snapshot']['allowed_user_ids'], \
        '恢复后白名单应含 warehouse_uid'

    # 验证恢复生效
    with app.app_context():
        assert wms_app._ai_global_enabled(), '恢复后全局开关应为 True'
        assert not wms_app._ai_force_fallback(), '恢复后紧急回滚应为 False'
        allowed = wms_app._ai_allowed_user_ids()
        assert warehouse_uid in allowed, '恢复后白名单应含 warehouse_uid'
        assert wms_app._ai_rollout_mode() == 'allowlist', '恢复后模式应为 allowlist'

    # 验证 AIRollbackEvent 已记录 restore
    with app.app_context():
        restore_events = wms_app.AIRollbackEvent.query.filter_by(action='restore').all()
        assert len(restore_events) >= 1, '应记录 restore 事件'

    # ---- 6. admin 查询审计记录 ----
    resp = client.get('/api/ai/rollout/audit')
    assert resp.status_code == 200, f'查询审计应 200，实际 {resp.status_code}'
    data = resp.get_json()
    assert data['status'] == 'ok'
    assert 'records' in data
    assert isinstance(data['records'], list)

    # ---- 7. admin 查询降级任务 ----
    resp = client.get('/api/ai/rollout/fallback_tasks')
    assert resp.status_code == 200, f'查询降级任务应 200，实际 {resp.status_code}'
    data = resp.get_json()
    assert data['status'] == 'ok'
    assert 'tasks' in data

    # ---- 8. 破坏性测试：恢复不修改业务数据（InOrder/OutOrder/User 表不变）----
    with app.app_context():
        # 记录关闭-恢复前后的业务表行数
        in_order_before = wms_app.InOrder.query.count()
        out_order_before = wms_app.OutOrder.query.count()
        user_count_before = wms_app.User.query.count()
        admin_user = wms_app.User.query.filter_by(role='admin').first()
        admin_pwd_before = admin_user.password_hash if admin_user else None

    # 再次关闭+恢复
    client.post('/api/ai/rollout/shutdown')
    client.post('/api/ai/rollout/restore')

    with app.app_context():
        in_order_after = wms_app.InOrder.query.count()
        out_order_after = wms_app.OutOrder.query.count()
        user_count_after = wms_app.User.query.count()
        admin_user_after = wms_app.User.query.filter_by(role='admin').first()
        admin_pwd_after = admin_user_after.password_hash if admin_user_after else None

        assert in_order_before == in_order_after, '关闭/恢复不应修改 InOrder 表'
        assert out_order_before == out_order_after, '关闭/恢复不应修改 OutOrder 表'
        assert user_count_before == user_count_after, '关闭/恢复不应修改 User 表'
        assert admin_pwd_before == admin_pwd_after, '关闭/恢复不应修改 admin 密码'

    print('PASS 测试8：端到端API闭环（非admin拒绝+admin状态/白名单/关闭/恢复/审计/降级任务查询+关闭不修改业务数据和密码）')


def main() -> int:
    tests = [
        test1_four_rollout_modes_decision,
        test2_permission_order_fixed,
        test3_allowlist_user_id_immediate,
        test4_shutdown_restore_within_10_minutes,
        test5_rollout_audit_no_sensitive,
        test6_manual_fallback_preserves_evidence,
        test7_admin_only_maintenance_and_auto_submit,
        test8_e2e_api_rollout_closure,
    ]
    failures = 0
    for test in tests:
        try:
            test()
        except Exception as exc:
            failures += 1
            print(f'FAIL {test.__name__}: {type(exc).__name__}: {exc}')
            import traceback
            traceback.print_exc()
    print(f'\n=== AI-R17-F01 Rollout Control Verification Summary ===')
    print(f'total={len(tests)} passed={len(tests) - failures} failed={failures}')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())

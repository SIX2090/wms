"""AI-R14 AI 数据保留、脱敏和清理任务专项验证。

# AI_TASK: AI-R14

8 项测试覆盖：
1. 默认保留配置（5 类数据分类保留期限 + dry_run + 关键审计豁免标记）
2. 清理预览（delete/keep/exempt/protected 4 种 action）
3. 业务数据保护（有业务关联的记录不得清理 - 验收1）
4. 关键审计豁免（is_critical 审计记录不清理 - 验收1）
5. 执行清理（实际删除 + 清理日志记录 + 不误删）
6. 导出脱敏（敏感字段已脱敏 - 验收2）
7. 日志脱敏（API key/Bearer/手机号/身份证不泄露 - 验收2）
8. 综合安全校验（一次性多项验收）

设计：纯逻辑测试，不依赖 Flask/ORM，使用内存数据结构模拟数据记录和清理日志。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-data-retention-secret'
sys.path.insert(0, str(APP_DIR))

from ai.ops.data_retention import (
    CATEGORY_CONVERSATIONS,
    CATEGORY_IMAGES,
    CATEGORY_TASKS,
    CATEGORY_FEEDBACK,
    CATEGORY_AUDIT,
    ALL_CATEGORIES,
    DEFAULT_RETENTION_DAYS,
    PROTECTED_BUSINESS_DATA,
    SENSITIVE_FIELDS,
    RetentionPolicy,
    RetentionConfig,
    DataRecord,
    CleanupPreviewItem,
    CleanupPreviewResult,
    CleanupExecutionResult,
    CleanupLogEntry,
    default_retention_config,
    compute_cutoff_date,
    is_record_expired,
    is_record_protected,
    preview_cleanup,
    execute_cleanup,
    mask_sensitive_value,
    sanitize_export_record,
    sanitize_log_text,
    validate_no_business_data_deleted,
    validate_export_sanitized,
    validate_log_sanitized,
    validate_critical_audit_exempt,
)


NOW_ISO = '2026-07-17T10:00:00'


def _make_record(
    record_id: int,
    category: str,
    days_ago: int,
    *,
    is_critical: bool = False,
    has_business_link: bool = False,
    content_preview: str = '',
) -> DataRecord:
    """构造测试数据记录（创建时间为 days_ago 天前）。"""
    from datetime import datetime, timedelta
    created = (datetime.fromisoformat(NOW_ISO) - timedelta(days=days_ago)).isoformat()
    return DataRecord(
        id=record_id,
        category=category,
        created_at=created,
        is_critical=is_critical,
        content_preview=content_preview,
        has_business_link=has_business_link,
    )


# ===== 测试1：默认保留配置 =====

def test1_default_retention_config():
    """测试1：默认保留配置（5 类数据分类保留期限 + dry_run + 关键审计豁免标记）。"""
    config = default_retention_config(dry_run=True)

    # 5 类数据全部覆盖
    categories_in_config = {p.category for p in config.policies}
    assert categories_in_config == set(ALL_CATEGORIES), f'应覆盖全部 5 类：{categories_in_config}'

    # 默认保留期限正确
    for cat, expected_days in DEFAULT_RETENTION_DAYS.items():
        policy = config.get_policy(cat)
        assert policy is not None, f'类别 {cat} 应有策略'
        assert policy.retention_days == expected_days, (
            f'{cat} 默认保留 {expected_days} 天，实际 {policy.retention_days}'
        )

    # 关键审计豁免标记：仅 audit 类别 critical_exempt=True
    audit_policy = config.get_policy(CATEGORY_AUDIT)
    assert audit_policy.critical_exempt is True, 'audit 类别应标记 critical_exempt=True'
    for cat in (CATEGORY_CONVERSATIONS, CATEGORY_IMAGES, CATEGORY_TASKS, CATEGORY_FEEDBACK):
        policy = config.get_policy(cat)
        assert policy.critical_exempt is False, f'{cat} 类别不应标记 critical_exempt'

    # dry_run 默认 True（仅预览）
    assert config.dry_run is True
    assert config.enabled is True

    # audit 默认 retention_days=0（永久保留）
    assert DEFAULT_RETENTION_DAYS[CATEGORY_AUDIT] == 0

    # 业务保护类别常量存在
    assert 'business_drafts' in PROTECTED_BUSINESS_DATA
    assert 'confirmation_records' in PROTECTED_BUSINESS_DATA
    assert 'critical_audit' in PROTECTED_BUSINESS_DATA

    # 敏感字段常量存在
    for field in ('phone', 'email', 'api_key', 'token', 'password', 'id_card'):
        assert any(field in sf for sf in SENSITIVE_FIELDS), f'敏感字段 {field} 应在 SENSITIVE_FIELDS 中'

    print('PASS 测试1：默认保留配置（5 类分类 + 保留期限 + 关键审计豁免标记 + 业务保护常量）')


# ===== 测试2：清理预览 delete/keep/exempt/protected =====

def test2_cleanup_preview_actions():
    """测试2：清理预览返回 delete/keep/exempt/protected 4 种 action。"""
    config = default_retention_config(dry_run=True)

    # 构造各类记录：conversations 90 天保留
    records_by_category = {
        CATEGORY_CONVERSATIONS: [
            _make_record(1, CATEGORY_CONVERSATIONS, days_ago=100, content_preview='旧对话'),  # 过期 delete
            _make_record(2, CATEGORY_CONVERSATIONS, days_ago=30, content_preview='新对话'),   # 未过期 keep
        ],
        CATEGORY_IMAGES: [
            _make_record(3, CATEGORY_IMAGES, days_ago=45, content_preview='旧图片'),  # 过期 delete
        ],
        CATEGORY_TASKS: [
            _make_record(4, CATEGORY_TASKS, days_ago=200, content_preview='旧任务'),  # 过期 delete
        ],
        CATEGORY_FEEDBACK: [
            _make_record(5, CATEGORY_FEEDBACK, days_ago=400, content_preview='旧反馈'),  # 过期 delete
        ],
        CATEGORY_AUDIT: [
            # audit retention_days=0 永久保留，不会进入预览
        ],
    }

    def query_expired(category, cutoff_iso):
        return records_by_category.get(category, [])

    preview = preview_cleanup(config, query_expired=query_expired, now_iso=NOW_ISO)

    actions = {item.action for item in preview.items}
    assert 'delete' in actions, '应有过期删除项'
    assert 'keep' in actions, '应有未过期保留项'

    # 检查 delete 项
    delete_items = [item for item in preview.items if item.action == 'delete']
    delete_ids = {item.record.id for item in delete_items}
    assert delete_ids == {1, 3, 4, 5}, f'delete 应包含过期记录：{delete_ids}'

    # 检查 keep 项
    keep_items = [item for item in preview.items if item.action == 'keep']
    keep_ids = {item.record.id for item in keep_items}
    assert keep_ids == {2}, f'keep 应包含未过期记录：{keep_ids}'

    # audit 类别 retention_days=0 应被跳过（不进入预览）
    audit_items = [item for item in preview.items if item.record.category == CATEGORY_AUDIT]
    assert len(audit_items) == 0, 'audit 永久保留应不进入预览'

    # 统计正确
    assert preview.to_delete_count == 4
    assert preview.to_keep_count == 1
    assert preview.exempt_count == 0
    assert preview.protected_count == 0

    print('PASS 测试2：清理预览（delete/keep 4 种 action + audit 永久保留跳过 + 统计正确）')


# ===== 测试3：业务数据保护（验收1）=====

def test3_business_data_protection():
    """测试3：业务数据保护（有业务关联的记录不得清理 - 验收1）。"""
    config = default_retention_config(dry_run=True)

    # 构造记录：有业务关联的过期记录应被 protected，不应 delete
    records = {
        CATEGORY_CONVERSATIONS: [
            # 过期但有业务关联 -> protected
            _make_record(101, CATEGORY_CONVERSATIONS, days_ago=200, has_business_link=True, content_preview='关联草稿的对话'),
            # 过期无业务关联 -> delete
            _make_record(102, CATEGORY_CONVERSATIONS, days_ago=200, has_business_link=False, content_preview='普通对话'),
        ],
        CATEGORY_TASKS: [
            # 过期但有业务关联（已生成草稿）-> protected
            _make_record(103, CATEGORY_TASKS, days_ago=300, has_business_link=True, content_preview='已生成草稿的任务'),
        ],
    }

    def query_expired(category, cutoff_iso):
        return records.get(category, [])

    preview = preview_cleanup(config, query_expired=query_expired, now_iso=NOW_ISO)

    protected_items = [item for item in preview.items if item.action == 'protected']
    protected_ids = {item.record.id for item in protected_items}
    assert 101 in protected_ids, '有业务关联的对话应被 protected'
    assert 103 in protected_ids, '有业务关联的任务应被 protected'

    # 有业务关联的记录不应被 delete
    delete_items = [item for item in preview.items if item.action == 'delete']
    for item in delete_items:
        assert not item.record.has_business_link, (
            f'记录 {item.record.id} 有业务关联不应被 delete'
        )

    # 102 无业务关联应被 delete
    delete_ids = {item.record.id for item in delete_items}
    assert 102 in delete_ids

    # 验收1：校验不误删业务数据
    ok, msg = validate_no_business_data_deleted(preview)
    assert ok, f'业务数据保护校验应通过：{msg}'

    # 反向测试：如果破坏 has_business_link 检查，校验应失败
    bad_preview = CleanupPreviewResult(
        items=[
            CleanupPreviewItem(
                record=_make_record(999, CATEGORY_CONVERSATIONS, days_ago=200, has_business_link=True),
                action='delete',  # 错误：有业务关联却标记 delete
                reason='被错误标记删除',
            ),
        ],
        to_delete_count=1, to_keep_count=0, exempt_count=0, protected_count=0,
        generated_at=NOW_ISO,
    )
    ok_bad, msg_bad = validate_no_business_data_deleted(bad_preview)
    assert not ok_bad, '有业务关联的记录被标记 delete 时校验应失败'
    assert '业务关联' in msg_bad

    print('PASS 测试3：业务数据保护（有业务关联 protected + 不误删 + 反向校验捕获）')


# ===== 测试4：关键审计豁免（验收1）=====

def test4_critical_audit_exempt():
    """测试4：关键审计豁免（is_critical 审计记录不清理 - 验收1）。"""
    # 自定义配置：audit 30 天保留 + critical_exempt=True
    custom_policies = (
        RetentionPolicy(
            category=CATEGORY_AUDIT, retention_days=30,
            critical_exempt=True, description='审计 30 天保留，关键豁免',
        ),
    )
    config = RetentionConfig(policies=custom_policies, dry_run=True, enabled=True)

    records = {
        CATEGORY_AUDIT: [
            # 过期但关键审计 -> exempt
            _make_record(201, CATEGORY_AUDIT, days_ago=60, is_critical=True, content_preview='关键审计：写操作'),
            # 过期非关键审计 -> delete
            _make_record(202, CATEGORY_AUDIT, days_ago=60, is_critical=False, content_preview='普通审计：读操作'),
            # 未过期关键审计 -> keep（未过期先于豁免判断）
            _make_record(203, CATEGORY_AUDIT, days_ago=10, is_critical=True, content_preview='近期关键审计'),
        ],
    }

    def query_expired(category, cutoff_iso):
        return records.get(category, [])

    preview = preview_cleanup(config, query_expired=query_expired, now_iso=NOW_ISO)

    exempt_items = [item for item in preview.items if item.action == 'exempt']
    exempt_ids = {item.record.id for item in exempt_items}
    assert 201 in exempt_ids, '过期关键审计应被 exempt'

    # 关键审计不应被 delete
    delete_items = [item for item in preview.items if item.action == 'delete']
    for item in delete_items:
        assert not item.record.is_critical, (
            f'关键审计记录 {item.record.id} 不应被 delete'
        )

    # 202 非关键过期应被 delete
    delete_ids = {item.record.id for item in delete_items}
    assert 202 in delete_ids, '非关键过期审计应被 delete'

    # 203 未过期关键审计应被 keep
    keep_items = [item for item in preview.items if item.action == 'keep']
    keep_ids = {item.record.id for item in keep_items}
    assert 203 in keep_ids

    # 验收1：校验关键审计豁免
    ok, msg = validate_critical_audit_exempt(preview)
    assert ok, f'关键审计豁免校验应通过：{msg}'

    # 反向测试：关键审计被标记 delete 时校验应失败
    bad_preview = CleanupPreviewResult(
        items=[
            CleanupPreviewItem(
                record=_make_record(888, CATEGORY_AUDIT, days_ago=60, is_critical=True),
                action='delete',  # 错误：关键审计被标记 delete
                reason='被错误标记删除',
            ),
        ],
        to_delete_count=1, to_keep_count=0, exempt_count=0, protected_count=0,
        generated_at=NOW_ISO,
    )
    ok_bad, msg_bad = validate_critical_audit_exempt(bad_preview)
    assert not ok_bad, '关键审计被标记 delete 时校验应失败'
    assert '关键审计' in msg_bad

    print('PASS 测试4：关键审计豁免（过期关键 exempt + 非关键 delete + 反向校验捕获）')


# ===== 测试5：执行清理（实际删除 + 清理日志 + 不误删）=====

def test5_execute_cleanup():
    """测试5：执行清理（实际删除 + 清理日志记录 + 不误删）。"""
    config = default_retention_config(dry_run=False)

    # 内存数据存储
    storage = {
        CATEGORY_CONVERSATIONS: [
            _make_record(301, CATEGORY_CONVERSATIONS, days_ago=100),  # 过期 delete
            _make_record(302, CATEGORY_CONVERSATIONS, days_ago=10),   # 未过期 keep
            _make_record(303, CATEGORY_CONVERSATIONS, days_ago=100, has_business_link=True),  # protected
        ],
        CATEGORY_IMAGES: [
            _make_record(304, CATEGORY_IMAGES, days_ago=45),  # 过期 delete
        ],
    }
    deleted_ids: dict[str, list[int]] = {CATEGORY_CONVERSATIONS: [], CATEGORY_IMAGES: []}
    saved_logs: list[CleanupLogEntry] = []

    def query_expired(category, cutoff_iso):
        return list(storage.get(category, []))

    def delete_records(category, ids):
        deleted = 0
        for rid in list(ids):
            storage[category] = [r for r in storage.get(category, []) if r.id != rid]
            deleted_ids.setdefault(category, []).append(rid)
            deleted += 1
        return deleted

    def save_log(log_entry):
        saved_logs.append(log_entry)
        return log_entry

    result = execute_cleanup(
        config,
        query_expired=query_expired,
        delete_records=delete_records,
        executed_by=1,
        now_iso=NOW_ISO,
        save_log=save_log,
    )

    # 执行成功
    assert result.success, f'清理应成功：{result.reason}'
    assert result.deleted_count == 2, f'应删除 2 条（301 + 304），实际 {result.deleted_count}'
    assert 301 in deleted_ids[CATEGORY_CONVERSATIONS]
    assert 304 in deleted_ids[CATEGORY_IMAGES]

    # 302 未过期不被删除
    assert 302 not in deleted_ids[CATEGORY_CONVERSATIONS], '未过期记录不应被删除'
    # 303 有业务关联不被删除
    assert 303 not in deleted_ids[CATEGORY_CONVERSATIONS], '有业务关联的记录不应被删除'

    # 清理日志已保存
    assert len(saved_logs) == 1, f'应保存 1 条清理日志，实际 {len(saved_logs)}'
    log = saved_logs[0]
    assert log.executed_by == 1
    assert log.deleted_count == 2
    assert log.protected_count >= 1, '应有 protected 计数'
    assert log.dry_run is False
    assert log.log_id.startswith('cleanup-')

    # 禁用清理时不执行
    disabled_config = RetentionConfig(
        policies=config.policies, dry_run=False, enabled=False,
    )
    result_disabled = execute_cleanup(
        disabled_config,
        query_expired=query_expired,
        delete_records=delete_records,
        executed_by=1,
        now_iso=NOW_ISO,
        save_log=save_log,
    )
    assert not result_disabled.success, '禁用清理时应返回失败'
    assert '未启用' in result_disabled.reason

    print('PASS 测试5：执行清理（删除过期 + 不误删业务 + 清理日志 + 禁用时不执行）')


# ===== 测试6：导出脱敏（验收2）=====

def test6_export_sanitized():
    """测试6：导出脱敏（敏感字段已脱敏 - 验收2）。"""
    # 构造含敏感字段的记录
    raw_record = {
        'id': 1,
        'phone': '13812345678',
        'mobile': '13987654321',
        'email': 'zhangsan@example.com',
        'api_key': 'sk-abcdef1234567890',
        'token': 'bearer-token-xyz',
        'password': 'secret123',
        'id_card': '110101199001011234',
        'content': '普通内容不脱敏',
        'name': '张三',
    }

    sanitized = sanitize_export_record(raw_record)

    # 密钥类应为 ***
    assert sanitized['api_key'] == '***', f"api_key 应脱敏为 ***，实际 {sanitized['api_key']}"
    assert sanitized['token'] == '***', f"token 应脱敏为 ***，实际 {sanitized['token']}"
    assert sanitized['password'] == '***', f"password 应脱敏为 ***，实际 {sanitized['password']}"

    # 手机号应含 ****
    assert '****' in sanitized['phone'], f"phone 应打码，实际 {sanitized['phone']}"
    assert sanitized['phone'].startswith('138'), 'phone 前 3 位保留'
    assert sanitized['phone'].endswith('5678'), 'phone 后 4 位保留'

    # 邮箱应含 ***
    assert '***' in sanitized['email'], f"email 应打码，实际 {sanitized['email']}"
    assert sanitized['email'].endswith('@example.com'), 'email 域名保留'

    # 身份证应含 ********
    assert '********' in sanitized['id_card'], f"id_card 应打码，实际 {sanitized['id_card']}"

    # 普通字段不脱敏
    assert sanitized['content'] == '普通内容不脱敏'
    assert sanitized['name'] == '张三'

    # 验收2：校验导出脱敏
    ok, msg = validate_export_sanitized([sanitized])
    assert ok, f'导出脱敏校验应通过：{msg}'

    # 反向测试：未脱敏的记录校验应失败
    ok_bad, msg_bad = validate_export_sanitized([raw_record])
    assert not ok_bad, '未脱敏记录校验应失败'
    assert '未脱敏' in msg_bad

    # 单独测试 mask_sensitive_value
    assert mask_sensitive_value('api_key', 'sk-secret') == '***'
    assert mask_sensitive_value('phone', '13812345678') == '138****5678'
    assert mask_sensitive_value('id_card', '110101199001011234').startswith('110101')
    assert '********' in mask_sensitive_value('id_card', '110101199001011234')
    assert mask_sensitive_value('email', 'ab@x.com') == '***@x.com' or '***' in mask_sensitive_value('email', 'ab@x.com')
    # None 值不报错
    assert mask_sensitive_value('phone', None) is None

    print('PASS 测试6：导出脱敏（密钥 *** + 手机号/身份证/邮箱打码 + 反向校验捕获 + None 安全）')


# ===== 测试7：日志脱敏（验收2）=====

def test7_log_sanitized():
    """测试7：日志脱敏（API key/Bearer/手机号/身份证不泄露 - 验收2）。"""
    # 含敏感信息的原始日志
    raw_log = (
        '调用 Provider 失败 api_key=sk-abcdef1234567890 '
        'Authorization: Bearer eyJhbGciOiJIUzI1NiJ9abc123 '
        '联系人手机 13812345678 身份证 110101199001011234 '
        '邮箱 zhangsan@example.com'
    )

    sanitized = sanitize_log_text(raw_log)

    # API key 应被替换
    assert 'sk-abcdef1234567890' not in sanitized, 'API key 不应出现在脱敏后日志'
    assert 'sk-***' in sanitized, 'API key 应替换为 sk-***'

    # Bearer token 应被替换
    assert 'eyJhbGciOiJIUzI1NiJ9abc123' not in sanitized, 'Bearer token 不应出现'
    assert 'Bearer ***' in sanitized, 'Bearer token 应替换为 Bearer ***'

    # 完整手机号应被打码
    assert '13812345678' not in sanitized, '完整手机号不应出现'
    assert '138****5678' in sanitized, '手机号应打码为 138****5678'

    # 完整身份证应被打码
    assert '110101199001011234' not in sanitized, '完整身份证不应出现'

    # 邮箱应被打码
    assert 'zhangsan@example.com' not in sanitized, '完整邮箱不应出现'

    # 验收2：校验日志脱敏
    ok, msg = validate_log_sanitized(sanitized)
    assert ok, f'日志脱敏校验应通过：{msg}'

    # 反向测试：未脱敏的日志校验应失败
    ok_bad1, _ = validate_log_sanitized('api_key=sk-abcdef1234567890')
    assert not ok_bad1, '含完整 API key 的日志校验应失败'

    ok_bad2, _ = validate_log_sanitized('Authorization: Bearer eyJhbGciOiJIUzI1NiJ9abc123')
    assert not ok_bad2, '含完整 Bearer token 的日志校验应失败'

    ok_bad3, _ = validate_log_sanitized('联系手机 13812345678')
    assert not ok_bad3, '含完整手机号的日志校验应失败'

    # 空文本安全
    ok_empty, _ = validate_log_sanitized('')
    assert ok_empty, '空文本应通过'

    # 普通文本不误报
    ok_normal, _ = validate_log_sanitized('cleanup executed successfully, deleted 5 records')
    assert ok_normal, '普通文本应通过'

    print('PASS 测试7：日志脱敏（API key/Bearer/手机号/身份证/邮箱替换 + 反向校验捕获 + 空文本安全）')


# ===== 测试8：综合安全校验 =====

def test8_comprehensive_safety_validation():
    """测试8：综合安全校验（一次性多项验收 + 截止日期计算 + 永久保留）。"""
    # 截止日期计算
    cutoff_90 = compute_cutoff_date(90, now_iso=NOW_ISO)
    assert cutoff_90 != '1970-01-01T00:00:00', '90 天保留应有实际截止日期'
    # 永久保留返回极早日期
    cutoff_perm = compute_cutoff_date(0, now_iso=NOW_ISO)
    assert cutoff_perm == '1970-01-01T00:00:00', '永久保留应返回极早日期'

    # 记录过期判断
    old_record = _make_record(1, CATEGORY_CONVERSATIONS, days_ago=100)
    new_record = _make_record(2, CATEGORY_CONVERSATIONS, days_ago=30)
    assert is_record_expired(old_record, cutoff_90, now_iso=NOW_ISO), '100 天前记录应过期'
    assert not is_record_expired(new_record, cutoff_90, now_iso=NOW_ISO), '30 天前记录不应过期'

    # 记录保护判断
    biz_record = _make_record(3, CATEGORY_TASKS, days_ago=200, has_business_link=True)
    critical_record = _make_record(4, CATEGORY_AUDIT, days_ago=200, is_critical=True)
    normal_record = _make_record(5, CATEGORY_CONVERSATIONS, days_ago=200)
    assert is_record_protected(biz_record), '有业务关联的记录应受保护'
    assert is_record_protected(critical_record), '关键审计应受保护'
    assert not is_record_protected(normal_record), '普通记录不受保护'

    # 综合预览场景：混合各类记录
    config = default_retention_config(dry_run=True)
    # 自定义 audit 30 天保留以测试 critical_exempt
    custom_policies = list(config.policies)
    for i, p in enumerate(custom_policies):
        if p.category == CATEGORY_AUDIT:
            custom_policies[i] = RetentionPolicy(
                category=CATEGORY_AUDIT, retention_days=30,
                critical_exempt=True, description=p.description,
            )
    config = RetentionConfig(policies=tuple(custom_policies), dry_run=True, enabled=True)

    records = {
        CATEGORY_CONVERSATIONS: [
            _make_record(11, CATEGORY_CONVERSATIONS, days_ago=100),  # delete
            _make_record(12, CATEGORY_CONVERSATIONS, days_ago=100, has_business_link=True),  # protected
        ],
        CATEGORY_AUDIT: [
            _make_record(13, CATEGORY_AUDIT, days_ago=60, is_critical=True),  # exempt
            _make_record(14, CATEGORY_AUDIT, days_ago=60, is_critical=False),  # delete
        ],
    }

    def query_expired(category, cutoff_iso):
        return list(records.get(category, []))

    preview = preview_cleanup(config, query_expired=query_expired, now_iso=NOW_ISO)

    # 一次性多项校验
    ok_biz, msg_biz = validate_no_business_data_deleted(preview)
    ok_exempt, msg_exempt = validate_critical_audit_exempt(preview)
    assert ok_biz, f'业务数据保护校验应通过：{msg_biz}'
    assert ok_exempt, f'关键审计豁免校验应通过：{msg_exempt}'

    # 验证 action 分布
    actions = {item.record.id: item.action for item in preview.items}
    assert actions[11] == 'delete', '11 过期无业务关联应 delete'
    assert actions[12] == 'protected', '12 有业务关联应 protected'
    assert actions[13] == 'exempt', '13 关键审计应 exempt'
    assert actions[14] == 'delete', '14 非关键过期审计应 delete'

    # 统计正确
    assert preview.to_delete_count == 2, f'delete 应为 2，实际 {preview.to_delete_count}'
    assert preview.protected_count == 1, f'protected 应为 1，实际 {preview.protected_count}'
    assert preview.exempt_count == 1, f'exempt 应为 1，实际 {preview.exempt_count}'

    # 导出脱敏综合校验
    export_records = [sanitize_export_record(item.record.to_dict()) for item in preview.items]
    ok_export, msg_export = validate_export_sanitized(export_records)
    assert ok_export, f'导出脱敏校验应通过：{msg_export}'

    # 日志脱敏综合校验
    log_text = (
        f'cleanup preview generated, api_key=sk-leak1234567890, '
        f'phone=13812345678, delete_count={preview.to_delete_count}'
    )
    sanitized_log = sanitize_log_text(log_text)
    ok_log, msg_log = validate_log_sanitized(sanitized_log)
    assert ok_log, f'日志脱敏校验应通过：{msg_log}'
    assert 'sk-leak1234567890' not in sanitized_log
    assert '13812345678' not in sanitized_log

    # CleanupLogEntry 序列化完整
    log_entry = CleanupLogEntry(
        log_id='cleanup-test-001', executed_by=1,
        categories=(CATEGORY_CONVERSATIONS, CATEGORY_AUDIT),
        dry_run=True, deleted_count=2, kept_count=0, exempt_count=1,
        protected_count=1, failed_count=0,
        cutoff_date=NOW_ISO, executed_at=NOW_ISO, notes='综合校验',
    )
    log_dict = log_entry.to_dict()
    assert log_dict['log_id'] == 'cleanup-test-001'
    assert log_dict['categories'] == [CATEGORY_CONVERSATIONS, CATEGORY_AUDIT]
    assert log_dict['deleted_count'] == 2

    print('PASS 测试8：综合安全校验（截止日期 + 过期判断 + 保护判断 + 多项验收 + 序列化）')


# ===== 主入口 =====

def main() -> int:
    print('=== AI-R14 AI 数据保留、脱敏和清理任务验证 ===')
    tests = [
        test1_default_retention_config,
        test2_cleanup_preview_actions,
        test3_business_data_protection,
        test4_critical_audit_exempt,
        test5_execute_cleanup,
        test6_export_sanitized,
        test7_log_sanitized,
        test8_comprehensive_safety_validation,
    ]
    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f'FAIL {test.__name__}: {e}')
            failed += 1
        except Exception as e:
            print(f'ERROR {test.__name__}: {type(e).__name__}: {e}')
            failed += 1
    print(f'\n=== AI-R14 AI 数据保留、脱敏和清理任务: {len(tests) - failed} PASS / {failed} FAIL ===')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

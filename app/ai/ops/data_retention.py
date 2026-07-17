"""AI-R14：AI 数据保留、脱敏和清理任务。

# AI_TASK: AI-R14

范围：对话、图片、任务、反馈和审计的分类保留期限；脱敏；清理预览；定时清理；
关键审计豁免；清理日志和管理员配置。

设计：
- 纯逻辑 + 依赖注入：不依赖 Flask/ORM，与 AI-R06~R13 一致。
- CI 无 DB 可 mock 测，生产由 app.py 提供 ORM adapter。
- 复用 security.py 的 mask_phone/email/id_card/address/contact/desensitize_text 函数。
- 5 类数据分类保留：conversations/images/tasks/feedback/audit。
- 关键审计豁免：标记 critical=True 的审计记录不清理。
- 清理预览：返回将删除的记录列表，不实际删除（dry_run）。
- 定时清理：执行删除，保留关键审计和未过期的记录。
- 清理日志：记录每次清理操作的统计（类别/删除数/保留数/豁免数）。
- 不得误删业务草稿、确认记录和必要审计。

验收：
1. 不得误删业务草稿、确认记录和必要审计。
2. 日志和导出不得泄露密钥或完整敏感原文。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional


# ===== 数据类别常量 =====

CATEGORY_CONVERSATIONS = 'conversations'   # AI 对话历史
CATEGORY_IMAGES = 'images'                  # AI 图片（OCR 原图/处理图）
CATEGORY_TASKS = 'tasks'                    # AI 文档任务
CATEGORY_FEEDBACK = 'feedback'              # AI 反馈记录
CATEGORY_AUDIT = 'audit'                    # AI 审计日志

ALL_CATEGORIES = (
    CATEGORY_CONVERSATIONS,
    CATEGORY_IMAGES,
    CATEGORY_TASKS,
    CATEGORY_FEEDBACK,
    CATEGORY_AUDIT,
)

# 默认保留期限（天），0 表示永不过期
DEFAULT_RETENTION_DAYS = {
    CATEGORY_CONVERSATIONS: 90,
    CATEGORY_IMAGES: 30,
    CATEGORY_TASKS: 180,
    CATEGORY_FEEDBACK: 365,
    CATEGORY_AUDIT: 0,  # 审计默认永久保留
}

# 业务保护类别：这些数据不得被 AI 清理任务删除
PROTECTED_BUSINESS_DATA = (
    'business_drafts',         # 业务草稿（InOrder/OutOrder 等草稿）
    'confirmation_records',    # 确认记录（AIDraftIdempotency/ConfirmationToken）
    'critical_audit',          # 关键审计（标记 critical=True）
)

# 敏感原文字段（导出/日志时必须脱敏）
SENSITIVE_FIELDS = (
    'phone', 'mobile', 'tel',
    'id_card', 'id_number',
    'email',
    'api_key', 'apikey', 'token', 'secret', 'password',
    'contact_phone', 'contact_name',
)


# ===== 数据结构 =====

@dataclass(frozen=True)
class RetentionPolicy:
    """单类数据保留策略。"""

    category: str
    retention_days: int              # 保留天数，0 表示永久
    critical_exempt: bool = False    # 关键审计豁免（仅 audit 类别有意义）
    description: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'category': self.category,
            'retention_days': self.retention_days,
            'critical_exempt': self.critical_exempt,
            'description': self.description,
        }


@dataclass(frozen=True)
class RetentionConfig:
    """保留策略配置（管理员可配置）。"""

    policies: tuple[RetentionPolicy, ...] = field(default_factory=tuple)
    dry_run: bool = False            # True=仅预览不删除；False=实际删除
    enabled: bool = True             # 是否启用清理

    def get_policy(self, category: str) -> Optional[RetentionPolicy]:
        for policy in self.policies:
            if policy.category == category:
                return policy
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            'policies': [p.to_dict() for p in self.policies],
            'dry_run': self.dry_run,
            'enabled': self.enabled,
        }


@dataclass(frozen=True)
class DataRecord:
    """待清理数据记录（纯数据，由 ORM adapter 转换）。"""

    id: int
    category: str
    created_at: str                  # ISO8601
    is_critical: bool = False        # 是否关键（critical_audit 标记）
    content_preview: str = ''        # 内容预览（脱敏后）
    has_business_link: bool = False  # 是否有业务关联（有则不清理）

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'category': self.category,
            'created_at': self.created_at,
            'is_critical': self.is_critical,
            'content_preview': self.content_preview,
            'has_business_link': self.has_business_link,
        }


@dataclass(frozen=True)
class CleanupPreviewItem:
    """清理预览单项。"""

    record: DataRecord
    action: str                      # 'delete' / 'keep' / 'exempt' / 'protected'
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'record': self.record.to_dict(),
            'action': self.action,
            'reason': self.reason,
        }


@dataclass(frozen=True)
class CleanupPreviewResult:
    """清理预览结果（dry_run=True 时不实际删除）。"""

    items: list[CleanupPreviewItem]
    to_delete_count: int
    to_keep_count: int
    exempt_count: int
    protected_count: int
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'items': [item.to_dict() for item in self.items],
            'to_delete_count': self.to_delete_count,
            'to_keep_count': self.to_keep_count,
            'exempt_count': self.exempt_count,
            'protected_count': self.protected_count,
            'generated_at': self.generated_at,
        }


@dataclass(frozen=True)
class CleanupExecutionResult:
    """清理执行结果。"""

    success: bool
    deleted_count: int
    kept_count: int
    exempt_count: int
    protected_count: int
    failed_count: int
    log_id: str
    reason: str
    executed_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'success': self.success,
            'deleted_count': self.deleted_count,
            'kept_count': self.kept_count,
            'exempt_count': self.exempt_count,
            'protected_count': self.protected_count,
            'failed_count': self.failed_count,
            'log_id': self.log_id,
            'reason': self.reason,
            'executed_at': self.executed_at,
        }


@dataclass(frozen=True)
class CleanupLogEntry:
    """清理日志条目。"""

    log_id: str
    executed_by: int                 # 执行人 user_id
    categories: tuple[str, ...]      # 清理的类别
    dry_run: bool
    deleted_count: int
    kept_count: int
    exempt_count: int
    protected_count: int
    failed_count: int
    cutoff_date: str                 # 清理截止日期 ISO8601
    executed_at: str
    notes: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'log_id': self.log_id,
            'executed_by': self.executed_by,
            'categories': list(self.categories),
            'dry_run': self.dry_run,
            'deleted_count': self.deleted_count,
            'kept_count': self.kept_count,
            'exempt_count': self.exempt_count,
            'protected_count': self.protected_count,
            'failed_count': self.failed_count,
            'cutoff_date': self.cutoff_date,
            'executed_at': self.executed_at,
            'notes': self.notes,
        }


# ===== 依赖注入回调类型 =====

QueryExpiredFn = Callable[[str, str], list[DataRecord]]   # (category, cutoff_iso) -> records
DeleteRecordsFn = Callable[[str, list[int]], int]         # (category, ids) -> deleted_count
SaveLogFn = Callable[[CleanupLogEntry], CleanupLogEntry]
QueryLogsFn = Callable[[int], list[CleanupLogEntry]]


# ===== 默认配置 =====

def default_retention_config(dry_run: bool = True) -> RetentionConfig:
    """默认保留配置（dry_run=True 仅预览）。"""
    policies = tuple(
        RetentionPolicy(
            category=cat,
            retention_days=days,
            critical_exempt=(cat == CATEGORY_AUDIT),
            description=f'{cat} 默认保留 {days if days > 0 else "永久"} 天',
        )
        for cat, days in DEFAULT_RETENTION_DAYS.items()
    )
    return RetentionConfig(policies=policies, dry_run=dry_run, enabled=True)


# ===== 核心逻辑 =====

def compute_cutoff_date(retention_days: int, *, now_iso: Optional[str] = None) -> str:
    """计算清理截止日期（创建时间早于此日期的记录可清理）。"""
    now = _parse_iso(now_iso) or datetime.now()
    if retention_days <= 0:
        # 永久保留，返回极早日期表示无记录可清理
        return '1970-01-01T00:00:00'
    cutoff = now - timedelta(days=retention_days)
    return cutoff.isoformat()


def is_record_expired(record: DataRecord, cutoff_iso: str, *, now_iso: Optional[str] = None) -> bool:
    """判断记录是否过期。"""
    cutoff = _parse_iso(cutoff_iso)
    created = _parse_iso(record.created_at)
    if cutoff is None or created is None:
        return False
    return created < cutoff


def is_record_protected(record: DataRecord) -> bool:
    """判断记录是否受业务保护（不得清理）。

    验收1：不得误删业务草稿、确认记录和必要审计。
    """
    # 有业务关联的记录不得清理
    if record.has_business_link:
        return True
    # 关键审计不得清理
    if record.is_critical:
        return True
    return False


def preview_cleanup(
    config: RetentionConfig,
    *,
    query_expired: QueryExpiredFn,
    categories: Optional[tuple[str, ...]] = None,
    now_iso: Optional[str] = None,
) -> CleanupPreviewResult:
    """清理预览（dry_run，不实际删除）。

    返回每条记录的 action：delete/keep/exempt/protected。
    - delete：过期且无保护
    - keep：未过期
    - exempt：关键审计豁免
    - protected：有业务关联或关键审计
    """
    now = _parse_iso(now_iso) or datetime.now()
    target_categories = categories or ALL_CATEGORIES

    items: list[CleanupPreviewItem] = []
    to_delete = 0
    to_keep = 0
    exempt = 0
    protected = 0

    for category in target_categories:
        policy = config.get_policy(category)
        if policy is None:
            # 无策略默认永久保留
            continue
        if policy.retention_days == 0:
            # 永久保留类别，跳过
            continue

        cutoff_iso = compute_cutoff_date(policy.retention_days, now_iso=now_iso)
        try:
            records = list(query_expired(category, cutoff_iso) or [])
        except Exception:
            records = []

        for record in records:
            # 验收1：业务保护 + 关键审计豁免的 action 分类
            # 1. 业务关联 → protected（最高优先级，无论是否过期/关键）
            if record.has_business_link:
                action = 'protected'
                reason = '记录有业务关联，不得清理'
                protected += 1
            # 2. 关键审计豁免：critical + critical_exempt 策略；过期 → exempt，未过期 → keep
            elif record.is_critical and policy.critical_exempt:
                if is_record_expired(record, cutoff_iso, now_iso=now_iso):
                    action = 'exempt'
                    reason = '关键审计豁免（已过期但不清理）'
                    exempt += 1
                else:
                    action = 'keep'
                    reason = '未过期'
                    to_keep += 1
            # 3. 关键记录无豁免策略 → protected（安全网，关键记录永不删除）
            elif record.is_critical:
                action = 'protected'
                reason = '关键记录受保护，不得清理'
                protected += 1
            # 4. 过期 → delete
            elif is_record_expired(record, cutoff_iso, now_iso=now_iso):
                action = 'delete'
                reason = f'已过期（保留期 {policy.retention_days} 天，创建于 {record.created_at}）'
                to_delete += 1
            # 5. 未过期 → keep
            else:
                action = 'keep'
                reason = '未过期'
                to_keep += 1
            items.append(CleanupPreviewItem(record=record, action=action, reason=reason))

    return CleanupPreviewResult(
        items=items,
        to_delete_count=to_delete,
        to_keep_count=to_keep,
        exempt_count=exempt,
        protected_count=protected,
        generated_at=now.isoformat(),
    )


def execute_cleanup(
    config: RetentionConfig,
    *,
    query_expired: QueryExpiredFn,
    delete_records: DeleteRecordsFn,
    executed_by: int,
    categories: Optional[tuple[str, ...]] = None,
    now_iso: Optional[str] = None,
    save_log: Optional[SaveLogFn] = None,
) -> CleanupExecutionResult:
    """执行清理（实际删除，保留关键审计和业务保护数据）。

    验收1：不得误删业务草稿、确认记录和必要审计。
    """
    now = _parse_iso(now_iso) or datetime.now()

    if not config.enabled:
        return CleanupExecutionResult(
            success=False,
            deleted_count=0, kept_count=0, exempt_count=0, protected_count=0,
            failed_count=0, log_id='', reason='清理任务未启用', executed_at=now.isoformat(),
        )

    # 强制 dry_run=False 时仍先预览，确保不误删
    preview = preview_cleanup(
        config,
        query_expired=query_expired,
        categories=categories,
        now_iso=now_iso,
    )

    # 收集要删除的记录（action=delete）
    to_delete_by_category: dict[str, list[int]] = {}
    for item in preview.items:
        if item.action == 'delete':
            to_delete_by_category.setdefault(item.record.category, []).append(item.record.id)

    deleted_total = 0
    failed_total = 0
    for category, ids in to_delete_by_category.items():
        if not ids:
            continue
        try:
            deleted = delete_records(category, ids)
            deleted_total += deleted
            if deleted < len(ids):
                failed_total += len(ids) - deleted
        except Exception:
            failed_total += len(ids)

    # 生成清理日志
    import uuid
    log_id = f'cleanup-{uuid.uuid4().hex[:12]}'
    target_categories = categories or ALL_CATEGORIES
    log_entry = CleanupLogEntry(
        log_id=log_id,
        executed_by=executed_by,
        categories=tuple(target_categories),
        dry_run=False,
        deleted_count=deleted_total,
        kept_count=preview.to_keep_count,
        exempt_count=preview.exempt_count,
        protected_count=preview.protected_count,
        failed_count=failed_total,
        cutoff_date=now.isoformat(),
        executed_at=now.isoformat(),
        notes=f'清理 {len(target_categories)} 类数据，删除 {deleted_total} 条',
    )
    if save_log is not None:
        try:
            save_log(log_entry)
        except Exception:
            pass

    return CleanupExecutionResult(
        success=failed_total == 0,
        deleted_count=deleted_total,
        kept_count=preview.to_keep_count,
        exempt_count=preview.exempt_count,
        protected_count=preview.protected_count,
        failed_count=failed_total,
        log_id=log_id,
        reason='清理完成' if failed_total == 0 else f'部分失败（{failed_total} 条）',
        executed_at=now.isoformat(),
    )


# ===== 脱敏（验收2：日志和导出不得泄露密钥或完整敏感原文） =====

def mask_sensitive_value(field_name: str, value: Any) -> Any:
    """脱敏字段值（复用 security.py 的脱敏逻辑）。

    - phone/mobile/tel/contact_phone：手机号脱敏（前3后4）
    - id_card/id_number：身份证脱敏（前6后4）
    - email：邮箱脱敏
    - api_key/apikey/token/secret/password：整体返回 ***（密钥类整体脱敏）
    - 其他：原值返回
    """
    if value is None:
        return None
    name_lower = (field_name or '').lower()
    # 密钥类整体脱敏
    if any(kw in name_lower for kw in ('api_key', 'apikey', 'token', 'secret', 'password')):
        return '***'
    # 空值不处理
    if not value:
        return value
    str_value = str(value)
    # 手机号脱敏
    if any(kw in name_lower for kw in ('phone', 'mobile', 'tel', 'contact_phone')):
        return _mask_phone_local(str_value)
    # 身份证脱敏
    if any(kw in name_lower for kw in ('id_card', 'id_number')):
        return _mask_id_card_local(str_value)
    # 邮箱脱敏
    if 'email' in name_lower:
        return _mask_email_local(str_value)
    return value


def sanitize_export_record(record: dict[str, Any]) -> dict[str, Any]:
    """脱敏导出记录（验收2）。

    遍历记录字段，对敏感字段进行脱敏。
    """
    sanitized = {}
    for key, value in record.items():
        if any(sensitive in key.lower() for sensitive in SENSITIVE_FIELDS):
            sanitized[key] = mask_sensitive_value(key, value)
        else:
            sanitized[key] = value
    return sanitized


def sanitize_log_text(text: str) -> str:
    """脱敏日志文本（验收2：日志不得泄露密钥或完整敏感原文）。

    复用 security.py 的 sanitize_log_message，但本模块独立实现避免循环依赖。
    """
    if not text:
        return ''
    result = text
    # API key / Bearer token
    import re
    result = re.sub(r'(sk-[A-Za-z0-9]{8,})', 'sk-***', result)
    result = re.sub(r'(Bearer\s+)[A-Za-z0-9\-_\.]+', r'\1***', result, flags=re.IGNORECASE)
    # 手机号
    result = re.sub(r'1[3-9]\d{9}', lambda m: m.group()[:3] + '****' + m.group()[-4:], result)
    # 身份证
    result = re.sub(r'\d{17}[\dXx]', lambda m: m.group()[:6] + '********' + m.group()[-4:], result)
    # 邮箱
    result = re.sub(r'[\w\.\-]+@[\w\.\-]+\.\w+', lambda m: m.group()[:2] + '***' + m.group()[-4:] if len(m.group()) > 6 else '***', result)
    return result


# ===== 校验函数 =====

def validate_no_business_data_deleted(
    preview: CleanupPreviewResult,
) -> tuple[bool, str]:
    """校验不误删业务数据（验收1）。

    检查预览结果中没有 action=delete 的记录具有 has_business_link=True 或 is_critical=True。
    """
    for item in preview.items:
        if item.action == 'delete':
            if item.record.has_business_link:
                return False, f'记录 {item.record.id}（{item.record.category}）有业务关联但被标记删除'
            if item.record.is_critical:
                return False, f'记录 {item.record.id}（{item.record.category}）是关键审计但被标记删除'
    return True, '业务数据保护校验通过'


def validate_export_sanitized(
    records: list[dict[str, Any]],
) -> tuple[bool, str]:
    """校验导出脱敏（验收2）。

    检查导出记录中敏感字段已脱敏。
    """
    for record in records:
        for key, value in record.items():
            if any(sensitive in key.lower() for sensitive in SENSITIVE_FIELDS):
                if value is None:
                    continue
                str_value = str(value)
                # 密钥类应为 ***
                if any(kw in key.lower() for kw in ('api_key', 'apikey', 'token', 'secret', 'password')):
                    if str_value != '***':
                        return False, f'字段 {key} 未脱敏（值不为 ***）：{str_value[:20]}'
                # 手机号应含 ****
                elif any(kw in key.lower() for kw in ('phone', 'mobile', 'tel', 'contact_phone')):
                    if len(str_value) >= 7 and '****' not in str_value:
                        return False, f'字段 {key} 未脱敏（手机号未打码）：{str_value[:20]}'
                # 身份证应含 ********
                elif any(kw in key.lower() for kw in ('id_card', 'id_number')):
                    if len(str_value) >= 10 and '********' not in str_value:
                        return False, f'字段 {key} 未脱敏（身份证未打码）：{str_value[:20]}'
                # 邮箱应含 ***
                elif 'email' in key.lower():
                    if '@' in str_value and '***' not in str_value:
                        return False, f'字段 {key} 未脱敏（邮箱未打码）：{str_value[:20]}'
    return True, '导出脱敏校验通过'


def validate_log_sanitized(text: str) -> tuple[bool, str]:
    """校验日志脱敏（验收2）。"""
    if not text:
        return True, '空文本'
    # 检查是否含未脱敏的敏感信息
    import re
    # 完整 API key（sk- 后跟 8 位以上字母数字）
    if re.search(r'sk-[A-Za-z0-9]{8,}', text):
        return False, '日志含未脱敏的 API key'
    # Bearer token
    if re.search(r'Bearer\s+[A-Za-z0-9\-_\.]{8,}', text, re.IGNORECASE):
        return False, '日志含未脱敏的 Bearer token'
    # 完整手机号
    if re.search(r'1[3-9]\d{9}', text) and '****' not in text:
        return False, '日志含未脱敏的手机号'
    # 完整身份证
    if re.search(r'\d{17}[\dXx]', text) and '********' not in text:
        return False, '日志含未脱敏的身份证号'
    return True, '日志脱敏校验通过'


def validate_critical_audit_exempt(
    preview: CleanupPreviewResult,
) -> tuple[bool, str]:
    """校验关键审计豁免（验收1：必要审计不清理）。"""
    for item in preview.items:
        if item.record.is_critical and item.action == 'delete':
            return False, f'关键审计记录 {item.record.id} 被标记删除'
    return True, '关键审计豁免校验通过'


# ===== 辅助函数 =====

def _parse_iso(iso_str: Optional[str]) -> Optional[datetime]:
    """解析 ISO8601 时间字符串。"""
    if not iso_str:
        return None
    try:
        if iso_str.endswith('Z'):
            iso_str = iso_str[:-1] + '+00:00'
        return datetime.fromisoformat(iso_str)
    except (ValueError, TypeError):
        return None


def _mask_phone_local(phone: str) -> str:
    """手机号脱敏（前3后4）。"""
    digits = ''.join(c for c in phone if c.isdigit())
    if len(digits) >= 7:
        return digits[:3] + '****' + digits[-4:]
    return '***' if digits else phone


def _mask_id_card_local(id_card: str) -> str:
    """身份证脱敏（前6后4）。"""
    digits = ''.join(c for c in id_card if c.isdigit() or c.upper() == 'X')
    if len(digits) >= 10:
        return digits[:6] + '********' + digits[-4:]
    return '***' if digits else id_card


def _mask_email_local(email: str) -> str:
    """邮箱脱敏。"""
    if '@' not in email:
        return email
    local, domain = email.rsplit('@', 1)
    if len(local) > 2:
        return local[:2] + '***@' + domain
    return '***@' + domain

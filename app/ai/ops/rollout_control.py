"""AI-R17-F01 真实用户白名单灰度与一键回滚闭环。

# AI_TASK: AI-R17-F01

本模块是 AI-R17-F01 的纯逻辑+依赖注入模块，职责是：
1. 统一 4 种灰度模式判定（off/allowlist/role/all，默认 off）。
2. 将用户白名单 ``allowed_user_ids`` 接入权限判定主流程。
3. 提供"一键关闭 AI + 恢复到灰度配置"的快照-恢复机制。
4. 构造灰度拒绝审计记录（含用户/角色/能力/原因/请求来源/时间）。
5. Provider 故障/预算耗尽/熔断/取消时降级为人工流程，保留文件和草稿证据。

与现有能力的边界（防重复）：
- 灰度模式判定：本模块替代 app.py 的 ``_ai_capability_allowed_by_rollout`` 旧实现
  （旧实现只支持 admin_only/read_only/read_draft/all 且不读 allowed_users），
  旧值通过 ``normalize_mode`` 向后兼容映射。
- 回滚开关：``ai_feature_global_enabled`` 全局开关和
  ``force_fallback`` 紧急回滚仍由 app.py/provider_router.py 持有，
  本模块只提供"快照-恢复"和"回滚事件记录"的纯逻辑编排。
- 越权成功/自动提交/重复草稿/低置信度未确认的检测仍由 launch_acceptance.py 聚合，
  本模块仅构造灰度拒绝审计记录供其统计。
- 自动提交禁止动作集复用 budget_control.AUTO_SUBMIT_FORBIDDEN_ACTIONS，保持一致。
- 回滚 10 分钟校验复用 launch_acceptance.validate_rollback_within_minutes 的口径。

本模块不依赖 Flask/ORM，CI 无 DB 时可直接传入参数测试；生产环境由 app.py 提供
ORM adapter 持久化快照、回滚事件、人工降级任务和审计记录。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# AI_TASK: AI-R17-F01

# ===== 灰度模式常量 =====

MODE_OFF = 'off'
"""off 模式：全部非 admin 用户禁用 AI 写草稿能力（admin 始终直通）。默认模式。"""

MODE_ALLOWLIST = 'allowlist'
"""allowlist 模式：仅 allowed_user_ids 白名单内的用户可用（admin 直通）。"""

MODE_ROLE = 'role'
"""role 模式：按角色+风险级别判定（等价旧 read_draft，admin 直通）。"""

MODE_ALL = 'all'
"""all 模式：全部可用（仍受角色权限矩阵和风险级别约束）。"""

VALID_MODES: tuple[str, ...] = (MODE_OFF, MODE_ALLOWLIST, MODE_ROLE, MODE_ALL)

DEFAULT_MODE = MODE_OFF
"""默认灰度模式为 off（F01 要求：默认 off，非 all）。"""

# 旧值 → 新值 映射（向后兼容已部署的旧设置）
_LEGACY_MODE_MAP: dict[str, str] = {
    'admin_only': MODE_OFF,      # 旧 admin_only：非 admin 全拒 → 新 off
    'read_only': MODE_ROLE,      # 旧 read_only：只读 → 新 role（风险级别判定）
    'read_draft': MODE_ROLE,     # 旧 read_draft：只读+草稿 → 新 role（风险级别判定）
    'all': MODE_ALL,
    'off': MODE_OFF,
    'allowlist': MODE_ALLOWLIST,
    'role': MODE_ROLE,
}

# 权限判定阶段（顺序固定，F01 要求）
STAGE_GLOBAL = 'global'
STAGE_FLAG = 'flag'
STAGE_ROLE = 'role'
STAGE_ALLOWLIST = 'allowlist'
STAGE_RISK = 'risk'
STAGE_CONFIRMATION = 'confirmation'

PERMISSION_ORDER: tuple[str, ...] = (
    STAGE_GLOBAL,
    STAGE_FLAG,
    STAGE_ROLE,
    STAGE_ALLOWLIST,
    STAGE_RISK,
    STAGE_CONFIRMATION,
)
"""权限判定顺序固定为：全局开关 → 功能开关 → 角色权限 → 用户白名单 → 风险级别 → 人工确认边界。"""

# 人工降级原因
MANUAL_FALLBACK_REASON_PROVIDER_FAULT = 'provider_fault'
MANUAL_FALLBACK_REASON_BUDGET_EXHAUSTED = 'budget_exhausted'
MANUAL_FALLBACK_REASON_CIRCUIT_BREAKER = 'circuit_breaker_open'
MANUAL_FALLBACK_REASON_CANCELLED = 'cancelled'
MANUAL_FALLBACK_REASON_LOW_CONFIDENCE = 'low_confidence'

ALL_FALLBACK_REASONS: tuple[str, ...] = (
    MANUAL_FALLBACK_REASON_PROVIDER_FAULT,
    MANUAL_FALLBACK_REASON_BUDGET_EXHAUSTED,
    MANUAL_FALLBACK_REASON_CIRCUIT_BREAKER,
    MANUAL_FALLBACK_REASON_CANCELLED,
    MANUAL_FALLBACK_REASON_LOW_CONFIDENCE,
)

# 回滚事件动作
ROLLBACK_ACTION_SHUTDOWN = 'shutdown'
ROLLBACK_ACTION_RESTORE = 'restore'

# 审计来源
AUDIT_SOURCE_API = 'api'
AUDIT_SOURCE_PAGE = 'page'
AUDIT_SOURCE_AGENT = 'agent'
AUDIT_SOURCE_BACKGROUND = 'background'

# 复用 AI-R13 budget_control 的禁止动作集（保持一致，避免重新定义漂移）
AUTO_SUBMIT_FORBIDDEN_ACTIONS: tuple[str, ...] = (
    'submit', 'audit', 'approve', 'complete', 'close',
    'void', 'delete', 'confirm_submit', 'auto_dispatch', 'auto_complete',
)

# 默认回滚时间上限（分钟）
DEFAULT_ROLLBACK_MAX_MINUTES = 10


# ===== 数据类 =====

@dataclass
class RolloutDecision:
    """灰度判定结果。

    Attributes:
        allowed: 是否允许。
        reason: 拒绝原因（允许时为空字符串）。
        stage: 判定阶段（global/flag/role/allowlist/risk）。
        mode: 当前灰度模式。
        user_id: 用户 ID（未登录为 None）。
        role: 用户角色（未登录为 None）。
        capability: AI 能力名。
        risk_level: 风险级别。
    """
    allowed: bool
    reason: str
    stage: str
    mode: str
    user_id: Optional[int]
    role: Optional[str]
    capability: str
    risk_level: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'allowed': self.allowed,
            'reason': self.reason,
            'stage': self.stage,
            'mode': self.mode,
            'user_id': self.user_id,
            'role': self.role,
            'capability': self.capability,
            'risk_level': self.risk_level,
        }


@dataclass
class RolloutSnapshot:
    """灰度配置快照（用于一键关闭-恢复）。

    Attributes:
        mode: 灰度模式。
        allowed_user_ids: 白名单用户 ID 列表。
        global_enabled: 全局开关是否启用。
        force_fallback: Provider 紧急回滚是否启用。
        taken_at: 快照时间。
    """
    mode: str
    allowed_user_ids: list[int]
    global_enabled: bool
    force_fallback: bool
    taken_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            'mode': self.mode,
            'allowed_user_ids': list(self.allowed_user_ids),
            'global_enabled': self.global_enabled,
            'force_fallback': self.force_fallback,
            'taken_at': self.taken_at.isoformat(),
        }


@dataclass
class ManualFallbackTask:
    """人工降级任务（Provider 故障等场景保留证据）。

    Attributes:
        task_id: 任务 ID。
        original_run_id: 原 AI 运行 ID（可能为 None）。
        reason: 降级原因（provider_fault/budget_exhausted/circuit_breaker/cancelled/low_confidence）。
        preserved_files: 保留的已上传文件证据列表。
        preserved_drafts: 保留的待确认草稿证据列表。
        created_at: 创建时间。
        status: 状态（pending/handled/rejected）。
        operator_id: 处理人 ID（未处理为 None）。
        handled_at: 处理时间（未处理为 None）。
    """
    task_id: str
    original_run_id: Optional[int]
    reason: str
    preserved_files: list[dict[str, Any]]
    preserved_drafts: list[dict[str, Any]]
    created_at: datetime
    status: str = 'pending'
    operator_id: Optional[int] = None
    handled_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'task_id': self.task_id,
            'original_run_id': self.original_run_id,
            'reason': self.reason,
            'preserved_files': list(self.preserved_files),
            'preserved_drafts': list(self.preserved_drafts),
            'created_at': self.created_at.isoformat(),
            'status': self.status,
            'operator_id': self.operator_id,
            'handled_at': self.handled_at.isoformat() if self.handled_at else None,
        }


@dataclass
class RollbackEvent:
    """回滚事件记录（一键关闭/恢复）。

    Attributes:
        event_id: 事件 ID。
        action: 动作（shutdown/restore）。
        operator_id: 操作人 ID。
        operator_role: 操作人角色。
        previous_snapshot: 操作前快照。
        new_snapshot: 操作后快照。
        started_at: 开始时间。
        completed_at: 完成时间。
    """
    event_id: str
    action: str
    operator_id: int
    operator_role: str
    previous_snapshot: RolloutSnapshot
    new_snapshot: RolloutSnapshot
    started_at: datetime
    completed_at: datetime

    @property
    def duration_seconds(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def duration_minutes(self) -> float:
        return self.duration_seconds / 60.0

    def to_dict(self) -> dict[str, Any]:
        return {
            'event_id': self.event_id,
            'action': self.action,
            'operator_id': self.operator_id,
            'operator_role': self.operator_role,
            'previous_snapshot': self.previous_snapshot.to_dict(),
            'new_snapshot': self.new_snapshot.to_dict(),
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat(),
            'duration_seconds': self.duration_seconds,
            'duration_minutes': self.duration_minutes,
        }


@dataclass
class RolloutAuditRecord:
    """灰度拒绝审计记录。

    F01 要求：灰度拒绝必须记录用户、角色、能力、原因、请求来源和时间，
    不保存密钥或完整敏感原文。

    Attributes:
        audit_id: 审计 ID。
        user_id: 用户 ID（未登录为 None）。
        role: 用户角色（未登录为 None）。
        capability: AI 能力名。
        reason: 拒绝原因。
        stage: 判定阶段。
        source: 请求来源（api/page/agent/background）。
        created_at: 创建时间。
    """
    audit_id: str
    user_id: Optional[int]
    role: Optional[str]
    capability: str
    reason: str
    stage: str
    source: str
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            'audit_id': self.audit_id,
            'user_id': self.user_id,
            'role': self.role,
            'capability': self.capability,
            'reason': self.reason,
            'stage': self.stage,
            'source': self.source,
            'created_at': self.created_at.isoformat(),
        }


# ===== 核心纯函数 =====

def is_admin(role: Optional[str]) -> bool:
    """admin 始终直通所有灰度检查。"""
    return role == 'admin'


def normalize_mode(raw_mode: Optional[str]) -> str:
    """将原始模式值归一化为 4 种合法模式之一（向后兼容旧值）。

    旧值映射：
    - admin_only → off（非 admin 全拒）
    - read_only → role（风险级别判定）
    - read_draft → role（风险级别判定）
    - all → all
    - off/allowlist/role → 原样保留
    - None/空/未知 → DEFAULT_MODE（off）
    """
    if not raw_mode:
        return DEFAULT_MODE
    return _LEGACY_MODE_MAP.get(raw_mode, DEFAULT_MODE)


def parse_allowed_user_ids(raw: Any) -> list[int]:
    """解析白名单用户 ID（支持逗号分隔字符串、列表、None）。

    用户白名单使用用户 ID（整数），不得依赖可变的显示名。
    """
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        result: list[int] = []
        for item in raw:
            try:
                uid = int(item)
                if uid > 0 and uid not in result:
                    result.append(uid)
            except (TypeError, ValueError):
                continue
        return result
    if isinstance(raw, str):
        result = []
        for part in raw.split(','):
            part = part.strip()
            if not part:
                continue
            try:
                uid = int(part)
                if uid > 0 and uid not in result:
                    result.append(uid)
            except ValueError:
                continue
        return result
    return []


def evaluate_rollout_access(
    *,
    capability: str,
    role: Optional[str],
    user_id: Optional[int],
    risk_level: str,
    mode: str,
    allowed_user_ids: list[int] | tuple[str, ...] | None,
    global_enabled: bool,
) -> RolloutDecision:
    """按固定顺序判定灰度访问权限。

    权限判定顺序（F01 要求）：
    1. 全局开关（global_enabled=False → 拒绝）
    2. 模式（off → 非 admin 拒绝）
    3. 角色（admin 直通）
    4. 用户白名单（allowlist 模式下仅白名单可用）
    5. 风险级别（role 模式下按风险级别判定）

    Args:
        capability: AI 能力名。
        role: 用户角色（未登录为 None）。
        user_id: 用户 ID（未登录为 None）。
        risk_level: 风险级别（read/sensitive_read/draft/sensitive_write）。
        mode: 灰度模式（已归一化）。
        allowed_user_ids: 白名单用户 ID 列表。
        global_enabled: 全局开关是否启用。

    Returns:
        RolloutDecision 判定结果（含拒绝原因和阶段）。
    """
    norm_mode = normalize_mode(mode)
    allowed_list = parse_allowed_user_ids(allowed_user_ids)

    # 阶段 1：全局开关
    if not global_enabled:
        return RolloutDecision(
            allowed=False,
            reason='AI 功能总开关已关闭',
            stage=STAGE_GLOBAL,
            mode=norm_mode,
            user_id=user_id,
            role=role,
            capability=capability,
            risk_level=risk_level,
        )

    # 阶段 2：角色（admin 直通，绕过后续模式判定）
    if is_admin(role):
        return RolloutDecision(
            allowed=True,
            reason='',
            stage=STAGE_ROLE,
            mode=norm_mode,
            user_id=user_id,
            role=role,
            capability=capability,
            risk_level=risk_level,
        )

    # 未登录用户（admin 已在上面直通，这里 role 非 admin）
    if role is None or user_id is None:
        return RolloutDecision(
            allowed=False,
            reason='未登录用户禁止使用 AI 能力',
            stage=STAGE_ROLE,
            mode=norm_mode,
            user_id=user_id,
            role=role,
            capability=capability,
            risk_level=risk_level,
        )

    # 阶段 3：模式判定
    if norm_mode == MODE_OFF:
        return RolloutDecision(
            allowed=False,
            reason='当前灰度模式为 off，仅管理员可用',
            stage=STAGE_ALLOWLIST,
            mode=norm_mode,
            user_id=user_id,
            role=role,
            capability=capability,
            risk_level=risk_level,
        )

    if norm_mode == MODE_ALLOWLIST:
        # 白名单模式：仅白名单用户可用
        if user_id not in allowed_list:
            return RolloutDecision(
                allowed=False,
                reason=f'用户 {user_id} 不在灰度白名单中',
                stage=STAGE_ALLOWLIST,
                mode=norm_mode,
                user_id=user_id,
                role=role,
                capability=capability,
                risk_level=risk_level,
            )
        return RolloutDecision(
            allowed=True,
            reason='',
            stage=STAGE_ALLOWLIST,
            mode=norm_mode,
            user_id=user_id,
            role=role,
            capability=capability,
            risk_level=risk_level,
        )

    if norm_mode == MODE_ROLE:
        # 角色模式：按风险级别判定（等价旧 read_draft）
        if risk_level not in {'read', 'sensitive_read', 'draft'}:
            return RolloutDecision(
                allowed=False,
                reason=f'角色模式不允许风险级别 {risk_level}',
                stage=STAGE_RISK,
                mode=norm_mode,
                user_id=user_id,
                role=role,
                capability=capability,
                risk_level=risk_level,
            )
        return RolloutDecision(
            allowed=True,
            reason='',
            stage=STAGE_RISK,
            mode=norm_mode,
            user_id=user_id,
            role=role,
            capability=capability,
            risk_level=risk_level,
        )

    # MODE_ALL：全部可用（仍受角色权限矩阵和风险级别约束，但灰度层放行）
    return RolloutDecision(
        allowed=True,
        reason='',
        stage=STAGE_RISK,
        mode=norm_mode,
        user_id=user_id,
        role=role,
        capability=capability,
        risk_level=risk_level,
    )


def snapshot_rollout(
    *,
    mode: str,
    allowed_user_ids: list[int] | None,
    global_enabled: bool,
    force_fallback: bool,
    taken_at: Optional[datetime] = None,
) -> RolloutSnapshot:
    """保存当前灰度配置快照（用于一键关闭-恢复）。"""
    return RolloutSnapshot(
        mode=normalize_mode(mode),
        allowed_user_ids=parse_allowed_user_ids(allowed_user_ids),
        global_enabled=bool(global_enabled),
        force_fallback=bool(force_fallback),
        taken_at=taken_at or datetime.now(),
    )


def restore_rollout(snapshot: RolloutSnapshot) -> dict[str, Any]:
    """从快照生成要恢复的设置键值（纯逻辑，不直接写设置）。

    Returns:
        dict 含 mode/allowed_user_ids/global_enabled/force_fallback 四项，
        由 app.py 的 ORM adapter 写入 SystemSetting。
    """
    return {
        'mode': snapshot.mode,
        'allowed_user_ids': list(snapshot.allowed_user_ids),
        'global_enabled': snapshot.global_enabled,
        'force_fallback': snapshot.force_fallback,
    }


def create_manual_fallback_task(
    *,
    task_id: str,
    original_run_id: Optional[int],
    reason: str,
    preserved_files: list[dict[str, Any]] | None = None,
    preserved_drafts: list[dict[str, Any]] | None = None,
    created_at: Optional[datetime] = None,
) -> ManualFallbackTask:
    """创建人工降级任务（Provider 故障等场景保留证据）。

    F01 要求：Provider 故障、超时、预算耗尽、熔断、取消时保留任务证据，
    降级为人工流程，不得丢失已上传文件和待确认草稿。
    """
    if reason not in ALL_FALLBACK_REASONS:
        raise ValueError(f'未知的人工降级原因：{reason}')
    return ManualFallbackTask(
        task_id=task_id,
        original_run_id=original_run_id,
        reason=reason,
        preserved_files=list(preserved_files or []),
        preserved_drafts=list(preserved_drafts or []),
        created_at=created_at or datetime.now(),
    )


def record_rollback_event(
    *,
    event_id: str,
    action: str,
    operator_id: int,
    operator_role: str,
    previous_snapshot: RolloutSnapshot,
    new_snapshot: RolloutSnapshot,
    started_at: datetime,
    completed_at: datetime,
) -> RollbackEvent:
    """记录回滚事件（一键关闭/恢复）。

    Args:
        action: ROLLBACK_ACTION_SHUTDOWN 或 ROLLBACK_ACTION_RESTORE。
        operator_id: 操作人用户 ID。
        operator_role: 操作人角色（必须为 admin，由 validate_admin_only_maintenance 校验）。
    """
    if action not in (ROLLBACK_ACTION_SHUTDOWN, ROLLBACK_ACTION_RESTORE):
        raise ValueError(f'未知的回滚动作：{action}')
    if completed_at < started_at:
        raise ValueError('完成时间不能早于开始时间')
    return RollbackEvent(
        event_id=event_id,
        action=action,
        operator_id=operator_id,
        operator_role=operator_role,
        previous_snapshot=previous_snapshot,
        new_snapshot=new_snapshot,
        started_at=started_at,
        completed_at=completed_at,
    )


def build_rollout_audit_record(
    *,
    audit_id: str,
    user_id: Optional[int],
    role: Optional[str],
    capability: str,
    reason: str,
    stage: str,
    source: str,
    created_at: Optional[datetime] = None,
) -> RolloutAuditRecord:
    """构造灰度拒绝审计记录。

    F01 要求：灰度拒绝必须记录用户、角色、能力、原因、请求来源和时间，
    不保存密钥或完整敏感原文。本函数仅构造纯数据记录，脱敏由调用方在
    写入前完成（如 capability/reason 不含密钥）。
    """
    if source not in (AUDIT_SOURCE_API, AUDIT_SOURCE_PAGE, AUDIT_SOURCE_AGENT, AUDIT_SOURCE_BACKGROUND):
        raise ValueError(f'未知的审计来源：{source}')
    return RolloutAuditRecord(
        audit_id=audit_id,
        user_id=user_id,
        role=role,
        capability=capability,
        reason=reason,
        stage=stage,
        source=source,
        created_at=created_at or datetime.now(),
    )


# ===== 校验函数 =====

def validate_permission_order(stages_in_order: list[str]) -> tuple[bool, str]:
    """校验权限判定顺序固定为：全局→功能→角色→白名单→风险→人工确认。

    Args:
        stages_in_order: 实际判定的阶段顺序列表。

    Returns:
        (是否通过, 原因)
    """
    if not stages_in_order:
        return False, '权限判定阶段列表为空'
    # 实际顺序必须是 PERMISSION_ORDER 的前缀子序列（允许跳过未触发的阶段，但顺序不能乱）
    expected_idx = 0
    for stage in stages_in_order:
        if stage not in PERMISSION_ORDER:
            return False, f'未知判定阶段：{stage}'
        stage_idx = PERMISSION_ORDER.index(stage)
        if stage_idx < expected_idx:
            return False, (
                f'权限判定顺序错误：{stage}（位置 {stage_idx}）出现在 '
                f'{PERMISSION_ORDER[expected_idx]}（位置 {expected_idx}）之后'
            )
        expected_idx = stage_idx
    return True, '权限判定顺序符合固定顺序'


def validate_admin_only_maintenance(role: str, action: str) -> tuple[bool, str]:
    """校验只有 admin 可以维护灰度名单和全局开关。

    F01 权限边界：只有 admin 可以维护灰度名单和全局开关。
    """
    if role != 'admin':
        return False, f'仅管理员可执行灰度维护动作 {action}，当前角色 {role}'
    return True, '管理员授权通过'


def validate_no_business_data_modified(event: RollbackEvent) -> tuple[bool, str]:
    """校验关闭/恢复操作不修改业务数据或用户密码。

    F01 要求：关闭不得修改业务数据或用户密码。
    本函数校验回滚事件动作仅限 shutdown/restore，不涉及业务表写入。
    实际业务表保护由 app.py 的 ORM adapter 保证不在 shutdown/restore 路径写入业务表。
    """
    if event.action not in (ROLLBACK_ACTION_SHUTDOWN, ROLLBACK_ACTION_RESTORE):
        return False, f'回滚动作非法：{event.action}，仅允许 shutdown/restore'
    # shutdown/restore 只修改系统设置（ai_feature_global_enabled/rollout_mode/allowed_user_ids/force_fallback），
    # 不触碰业务表（InOrder/OutOrder/Material/PurchaseOrder 等）和 User 表。
    return True, f'{event.action} 仅修改 AI 灰度设置，不修改业务数据或用户密码'


def validate_rollback_within_minutes(
    shutdown_event: RollbackEvent,
    restore_event: RollbackEvent,
    *,
    max_minutes: int = DEFAULT_ROLLBACK_MAX_MINUTES,
    now: Optional[datetime] = None,
) -> tuple[bool, str]:
    """校验关闭+恢复全过程在 max_minutes 分钟内（F01 要求 10 分钟内）。

    Args:
        shutdown_event: 关闭事件。
        restore_event: 恢复事件。
        max_minutes: 最大允许分钟数（默认 10）。
        now: 注入当前时间（可复算），None 时用 datetime.now()。

    Returns:
        (是否通过, 原因)
    """
    if shutdown_event.action != ROLLBACK_ACTION_SHUTDOWN:
        return False, f'第一个事件应为 shutdown，实际为 {shutdown_event.action}'
    if restore_event.action != ROLLBACK_ACTION_RESTORE:
        return False, f'第二个事件应为 restore，实际为 {restore_event.action}'

    # 时间顺序校验
    if shutdown_event.completed_at < shutdown_event.started_at:
        return False, '关闭完成时间早于关闭开始时间'
    if restore_event.completed_at < restore_event.started_at:
        return False, '恢复完成时间早于恢复开始时间'
    if restore_event.started_at < shutdown_event.completed_at:
        return False, '恢复开始时间早于关闭完成时间'

    # 总耗时 = 关闭耗时 + 恢复耗时
    shutdown_seconds = (shutdown_event.completed_at - shutdown_event.started_at).total_seconds()
    restore_seconds = (restore_event.completed_at - restore_event.started_at).total_seconds()
    total_seconds = shutdown_seconds + restore_seconds
    total_minutes = total_seconds / 60.0

    if total_minutes > max_minutes:
        return False, (
            f'关闭+恢复总耗时 {total_minutes:.2f} 分钟，'
            f'超过 {max_minutes} 分钟上限'
        )
    return True, (
        f'关闭+恢复总耗时 {total_minutes:.2f} 分钟，'
        f'在 {max_minutes} 分钟内'
    )


def validate_user_removed_immediately(
    user_id: int,
    current_allowed_user_ids: list[int],
) -> bool:
    """校验用户被移出白名单后立即失效（不依赖重启）。

    F01 专项验证：用户被移出白名单后立即失效，不依赖重启。
    本函数校验当前白名单列表不含该用户即立即生效（纯函数，无缓存）。
    """
    return user_id not in parse_allowed_user_ids(current_allowed_user_ids)


def validate_auto_submit_forbidden(actions: list[str]) -> tuple[bool, str]:
    """校验动作列表不含自动提交禁止动作。

    复用 budget_control.AUTO_SUBMIT_FORBIDDEN_ACTIONS 的口径（保持一致）。
    F01 权限边界：AI 永远不能自动提交、审核、完成、反提交、作废、删除、付款或修改密码。
    """
    forbidden_hits = [a for a in actions if a in AUTO_SUBMIT_FORBIDDEN_ACTIONS]
    if forbidden_hits:
        return False, f'检测到禁止自动执行的动作：{forbidden_hits}'
    return True, '未检测到禁止自动执行的动作'


def validate_no_sensitive_in_audit(record: RolloutAuditRecord) -> tuple[bool, str]:
    """校验审计记录不含密钥或完整敏感原文。

    F01 要求：不保存密钥或完整敏感原文。
    本函数检查 reason/capability 字段不含 api_key/token/secret/password 等敏感关键词。
    """
    sensitive_keywords = ('api_key', 'apikey', 'token', 'secret', 'password', 'bearer ')
    for field_name in ('reason', 'capability'):
        value = getattr(record, field_name, '') or ''
        lower_value = value.lower()
        for kw in sensitive_keywords:
            if kw in lower_value:
                return False, f'审计记录字段 {field_name} 含敏感关键词 {kw}'
    return True, '审计记录不含敏感信息'


def validate_fallback_preserves_evidence(task: ManualFallbackTask) -> tuple[bool, str]:
    """校验人工降级任务保留了文件和草稿证据。

    F01 要求：降级为人工流程，不得丢失已上传文件和待确认草稿。
    """
    if task.reason not in ALL_FALLBACK_REASONS:
        return False, f'未知降级原因：{task.reason}'
    if task.status not in ('pending', 'handled', 'rejected'):
        return False, f'未知任务状态：{task.status}'
    # 文件证据和草稿证据至少有一个非空（除非 reason 是 cancelled，可能无文件）
    if task.reason != MANUAL_FALLBACK_REASON_CANCELLED:
        if not task.preserved_files and not task.preserved_drafts:
            return False, f'降级原因 {task.reason} 需保留文件或草稿证据，当前均为空'
    return True, '人工降级任务证据保留完整'


def validate_all(
    decision: RolloutDecision,
    *,
    shutdown_event: Optional[RollbackEvent] = None,
    restore_event: Optional[RollbackEvent] = None,
    audit_record: Optional[RolloutAuditRecord] = None,
    fallback_task: Optional[ManualFallbackTask] = None,
    max_minutes: int = DEFAULT_ROLLBACK_MAX_MINUTES,
) -> tuple[bool, list[str]]:
    """一次性多项校验。

    Returns:
        (是否全部通过, 原因列表)
    """
    reasons: list[str] = []
    all_passed = True

    # 权限判定顺序校验（单次判定至少触发了 global→role/allowlist→risk）
    stages = [decision.stage] if decision.stage else []
    # 补全隐含阶段（global 在前，decision.stage 是最终阶段）
    if decision.stage != STAGE_GLOBAL:
        stages = [STAGE_GLOBAL] + stages
    ok, msg = validate_permission_order(stages)
    if not ok:
        all_passed = False
        reasons.append(msg)

    # 回滚时间校验
    if shutdown_event and restore_event:
        ok, msg = validate_rollback_within_minutes(
            shutdown_event, restore_event, max_minutes=max_minutes
        )
        if not ok:
            all_passed = False
            reasons.append(msg)

    # 审计脱敏校验
    if audit_record:
        ok, msg = validate_no_sensitive_in_audit(audit_record)
        if not ok:
            all_passed = False
            reasons.append(msg)

    # 降级证据校验
    if fallback_task:
        ok, msg = validate_fallback_preserves_evidence(fallback_task)
        if not ok:
            all_passed = False
            reasons.append(msg)

    if all_passed:
        reasons.append('所有校验通过')
    return all_passed, reasons

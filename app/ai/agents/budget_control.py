"""AI-R13：Agent 预算、取消、熔断和并发控制。

# AI_TASK: AI-R13

范围：最大步骤、最大耗时、最大工具调用、截止时间、取消、并发互斥、失败重试来源、
Provider 熔断和等待人工状态。

设计：
- 纯逻辑 + 依赖注入：不依赖 Flask/ORM，与 AI-R06~R12 一致。
- CI 无 DB 可 mock 测，生产由 app.py 提供 ORM adapter。
- 作为现有 framework.py 的增强层，不修改现有 AgentRun/AgentExecutor 接口。
- 提供预算检查、并发锁、Provider 熔断器、等待人工状态、重试证据保留 5 大能力。

验收：
1. 无无限循环：max_steps 校验，超出预算安全停止。
2. 超预算、越权和故障安全停止：budget check + circuit breaker。
3. 重试保留原证据：retry record 含原 run_id 和 evidence。
4. 自动提交业务单据次数为 0：validate_no_auto_submit 校验。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional


# ===== 常量 =====

# 预算违规类型
VIOLATION_MAX_STEPS = 'max_steps_exceeded'
VIOLATION_MAX_DURATION = 'max_duration_exceeded'
VIOLATION_MAX_TOOL_CALLS = 'max_tool_calls_exceeded'
VIOLATION_DEADLINE = 'deadline_exceeded'
VIOLATION_CIRCUIT_OPEN = 'circuit_breaker_open'
VIOLATION_CONCURRENCY_LOCK = 'concurrency_lock_held'
VIOLATION_WAITING_HUMAN = 'waiting_human_confirmation'

# 熔断器状态
CIRCUIT_CLOSED = 'closed'        # 正常，允许调用
CIRCUIT_OPEN = 'open'            # 熔断，拒绝调用
CIRCUIT_HALF_OPEN = 'half_open'  # 半开，允许试探性调用

# 运行状态扩展（与 framework.AgentRunStatus 兼容）
STATUS_WAITING_HUMAN = 'waiting_human'  # 等待人工确认
STATUS_CANCELLED = 'cancelled'

# 自动提交业务单据禁止动作
AUTO_SUBMIT_FORBIDDEN_ACTIONS = (
    'submit', 'audit', 'approve', 'complete', 'close', 'void',
    'delete', 'confirm_submit', 'auto_dispatch', 'auto_complete',
)


# ===== 数据结构 =====

@dataclass(frozen=True)
class BudgetConfig:
    """Agent 运行预算配置。"""

    max_steps: int = 20                  # 最大步骤数
    max_duration_seconds: int = 600      # 最大耗时（秒）
    max_tool_calls: int = 50             # 最大工具调用次数
    deadline_iso: Optional[str] = None   # 截止时间 ISO8601（None 表示无截止）
    concurrency_key: Optional[str] = None  # 并发互斥键（如 user_id:agent_name）

    def to_dict(self) -> dict[str, Any]:
        return {
            'max_steps': self.max_steps,
            'max_duration_seconds': self.max_duration_seconds,
            'max_tool_calls': self.max_tool_calls,
            'deadline_iso': self.deadline_iso,
            'concurrency_key': self.concurrency_key,
        }


@dataclass(frozen=True)
class BudgetCheckResult:
    """预算检查结果。"""

    passed: bool
    reason: str
    violation_type: Optional[str] = None
    current_steps: int = 0
    current_duration_seconds: int = 0
    current_tool_calls: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            'passed': self.passed,
            'reason': self.reason,
            'violation_type': self.violation_type,
            'current_steps': self.current_steps,
            'current_duration_seconds': self.current_duration_seconds,
            'current_tool_calls': self.current_tool_calls,
        }


@dataclass
class CircuitBreakerState:
    """Provider 熔断器状态（可变，记录连续失败计数）。"""

    provider_name: str
    failure_count: int = 0
    threshold: int = 5                  # 连续失败 5 次触发熔断
    cooldown_seconds: int = 60          # 熔断冷却时间（秒）
    state: str = CIRCUIT_CLOSED
    last_failure_at: Optional[str] = None
    last_failure_reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'provider_name': self.provider_name,
            'failure_count': self.failure_count,
            'threshold': self.threshold,
            'cooldown_seconds': self.cooldown_seconds,
            'state': self.state,
            'last_failure_at': self.last_failure_at,
            'last_failure_reason': self.last_failure_reason,
        }


@dataclass(frozen=True)
class ConcurrencyLock:
    """并发互斥锁。"""

    key: str
    holder_run_id: str
    locked_until: str  # ISO8601
    acquired_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'key': self.key,
            'holder_run_id': self.holder_run_id,
            'locked_until': self.locked_until,
            'acquired_at': self.acquired_at,
        }


@dataclass(frozen=True)
class RetryRecord:
    """重试记录（保留原证据，验收3）。"""

    retry_id: str
    original_run_id: str                # 原 run_id
    retry_run_id: str                   # 重试 run_id
    retry_reason: str
    original_evidence: dict[str, Any]   # 原运行证据（步骤结果/工具调用记录）
    retry_count: int                    # 第几次重试（1 开始）
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'retry_id': self.retry_id,
            'original_run_id': self.original_run_id,
            'retry_run_id': self.retry_run_id,
            'retry_reason': self.retry_reason,
            'original_evidence': self.original_evidence,
            'retry_count': self.retry_count,
            'created_at': self.created_at,
        }


@dataclass(frozen=True)
class HumanConfirmationRequest:
    """等待人工确认请求。"""

    run_id: str
    step_no: int
    action: str                         # 待确认动作（如 submit/audit）
    target_type: str                    # 目标单据类型（如 in_order/out_order）
    target_id: Optional[int]            # 目标单据 ID
    reason: str                         # 需要人工确认的原因
    created_at: str
    status: str = STATUS_WAITING_HUMAN  # waiting_human / confirmed / rejected

    def to_dict(self) -> dict[str, Any]:
        return {
            'run_id': self.run_id,
            'step_no': self.step_no,
            'action': self.action,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'reason': self.reason,
            'created_at': self.created_at,
            'status': self.status,
        }


# ===== 依赖注入回调类型 =====

AcquireLockFn = Callable[[str, str, str], bool]
ReleaseLockFn = Callable[[str, str], bool]
QueryLockFn = Callable[[str], Optional[ConcurrencyLock]]
SaveRetryFn = Callable[[RetryRecord], RetryRecord]
QueryRetryFn = Callable[[str], list[RetryRecord]]
SaveHumanReqFn = Callable[[HumanConfirmationRequest], HumanConfirmationRequest]
UpdateHumanReqFn = Callable[[str, str], HumanConfirmationRequest]
QueryHumanReqFn = Callable[[str], Optional[HumanConfirmationRequest]]


# ===== 预算检查 =====

def check_budget(
    config: BudgetConfig,
    *,
    current_steps: int,
    started_at_iso: str,
    current_tool_calls: int,
    now_iso: Optional[str] = None,
) -> BudgetCheckResult:
    """检查 Agent 运行预算（验收1+2：无无限循环+超预算安全停止）。

    检查项：
    1. max_steps：当前步骤数不超过上限。
    2. max_duration_seconds：已运行时长不超过上限。
    3. max_tool_calls：当前工具调用次数不超过上限。
    4. deadline_iso：未超过截止时间。
    """
    now = _parse_iso(now_iso) or datetime.now()
    started = _parse_iso(started_at_iso)
    if started is None:
        return BudgetCheckResult(
            passed=False,
            reason='启动时间无效，无法校验预算',
            violation_type=VIOLATION_MAX_DURATION,
            current_steps=current_steps,
            current_tool_calls=current_tool_calls,
        )

    duration_seconds = int((now - started).total_seconds())
    if duration_seconds < 0:
        duration_seconds = 0

    # 1. max_steps
    if current_steps > config.max_steps:
        return BudgetCheckResult(
            passed=False,
            reason=f'步骤数 {current_steps} 超过上限 {config.max_steps}',
            violation_type=VIOLATION_MAX_STEPS,
            current_steps=current_steps,
            current_duration_seconds=duration_seconds,
            current_tool_calls=current_tool_calls,
        )

    # 2. max_duration_seconds
    if duration_seconds > config.max_duration_seconds:
        return BudgetCheckResult(
            passed=False,
            reason=f'运行时长 {duration_seconds}s 超过上限 {config.max_duration_seconds}s',
            violation_type=VIOLATION_MAX_DURATION,
            current_steps=current_steps,
            current_duration_seconds=duration_seconds,
            current_tool_calls=current_tool_calls,
        )

    # 3. max_tool_calls
    if current_tool_calls > config.max_tool_calls:
        return BudgetCheckResult(
            passed=False,
            reason=f'工具调用次数 {current_tool_calls} 超过上限 {config.max_tool_calls}',
            violation_type=VIOLATION_MAX_TOOL_CALLS,
            current_steps=current_steps,
            current_duration_seconds=duration_seconds,
            current_tool_calls=current_tool_calls,
        )

    # 4. deadline_iso
    if config.deadline_iso:
        deadline = _parse_iso(config.deadline_iso)
        if deadline is not None and now > deadline:
            return BudgetCheckResult(
                passed=False,
                reason=f'当前时间 {now.isoformat()} 超过截止时间 {config.deadline_iso}',
                violation_type=VIOLATION_DEADLINE,
                current_steps=current_steps,
                current_duration_seconds=duration_seconds,
                current_tool_calls=current_tool_calls,
            )

    return BudgetCheckResult(
        passed=True,
        reason='预算检查通过',
        current_steps=current_steps,
        current_duration_seconds=duration_seconds,
        current_tool_calls=current_tool_calls,
    )


# ===== 并发互斥 =====

def acquire_concurrency_lock(
    config: BudgetConfig,
    run_id: str,
    *,
    now_iso: Optional[str] = None,
    acquire_fn: Optional[AcquireLockFn] = None,
    query_fn: Optional[QueryLockFn] = None,
    lock_ttl_seconds: int = 600,
) -> tuple[bool, Optional[ConcurrencyLock], str]:
    """获取并发互斥锁（验收2：超预算/越权/故障安全停止）。

    同 concurrency_key 同时只能有一个 Agent 运行；锁含 TTL 防止死锁。
    """
    if not config.concurrency_key:
        return True, None, '无并发键，跳过锁校验'

    now = _parse_iso(now_iso) or datetime.now()
    locked_until = (now + timedelta(seconds=lock_ttl_seconds)).isoformat()

    # 查询现有锁
    if query_fn is not None:
        try:
            existing = query_fn(config.concurrency_key)
            if existing is not None:
                existing_until = _parse_iso(existing.locked_until)
                if existing_until is not None and now < existing_until and existing.holder_run_id != run_id:
                    return False, existing, f'并发锁被 {existing.holder_run_id} 持有至 {existing.locked_until}'
        except Exception:
            pass

    # 获取锁
    if acquire_fn is not None:
        try:
            ok = acquire_fn(config.concurrency_key, run_id, locked_until)
            if not ok:
                return False, None, '并发锁获取失败'
        except Exception as exc:
            return False, None, f'并发锁获取异常：{exc}'

    lock = ConcurrencyLock(
        key=config.concurrency_key,
        holder_run_id=run_id,
        locked_until=locked_until,
        acquired_at=now.isoformat(),
    )
    return True, lock, '并发锁获取成功'


def release_concurrency_lock(
    config: BudgetConfig,
    run_id: str,
    *,
    release_fn: Optional[ReleaseLockFn] = None,
) -> bool:
    """释放并发互斥锁。"""
    if not config.concurrency_key:
        return True
    if release_fn is None:
        return True
    try:
        return release_fn(config.concurrency_key, run_id)
    except Exception:
        return False


# ===== Provider 熔断 =====

def record_provider_call(
    breaker: CircuitBreakerState,
    *,
    success: bool,
    failure_reason: Optional[str] = None,
    now_iso: Optional[str] = None,
) -> CircuitBreakerState:
    """记录 Provider 调用结果，更新熔断器状态（验收2：故障安全停止）。

    - 成功：重置 failure_count=0，状态 closed。
    - 失败：failure_count+1；达到阈值时状态 open；冷却期后半开。
    """
    now = _parse_iso(now_iso) or datetime.now()
    now_str = now.isoformat()

    if success:
        breaker.failure_count = 0
        breaker.state = CIRCUIT_CLOSED
        breaker.last_failure_reason = None
        return breaker

    # 失败
    breaker.failure_count += 1
    breaker.last_failure_at = now_str
    breaker.last_failure_reason = failure_reason or '未知错误'

    # 检查是否从 open 转为 half_open（冷却期已过）
    if breaker.state == CIRCUIT_OPEN and breaker.last_failure_at:
        last_at = _parse_iso(breaker.last_failure_at)
        if last_at is not None:
            elapsed = (now - last_at).total_seconds()
            if elapsed >= breaker.cooldown_seconds:
                breaker.state = CIRCUIT_HALF_OPEN

    # half_open 状态下失败，立即回到 open
    if breaker.state == CIRCUIT_HALF_OPEN:
        breaker.state = CIRCUIT_OPEN
    # closed 状态下达到阈值，转为 open
    elif breaker.state == CIRCUIT_CLOSED and breaker.failure_count >= breaker.threshold:
        breaker.state = CIRCUIT_OPEN

    return breaker


def check_circuit_breaker(
    breaker: CircuitBreakerState,
    *,
    now_iso: Optional[str] = None,
) -> BudgetCheckResult:
    """检查熔断器是否允许调用（验收2：故障安全停止）。"""
    if breaker.state == CIRCUIT_CLOSED:
        return BudgetCheckResult(passed=True, reason='熔断器关闭，允许调用')

    if breaker.state == CIRCUIT_OPEN:
        # 检查冷却期是否已过
        if breaker.last_failure_at:
            last_at = _parse_iso(breaker.last_failure_at)
            now = _parse_iso(now_iso) or datetime.now()
            if last_at is not None and (now - last_at).total_seconds() >= breaker.cooldown_seconds:
                return BudgetCheckResult(
                    passed=True,
                    reason='熔断器冷却期已过，转半开状态允许试探性调用',
                )
        return BudgetCheckResult(
            passed=False,
            reason=f'Provider {breaker.provider_name} 熔断中（连续失败 {breaker.failure_count} 次）',
            violation_type=VIOLATION_CIRCUIT_OPEN,
        )

    # half_open
    return BudgetCheckResult(passed=True, reason='熔断器半开，允许试探性调用')


# ===== 等待人工状态 =====

def request_human_confirmation(
    run_id: str,
    step_no: int,
    action: str,
    target_type: str,
    *,
    target_id: Optional[int] = None,
    reason: str = '',
    now_iso: Optional[str] = None,
    save_fn: Optional[SaveHumanReqFn] = None,
) -> HumanConfirmationRequest:
    """发起人工确认请求（验收4：自动提交业务单据次数为 0）。

    涉及 submit/audit/approve/complete/close/void/delete 等动作必须人工确认。
    """
    now = _parse_iso(now_iso) or datetime.now()
    request = HumanConfirmationRequest(
        run_id=run_id,
        step_no=step_no,
        action=action,
        target_type=target_type,
        target_id=target_id,
        reason=reason or f'动作 {action} 需要人工确认',
        created_at=now.isoformat(),
        status=STATUS_WAITING_HUMAN,
    )
    if save_fn is not None:
        try:
            saved = save_fn(request)
            return saved
        except Exception:
            return request
    return request


def resume_from_human_confirmation(
    run_id: str,
    decision: str,
    *,
    update_fn: Optional[UpdateHumanReqFn] = None,
) -> tuple[bool, str, Optional[HumanConfirmationRequest]]:
    """恢复等待人工确认的运行。

    decision: 'confirmed' 或 'rejected'
    返回: (是否继续执行, 原因, 更新后的请求)
    """
    if decision not in ('confirmed', 'rejected'):
        return False, f'无效决策：{decision}，必须是 confirmed 或 rejected', None

    if update_fn is not None:
        try:
            updated = update_fn(run_id, decision)
        except Exception as exc:
            return False, f'更新人工确认请求异常：{exc}', None
    else:
        updated = None

    if decision == 'confirmed':
        return True, '人工确认通过，继续执行', updated
    return False, '人工确认拒绝，停止执行', updated


# ===== 重试证据保留 =====

def create_retry_record(
    original_run_id: str,
    retry_run_id: str,
    retry_reason: str,
    original_evidence: dict[str, Any],
    retry_count: int,
    *,
    now_iso: Optional[str] = None,
    save_fn: Optional[SaveRetryFn] = None,
) -> RetryRecord:
    """创建重试记录（验收3：重试保留原证据）。

    原运行证据（步骤结果、工具调用记录）必须保留，不覆盖历史记录。
    """
    now = _parse_iso(now_iso) or datetime.now()
    import uuid
    record = RetryRecord(
        retry_id=f'retry-{uuid.uuid4().hex[:12]}',
        original_run_id=original_run_id,
        retry_run_id=retry_run_id,
        retry_reason=retry_reason,
        original_evidence=dict(original_evidence) if original_evidence else {},
        retry_count=retry_count,
        created_at=now.isoformat(),
    )
    if save_fn is not None:
        try:
            saved = save_fn(record)
            return saved
        except Exception:
            return record
    return record


def list_retry_history(
    original_run_id: str,
    *,
    query_fn: Optional[QueryRetryFn] = None,
) -> list[RetryRecord]:
    """查询重试历史（验收3：重试保留原证据可追溯）。"""
    if query_fn is None:
        return []
    try:
        return list(query_fn(original_run_id) or [])
    except Exception:
        return []


# ===== 校验函数 =====

def validate_no_infinite_loop(
    config: BudgetConfig,
    current_steps: int,
    started_at_iso: str,
    current_tool_calls: int,
    *,
    now_iso: Optional[str] = None,
) -> tuple[bool, str]:
    """校验无无限循环（验收1）。"""
    result = check_budget(
        config,
        current_steps=current_steps,
        started_at_iso=started_at_iso,
        current_tool_calls=current_tool_calls,
        now_iso=now_iso,
    )
    if not result.passed:
        return False, f'检测到无限循环或超预算：{result.reason}'
    return True, '无无限循环校验通过'


def validate_no_auto_submit(
    actions: list[str],
) -> tuple[bool, str, list[str]]:
    """校验自动提交业务单据次数为 0（验收4）。

    检查动作列表中是否包含禁止的自动提交动作。
    返回: (是否通过, 原因, 违规动作列表)
    """
    violations = [a for a in actions if a in AUTO_SUBMIT_FORBIDDEN_ACTIONS]
    if violations:
        return False, f'检测到自动提交业务单据动作：{violations}', violations
    return True, '自动提交业务单据次数为 0', []


def validate_retry_preserves_evidence(
    record: RetryRecord,
    original_run_evidence: dict[str, Any],
) -> tuple[bool, str]:
    """校验重试保留原证据（验收3）。"""
    if not record.original_evidence:
        return False, '重试记录未保留原证据'
    # 原证据中的关键字段必须存在于重试记录中
    for key in original_run_evidence:
        if key not in record.original_evidence:
            return False, f'重试记录缺失原证据字段：{key}'
    if record.original_run_id != original_run_evidence.get('original_run_id', record.original_run_id):
        if record.original_run_id and original_run_evidence.get('original_run_id'):
            if record.original_run_id != original_run_evidence['original_run_id']:
                return False, '重试记录 original_run_id 与原运行不一致'
    return True, '重试保留原证据校验通过'


def validate_safety_stop_on_violation(
    budget_result: BudgetCheckResult,
    was_stopped: bool,
) -> tuple[bool, str]:
    """校验超预算/越权/故障时安全停止（验收2）。"""
    if not budget_result.passed and not was_stopped:
        return False, f'预算违规但未安全停止：{budget_result.reason}'
    if budget_result.passed and was_stopped:
        return False, '预算通过但被错误停止'
    return True, '安全停止校验通过'


def validate_permission_boundary(
    user_role: str,
    action: str,
    allowed_roles_for_action: tuple[str, ...],
) -> tuple[bool, str]:
    """校验越权安全停止（验收2：越权安全停止）。"""
    if user_role not in allowed_roles_for_action:
        return False, f'角色 {user_role} 无权执行动作 {action}（允许：{allowed_roles_for_action}）'
    return True, '权限边界校验通过'


# ===== 辅助函数 =====

def _parse_iso(iso_str: Optional[str]) -> Optional[datetime]:
    """解析 ISO8601 时间字符串，失败返回 None。"""
    if not iso_str:
        return None
    try:
        # 兼容带/不带微秒的格式
        if iso_str.endswith('Z'):
            iso_str = iso_str[:-1] + '+00:00'
        return datetime.fromisoformat(iso_str)
    except (ValueError, TypeError):
        return None

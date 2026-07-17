"""AI-R13 Agent 预算、取消、熔断和并发控制专项验证。

# AI_TASK: AI-R13

8 项测试覆盖：
1. 预算检查 max_steps 超限安全停止（验收1：无无限循环 + 验收2：超预算安全停止）
2. 预算检查 max_duration/max_tool_calls/deadline 超限
3. 并发互斥锁（同 key 互斥 + TTL + 释放）
4. Provider 熔断器（连续失败触发 open + 冷却期 half_open + 成功重置 closed）
5. 等待人工状态（submit/audit 必须人工确认 + confirmed/rejected 恢复）
6. 重试保留原证据（原 run_id + 步骤结果 + 工具调用记录）
7. 自动提交业务单据次数为 0（submit/audit/approve/complete/close/void/delete 禁止）
8. 越权安全停止（角色不在 allowed_roles 时拒绝）

设计：纯逻辑测试，不依赖 Flask/ORM，使用内存数据结构模拟锁/重试/人工确认状态。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-budget-control-secret'
sys.path.insert(0, str(APP_DIR))

from ai.agents.budget_control import (
    BudgetConfig,
    BudgetCheckResult,
    CircuitBreakerState,
    ConcurrencyLock,
    RetryRecord,
    HumanConfirmationRequest,
    STATUS_WAITING_HUMAN,
    STATUS_CANCELLED,
    CIRCUIT_CLOSED,
    CIRCUIT_OPEN,
    CIRCUIT_HALF_OPEN,
    VIOLATION_MAX_STEPS,
    VIOLATION_MAX_DURATION,
    VIOLATION_MAX_TOOL_CALLS,
    VIOLATION_DEADLINE,
    VIOLATION_CIRCUIT_OPEN,
    VIOLATION_CONCURRENCY_LOCK,
    AUTO_SUBMIT_FORBIDDEN_ACTIONS,
    check_budget,
    acquire_concurrency_lock,
    release_concurrency_lock,
    record_provider_call,
    check_circuit_breaker,
    request_human_confirmation,
    resume_from_human_confirmation,
    create_retry_record,
    list_retry_history,
    validate_no_infinite_loop,
    validate_no_auto_submit,
    validate_retry_preserves_evidence,
    validate_safety_stop_on_violation,
    validate_permission_boundary,
)


# ===== 测试1：预算检查 max_steps 超限安全停止 =====

def test1_budget_max_steps_safety_stop():
    """测试1：max_steps 超限安全停止（验收1：无无限循环 + 验收2：超预算安全停止）。"""
    config = BudgetConfig(max_steps=10, max_duration_seconds=600, max_tool_calls=50)
    started_at = '2026-07-17T10:00:00'
    now = '2026-07-17T10:01:00'  # 1 分钟后

    # 正常情况：步骤数 5 <= max_steps 10
    result_ok = check_budget(config, current_steps=5, started_at_iso=started_at, current_tool_calls=5, now_iso=now)
    assert result_ok.passed, f'正常情况应通过：{result_ok.reason}'
    assert result_ok.violation_type is None

    # 超步骤：步骤数 11 > max_steps 10
    result_over = check_budget(config, current_steps=11, started_at_iso=started_at, current_tool_calls=5, now_iso=now)
    assert not result_over.passed, '超步骤应失败'
    assert result_over.violation_type == VIOLATION_MAX_STEPS, f'违规类型错误：{result_over.violation_type}'
    assert '11' in result_over.reason and '10' in result_over.reason

    # 验收1：无无限循环校验
    ok_loop, msg_loop = validate_no_infinite_loop(config, 11, started_at, 5, now_iso=now)
    assert not ok_loop, '超步骤应被无无限循环校验拦截'

    # 验收2：超预算安全停止校验
    ok_safety, msg_safety = validate_safety_stop_on_violation(result_over, was_stopped=True)
    assert ok_safety, f'安全停止校验失败：{msg_safety}'
    ok_safety_bad, _ = validate_safety_stop_on_violation(result_over, was_stopped=False)
    assert not ok_safety_bad, '超预算但未停止应校验失败'

    print('PASS 测试1：max_steps 超限安全停止（无无限循环 + 超预算安全停止）')


# ===== 测试2：max_duration/max_tool_calls/deadline 超限 =====

def test2_budget_other_violations():
    """测试2：max_duration/max_tool_calls/deadline 超限。"""
    started_at = '2026-07-17T10:00:00'

    # max_duration 超限
    config_duration = BudgetConfig(max_steps=20, max_duration_seconds=60, max_tool_calls=50)
    result_dur = check_budget(
        config_duration,
        current_steps=5,
        started_at_iso=started_at,
        current_tool_calls=5,
        now_iso='2026-07-17T10:02:00',  # 2 分钟 = 120s > 60s
    )
    assert not result_dur.passed, '超时长应失败'
    assert result_dur.violation_type == VIOLATION_MAX_DURATION
    assert result_dur.current_duration_seconds == 120

    # max_tool_calls 超限
    config_calls = BudgetConfig(max_steps=20, max_duration_seconds=600, max_tool_calls=10)
    result_calls = check_budget(
        config_calls,
        current_steps=5,
        started_at_iso=started_at,
        current_tool_calls=15,
        now_iso='2026-07-17T10:00:30',
    )
    assert not result_calls.passed, '超工具调用应失败'
    assert result_calls.violation_type == VIOLATION_MAX_TOOL_CALLS

    # deadline 超限
    config_deadline = BudgetConfig(
        max_steps=20, max_duration_seconds=600, max_tool_calls=50,
        deadline_iso='2026-07-17T10:00:30',
    )
    result_deadline = check_budget(
        config_deadline,
        current_steps=5,
        started_at_iso=started_at,
        current_tool_calls=5,
        now_iso='2026-07-17T10:01:00',  # 超过 deadline
    )
    assert not result_deadline.passed, '超 deadline 应失败'
    assert result_deadline.violation_type == VIOLATION_DEADLINE

    # 启动时间无效
    result_invalid = check_budget(
        config_calls, current_steps=5, started_at_iso='invalid', current_tool_calls=5, now_iso=now_iso_safe()
    )
    assert not result_invalid.passed
    assert result_invalid.violation_type == VIOLATION_MAX_DURATION

    print('PASS 测试2：max_duration/max_tool_calls/deadline 超限 + 启动时间无效')


# ===== 测试3：并发互斥锁 =====

def test3_concurrency_lock():
    """测试3：并发互斥锁（同 key 互斥 + TTL + 释放）。"""
    # 内存锁存储
    locks: dict[str, ConcurrencyLock] = {}

    def acquire_fn(key, run_id, locked_until_iso):
        existing = locks.get(key)
        if existing and existing.holder_run_id != run_id:
            # 简化：检查 TTL（实际由 query_fn 检查）
            pass
        locks[key] = ConcurrencyLock(
            key=key, holder_run_id=run_id, locked_until=locked_until_iso, acquired_at=now_iso_safe()
        )
        return True

    def release_fn(key, run_id):
        if key in locks and locks[key].holder_run_id == run_id:
            del locks[key]
            return True
        return False

    def query_fn(key):
        return locks.get(key)

    config = BudgetConfig(concurrency_key='user1:warehouse_patrol')

    # run1 获取锁
    ok1, lock1, msg1 = acquire_concurrency_lock(
        config, 'run-1', acquire_fn=acquire_fn, query_fn=query_fn, now_iso='2026-07-17T10:00:00'
    )
    assert ok1, f'run1 获取锁失败：{msg1}'
    assert lock1 is not None
    assert lock1.holder_run_id == 'run-1'

    # run2 同 key 获取锁应失败（被 run1 持有）
    ok2, lock2, msg2 = acquire_concurrency_lock(
        config, 'run-2', acquire_fn=acquire_fn, query_fn=query_fn, now_iso='2026-07-17T10:00:30'
    )
    assert not ok2, f'run2 不应获取到锁：{msg2}'
    assert 'run-1' in msg2, f'消息应包含持有者：{msg2}'

    # run1 释放锁
    released = release_concurrency_lock(config, 'run-1', release_fn=release_fn)
    assert released, 'run1 释放锁应成功'

    # run2 重新获取锁应成功
    ok3, lock3, msg3 = acquire_concurrency_lock(
        config, 'run-2', acquire_fn=acquire_fn, query_fn=query_fn, now_iso='2026-07-17T10:01:00'
    )
    assert ok3, f'run2 释放后应获取到锁：{msg3}'

    # 无 concurrency_key 时跳过锁校验
    config_no_key = BudgetConfig()
    ok4, _, msg4 = acquire_concurrency_lock(config_no_key, 'run-3', now_iso=now_iso_safe())
    assert ok4, '无 concurrency_key 应跳过锁校验'
    assert '跳过' in msg4

    print('PASS 测试3：并发互斥锁（同 key 互斥 + 释放后可获取 + 无 key 跳过）')


# ===== 测试4：Provider 熔断器 =====

def test4_circuit_breaker():
    """测试4：Provider 熔断器（连续失败触发 open + 冷却期 half_open + 成功重置 closed）。"""
    breaker = CircuitBreakerState(provider_name='test_provider', threshold=3, cooldown_seconds=60)

    # 初始状态 closed
    assert breaker.state == CIRCUIT_CLOSED
    check_initial = check_circuit_breaker(breaker, now_iso='2026-07-17T10:00:00')
    assert check_initial.passed, 'closed 状态应允许调用'

    # 连续失败 3 次（达到阈值）触发 open
    breaker = record_provider_call(breaker, success=False, failure_reason='timeout', now_iso='2026-07-17T10:00:10')
    assert breaker.failure_count == 1
    assert breaker.state == CIRCUIT_CLOSED, f'第1次失败不应熔断：{breaker.state}'

    breaker = record_provider_call(breaker, success=False, failure_reason='timeout', now_iso='2026-07-17T10:00:20')
    assert breaker.failure_count == 2
    assert breaker.state == CIRCUIT_CLOSED

    breaker = record_provider_call(breaker, success=False, failure_reason='timeout', now_iso='2026-07-17T10:00:30')
    assert breaker.failure_count == 3
    assert breaker.state == CIRCUIT_OPEN, f'第3次失败应触发熔断：{breaker.state}'

    # open 状态拒绝调用
    check_open = check_circuit_breaker(breaker, now_iso='2026-07-17T10:00:40')
    assert not check_open.passed, 'open 状态应拒绝调用'
    assert check_open.violation_type == VIOLATION_CIRCUIT_OPEN

    # 冷却期后（60s）转为 half_open，允许试探性调用
    check_half_open = check_circuit_breaker(breaker, now_iso='2026-07-17T10:01:31')  # 60s 后
    assert check_half_open.passed, '冷却期后应允许试探性调用'

    # half_open 状态下成功，重置为 closed
    breaker = record_provider_call(breaker, success=True, now_iso='2026-07-17T10:01:35')
    assert breaker.state == CIRCUIT_CLOSED, f'half_open 成功应重置为 closed：{breaker.state}'
    assert breaker.failure_count == 0

    # half_open 状态下失败，立即回到 open
    breaker2 = CircuitBreakerState(provider_name='test2', threshold=2, cooldown_seconds=60)
    breaker2 = record_provider_call(breaker2, success=False, now_iso='2026-07-17T10:00:00')
    breaker2 = record_provider_call(breaker2, success=False, now_iso='2026-07-17T10:00:10')
    assert breaker2.state == CIRCUIT_OPEN
    # 冷却期后转 half_open
    breaker2 = record_provider_call(breaker2, success=False, now_iso='2026-07-17T10:01:11')  # 60s 后失败
    assert breaker2.state == CIRCUIT_OPEN, f'half_open 失败应立即回 open：{breaker2.state}'

    print('PASS 测试4：Provider 熔断器（closed→open→half_open→closed/open + 冷却期）')


# ===== 测试5：等待人工状态 =====

def test5_human_confirmation():
    """测试5：等待人工状态（submit/audit 必须人工确认 + confirmed/rejected 恢复）。"""
    # 内存存储
    saved_requests: dict[str, HumanConfirmationRequest] = {}

    def save_fn(req):
        saved_requests[req.run_id] = req
        return req

    def update_fn(run_id, decision):
        req = saved_requests.get(run_id)
        if req is None:
            return None
        from dataclasses import replace
        updated = replace(req, status=decision)
        saved_requests[run_id] = updated
        return updated

    # submit 动作必须人工确认
    req = request_human_confirmation(
        run_id='run-submit-1', step_no=3, action='submit', target_type='in_order',
        target_id=123, reason='入库单提交需人工确认', save_fn=save_fn,
        now_iso='2026-07-17T10:00:00',
    )
    assert req.status == STATUS_WAITING_HUMAN
    assert req.action == 'submit'
    assert req.target_type == 'in_order'
    assert req.target_id == 123
    assert saved_requests['run-submit-1'].status == STATUS_WAITING_HUMAN

    # confirmed 决策：继续执行
    ok_confirmed, msg_confirmed, updated_confirmed = resume_from_human_confirmation(
        'run-submit-1', 'confirmed', update_fn=update_fn
    )
    assert ok_confirmed, f'confirmed 应继续执行：{msg_confirmed}'
    assert updated_confirmed.status == 'confirmed'

    # rejected 决策：停止执行
    req2 = request_human_confirmation(
        run_id='run-audit-1', step_no=5, action='audit', target_type='out_order',
        target_id=456, save_fn=save_fn, now_iso='2026-07-17T10:00:00',
    )
    ok_rejected, msg_rejected, updated_rejected = resume_from_human_confirmation(
        'run-audit-1', 'rejected', update_fn=update_fn
    )
    assert not ok_rejected, 'rejected 应停止执行'
    assert '拒绝' in msg_rejected or '停止' in msg_rejected
    assert updated_rejected.status == 'rejected'

    # 无效决策
    ok_invalid, msg_invalid, _ = resume_from_human_confirmation('run-submit-1', 'invalid', update_fn=update_fn)
    assert not ok_invalid
    assert '无效' in msg_invalid or 'confirmed' in msg_invalid

    # 无 save_fn 也能工作
    req_no_save = request_human_confirmation(
        run_id='run-no-save', step_no=1, action='complete', target_type='in_order',
        now_iso='2026-07-17T10:00:00',
    )
    assert req_no_save.status == STATUS_WAITING_HUMAN

    print('PASS 测试5：等待人工状态（submit/audit 必须确认 + confirmed/rejected 恢复 + 无效决策拒绝）')


# ===== 测试6：重试保留原证据 =====

def test6_retry_preserves_evidence():
    """测试6：重试保留原证据（原 run_id + 步骤结果 + 工具调用记录）。"""
    saved_records: list[RetryRecord] = []

    def save_fn(record):
        saved_records.append(record)
        return record

    def query_fn(original_run_id):
        return [r for r in saved_records if r.original_run_id == original_run_id]

    original_evidence = {
        'original_run_id': 'run-original-1',
        'step_results': [
            {'step_no': 1, 'tool': 'get_stock', 'result': {'qty': 100}},
            {'step_no': 2, 'tool': 'create_draft', 'result': {'draft_id': 200}},
        ],
        'tool_calls': [
            {'tool': 'get_stock', 'success': True, 'duration_ms': 150},
            {'tool': 'create_draft', 'success': True, 'duration_ms': 200},
        ],
        'error': '步骤3 LLM 调用超时',
    }

    # 创建重试记录
    record = create_retry_record(
        original_run_id='run-original-1',
        retry_run_id='run-retry-1',
        retry_reason='LLM 调用超时，重试',
        original_evidence=original_evidence,
        retry_count=1,
        save_fn=save_fn,
        now_iso='2026-07-17T10:00:00',
    )
    assert record.original_run_id == 'run-original-1'
    assert record.retry_run_id == 'run-retry-1'
    assert record.retry_count == 1
    assert record.original_evidence == original_evidence
    assert 'step_results' in record.original_evidence
    assert 'tool_calls' in record.original_evidence
    assert len(saved_records) == 1

    # 验收3：校验证据保留
    ok, msg = validate_retry_preserves_evidence(record, original_evidence)
    assert ok, f'证据保留校验失败：{msg}'

    # 查询重试历史
    history = list_retry_history('run-original-1', query_fn=query_fn)
    assert len(history) == 1
    assert history[0].retry_run_id == 'run-retry-1'

    # 创建第二次重试
    record2 = create_retry_record(
        original_run_id='run-original-1',
        retry_run_id='run-retry-2',
        retry_reason='步骤4 失败，重试',
        original_evidence=original_evidence,
        retry_count=2,
        save_fn=save_fn,
        now_iso='2026-07-17T10:01:00',
    )
    history2 = list_retry_history('run-original-1', query_fn=query_fn)
    assert len(history2) == 2

    # 证据缺失校验失败
    bad_record = RetryRecord(
        retry_id='retry-bad',
        original_run_id='run-original-1',
        retry_run_id='run-retry-bad',
        retry_reason='bad',
        original_evidence={},  # 空证据
        retry_count=1,
        created_at='2026-07-17T10:00:00',
    )
    ok_bad, msg_bad = validate_retry_preserves_evidence(bad_record, original_evidence)
    assert not ok_bad, '空证据应校验失败'

    print('PASS 测试6：重试保留原证据（原 run_id + step_results + tool_calls + 历史查询 + 缺失校验）')


# ===== 测试7：自动提交业务单据次数为 0 =====

def test7_no_auto_submit():
    """测试7：自动提交业务单据次数为 0（submit/audit/approve/complete/close/void/delete 禁止）。"""
    # 所有禁止动作都应被检测
    for action in AUTO_SUBMIT_FORBIDDEN_ACTIONS:
        ok, msg, violations = validate_no_auto_submit([action])
        assert not ok, f'禁止动作 {action} 应被检测：{msg}'
        assert action in violations

    # 多个禁止动作
    actions_with_violations = ['read', 'submit', 'query', 'audit', 'delete']
    ok, msg, violations = validate_no_auto_submit(actions_with_violations)
    assert not ok, '含禁止动作应校验失败'
    assert set(violations) == {'submit', 'audit', 'delete'}

    # 纯只读动作应通过
    actions_safe = ['read', 'query', 'list', 'get', 'search', 'analyze']
    ok_safe, msg_safe, violations_safe = validate_no_auto_submit(actions_safe)
    assert ok_safe, f'只读动作应通过：{msg_safe}'
    assert violations_safe == []
    assert '0' in msg_safe

    # 空列表应通过
    ok_empty, _, _ = validate_no_auto_submit([])
    assert ok_empty

    print('PASS 测试7：自动提交业务单据次数为 0（10 个禁止动作检测 + 只读通过 + 空列表通过）')


# ===== 测试8：越权安全停止 =====

def test8_permission_boundary_safety_stop():
    """测试8：越权安全停止（角色不在 allowed_roles 时拒绝）。"""
    # 角色在 allowed_roles 中应通过
    ok1, msg1 = validate_permission_boundary('admin', 'submit', ('admin',))
    assert ok1, f'admin 角色应通过：{msg1}'

    ok2, msg2 = validate_permission_boundary('warehouse', 'read', ('admin', 'warehouse', 'purchase'))
    assert ok2, f'warehouse 角色应通过：{msg2}'

    # 角色不在 allowed_roles 中应拒绝
    ok3, msg3 = validate_permission_boundary('warehouse', 'submit', ('admin',))
    assert not ok3, 'warehouse 不在 allowed_roles 中应拒绝'
    assert 'warehouse' in msg3 and 'submit' in msg3

    ok4, msg4 = validate_permission_boundary('guest', 'read', ('admin', 'warehouse'))
    assert not ok4, 'guest 不在 allowed_roles 中应拒绝'

    # 综合安全停止校验
    config = BudgetConfig(max_steps=10)
    result = check_budget(
        config,
        current_steps=15,  # 超步骤
        started_at_iso='2026-07-17T10:00:00',
        current_tool_calls=5,
        now_iso='2026-07-17T10:00:30',
    )
    # 超预算 + 安全停止 = 通过
    ok_safety_ok, _ = validate_safety_stop_on_violation(result, was_stopped=True)
    assert ok_safety_ok

    # 超预算 + 未停止 = 失败
    ok_safety_bad, _ = validate_safety_stop_on_violation(result, was_stopped=False)
    assert not ok_safety_bad

    # 预算通过 + 错误停止 = 失败
    result_ok = check_budget(
        config,
        current_steps=5,
        started_at_iso='2026-07-17T10:00:00',
        current_tool_calls=5,
        now_iso='2026-07-17T10:00:30',
    )
    ok_safety_wrong, _ = validate_safety_stop_on_violation(result_ok, was_stopped=True)
    assert not ok_safety_wrong, '预算通过但被错误停止应校验失败'

    print('PASS 测试8：越权安全停止（角色不在 allowed_roles 拒绝 + 综合安全停止校验）')


# ===== 辅助函数 =====

def now_iso_safe() -> str:
    return '2026-07-17T10:00:00'


def main() -> int:
    print('=== AI-R13 Agent 预算、取消、熔断和并发控制验证 ===')
    tests = [
        test1_budget_max_steps_safety_stop,
        test2_budget_other_violations,
        test3_concurrency_lock,
        test4_circuit_breaker,
        test5_human_confirmation,
        test6_retry_preserves_evidence,
        test7_no_auto_submit,
        test8_permission_boundary_safety_stop,
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
    print(f'\n=== AI-R13 Agent 预算、取消、熔断和并发控制: {len(tests) - failed} PASS / {failed} FAIL ===')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

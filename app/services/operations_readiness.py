"""Pure offline readiness and notification transitions; no probing or sending.

Callers supply authorized facts and persist the returned checkpoint. This module
does not open a database, inspect a disk, send a notification or schedule work.
Backup states use the existing backup_scheduler execution/freshness policy.
"""

MESSAGES = {
    'database_locked': '数据库暂时被锁定，请保留现场并检查写入任务',
    'database_schema_missing': '数据库结构不完整，请停止维护操作并人工检查',
    'database_unavailable': '数据库检查未完成，请人工检查',
    'database_unknown': '数据库就绪状态未知',
    'backup_failure': '最近一次自动备份失败，请人工检查',
    'backup_stale': '最近一次成功备份已超过现有新鲜度窗口',
    'backup_unknown': '尚无有效的备份执行证据',
    'space_low': '可用空间低于本次明确指定的检查门槛',
    'space_unknown': '可用空间证据未知',
}


def assess_readiness(database_state, backup_state, free_bytes, minimum_free_bytes):
    """Assess supplied facts only; the caller must choose its own space target."""
    if type(minimum_free_bytes) is not int or minimum_free_bytes <= 0:
        raise ValueError('空间检查门槛必须为明确的正整数')
    database = database_state if database_state in (
        'ok', 'locked', 'schema_missing', 'unavailable') else 'unknown'
    backup = backup_state if backup_state in ('success', 'failure', 'stale') else 'unknown'
    space = ('unknown' if type(free_bytes) is not int or free_bytes < 0
             else 'low' if free_bytes < minimum_free_bytes else 'ok')
    issues = []
    if database != 'ok':
        issues.append('database_' + database)
    if backup != 'success':
        issues.append('backup_' + backup)
    if space != 'ok':
        issues.append('space_' + space)
    return {'status': 'not_ready' if issues else 'ready',
            'checks': {'database': database, 'backup': backup, 'space': space},
            'issues': sorted(issues)}


def alert_transitions(previous, issues):
    """Return fixed messages only for newly raised or recovered issue codes.

    Pass the prior persisted checkpoint after a process restart. Invalid state
    is rejected instead of manufacturing recovery or copying arbitrary strings.
    The returned events have no transport; an operator must authorize one.
    """
    if (type(issues) is not list or
            any(type(code) is not str or code not in MESSAGES for code in issues)):
        raise ValueError('就绪问题代码无效')
    old = []
    if previous is not None:
        if (type(previous) is not dict or set(previous) != {'open_issues'} or
                type(previous['open_issues']) is not list or
                any(type(code) is not str or code not in MESSAGES
                    for code in previous['open_issues'])):
            raise ValueError('告警检查点无效，请保留原记录并人工检查')
        old = previous['open_issues']
    current, before = set(issues), set(old)
    events = [{'kind': 'raised', 'code': code, 'message': MESSAGES[code]}
              for code in sorted(current - before)]
    events += [{'kind': 'recovered', 'code': code, 'message': '已恢复：' + MESSAGES[code]}
               for code in sorted(before - current)]
    return {'checkpoint': {'open_issues': sorted(current)}, 'events': events}

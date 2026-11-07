"""Passive task/process/release identity; no application, DB, HTTP or service action.

Repair: BUG-2026-11-07-008 (improvement plan B3/A03).
This verifies metadata consistency, not application or database health.
"""
from __future__ import annotations

import json
import ntpath
from pathlib import Path
import re
import stat
import sys


def _path(value):
    return ntpath.normcase(ntpath.normpath(str(value or '').replace('/', '\\')))


def _command_matches(row, executable, arguments):
    if _path(row.get('executable')) != _path(executable):
        return False
    token = re.escape(str(executable).replace('/', '\\'))
    command = str(row.get('command') or '').replace('/', '\\')
    match = re.match(r'^\s*(?:"' + token + r'"|' + token + r')\s+(.*)$', command, re.I)
    return bool(match and match.group(1).strip() == str(arguments or '').replace('/', '\\').strip())


def read_manifest(root):
    """Read only this fixed program manifest; refuse every link and oversized input."""
    directory = Path(root)
    if not directory.is_absolute():
        raise ValueError('制品目录必须是绝对路径')
    path = directory/'wms-release.json'
    for part in (*reversed(path.parents), path):
        info = part.stat(follow_symlinks=False)
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('制品清单路径不可经过链接或目录联接')
        if part == path and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
            raise ValueError('制品清单必须是无硬链接的普通文件')
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('制品清单过大')
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError('制品清单必须是对象')
    return data


def check_identity(snapshot, expected, manifest):
    """Fail closed on unknown ownership; never substitute any Python/HTTP 200."""
    if not all(isinstance(value, dict) for value in (snapshot, expected, manifest)):
        raise ValueError('身份资料必须是对象')
    failures = []
    source = expected.get('source_sha', '')
    python = expected.get('python', '')
    entry = expected.get('entry', '')
    entry_arguments = expected.get('entry_arguments', '')
    if not isinstance(entry_arguments, str):
        raise ValueError('入口参数无效')
    root = _path(expected.get('release_root'))
    if (not isinstance(source, str) or not re.fullmatch(r'[0-9a-f]{40}', source) or not root
            or not isinstance(expected.get('task_name'), str) or not expected['task_name'].strip()
            or type(expected.get('port')) is not int or not 1 <= expected['port'] <= 65535
            or snapshot.get('port') != expected.get('port')
            or not ntpath.isabs(python) or not ntpath.isabs(entry)
            or _path(entry) != ntpath.join(root, 'verified_entry.py')
            or _path(python) != ntpath.join(root, 'python', 'python.exe')):
        failures.append('必须明确核对完整SHA、制品根目录、固定解释器和verified_entry.py')
    if manifest.get('source_sha') != source or manifest.get('ui_sha') != source:
        failures.append('制品后台或界面来源与预期不一致')
    task = snapshot.get('task') or {}
    if not isinstance(task, dict):
        raise ValueError('任务资料无效')
    if task.get('name') != expected.get('task_name') or task.get('state') != 'Running':
        failures.append('指定计划任务未运行或无法确认')
    actions = task.get('actions') or []
    if not isinstance(actions, list) or any(not isinstance(row, dict) for row in actions):
        raise ValueError('任务动作无效')
    if len(actions) != 1 or not actions[0].get('execute') or not actions[0].get('arguments'):
        failures.append('计划任务动作缺失或不唯一')
    owners = snapshot.get('listeners') or []
    if not isinstance(owners, list):
        raise ValueError('监听资料无效')
    if len(owners) != 1 or type(owners[0]) is not int or owners[0] <= 0:
        failures.append('监听PID缺失或不唯一')
    rows = snapshot.get('processes') or []
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError('进程资料无效')
    processes = {row.get('pid'): row for row in rows}
    if len(processes) != len(rows):
        failures.append('进程快照PID重复')
    chain, seen = [], set()
    current = processes.get(owners[0]) if len(owners) == 1 else None
    expected_commands = [options + token + (' '+entry_arguments if entry_arguments else '')
                         for options in ('', '-I -B ') for token in ('"'+entry+'"', entry)]
    if not current or not any(_command_matches(current, python, text) for text in expected_commands):
        failures.append('端口不属于指定解释器及完整入口')
    for _ in range(32):
        if current is None:
            break
        pid = current.get('pid')
        if pid in seen or type(current.get('created_ticks')) is not int:
            failures.append('进程父链循环或启动时间缺失')
            break
        seen.add(pid)
        chain.append(current)
        parent = processes.get(current.get('ppid'))
        if parent and (type(parent.get('created_ticks')) is not int
                       or parent['created_ticks'] > current['created_ticks']):
            failures.append('父进程时间不符，可能已复用PID')
            break
        current = parent
    else:
        failures.append('进程父链过深')
    if len(actions) == 1 and not any(_command_matches(row, actions[0].get('execute'),
                                                    actions[0].get('arguments')) for row in chain):
        failures.append('监听进程父链不能关联指定计划任务动作')
    return {'identity_verified': not failures, 'failures': failures,
            'listener_pid': owners[0] if len(owners) == 1 else None,
            'source_sha': source, 'task_name': expected.get('task_name'),
            'scope': '被动元数据身份；不代表封存文件完整性、HTTP、数据库或业务健康',
            'database_access': False, 'http_request': False, 'service_action': False}


def main():
    try:
        raw = sys.stdin.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError('进程快照过大')
        packet = json.loads(raw.lstrip('\ufeff'))
        expected = packet['expected']
        manifest = read_manifest(expected['release_root'])
        result = check_identity(packet['snapshot'], expected, manifest)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['identity_verified'] else 1
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({'identity_verified': False, 'failures': ['身份资料缺失或无效，未执行应用或数据库检查']}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

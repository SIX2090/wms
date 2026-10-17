# -*- coding: utf-8 -*-
"""A16 回归锁：非法环境变量不能让 import config 抛异常。

AUDIT-FULL-20261016-001-F09-F06（原 A16）：BACKUP_RETENTION_DAYS='bad' 时旧实现
int() 直接 ValueError，app.py 启动即失败；调度器里的回退逻辑没有机会执行。
用子进程隔离验证，避免同进程 reload 污染其它测试的 Config。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
SNIPPET = (
    'import json, config; '
    'print(json.dumps({"retention": config.Config.BACKUP_RETENTION_DAYS, '
    '"remember_days": config.Config.REMEMBER_COOKIE_DURATION.days}))'
)


def _load(env_value, remember=None):
    env = {k: v for k, v in os.environ.items() if k not in ('BACKUP_RETENTION_DAYS', 'WMS_REMEMBER_LOGIN_DAYS')}
    env['PYTHONPATH'] = str(APP_DIR)
    env['PYTHONIOENCODING'] = 'utf-8'
    if env_value is not None:
        env['BACKUP_RETENTION_DAYS'] = env_value
    if remember is not None:
        env['WMS_REMEMBER_LOGIN_DAYS'] = remember
    result = subprocess.run([sys.executable, '-c', SNIPPET], cwd=str(APP_DIR), env=env,
                            capture_output=True, text=True, encoding='utf-8', timeout=120)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize('value,expected', [
    ('bad-value', 30), ('', 30), ('0', 30), ('-5', 30), ('99999', 30), ('45', 45),
])
def test_invalid_retention_falls_back(value, expected):
    assert _load(value)['retention'] == expected


@pytest.mark.parametrize('value,expected', [
    ('bad', 365), ('', 365), ('-1', 365), ('0', 0), ('30', 30),
])
def test_remember_days_parsing(value, expected):
    assert _load('30', remember=value)['remember_days'] == expected

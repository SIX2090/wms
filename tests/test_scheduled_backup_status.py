"""Administrator sees actual execution status; all database files are synthetic."""
import json
import os
from pathlib import Path
import subprocess
import sys

import backup_scheduler as backups
from tests.test_audit_backup_catalog import case

ROOT = Path(__file__).resolve().parents[1]


def test_backup_page_unknown_status_is_honest_and_read_only(case):
    before = case.database.read_bytes()
    response = case.client.get('/backup?embedded=1')
    assert response.status_code == 200
    assert '尚无有效的自动备份执行记录' in response.get_data(as_text=True)
    assert not (case.daily / backups.DAILY_STATUS_NAME).exists()
    assert case.database.read_bytes() == before


def test_backup_page_failure_then_success_persists_across_requests(case):
    try:
        backups.run_backup_for_source(case.daily / 'missing.db')
    except FileNotFoundError:
        pass
    response = case.client.get('/backup?embedded=1')
    assert response.status_code == 200
    assert '最近一次自动备份失败' in response.get_data(as_text=True)
    target = backups.run_backup_for_source(case.database)
    for _ in range(2):
        response = case.client.get('/backup?embedded=1')
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert '最近一次自动备份成功' in html and target.name in html
    assert case.client.get('/backup/download/' + target.name + '?source=daily').data == target.read_bytes()


def test_disabled_independent_backup_does_not_open_or_create_any_database(tmp_path):
    directory = tmp_path / 'daily'
    result = subprocess.run([sys.executable, str(ROOT / 'tools/run_scheduled_backup.py'),
        '--source', str(tmp_path / 'missing.db'), '--directory', str(directory)],
        env=dict(os.environ, AUTO_BACKUP_ENABLED='false'), capture_output=True, timeout=20)
    assert result.returncode == 0
    assert not directory.exists() and not (tmp_path / 'missing.db').exists()

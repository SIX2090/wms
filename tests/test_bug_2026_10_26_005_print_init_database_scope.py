"""BUG-2026-10-26-005: printing maintenance must respect non-file databases."""
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

import app as wms
import doc_print_excel as excel
import local_print_agent as agent


@pytest.mark.parametrize('uri', ['sqlite:///:memory:', 'sqlite://', 'postgresql://fixture/db'])
@pytest.mark.parametrize('helper', ['excel', 'workstation'])
def test_non_file_print_initializers_never_connect(monkeypatch, tmp_path, uri, helper):
    monkeypatch.setitem(wms.app.config, 'SQLALCHEMY_DATABASE_URI', uri)
    connect = Mock(side_effect=AssertionError('unexpected file access'))
    monkeypatch.setattr('sqlite3.connect', connect)
    if helper == 'excel':
        excel.ensure_builtin_excel_doc_templates(static_folder=str(tmp_path))
    else:
        agent.ensure_builtin_print_workstation()
    assert connect.call_count == 0
    assert not list(tmp_path.rglob('*.xlsx'))


def test_excel_resolver_failure_does_not_fallback(monkeypatch):
    def unavailable():
        raise RuntimeError('resolver unavailable')
    monkeypatch.setattr(wms, '_resolve_sqlite_db_path', unavailable)
    assert excel._default_db_path() is None


@pytest.mark.parametrize('helper', ['excel', 'workstation'])
@pytest.mark.parametrize('resolver_raises', [False, True])
def test_print_resolver_failure_never_probes_guessed_database(monkeypatch, helper, resolver_raises):
    def resolve():
        if resolver_raises:
            raise RuntimeError('synthetic resolver unavailable')
        return None
    monkeypatch.setattr(wms, '_resolve_sqlite_db_path', resolve)
    exists = Mock(side_effect=AssertionError('guessed database must not be inspected'))
    connect = Mock(side_effect=AssertionError('unknown database must not be connected'))
    monkeypatch.setattr(os.path, 'exists', exists)
    monkeypatch.setattr('sqlite3.connect', connect)
    if helper == 'excel':
        assert excel._default_db_path() is None
        excel.ensure_builtin_excel_doc_templates(static_folder='synthetic-unused-static')
    else:
        agent.ensure_builtin_print_workstation()
    assert exists.call_count == connect.call_count == 0


def test_fresh_memory_app_import_does_not_attempt_production_maintenance(tmp_path):
    env = os.environ.copy()
    env.update(DATABASE_URL='sqlite:///:memory:', WMS_DATABASE_URI='sqlite:///:memory:',
               LOG_FILE=str(tmp_path / 'child.log'))
    app_dir = str(Path(__file__).resolve().parents[1] / 'app')
    code = (f"import sys; sys.path.insert(0, {app_dir!r}); import app; "
            "print(app.app.config['SQLALCHEMY_DATABASE_URI'])")
    result = subprocess.run([sys.executable, '-c', code], env=env, cwd=tmp_path,
                            capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert result.returncode == 0, result.stderr
    assert 'sqlite:///:memory:' in result.stdout
    assert 'QA SQLite guard rejected' not in result.stderr
    assert 'ensure_builtin_excel_doc_templates' not in result.stderr
    assert 'ensure_builtin_print_workstation' not in result.stderr

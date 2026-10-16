"""运行锁双向互斥；仅临时路径，无真实服务停机/数据库恢复。"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from runtime_guard import acquire_database_lease, server_database_path


def test_acquire_database_lease(tmp_path):
    target = tmp_path / 'inventory.db'
    with acquire_database_lease(target):
        with pytest.raises(RuntimeError, match='独占运行锁'):
            acquire_database_lease(target)
    # 锁文件仍存在，真正的OS锁已经随句柄关闭释放，不能误判为永远被占用。
    with acquire_database_lease(target):
        pass
    assert not target.exists()


@pytest.mark.parametrize('env', [{'FLASK_ENV': 'testing'}, {'DATABASE_URL': 'sqlite:///:memory:'},
                                  {'DATABASE_URL': 'postgresql://unused/fixture'}])
def test_server_database_path_skips_non_file_database(env):
    assert server_database_path(env) is None


def test_server_database_path(tmp_path):
    target = tmp_path / 'inventory.db'
    assert server_database_path({'DATABASE_URL': 'sqlite:///' + target.as_posix()}) == target.resolve()
    assert server_database_path({}) == Path(__file__).resolve().parents[1] / 'app/instance/inventory.db'


def test_server_cannot_import_app_during_maintenance(tmp_path):
    target = tmp_path / 'inventory.db'
    env = dict(os.environ, FLASK_ENV='production', DATABASE_URL='sqlite:///' + target.as_posix(),
               PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    server = Path(__file__).resolve().parents[1] / 'app/run_server.py'
    with acquire_database_lease(target):
        result = subprocess.run([sys.executable, str(server)], env=env, capture_output=True,
                                text=True, encoding='utf-8', timeout=20)
    assert result.returncode != 0
    assert '独占运行锁' in result.stderr
    assert not target.exists(), '必须在app导入和启动DDL前拒绝启动'

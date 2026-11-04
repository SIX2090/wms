from pathlib import Path
import subprocess
import sys


def test_delete_checks_hold_sqlite_write_lock_against_new_references(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root/'tests/material_unused_delete_lock_probe.py'),
                             str(tmp_path/'lock-test.db')], cwd=root, capture_output=True,
                            text=True, encoding='utf8', timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"writer_during_check": "locked"' in result.stdout
    assert '"writer_after_delete": "foreign_key_rejected"' in result.stdout

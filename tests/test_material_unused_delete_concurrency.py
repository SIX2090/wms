from pathlib import Path
import subprocess
import sys

import pytest


# 探针 `tests/material_unused_delete_lock_probe.py` 的第一条可执行语句就是
# raise RuntimeError('物料并发验证已阻止：隔离文件库及应用出站尚未证明')，
# 并且 `tests/test_material_lock_probe_fail_closed_20261108.py` 专门断言它
# **必须先阻断**（不得先建库、不得先 import app）。两条用例互斥：
# 在隔离前提（隔离文件库 + 应用出站可控）被真正证明之前，这条并发验证
# 不可能执行。这里如实标记为未验证，而不是把探针的守卫摘掉换取「绿」。
@pytest.mark.skip(reason=(
    '隔离文件库与应用出站尚未证明：探针按设计 fail-closed 阻断；'
    '守卫契约见 tests/test_material_lock_probe_fail_closed_20261108.py。'
    '前提成立后应删除本 skip 并恢复执行。'
))
def test_delete_checks_hold_sqlite_write_lock_against_new_references(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root/'tests/material_unused_delete_lock_probe.py'),
                             str(tmp_path/'lock-test.db')], cwd=root, capture_output=True,
                            text=True, encoding='utf8', timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"writer_during_check": "locked"' in result.stdout
    assert '"writer_after_delete": "foreign_key_rejected"' in result.stdout


def test_lock_probe_guard_is_still_armed():
    """守卫仍在位：探针未被执行前必须先阻断（防止有人为了变绿摘掉守卫）。"""
    probe = Path(__file__).resolve().parent / 'material_unused_delete_lock_probe.py'
    text = probe.read_text(encoding='utf-8-sig')
    assert "raise RuntimeError('物料并发验证已阻止" in text

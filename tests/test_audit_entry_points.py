# -*- coding: utf-8 -*-
"""A12 回归锁：app 目录的旧入口必须指向真实存在的根 install.bat，且保持 CRLF。

AUDIT-FULL-20261016-001-F09-F02（原 A12）：app/wms.bat、app/wms.cmd 调用同目录
install.bat，但该文件从未存在（唯一安装入口在仓库根），双击必然失败。
本用例只做静态契约，绝不执行安装脚本（会写系统/装服务）。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRIES = [ROOT / 'app' / 'wms.bat', ROOT / 'app' / 'wms.cmd']
SEP = chr(92)


def test_root_installer_exists():
    assert (ROOT / 'install.bat').is_file()


def test_entries_call_root_installer():
    expected = '..' + SEP + 'install.bat'
    for entry in ENTRIES:
        text = entry.read_text(encoding='utf-8')
        assert expected in text, entry.name
        assert '"%~dp0install.bat"' not in text, entry.name


def test_entries_keep_crlf_and_propagate_exit_code():
    for entry in ENTRIES:
        data = entry.read_bytes()
        assert b'\r\n' in data, entry.name
        assert b'exit /b %ERRORLEVEL%' in data, entry.name

# -*- coding: utf-8 -*-
"""A11 回归锁：健康检查必须同时识别 app/logs/app.log 与扁平 logs/app.log。

AUDIT-FULL-20261016-001-F09（原 A11）：脚本只读 InstallDir/logs/app.log，
而 app/config.py 的 LOG_FILE 锚定 app/logs/app.log，生产上必然误报"日志不存在"。
本用例是静态契约：脚本是 PowerShell，Linux CI 无 pwsh，行为验证放在 Windows 手工执行。
回退验证：把 health_check.ps1 换回修复前版本，本用例必须失败（缺少 app/logs 候选）。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'health_check.ps1'
SEP = chr(92)


def _text():
    return SCRIPT.read_text(encoding='utf-8')


def test_probes_repo_layout_log_path():
    expected = 'Join-Path $InstallDir "app' + SEP + 'logs' + SEP + 'app.log"'
    assert expected in _text()


def test_probes_flat_layout_log_path():
    expected = 'Join-Path $InstallDir "logs' + SEP + 'app.log"'
    assert expected in _text()


def test_utf8_bom_for_windows_powershell():
    r"""Windows PowerShell 5.1 对无 BOM 的 UTF-8 脚本按 ANSI(cp936) 解码，
    中文串会吞掉后续引号导致整份脚本解析失败（实测 6 个 parse error）。
    有 BOM 时 5.1/7 都按 UTF-8 读取，因此 BOM 是本脚本能在生产控制台运行的前提。
    """
    assert SCRIPT.read_bytes().startswith(b'\xef\xbb\xbf')


def test_picks_newest_existing_candidate():
    text = _text()
    assert '$logCandidates' in text
    assert 'LastWriteTime' in text
    assert 'foreach ($candidate in $logCandidates)' in text

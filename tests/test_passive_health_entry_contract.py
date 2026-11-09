"""Correct source contracts for the existing PowerShell entry (old code fails)."""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('forbidden',['Invoke-WebRequest','inventory.db','Get-Process -Name python',
                                    'Get-Service -Name $ServiceName'])
def test_passive_entry_never_probes_business_or_accepts_any_python(forbidden):
    assert forbidden not in (ROOT/'scripts/health_check.ps1').read_text(encoding='utf-8-sig')


def test_passive_entry_checks_registered_task_and_exact_expectations():
    text = (ROOT/'scripts/health_check.ps1').read_text(encoding='utf-8-sig')
    assert 'Get-ScheduledTask -TaskName $TaskName' in text
    assert 'passive_wms_identity.py' in text
    assert 'ExpectedSourceSha' in text and 'ExpectedPython' in text and 'ExpectedEntry' in text
    assert text.index('if (!$value') < text.index('Get-ScheduledTask -TaskName')
    assert 'Stop-Process' not in text and 'Start-ScheduledTask' not in text


@pytest.mark.parametrize('unsafe',[
    'taskkill /F /IM python.exe',
    'Copy-Item C:\\wms\\backups',
    'Remove-Item C:\\wms -Recurse',
])
def test_current_runbook_has_no_destructive_legacy_recipe(unsafe):
    text = (ROOT/'docs/部署验证与回滚手册.md').read_text(encoding='utf-8')
    assert unsafe not in text

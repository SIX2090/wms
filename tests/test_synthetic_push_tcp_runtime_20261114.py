"""Real TCP CLI only in the existing immutable Linux isolation boundary."""
import json
from pathlib import Path
import re
import subprocess
import sys

from scripts.verify_db_guard import require_isolated_test_runtime
require_isolated_test_runtime()

import pytest  # noqa: E402
from scripts.linux_test_runtime import PROOF, require_subprocess_boundary  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = ROOT / 'scripts/diagnose_synthetic_push_tcp.py'


@pytest.mark.parametrize('rows', (1, 25))
def test_actual_tcp_push_preserves_protocol_stock_identity_and_cleanup(rows):
    require_subprocess_boundary()
    result = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', str(DIAGNOSTIC),
                             '--scenario', 'inbound-push-tcp', '--rows', str(rows)],
                            capture_output=True, text=True, encoding='utf-8', timeout=150)
    assert result.returncode == 0, result.stdout + result.stderr
    lines = [line for line in result.stdout.splitlines() if line.startswith('WMS_SYNTHETIC_TCP_DIAGNOSTIC=')]
    assert len(lines) == 1, result.stdout
    report = json.loads(lines[0].split('=', 1)[1])
    assert report['rows'] == rows and report['transport'] == 'tcp'
    assert report['source_sha'] == json.loads(PROOF.read_text(encoding='utf-8'))['sha']
    assert report['database'] == 'sqlite:///:memory:'
    assert [stage['stage'] for stage in report['stages']] == [
        'save_inbound', 'complete_inbound', 'render_inbound_detail', 'render_push',
        'push_draft', 'replay_push', 'render_target_detail']
    assert all(stage['http_status'] == 200 and stage['elapsed_ms'] >= 0 for stage in report['stages'])
    details = [stage for stage in report['stages'] if stage['stage'] in ('render_inbound_detail', 'render_target_detail')]
    assert len(details) == 2 and all(stage['document_verified'] and stage['verified_material_rows'] == rows for stage in details)
    assert [item['phase'] for item in report['protocol_reads']] == ['new_document_page', 'completion_snapshot']
    assert [item['phase'] for item in report['authentication']] == ['login_page', 'login', 'authenticated_api']
    assert [(item['phase'], item['http_status']) for item in report['security_checks']] == [
        ('missing_csrf', 400), ('invalid_revision', 409)]
    timings = report['stages'] + report['protocol_reads'] + report['authentication'] + report['security_checks']
    assert all(item['elapsed_ms'] >= 0 for item in timings)
    assert report['elapsed_ms_total'] >= sum(item['elapsed_ms'] for item in timings)
    assert report['source_status'] == 'completed' and report['target_status'] == 'pending'
    assert report['target_count'] == 1 and report['target_quantity'] == rows
    assert report['stock_before'] == 0 and report['stock_after_inbound'] == rows * 2
    assert report['stock_after_push'] == report['stock_after_inbound'] and report['other_warehouse_stock'] == 0
    assert all(report[name] is True for name in (
        'request_replayed', 'csrf_enabled', 'missing_csrf_rejected', 'page_revision_used',
        'invalid_revision_rejected', 'response_identity_verified', 'owned_listener_closed', 'owned_server_stopped'))
    assert not any(name in report for name in ('password', 'username', 'nonce', 'base_url', 'headers', 'payload'))
    assert not re.search(r'http[s]?://', lines[0])

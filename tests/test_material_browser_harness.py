"""Bounded fixture startup and CI gate; no local Chrome or production service."""
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.request

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_browser_fixture_owns_temporary_database_and_port():
    with tempfile.TemporaryDirectory(prefix='wms-browser-fixture-check-') as directory:
        with socket.socket() as socket_:
            socket_.bind(('127.0.0.1', 0)); port = socket_.getsockname()[1]
        environment = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
        process = subprocess.Popen([sys.executable, str(ROOT / 'tests/material_browser_server.py'),
                                    '--root', directory, '--source-root', str(ROOT), '--port', str(port),
                                    '--instance', 'synthetic-fixture-check'], env=environment,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        lines = queue.Queue()

        def read():
            for line in process.stdout:
                lines.put(line)

        reader = threading.Thread(target=read, daemon=True); reader.start()
        captured = []
        try:
            while True:
                line = lines.get(timeout=35); captured.append(line)
                if '"ready": true' in line:
                    break
                assert process.poll() is None, ''.join(captured)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            request = urllib.request.Request('http://127.0.0.1:' + str(port) + '/__lab/state',
                                             headers={'X-Lab-Instance': 'synthetic-fixture-check'})
            with opener.open(request, timeout=5) as response:
                assert response.headers['X-WMS-Isolated-Test'] == 'synthetic-fixture-check'
                state = json.load(response)
            assert state['stock'] == state['location_stock'] == state['transaction_stock'] == 25
            assert state['inbound'][0]['status'] == state['outbound'][0]['status'] == 'pending'
            assert (Path(directory) / 'synthetic.db').is_file()
        finally:
            process.terminate(); process.wait(timeout=10); reader.join(timeout=2); process.stdout.close()


@pytest.mark.parametrize('forbidden', ['8080', '5098'])
def test_browser_fixture_rejects_live_ports_before_loading_app(tmp_path, forbidden):
    result = subprocess.run([sys.executable, str(ROOT / 'tests/material_browser_server.py'), '--root', str(tmp_path),
                             '--source-root', str(ROOT), '--port', forbidden, '--instance', 'synthetic'],
                            capture_output=True, timeout=10)
    assert result.returncode != 0
    assert not (tmp_path / 'synthetic.db').exists()


def test_locked_browser_dependency_and_required_workflow():
    package = json.loads((ROOT / 'tools/browser_checks/package.json').read_text())
    lock = json.loads((ROOT / 'tools/browser_checks/package-lock.json').read_text())
    assert package['private'] is True and package['dependencies'] == {'playwright-core': '1.57.0'}
    assert lock['packages']['node_modules/playwright-core']['integrity'].startswith('sha512-')
    workflow = yaml.safe_load((ROOT / '.github/workflows/ci.yml').read_text())
    job = workflow['jobs']['browser-material-entry']
    assert job['needs'] == 'changes' and job['runs-on'] == 'ubuntu-24.04'
    assert job['timeout-minutes'] == 10 and not job.get('continue-on-error')
    commands = '\n'.join(step.get('run', '') for step in job['steps'])
    assert 'google-chrome --version' in commands
    assert 'npm ci --prefix tools/browser_checks --ignore-scripts' in commands
    assert 'node tests/material_browser_check.cjs' in commands
    assert 'browser-material-entry' in workflow['jobs']['gate']['needs']


@pytest.mark.parametrize('result', ['failure', 'cancelled', 'skipped', 'missing'])
def test_browser_failure_cannot_pass_full_gate(result):
    from tests.test_ci_docs_mode_workflows import results, run_gate
    needs = results('ci', False)
    if result == 'missing':
        needs.pop('browser-material-entry')
    else:
        needs['browser-material-entry']['result'] = result
    assert run_gate('ci', needs).returncode != 0

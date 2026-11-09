"""Container PID 1: wait for the host's inspected boundary, then execute one job."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from linux_test_runtime import PROFILE, PROOF, require_linux_runtime


def main():
    PROFILE.mkdir(mode=0o700)
    for name in ('tmp', 'logs', 'uploads', 'home'):
        (PROFILE / name).mkdir()
    deadline = time.monotonic() + 30
    while not PROOF.exists():
        if time.monotonic() >= deadline:
            raise SystemExit('安全阻断：启动器未签发隔离证明')
        time.sleep(0.05)
    require_linux_runtime()
    probe = subprocess.run([sys.executable, '-I', '-B', '/opt/wms/scripts/verify_ci_isolation.py'], timeout=60)
    if probe.returncode:
        return probe.returncode
    request = json.loads(Path('/opt/wms-ci-request.json').read_text())
    command = request['command']
    if not command or command[0] not in ('python', 'node'):
        raise SystemExit('安全阻断：测试命令为空或不受支持')
    print('[isolation] verified read-only source, private PID/network namespaces; running: '
          + ' '.join(command), flush=True)
    # PID 1 stays alive while descendants verify its creation identity.
    try:
        result = subprocess.run(command, cwd='/opt/wms', timeout=1500)
        returncode = result.returncode
    except subprocess.TimeoutExpired:
        print('::error::Isolated verification exceeded 1500 seconds', flush=True)
        returncode = 124
    # tmpfs disappears on container exit. Keep PID 1 (and its proof identity)
    # alive until the host has exported the reports; never lose failure evidence.
    Path('/work/test-complete').write_text(json.dumps({'exit_code': returncode}))
    deadline = time.monotonic() + 60
    while not (PROOF.parent / 'reports-exported').exists():
        if time.monotonic() >= deadline:
            print('::error::Controller did not export the test reports', flush=True)
            return 125
        time.sleep(0.1)
    return returncode


if __name__ == '__main__':
    sys.exit(main())

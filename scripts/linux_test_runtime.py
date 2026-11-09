"""Verify the kernel boundary issued by run_ci_isolated, before loading WMS.

The proof is read-only to the test UID and binds the container's live PID 1 and
namespaces. Environment flags alone never grant access. Descendants remain in
the same unprivileged, network-none, read-only container boundary.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat

SOURCE = Path('/opt/wms')
PROOF = Path('/run/wms-proof/proof.json')
PROFILE = Path('/work/profile')
NAMESPACES = ('mnt', 'net', 'pid', 'user')


def kernel_identity():
    """Called by the host via docker exec, and rechecked inside every child."""
    return {
        'namespaces': {name: os.readlink('/proc/self/ns/' + name) for name in NAMESPACES},
        'init_start': Path('/proc/1/stat').read_text().rsplit(')', 1)[1].split()[19],
    }


def _mounts():
    return {line.split()[4]: line.split()[5].split(',')
            for line in Path('/proc/self/mountinfo').read_text().splitlines()}


def require_linux_boundary():
    """No database, application import, network request or child creation here."""
    try:
        if os.name != 'posix' or os.getuid() != 10001 or os.geteuid() != 10001:
            raise ValueError('wrong test UID')
        if os.environ.get('WMS_TEST_RUNTIME_PROOF') != str(PROOF):
            raise ValueError('missing launcher capability')
        status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines())
        if (int(status['CapEff'].strip(), 16) or int(status['CapPrm'].strip(), 16)
                or status['NoNewPrivs'].strip() != '1' or status['Seccomp'].strip() != '2'):
            raise ValueError('process privileges are not restricted')
        mounts = _mounts()
        if ('ro' not in mounts.get('/', ()) or 'ro' not in mounts.get('/run/wms-proof', ())
                or any(path == '/opt/wms' or path.startswith('/opt/wms/scripts')
                       or path.startswith('/opt/wms/app/app.py') for path in mounts)):
            raise ValueError('source or proof is writable')
        for path in (PROOF.parent, PROOF):
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or info.st_uid == os.geteuid() or info.st_mode & 0o022:
                raise ValueError('proof ownership is invalid')
        if not stat.S_ISREG(PROOF.stat().st_mode) or PROOF.stat().st_size > 16384:
            raise ValueError('invalid proof file')
        proof = json.loads(PROOF.read_text())
        identity = kernel_identity()
        if (proof.get('schema') != 1 or proof.get('boundary') != 'docker-network-none'
                or not re.fullmatch('[0-9a-f]{64}', proof.get('container_id', ''))
                or proof.get('identity') != identity
                or proof.get('app_sha256') != hashlib.sha256((SOURCE / 'app/app.py').read_bytes()).hexdigest()
                or any(identity['namespaces'][name] == proof['host_namespaces'][name]
                       for name in ('mnt', 'net', 'pid'))):
            raise ValueError('stale or mismatched proof')
        # No interface other than this namespace's loopback; never probe a real host.
        devices = {line.split(':', 1)[0].strip() for line in Path('/proc/net/dev').read_text().splitlines()[2:]}
        if devices != {'lo'} or Path('/var/run/docker.sock').exists():
            raise ValueError('external network or engine socket is exposed')
        if Path(__file__).resolve() != SOURCE / 'scripts/linux_test_runtime.py':
            raise ValueError('runtime verifier is not the immutable source')
        if PROFILE.is_symlink() or PROFILE.stat().st_uid != 10001:
            raise ValueError('invalid synthetic profile')
        return PROFILE
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        raise SystemExit('安全阻断：Linux 测试隔离能力无效：' + str(exc)) from None


def require_linux_runtime():
    profile = require_linux_boundary()
    if (any(os.environ.get(key) != 'sqlite:///:memory:' for key in ('DATABASE_URL', 'WMS_DATABASE_URI'))
            or os.environ.get('FLASK_ENV') != 'testing'):
        raise SystemExit('安全阻断：测试入口只能继承合成内存库和 testing 环境')
    return profile


def require_subprocess_boundary():
    """Windows LPAC descendants need separately issued handles; do not fake them."""
    return require_linux_boundary()


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['--identity']:
        print(json.dumps(kernel_identity()))
    else:
        require_linux_boundary()

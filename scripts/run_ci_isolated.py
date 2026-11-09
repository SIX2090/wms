"""Run CI tests in a fresh source-only, unprivileged, network-none container.

Only Git blobs enter the image: no checkout mount, database, backup, credentials,
Docker socket or host service. The controller inspects the exact new container
before issuing a read-only proof. Windows keeps its existing LPAC launcher.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'wms.synthetic.run'
STATE_MOUNTS = ('/work', '/tmp', '/opt/wms/app/instance', '/opt/wms/app/logs',
                '/opt/wms/app/backups', '/opt/wms/app/static/uploads', '/opt/wms/output')
FORWARDED = ('VERIFY_TEST_SHARDS', 'VERIFY_TEST_SHARD', 'VERIFY_TEST_WORKERS',
             'VERIFY_SHARDS', 'VERIFY_SHARD', 'VERIFY_WORKERS', 'VERIFY_AI_WORKERS', 'AI_LEDGER_ENFORCE')


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def source_member(name):
    """Check names before reading blobs; never inspect production files."""
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name:
        raise ValueError('unsafe archive path')
    parts = {part.lower() for part in path.parts}
    if parts & {'.git', 'instance', 'backups', 'backup', 'logs', 'uploads', 'node_modules',
                '.venv', 'venv', '__pycache__', 'output', 'outputs'}:
        return False
    if any(part.startswith('.env') for part in path.parts):
        return False
    return not re.search(r'\.(db|sqlite|sqlite3|bak|dump|sql|log)(-|\.|$)', path.name, re.I)


def export_source(repo, revision, target):
    """Select source names before reading any blob; never archive excluded data."""
    listing = run(['git', '-C', str(repo), 'ls-tree', '-rz', revision], capture_output=True).stdout
    selected = []
    for record in listing.split(b'\0'):
        if not record:
            continue
        metadata, raw_name = record.split(b'\t', 1)
        mode, kind, oid = metadata.decode('ascii').split()
        name = raw_name.decode('utf-8')
        if not source_member(name):
            continue
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise ValueError('source contains a link or submodule: ' + name)
        selected.append((name, oid, mode))
    count = 0
    with subprocess.Popen(['git', '-C', str(repo), 'cat-file', '--batch'],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE) as stream:
        for name, oid, mode in selected:
            stream.stdin.write((oid + '\n').encode('ascii')); stream.stdin.flush()
            header = stream.stdout.readline().decode('ascii').split()
            if len(header) != 3 or header[:2] != [oid, 'blob']:
                raise ValueError('unexpected Git blob response')
            content = stream.stdout.read(int(header[2]))
            if len(content) != int(header[2]) or stream.stdout.read(1) != b'\n':
                raise ValueError('truncated Git blob')
            path = target.joinpath(*PurePosixPath(name).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            path.chmod(0o755 if mode == '100755' else 0o644)
            count += 1
        stream.stdin.close()
        if stream.wait() != 0:
            raise ValueError('Git blob export failed')
    if not count or not (target / 'app/app.py').is_file():
        raise ValueError('empty or incomplete source snapshot')
    return count


def validate_inspect(record, *, container, image, nonce, proof_dir):
    """Reject configuration drift before the waiting child receives a capability."""
    host, config = record['HostConfig'], record['Config']
    mounts = record['Mounts']
    bindings = [mount for mount in mounts if mount['Type'] == 'bind']
    if (record['Id'] != container or record['Image'] != image
            or config.get('Labels', {}).get(LABEL) != nonce or config['User'] != '10001:10001'
            or not host['ReadonlyRootfs'] or host['Privileged'] or host['NetworkMode'] != 'none'
            or host.get('PidMode') or host.get('IpcMode') not in ('private', '')
            or host.get('CapAdd') or set(host.get('CapDrop') or []) != {'ALL'}
            or not any(value in ('no-new-privileges', 'no-new-privileges=true')
                       for value in host.get('SecurityOpt', []))
            or any('unconfined' in value for value in host.get('SecurityOpt', []))
            or host.get('Devices') or host.get('DeviceRequests') or host.get('PortBindings')
            or host.get('VolumesFrom') or config.get('Volumes')
            or set(host.get('Tmpfs', {})) != set(STATE_MOUNTS)
            or len(bindings) != 1 or bindings[0]['Destination'] != '/run/wms-proof'
            or bindings[0]['RW'] or bindings[0]['Source'] != str(proof_dir)
            or any(mount['Type'] not in ('bind', 'tmpfs') for mount in mounts)):
        raise ValueError('container does not match the required isolation boundary')


def docker_environment():
    # A remote engine could mount a different path; it is not a supported target.
    if os.name != 'posix' or not sys.platform.startswith('linux'):
        raise SystemExit('安全阻断：此启动器仅用于 Linux 本地 Docker；Windows 请使用已核验 LPAC 启动器')
    if any(os.environ.get(name) for name in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH')):
        raise SystemExit('安全阻断：不接受继承的远程 Docker 配置')
    endpoint = run(['docker', 'context', 'inspect', '--format', '{{.Endpoints.docker.Host}}'],
                   capture_output=True, text=True).stdout.strip()
    if endpoint != 'unix:///var/run/docker.sock':
        raise SystemExit('安全阻断：只允许本机 Docker socket')
    for key in ('DATABASE_URL', 'WMS_DATABASE_URI'):
        if os.environ.get(key, '') not in ('', 'sqlite:///:memory:'):
            raise SystemExit('安全阻断：不能继承非测试数据库目标')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command or command[0] not in ('python', 'python3', 'node') or len(command) < 2:
        parser.error('必须显式提供非空 Python/Node 测试命令')
    command[0] = 'python' if command[0] == 'python3' else command[0]
    docker_environment()
    nonce, container, logs = uuid.uuid4().hex, None, None
    sha = run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    # A local invocation must not silently test a stale HEAD while claiming dirty code passed.
    dirty = run(['git', '-C', str(ROOT), 'status', '--porcelain', '--untracked-files=no'],
                capture_output=True, text=True).stdout
    if dirty.strip():
        raise SystemExit('安全阻断：源码须先提交；隔离运行器只验证精确 Git 提交')
    with tempfile.TemporaryDirectory(prefix='wms-ci-source-') as temp:
        scratch = Path(temp)
        source, proof_dir = scratch / 'source', scratch / 'proof'
        source.mkdir(); proof_dir.mkdir(mode=0o755)
        count = export_source(ROOT, sha, source)
        baseline = os.environ.get('WMS_BROWSER_BASELINE', '')
        if command == ['node', 'tests/material_browser_check.cjs']:
            if not re.fullmatch('[0-9a-f]{40}', baseline):
                raise ValueError('browser baseline must be an exact commit')
            run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', baseline, sha])
            old = scratch / 'baseline'; old.mkdir()
            export_source(ROOT, baseline, old)
        else:
            (scratch / 'baseline').mkdir()
        (scratch / 'request.json').write_text(json.dumps({'command': command, 'sha': sha, 'baseline': baseline}))
        dockerfile = (source / 'scripts/ci-test.Dockerfile').read_text()
        (scratch / 'Dockerfile').write_text(dockerfile)
        iid = scratch / 'image-id'
        browser = command == ['node', 'tests/material_browser_check.cjs']
        run(['docker', 'build', '--build-arg', 'BROWSER=' + str(int(browser)), '--iidfile', str(iid), str(scratch)])
        image = iid.read_text().strip()
        options = ['docker', 'create', '--label', LABEL + '=' + nonce,
                   '--user', '10001:10001', '--network', 'none', '--read-only',
                   '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges=true',
                   '--pids-limit', '256', '--memory', '5g', '--cpus', '4', '--shm-size', '256m',
                   '--mount', 'type=bind,src=' + str(proof_dir) + ',dst=/run/wms-proof,readonly']
        for target in STATE_MOUNTS:
            options += ['--tmpfs', target + ':rw,nosuid,nodev,uid=10001,gid=10001,mode=700,size=2g']
        for key in FORWARDED:
            if key in os.environ:
                options += ['--env', key + '=' + os.environ[key]]
        options += [image]
        try:
            container = run(options, capture_output=True, text=True).stdout.strip()
            if not re.fullmatch('[0-9a-f]{64}', container):
                raise ValueError('invalid newly created container ID')
            inspect = json.loads(run(['docker', 'inspect', container], capture_output=True, text=True).stdout)[0]
            validate_inspect(inspect, container=container, image=image, nonce=nonce, proof_dir=proof_dir)
            run(['docker', 'start', container], capture_output=True)
            identity = json.loads(run(['docker', 'exec', container, 'python',
                                      '/opt/wms/scripts/linux_test_runtime.py', '--identity'],
                                     capture_output=True, text=True).stdout)
            proof = {'schema': 1, 'boundary': 'docker-network-none', 'container_id': container,
                     'identity': identity, 'host_namespaces': {
                         name: os.readlink('/proc/self/ns/' + name) for name in ('mnt', 'net', 'pid', 'user')},
                     'sha': sha, 'source_files': count,
                     'app_sha256': hashlib.sha256((source / 'app/app.py').read_bytes()).hexdigest()}
            pending = proof_dir / 'pending.json'; pending.write_text(json.dumps(proof)); pending.chmod(0o444)
            pending.replace(proof_dir / 'proof.json')
            # Stream real assertions while PID 1 holds tmpfs reports for export.
            logs = subprocess.Popen(['docker', 'logs', '--follow', container])
            deadline = time.monotonic() + 1560
            while True:
                state = json.loads(run(['docker', 'inspect', container], capture_output=True, text=True).stdout)[0]
                if not state['State']['Running']:
                    break
                completed = subprocess.run(['docker', 'exec', container, 'test', '-f', '/work/test-complete'],
                                           capture_output=True, timeout=10)
                if completed.returncode == 0:
                    output = ROOT / 'output'; output.mkdir(exist_ok=True)
                    run(['docker', 'cp', container + ':/opt/wms/output/.', str(output)])
                    (proof_dir / 'reports-exported').write_text(nonce)
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError('isolated job did not finish within its deadline')
                time.sleep(1)
            logs.wait(timeout=30)
            state = json.loads(run(['docker', 'inspect', container], capture_output=True, text=True).stdout)[0]
            if state['State']['Running'] or logs.returncode:
                raise RuntimeError('container did not finish cleanly')
            print('[isolation] exact source=' + sha + '; test exit=' + str(state['State']['ExitCode']), flush=True)
            return state['State']['ExitCode']
        finally:
            if container and re.fullmatch('[0-9a-f]{64}', container):
                state = json.loads(run(['docker', 'inspect', container], capture_output=True, text=True).stdout)[0]
                if state['Config'].get('Labels', {}).get(LABEL) != nonce:
                    raise RuntimeError('refusing to remove a container not owned by this invocation')
                run(['docker', 'rm', '--force', container], capture_output=True)
            if logs is not None and logs.poll() is None:
                logs.wait(timeout=10)


if __name__ == '__main__':
    sys.exit(main())

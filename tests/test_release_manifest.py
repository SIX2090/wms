"""Release identity checks use only synthetic files; never load WMS or a live DB."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

MODULE = Path(__file__).resolve().parents[1] / 'app/services/release_manifest.py'
spec = importlib.util.spec_from_file_location('release_manifest_test_target', MODULE)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.fixture
def artifact(tmp_path):
    root = tmp_path / 'artifact'
    for name, data in {'app/app.py': b'# synthetic source', 'app/static/site.css': b'body{}',
                       'tools/helper.py': b'# synthetic tool', 'overlay/app/site.css': b'body{color:blue}',
                       'runtime/python.exe': b'synthetic runtime',
                       'runtime/Lib/site-packages/certifi/cacert.pem': b'public certificate bundle'}.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    report = {'success': True, 'python_version': '3.11.9', 'python': 'C:/private/runtime/python.exe',
              'requirements': 'C:/private/app/requirements.txt', 'failures': [],
              'packages': [{'name': 'certifi', 'required': '2026.10.18', 'installed': '2026.10.18',
                            'module_file': 'C:/private/site-packages/certifi/__init__.py',
                            'loaded_version': '2026.10.18'}]}
    manifest = release.build_release_manifest(root, source_sha='a' * 40, ui_sha='b' * 40,
        includes=['app', 'tools', 'overlay', 'runtime'], application_root='app',
        overlay_roots=['overlay'], runtime_report=report, external_operations_paused=True)
    (root / 'wms-release.json').write_text(json.dumps(manifest), encoding='utf-8')
    return root, manifest


def test_build_release_manifest(artifact, tmp_path):
    root, manifest = artifact
    destination = tmp_path / 'empty restored artifact'
    destination.mkdir()
    for row in manifest['files']:
        target = destination / row['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / row['path'], target)
    assert release.verify_release_manifest(destination, manifest)['artifact_id'] == manifest['artifact_id']
    assert manifest['source_sha'] == 'a' * 40 and manifest['ui_sha'] == 'b' * 40
    assert manifest['overlay_roots'] == ['overlay']
    assert any(row['path'].endswith('cacert.pem') for row in manifest['files'])
    assert 'C:/private' not in json.dumps(manifest)


@pytest.mark.parametrize('change', ['source', 'overlay', 'runtime', 'missing', 'extra', 'case_collision'])
def test_verify_release_manifest(artifact, change):
    root, manifest = artifact
    target = root / {'source': 'app/app.py', 'overlay': 'overlay/app/site.css',
                     'runtime': 'runtime/python.exe', 'missing': 'tools/helper.py',
                     'extra': 'app/unlisted.py', 'case_collision': 'app/UNLISTED.py'}[change]
    if change == 'missing':
        target.unlink()
    else:
        target.write_bytes(b'changed content')
    with pytest.raises(ValueError):
        release.verify_release_manifest(root, manifest)


def test_build_release_manifest_excludes_mutable_and_private_data(artifact):
    root, _ = artifact
    for name in ['app/instance/inventory.db', 'app/uploads/customer.txt', 'app/backups/old.db',
                 'app/.env', 'app/logs/runtime.log', 'runtime/__pycache__/cached.pyc']:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'private synthetic content')
    report = {'success': True, 'python_version': '3.11.9', 'packages': [], 'failures': []}
    manifest = release.build_release_manifest(root, source_sha='a'*40, ui_sha='a'*40,
        includes=['app', 'tools', 'runtime'], application_root='app', overlay_roots=[],
        runtime_report=report, external_operations_paused=False)
    assert len(manifest['files']) == 5
    assert not any('private synthetic' in str(item) for item in manifest.values())


@pytest.mark.parametrize('bad', ['../outside', '/absolute', 'C:/outside', 'app/../tools',
                               'app\\escape', '', 'app:stream', 'app//nested'])
def test_build_release_manifest_rejects_unsafe_paths(artifact, bad):
    root, _ = artifact
    with pytest.raises(ValueError):
        release.build_release_manifest(root, source_sha='a'*40, ui_sha='a'*40,
            includes=[bad], application_root='app', overlay_roots=[],
            runtime_report={'success': True, 'python_version': '3.11.9', 'packages': [], 'failures': []},
            external_operations_paused=True)


@pytest.mark.parametrize('field,value', [('source_sha', 'not-a-sha'), ('ui_sha', 'a'*39),
                                      ('external_operations_paused', 'false')])
def test_verify_release_manifest_rejects_untrusted_metadata(artifact, field, value):
    root, manifest = artifact
    manifest = copy.deepcopy(manifest)
    manifest[field] = value
    with pytest.raises(ValueError):
        release.verify_release_manifest(root, manifest)


@pytest.mark.parametrize('bad_report', [
    {'success': False, 'python_version': '3.11.9', 'packages': [], 'failures': ['missing']},
    {'success': True, 'python_version': '3.11.9', 'packages': [
        {'name': 'certifi', 'required': '2', 'installed': '1'}], 'failures': []},
])
def test_build_release_manifest_rejects_failed_dependency_receipt(artifact, bad_report):
    root, _ = artifact
    with pytest.raises(ValueError):
        release.build_release_manifest(root, source_sha='a'*40, ui_sha='a'*40,
            includes=['app'], application_root='app', overlay_roots=[],
            runtime_report=bad_report, external_operations_paused=False)


def test_verify_release_manifest_rejects_self_consistent_path_escape(artifact):
    root, manifest = artifact
    manifest['files'][0]['path'] = '../outside.txt'
    with pytest.raises(ValueError):
        release.verify_release_manifest(root, manifest)


def test_build_release_manifest_rejects_symlink_without_reading_target(artifact, tmp_path):
    root, _ = artifact
    outside = tmp_path / 'outside.txt'
    outside.write_text('private', encoding='utf-8')
    try:
        (root/'app/link.txt').symlink_to(outside)
    except OSError:
        pytest.skip('OS does not permit this test account to create symbolic links')
    with pytest.raises(ValueError):
        release.build_release_manifest(root, source_sha='a'*40, ui_sha='a'*40,
            includes=['app'], application_root='app', overlay_roots=[],
            runtime_report={'success': True, 'python_version': '3.11.9', 'packages': [], 'failures': []},
            external_operations_paused=False)


def test_manage_release_manifest_cli_verifies_without_importing_application(artifact):
    root, manifest = artifact
    cli = MODULE.parents[2] / 'tools/manage_release_manifest.py'
    # app.py is deliberately not executable application code. Verification only hashes it.
    result = subprocess.run([sys.executable, str(cli), 'verify', '--root', str(root)],
                            capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['artifact_id'] == manifest['artifact_id']
    (root/'app/app.py').write_text("raise AssertionError('must not import app')", encoding='utf-8')
    result = subprocess.run([sys.executable, str(cli), 'verify', '--root', str(root)],
                            capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 1 and 'AssertionError' not in result.stderr


def test_build_release_manifest_rejects_overlapping_file_scopes(artifact):
    root, _ = artifact
    with pytest.raises(ValueError):
        release.build_release_manifest(root, source_sha='a'*40, ui_sha='a'*40,
            includes=['app', 'app/app.py'], application_root='app', overlay_roots=[],
            runtime_report={'success': True, 'python_version': '3.11.9', 'packages': [], 'failures': []},
            external_operations_paused=False)


def test_verify_manifest_requires_its_canonical_payload_digest(artifact):
    root, manifest = artifact
    # Python considers 1 == 1.0; the canonical JSON digest must still bind the exact payload.
    manifest['files'][0]['size'] = float(manifest['files'][0]['size'])
    with pytest.raises(ValueError):
        release.verify_release_manifest(root, manifest)

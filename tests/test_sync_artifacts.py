from __future__ import annotations

import subprocess
import json
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent


def _exported_tracked_paths(request_file):
    data = json.loads(request_file.read_text(encoding='utf-8'))
    assert re.fullmatch('[0-9a-f]{40}', data.get('sha', '')), 'missing exact source identity'
    paths = data.get('tracked_paths')
    assert isinstance(paths, list) and paths and all(isinstance(p, str) and p for p in paths)
    return paths


def test_decompiled_apk_output_is_not_versioned_or_present():
    if (ROOT / '.git').exists():
        tracked = subprocess.run(
            ["git", "ls-files", "--", "apk_source"], cwd=ROOT,
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()
    else:
        # A verified CI source image has no host .git. The controller preserves
        # all tracked names (including excluded data names) in its immutable
        # request, so this still detects versioned output, not just visible files.
        from scripts.linux_test_runtime import require_linux_runtime
        require_linux_runtime()
        tracked = [name for name in _exported_tracked_paths(Path('/opt/wms-ci-request.json'))
                   if name == 'apk_source' or name.startswith('apk_source/')]
    assert tracked == []
    assert not (ROOT / "apk_source").exists()
    assert "apk_source/" in (ROOT / ".gitignore").read_text(encoding="utf-8")


@pytest.mark.parametrize('data', [
    {}, {'sha': 'a' * 40}, {'sha': 'a' * 40, 'tracked_paths': []},
    {'sha': 'short', 'tracked_paths': ['app/app.py']},
    {'sha': 'a' * 40, 'tracked_paths': [None]},
])
def test_source_inventory_fails_closed(tmp_path, data):
    path = tmp_path / 'request.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(AssertionError):
        _exported_tracked_paths(path)


def test_source_inventory_retains_excluded_tracked_names(tmp_path):
    paths = ['app/app.py', 'apk_source/private.db']
    path = tmp_path / 'request.json'
    path.write_text(json.dumps({'sha': 'a' * 40, 'tracked_paths': paths}), encoding='utf-8')
    assert _exported_tracked_paths(path) == paths

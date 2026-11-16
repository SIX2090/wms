"""Pure Node/actual ZXing regression; never imports WMS or accesses a database."""
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize('scenario', ['decode-miss', 'checksum-miss', 'format-miss', 'fatal-callback'])
def test_actual_bundled_zxing_scanner_behavior(scenario, tmp_path):
    root = Path(__file__).resolve().parents[1]
    node = shutil.which('node')
    assert node, 'Node is required for the actual vendored ZXing contract'
    result = subprocess.run(
        [node, '--max-old-space-size=96', '--require',
         str(root / 'tests/audit_regressions/network_guard.cjs'),
         str(root / 'tests/mobile_scanner_fullscreen_20261116.cjs'),
         '--root', str(root), '--scenario', scenario,
         '--evidence', str(tmp_path / (scenario + '.json'))],
        capture_output=True, text=True, encoding='utf-8', timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"passed":true' in result.stdout

"""Run actual BOM/shared table interactions in a local Node VM."""
from pathlib import Path
import shutil
import subprocess


def test_bom_recorded_cost_browser_interactions():
    node = shutil.which('node')
    assert node, 'Node.js is required for the BOM browser interaction contract'
    result = subprocess.run([node, str(Path(__file__).with_suffix('.cjs'))],
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'TOTAL 17 passed=17 failed=0' in result.stdout

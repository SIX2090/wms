"""Execute real inline-product functions without importing the WMS app."""
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize("scenario", [
    "readonly", "initial", "zero", "switch", "input", "clear", "unknown",
    "blur", "change", "enter", "copy", "copy_existing", "empty_new", "save",
])
def test_subcontract_inline_master_price(scenario):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for real template functions")
    runner = Path(__file__).with_name("subcontract_inline_master_price_runtime.cjs")
    result = subprocess.run([node, str(runner), scenario], capture_output=True,
                            encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr

"""Real purchase-request/material-add scripts; isolated DOM and network, no app import."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("page", ["purchase-", "material-"])
def test_form_identity_consistency_runtime(page):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required")
    result = subprocess.run(
        [node, "--max-old-space-size=96",
         str(ROOT / "tests/frontend_form_identity_consistency.cjs"), str(ROOT), page],
        capture_output=True, text=True, encoding="utf-8", timeout=25,
    )
    assert result.returncode == 0, result.stdout + result.stderr

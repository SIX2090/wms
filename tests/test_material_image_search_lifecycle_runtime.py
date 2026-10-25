"""Run real material image search and API scripts with isolated DOM/transport."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_material_image_search_lifecycle_runtime():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required")
    result = subprocess.run(
        [node, "--max-old-space-size=96",
         str(ROOT / "tests/frontend_material_image_search_lifecycle.cjs"), str(ROOT)],
        capture_output=True, text=True, encoding="utf-8", timeout=25,
    )
    assert result.returncode == 0, result.stdout + result.stderr

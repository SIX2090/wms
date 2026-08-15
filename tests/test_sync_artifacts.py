from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_decompiled_apk_output_is_not_versioned_or_present():
    tracked = subprocess.run(
        ["git", "ls-files", "--", "apk_source"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert tracked.stdout == ""
    assert not (ROOT / "apk_source").exists()
    assert "apk_source/" in (ROOT / ".gitignore").read_text(encoding="utf-8")

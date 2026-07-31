#!/usr/bin/env python3
# AI_TASK: AI-SEC-F01-F01
"""Verify the Windows offline wheelhouse resolves the locked application requirements."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT_DIR / "app" / "requirements.txt"
WHEELHOUSE = ROOT_DIR / "wheelhouse"


def verify_offline_wheelhouse(wheelhouse: Path = WHEELHOUSE) -> None:
    """Ask pip to resolve requirements without network or installed packages."""
    if not REQUIREMENTS.is_file():
        raise SystemExit(f"requirements file is missing: {REQUIREMENTS}")
    if not wheelhouse.is_dir():
        raise SystemExit(f"wheelhouse is missing: {wheelhouse}")

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--dry-run", "--ignore-installed",
         "--no-index", "--find-links", str(wheelhouse), "-r", str(REQUIREMENTS)],
        cwd=ROOT_DIR,
        check=False,
    )
    if result.returncode:
        raise SystemExit(result.returncode)
    print("PASS: offline wheelhouse resolves app/requirements.txt")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheelhouse", type=Path, default=WHEELHOUSE)
    verify_offline_wheelhouse(parser.parse_args().wheelhouse)


if __name__ == "__main__":
    main()

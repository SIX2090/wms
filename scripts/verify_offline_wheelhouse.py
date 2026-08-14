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


def _is_tracked_but_sparse(path: Path) -> bool:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(path / "*")],
        cwd=ROOT_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def verify_offline_wheelhouse(wheelhouse: Path = WHEELHOUSE) -> None:
    """Validate the Windows offline wheelhouse resolves the locked requirements.

    The wheelhouse ships win_amd64 wheels (deployment target is a Windows host),
    so dry-run resolution must be pinned to the target wheel platform instead of
    the host OS. This lets the check run on Linux CI and still prove the bundle
    is complete for the Windows deployment target.
    """
    if not REQUIREMENTS.is_file():
        raise SystemExit(f"requirements file is missing: {REQUIREMENTS}")
    if not wheelhouse.is_dir():
        if _is_tracked_but_sparse(wheelhouse):
            raise SystemExit(
                "wheelhouse is tracked but absent from this sparse checkout; "
                "run: git sparse-checkout add /wheelhouse/"
            )
        raise SystemExit(f"wheelhouse is missing: {wheelhouse}")

    # 目标平台：Windows amd64 + CPython 3.11（与 wheelhouse 内 cp311 wheels 一致）。
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--dry-run", "--ignore-installed",
         "--no-index", "--find-links", str(wheelhouse), "-r", str(REQUIREMENTS),
         "--platform", "win_amd64", "--python-version", "3.11",
         "--implementation", "cp", "--abi", "cp311", "--only-binary=:all:"],
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

#!/usr/bin/env python3
# AI_TASK: AI-STAB-F01
"""Run the mandatory WMS stabilization release gate."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
COMMANDS = (
    ("lint rules", ("scripts/lint_wms_rules.py",)),
    ("non-GET fetch lint", ("scripts/lint_no_raw_post_fetch.py",)),
    ("bug regression", ("scripts/verify_wms_bugs.py",)),
    ("inbound state machine", ("scripts/verify_in_order_state_machine.py",)),
    ("outbound state machine", ("scripts/verify_out_order_state_machine.py",)),
    ("offline wheelhouse", ("scripts/verify_offline_wheelhouse.py",)),
    ("pytest", ("-m", "pytest", "tests/", "-q")),
)


def run_stability_gate() -> int:
    """Run every required gate in a deterministic order and stop on failure."""
    for label, arguments in COMMANDS:
        command = (sys.executable, *arguments)
        print(f"== {label}: {' '.join(command)}")
        if subprocess.run(command, cwd=ROOT_DIR, check=False).returncode:
            print(f"FAIL: {label}")
            return 1
    print("PASS: WMS stabilization release gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_stability_gate())

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    tracked = subprocess.run(
        ["git", "ls-files", "--", "apk_source"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "apk_source/example.java"],
        cwd=ROOT,
    )

    failures: list[str] = []
    if tracked.stdout:
        failures.append("apk_source 仍被 Git 跟踪")
    if (ROOT / "apk_source").exists():
        failures.append("apk_source 目录仍存在")
    if ignored.returncode != 0:
        failures.append("apk_source 未被 .gitignore 忽略")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print("PASS: apk_source 已移除、未跟踪且被忽略")
    return 0


if __name__ == "__main__":
    sys.exit(main())

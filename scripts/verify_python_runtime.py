from __future__ import annotations

import argparse
import importlib
import sys


REQUIRED_IMPORTS = ("flask", "sqlalchemy", "PIL", "openpyxl")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the WMS Python runtime.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    failures: list[str] = []
    if sys.version_info[:2] != (3, 11):
        failures.append(f"Python 3.11 is required; found {sys.version.split()[0]}")

    for module_name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            failures.append(f"cannot import {module_name}: {exc}")

    if failures:
        for failure in failures:
            print(f"[ERROR] {failure}")
        return 1

    if not args.quiet:
        print("PASS PYTHON-RUNTIME: Python 3.11 and required imports are available")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

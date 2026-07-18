"""AI-R18-F02 verification for the administrator acceptance desk."""
from __future__ import annotations

import re
from pathlib import Path

# AI_TASK: AI-R18-F02
ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app" / "app.py").read_text(encoding="utf-8")
PAGE = (ROOT / "app" / "templates" / "ai_acceptance.html").read_text(encoding="utf-8")


def main() -> int:
    route_start = APP.index("def ai_acceptance_page")
    checks = {
        "admin page route": "@require_role('admin')" in APP[route_start - 140:route_start],
        "task marker": "AI_TASK: AI-R18-F02" in APP and "AI_TASK: AI-R18-F02" in PAGE,
        "snapshot API": "/api/ai/acceptance/daily_snapshots" in PAGE and "/api/ai/acceptance/daily_snapshot" in PAGE,
        "evidence API": "/api/ai/acceptance/evidence_package" in PAGE,
        "manual signature API": "/api/ai/acceptance/go_no_go" in PAGE and "signButton" in PAGE,
        "no automatic business action": not re.search(r"/(submit|audit|complete|delete|void|ship|auto_dispatch)", PAGE, re.I),
        "no password operation": not re.search(r"password|reset_password|change_password", PAGE, re.I),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        print("FAIL AI-R18-F02 acceptance page: " + ", ".join(failed))
        return 1
    print(f"PASS AI-R18-F02 acceptance page: {len(checks)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

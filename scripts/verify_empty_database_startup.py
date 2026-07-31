#!/usr/bin/env python3
# AI_TASK: AI-STAB-F04
"""Verify an empty in-memory database can migrate and serve the login page."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import inspect


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    sys.path.insert(0, str(ROOT / "app"))
    os.environ.setdefault("FLASK_ENV", "testing")
    os.environ.setdefault("WMS_SKIP_DB_UPGRADE", "1")
    import app as wms

    wms.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with wms.app.app_context():
        wms.db.drop_all()
        wms.auto_migrate_database()
        wms.db.create_all()
        assert inspect(wms.db.engine).has_table("user")
    response = wms.app.test_client().get("/login")
    assert response.status_code == 200
    print("PASS: empty database migrates and serves login")


if __name__ == "__main__":
    main()

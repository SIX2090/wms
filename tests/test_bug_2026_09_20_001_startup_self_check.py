# -*- coding: utf-8 -*-
"""BUG-2026-09-20-001 回归测试：启动自检 banner（P0-3 / R3 生效闭环）。

覆盖：
- config-check 行格式：wms vX.Y.Z 开头、含 env/session_cookie/csrf/secret_key/db/migrate
- 敏感值不落行：SECRET_KEY 本体、数据库口令不出现在自检行
- 生产显式放行/HTTPS/开发环境三种 session_cookie 状态
- git 短 SHA 解析（仓库内返回 7 位 hex；异常路径返回 None）
- db-check 迁移哨兵：初始化后全 ok；缺列时报 missing 且不抛异常
- run_server.main 接线静态断言：先 config-check 后 db-check
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

import app as app_module  # noqa: E402
from startup_check import (build_config_check_line, build_db_check_line,  # noqa: E402
                           git_short_sha, log_startup_self_check, version_string)

app_module.app.config["TESTING"] = True  # guarded_drop_all 要求内存库 + TESTING


def test_git_short_sha():
    sha = git_short_sha()
    if (ROOT / ".git").is_dir():
        assert sha is not None and len(sha) == 7
        int(sha, 16)  # 合法 hex
    else:
        assert sha is None


def test_version_string():
    v = version_string()
    assert v.startswith("v")
    # vX.Y.Z 形态
    core = v.split(" ", 1)[0][1:]
    assert len(core.split(".")) == 3


def test_build_config_check_line():
    line = build_config_check_line(app_module.app, env_name="production")
    assert line.startswith("wms v")
    assert " config-check: " in line
    for key in ("env=production", "session_cookie=", "csrf=", "secret_key=", "db=sqlite", "migrate=pending-init"):
        assert key in line, key
    # 敏感值不落行
    secret = app_module.app.config.get("SECRET_KEY") or ""
    assert not secret or secret not in line
    assert "inventory.db" not in line or "db=sqlite;" in line


def test_build_config_check_line_session_cookie_states(monkeypatch):
    app = app_module.app
    monkeypatch.setitem(app.config, "SESSION_COOKIE_SECURE", False)
    # 生产显式放行（能启动即已 opt-in）
    assert "session_cookie=insecure-explicit-optin!" in build_config_check_line(app, "production")
    # 开发环境
    assert "session_cookie=insecure-dev" in build_config_check_line(app, "development")
    # HTTPS 部署
    monkeypatch.setitem(app.config, "SESSION_COOKIE_SECURE", True)
    assert "session_cookie=secure" in build_config_check_line(app, "production")


def test_build_db_check_line():
    with app_module.app.app_context():
        app_module.db.drop_all()
        app_module.db.create_all()
    line = build_db_check_line(app_module.app, app_module.db)
    assert line.startswith("wms v")
    assert " db-check: migrate=ok" in line


def test_build_db_check_line_missing_column_reports_not_raises():
    with app_module.app.app_context():
        app_module.db.drop_all()
        app_module.db.create_all()
        # 模拟老库缺列：删 location_inventory 表制造缺失
        app_module.db.session.execute(app_module.db.text("DROP TABLE location_inventory"))
        app_module.db.session.commit()
    try:
        line = build_db_check_line(app_module.app, app_module.db)
        assert "missing: location_inventory(table)" in line
    finally:
        with app_module.app.app_context():
            app_module.db.drop_all()
            app_module.db.create_all()


def test_log_startup_self_check():
    line = log_startup_self_check(app_module.app)
    assert " config-check: " in line
    line2 = log_startup_self_check(app_module.app, db=app_module.db, include_db=True)
    assert " db-check: " in line2


def test_run_server_wires_self_check_before_serve():
    """静态断言：run_server.main 在 serve 之前依次输出 config-check 与 db-check。"""
    src = (APP_DIR / "run_server.py").read_text(encoding="utf-8")
    i_cfg = src.index("log_startup_self_check(app)")
    i_db = src.index("include_db=True")
    i_serve = src.index("serve(app,")
    assert i_cfg < i_db < i_serve

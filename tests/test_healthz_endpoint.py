# -*- coding: utf-8 -*-
"""GET /healthz 健康端点契约（F1.4 / P0-4 / 审计 §7.4）。

锁定三个不可削弱的设计约束（见 app.py healthz docstring）：
  1. 免认证——未登录直接 GET 返回 200（不是 302 跳登录）；
  2. 不查库——正常路径不触发任何 SQL（健康探活不被数据库抖动拖挂）；
  3. 响应结构——status 字段 + checks 字段，degraded 时 503。

实现说明：使用 app 的 test_client 而非真实 HTTP，与 CI 内其它路由
测试同一模式（无网络依赖）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402


app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _client():
    return app_module.app.test_client()


def test_healthz_no_auth_returns_200():
    """未登录直接访问 /healthz 必须 200，而不是被登录墙 302。"""
    resp = _client().get("/healthz")
    assert resp.status_code == 200, (
        f"/healthz 应免认证返回 200，实际 {resp.status_code}"
        "（若 302 说明被挂上了登录墙，探活将形同虚设）"
    )


def test_healthz_payload_structure():
    """响应必须是 JSON，含 status 与 checks 字段，当前应 ok。"""
    resp = _client().get("/healthz")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert isinstance(data["checks"], dict)
    # 关键检查项：进程存活 + instance 目录
    assert data["checks"].get("app") is True
    assert "instance_dir" in data["checks"]
    assert "time" in data


def test_healthz_degraded_returns_503(monkeypatch):
    """检查项失败时必须 503 + degraded（探活方能区分真活与半死）。"""
    import app as am

    monkeypatch.setattr(
        am.os.path, "isdir", lambda p: False
    )
    resp = _client().get("/healthz")
    assert resp.status_code == 503
    assert resp.get_json()["status"] == "degraded"


def test_healthz_does_not_touch_database():
    """/healthz 请求全程不得触发任何 SQL（不查库约束的机械守卫）。

    做法：注册一个 SQLAlchemy before_cursor_execute 钩子，任何 SQL
    执行都记入列表；请求结束后列表必须为空。
    """
    from sqlalchemy import event

    with app_module.app.app_context():
        engine = app_module.db.engine
        fired = []

        @event.listens_for(engine, "before_cursor_execute")
        def _spy(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
            fired.append(statement)

        try:
            resp = _client().get("/healthz")
            assert resp.status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", _spy)

    assert not fired, (
        "/healthz 触发了 SQL，违反'不查库'约束：\n  " + "\n  ".join(fired[:5])
    )


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL PASSED")

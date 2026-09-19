# -*- coding: utf-8 -*-
"""AI-MOB-CRASH-01：移动端崩溃上报端点 /api/mobile/crash_report 回归测试。

设计依据（app/routes/native_api.py mobile_api_crash_report）：
- 崩溃可能发生在登录前 / token 失效后，端点**不强制鉴权**：带合法 Bearer 记用户名，
  无鉴权记 anonymous——不得把"登录页就崩"这类最高价值崩溃拒之门外。
- 报告写入 logs/crash_reports.log（JSON 行）。测试用捕获 handler 替换 wms.crash
  的 handlers，既验证写入内容又避免真实落盘。
- A8：pydantic 校验，缺必填字段 / 字段超限一律 400 且不写盘。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

import pytest

import app as wms


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setitem(wms.app.config, "TESTING", True)
    monkeypatch.setitem(wms.app.config, "WTF_CSRF_ENABLED", False)
    with wms.app.app_context():
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()
        user = wms.User(username="op1", password_hash="unused", role="admin",
                        must_change_password=False)
        wms.db.session.add(user)
        wms.db.session.commit()
        yield wms.app.test_client()
        # teardown 与 setup 对称，交还干净库（AI-CI-GREEN-001 污染治理）
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()


@pytest.fixture
def crash_capture():
    """替换 wms.crash 的 handlers 为捕获 handler：生产代码见 handlers 非空即跳过
    文件初始化，直接把 JSON 行打进本 handler，断言无需触碰真实日志文件。"""
    logger = logging.getLogger("wms.crash")
    old_handlers = logger.handlers[:]
    old_level = logger.level
    records = []

    class _H(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    logger.handlers = [_H()]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    yield records
    logger.handlers = old_handlers
    logger.setLevel(old_level)


def _bearer():
    user = wms.User.query.filter_by(username="op1").one()
    wms.db.session.add(wms.ApiToken(token="crash-test", user_id=user.id,
                                    expires_at=datetime.now() + timedelta(hours=1)))
    wms.db.session.commit()
    return {"Authorization": "Bearer crash-test"}


def _payload(**over):
    base = {
        "app_version": "3.8.0",
        "version_code": 14,
        "android_sdk": 33,
        "device": "rockchip PDA",
        "thread": "main",
        "exception": "NullPointerException: Attempt to read field on null",
        "stacktrace": "java.lang.NullPointerException\n\tat com.factory.wms.MainActivity.onCreate",
        "occurred_at": 1726000000000,
    }
    base.update(over)
    return base


def test_crash_report_with_bearer_records_username(client, crash_capture):
    resp = client.post("/api/mobile/crash_report", headers=_bearer(), json=_payload())
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["success"] is True
    assert len(crash_capture) == 1
    record = json.loads(crash_capture[0])
    assert record["username"] == "op1"
    assert record["exception"].startswith("NullPointerException")
    assert record["app_version"] == "3.8.0"
    assert record["version_code"] == 14


def test_crash_report_anonymous_accepted(client, crash_capture):
    # 登录前崩溃不得被拒收：无 Bearer 也应 200，记 anonymous
    resp = client.post("/api/mobile/crash_report", json=_payload())
    assert resp.status_code == 200, resp.get_json()
    assert len(crash_capture) == 1
    assert json.loads(crash_capture[0])["username"] == "anonymous"


def test_crash_report_missing_required_field_400(client, crash_capture):
    bad = _payload()
    bad.pop("exception")
    resp = client.post("/api/mobile/crash_report", json=bad)
    assert resp.status_code == 400
    assert crash_capture == []  # 校验失败不写盘


def test_crash_report_oversize_stacktrace_400(client, crash_capture):
    resp = client.post("/api/mobile/crash_report",
                       json=_payload(stacktrace="x" * 20001))
    assert resp.status_code == 400
    assert crash_capture == []


def test_crash_report_empty_body_400(client, crash_capture):
    resp = client.post("/api/mobile/crash_report", json={})
    assert resp.status_code == 400
    assert crash_capture == []

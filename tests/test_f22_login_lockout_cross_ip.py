# -*- coding: utf-8 -*-
"""F2.2 / S3 回归：账号维度跨 IP 累计锁定 + 单 IP 全局限流。

背景（S3）：原实现按「账号 + 来源 IP」计数，攻击者换 IP 即清零重来，可无限爆破。
修复后：账号维度累计（跨 IP 不清零），达阈值锁定账号（对所有 IP 生效）；并叠加
单 IP 全局失败限流（跨账号）防扫号。
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

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
import rate_limit  # noqa: E402
from app import User, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _seed():
    db.drop_all()
    db.create_all()
    db.session.add(User(
        username="victim", password_hash=generate_password_hash("correct"),
        role="user", status="normal", must_change_password=False,
    ))
    db.session.commit()


def test_account_locks_across_different_ips():
    """同一账号跨不同 IP 累计失败达阈值 → 账号锁定（对所有 IP 生效）。"""
    with app_module.app.app_context():
        _seed()
        u = User.query.filter_by(username="victim").first()
        limit = app_module.max_login_failures()
        for i in range(limit):
            u.increment_failed_count("10.0.0.%d" % (i + 1))
        db.session.commit()
        u2 = User.query.filter_by(username="victim").first()
        assert u2.is_locked is True
        assert u2.is_locked_for("10.0.0.99") is True  # 换一个 IP 仍被锁定


def test_switching_ip_does_not_reset_account_counter():
    """换 IP 不再清零账号维度计数（S3 核心）。"""
    with app_module.app.app_context():
        _seed()
        u = User.query.filter_by(username="victim").first()
        u.increment_failed_count("1.1.1.1")
        u.increment_failed_count("2.2.2.2")
        u.increment_failed_count("3.3.3.3")
        db.session.commit()
        u2 = User.query.filter_by(username="victim").first()
        assert u2.login_failed_count == 3  # 未被换 IP 清零


def test_successful_login_resets_account_counter():
    """成功登录清零账号维度计数（正常用户不受影响）。"""
    with app_module.app.app_context():
        _seed()
        u = User.query.filter_by(username="victim").first()
        u.increment_failed_count("1.1.1.1")
        u.reset_failed_count()
        db.session.commit()
        u2 = User.query.filter_by(username="victim").first()
        assert u2.login_failed_count == 0
        assert u2.is_locked is False


def test_ip_global_rate_limit_blocks_after_threshold():
    """单 IP 全局失败限流：达到阈值后 POST /login 返回 429。"""
    rate_limit.reset()
    with app_module.app.app_context():
        _seed()
    client = app_module.app.test_client()
    limit = app_module.LOGIN_IP_RATE_LIMIT_PER_MINUTE
    assert limit > 0, "测试需 LOGIN_IP_RATE_LIMIT_PER_MINUTE > 0"
    for _ in range(limit):
        client.post("/login", data={"username": "ghost", "password": "x"},
                    content_type="application/x-www-form-urlencoded")
    resp = client.post("/login", data={"username": "ghost", "password": "x"},
                       content_type="application/x-www-form-urlencoded")
    assert resp.status_code == 429, "单 IP 失败达到上限后应返回 429"

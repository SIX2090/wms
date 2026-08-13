# -*- coding: utf-8 -*-
"""
BUG-2026-08-13-005 回归测试：Bearer Token 写放大与无限续期。
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402
from app import ApiToken, User, db  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _seed_user(role="warehouse") -> User:
    u = User(username=f"tok_{role}_{os.urandom(3).hex()}", role=role,
             password_hash=generate_password_hash("x"),
             status="normal", must_change_password=False)
    db.session.add(u)
    db.session.commit()
    return u


def _make_token(user, expires_at, last_used_at=None) -> ApiToken:
    t = ApiToken(
        token=f"tok_{os.urandom(6).hex()}",
        user_id=user.id,
        expires_at=expires_at,
        last_used_at=last_used_at,
        revoked=False,
    )
    db.session.add(t)
    db.session.commit()
    return t


class _CommitCounter:
    def __enter__(self):
        self._orig = db.session.commit
        self.count = 0
        def counting(*a, **kw):
            self.count += 1
            return self._orig(*a, **kw)
        db.session.commit = counting
        return self
    def __exit__(self, *exc):
        db.session.commit = self._orig
        return False


class TestBearerTokenRenewal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()

    def setUp(self):
        with app_module.app.app_context():
            ApiToken.query.delete()
            User.query.filter(User.username.like("tok_%")).delete(synchronize_session=False)
            db.session.commit()

    def _call(self, token_value):
        with app_module.app.test_request_context("/", headers={
            "Authorization": f"Bearer {token_value}"
        }):
            return app_module.get_bearer_user()

    def test_first_use_sets_last_used_no_renew(self):
        """T1：首次请求写 last_used_at，expires_at 不变（剩余 7d）。"""
        with app_module.app.app_context():
            user = _seed_user()
            exp = datetime.now() + timedelta(days=7)
            token = _make_token(user, exp, None)
            orig_exp = token.expires_at
            tv = token.token
            with _CommitCounter() as cc:
                self._call(tv)
            self.assertEqual(cc.count, 1)
            r = db.session.get(ApiToken, token.id)
            self.assertIsNotNone(r.last_used_at)
            self.assertEqual(r.expires_at.replace(microsecond=0),
                             orig_exp.replace(microsecond=0))

    def test_rapid_requests_no_commit(self):
        """T2：5 分钟内 5 次请求 0 commit（last_used 节流 + expires 不动）。"""
        with app_module.app.app_context():
            user = _seed_user()
            exp = datetime.now() + timedelta(days=7)
            token = _make_token(user, exp, datetime.now())
            tv = token.token
            with _CommitCounter() as cc:
                for _ in range(5):
                    self._call(tv)
            self.assertEqual(cc.count, 0)

    def test_far_from_expiry_not_renewed(self):
        """T3：剩余 >1d，expires_at 不前推。"""
        with app_module.app.app_context():
            user = _seed_user()
            exp = datetime.now() + timedelta(days=3)
            token = _make_token(user, exp, datetime.now())
            tv = token.token
            self._call(tv)
            r = db.session.get(ApiToken, token.id)
            self.assertEqual(r.expires_at.replace(microsecond=0),
                             exp.replace(microsecond=0))

    def test_near_expiry_renewed(self):
        """T4：剩余 <1d 时顺延 7d。"""
        with app_module.app.app_context():
            user = _seed_user()
            exp = datetime.now() + timedelta(hours=2)
            token = _make_token(user, exp, datetime.now())
            tv = token.token
            before = datetime.now()
            self._call(tv)
            r = db.session.get(ApiToken, token.id)
            remaining = (r.expires_at - before).total_seconds()
            lo = timedelta(days=6, hours=23).total_seconds()
            hi = timedelta(days=7, seconds=10).total_seconds()
            self.assertGreater(remaining, lo)
            self.assertLess(remaining, hi)

    def test_last_used_flushed_after_window(self):
        """T5：last_used 距上次 >=5min 再次请求会刷新并 commit。"""
        with app_module.app.app_context():
            user = _seed_user()
            exp = datetime.now() + timedelta(days=7)
            old = datetime.now() - timedelta(minutes=10)
            token = _make_token(user, exp, old)
            tv = token.token
            with _CommitCounter() as cc:
                self._call(tv)
            self.assertEqual(cc.count, 1)
            r = db.session.get(ApiToken, token.id)
            self.assertGreater(r.last_used_at, old)

    def test_expired_revoked_no_commit(self):
        """T6：过期/吊销 token 不 commit。"""
        with app_module.app.app_context():
            user = _seed_user()
            e = _make_token(user, datetime.now() - timedelta(days=1), None)
            r = _make_token(user, datetime.now() + timedelta(days=7), None)
            r.revoked = True
            db.session.commit()
            with _CommitCounter() as cc:
                self.assertIsNone(self._call(e.token))
                self.assertIsNone(self._call(r.token))
            self.assertEqual(cc.count, 0)

    def test_source_policy_signals(self):
        """T7：源码静态。"""
        import inspect
        src = inspect.getsource(app_module.get_bearer_user)
        self.assertNotIn("token.expires_at = datetime.now() + timedelta(days=7)", src)
        self.assertIn("LAST_USED_FLUSH_SECONDS", src)
        self.assertIn("RENEW_THRESHOLD_SECONDS", src)
        self.assertIn("need_flush_last_used", src)
        self.assertIn("need_renew", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)

# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：审批中心（approval）域路由迁移到 routes/approval.py。

采用 register-on-app 模式（register_approval_routes(app)），endpoint 名保持不变
（approval_list/approve_from_approval_center/reject_from_approval_center），
URL 路径不变。

验收点：
S1. 3 个 endpoint 已注册，仍是原始 endpoint 名，不存在 approval.xxx 重复。
S2. URL 路径保持不变（/approval、/approval/<id>/approve、/approval/<id>/reject）。
S3. 审批列表页可渲染（200，含采购申请字样）。
S4. 批准采购申请成功，状态变为 approved。
S5. 驳回采购申请成功，状态变为 rejected。
"""
from __future__ import annotations

import os
import sys
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
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

APPROVAL_ENDPOINTS = [
    "approval_list",
    "approve_from_approval_center",
    "reject_from_approval_center",
]


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    return app_module.app.test_client()


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


def _seed_purchase_request():
    from app import PurchaseRequest
    pr = PurchaseRequest(
        request_no="PR0001",
        date=app_module.date.today(),
        applicant="张三",
        status="pending",
    )
    db.session.add(pr)
    db.session.commit()
    return pr.id


class TestApprovalRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
        return _make_client()

    def test_endpoints_and_urls(self):
        """S1/S2：3 个 endpoint 注册、URL 不变、无前缀重复。"""
        with app_module.app.app_context():
            for ep in APPROVAL_ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
            for ep in APPROVAL_ENDPOINTS:
                assert f"approval.{ep}" not in app_module.app.view_functions, f"approval.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("approval_list") == "/approval"
                assert url_for("approve_from_approval_center", id=1) == "/approval/1/approve"
                assert url_for("reject_from_approval_center", id=1) == "/approval/1/reject"

    def test_approval_list(self):
        """S3：审批列表页可渲染。"""
        client = self._setup()
        _login(client)
        with app_module.app.app_context():
            _seed_purchase_request()
        resp = client.get("/approval")
        assert resp.status_code == 200
        assert "采购申请" in resp.get_data(as_text=True)

    def test_approve(self):
        """S4：批准成功，状态变为 approved。"""
        client = self._setup()
        _login(client)
        with app_module.app.app_context():
            pr_id = _seed_purchase_request()
        resp = client.post(f"/approval/{pr_id}/approve")
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            from app import PurchaseRequest
            assert db.session.get(PurchaseRequest, pr_id).status == "approved"

    def test_reject(self):
        """S5：驳回成功，状态变为 rejected。"""
        client = self._setup()
        _login(client)
        with app_module.app.app_context():
            pr_id = _seed_purchase_request()
        resp = client.post(f"/approval/{pr_id}/reject")
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            from app import PurchaseRequest
            assert db.session.get(PurchaseRequest, pr_id).status == "rejected"
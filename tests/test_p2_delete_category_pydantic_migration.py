# -*- coding: utf-8 -*-
"""P2-B 回归：delete_category 存量路由 Pydantic 迁移示范（A8/A9 模式）。

Pydantic 迁移模式（存量路由通用参考）：
  1. 路由体内延迟 `from pydantic import BaseModel, Field`
  2. 定义 `class <Endpoint>Request(BaseModel)` 声明字段/类型/约束
  3. `payload = request.get_json(silent=True) or {}` 防 None / 非 JSON
  4. `DeleteCategoryRequest.model_validate(payload)` 做类型校验
  5. 校验失败统一 return 400 + 可读 msg
  6. 后续业务逻辑直接用强类型 req.xxx（无需 str/int 手工转换）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import MaterialCategory, User, db  # noqa: E402


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    db.session.add(User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin", must_change_password=False,
    ))
    db.session.commit()


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
    c = app_module.app.test_client()
    _login(c)
    yield c


def test_delete_category_accepts_int_ids(client):
    """合法请求：ids 为整数列表 → Pydantic 通过，后端正常处理（空列表=空删除）。"""
    resp = client.post("/category/delete", json={"ids": []})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data


def test_delete_category_rejects_bad_type_ids(client):
    """非法请求：ids 含非数字 → Pydantic 校验失败，返回 400（A8 模式）。"""
    resp = client.post("/category/delete", json={"ids": ["not_a_number"]})
    assert resp.status_code == 400, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "error", data
    assert "校验失败" in data.get("msg", "")


def test_delete_category_rejects_ids_not_list(client):
    """非法请求：ids 不是列表 → Pydantic 校验失败 400。"""
    resp = client.post("/category/delete", json={"ids": 123})
    assert resp.status_code == 400, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "error", data


def test_delete_category_valid_deletes(client):
    """建一个无子无引用的分类，删除成功且 DB 记录消失。"""
    with app_module.app.app_context():
        cat = MaterialCategory(code="C1", name="待删分类")
        db.session.add(cat)
        db.session.commit()
        cat_id = cat.id
    resp = client.post("/category/delete", json={"ids": [cat_id]})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        assert db.session.get(MaterialCategory, cat_id) is None

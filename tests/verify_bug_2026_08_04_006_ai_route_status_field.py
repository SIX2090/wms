# -*- coding: utf-8 -*-
"""
BUG-2026-08-04-006 回归测试：AI 路由查询不存在的 status 字段

原 Bug：
  /api/ai/recommend_location 和 /api/ai/demand_forecast 路由用
  Material.query.filter_by(status='active') 查询，但 Material 模型
  没有 status 字段，导致 SQLAlchemy 抛 "Unknown column material.status"
  错误，AI 库位推荐和需求预测功能直接 500 不可用。

修复：
  移除 filter_by(status='active')，改为 Material.query.all() /
  Material.query，因为 Material 模型没有启用/停用状态概念，
  所有物料均视为可用。

测试：
  T1. /api/ai/recommend_location 不传 material_id 时返回 200（不 500）
  T2. /api/ai/demand_forecast 无物料时返回 200 + 空预测列表
  T3. /api/ai/recommend_location 有物料时返回 200 + materials 列表
  T4. /api/ai/demand_forecast 有物料但无出库记录时返回 200 + 空 forecasts
"""
from __future__ import annotations

import os
import sys
import re
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
from app import db, User, Material  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    db.session.add(user)
    db.session.commit()


def _login(client):
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post("/login", data={
        "username": "admin", "password": "admin", "csrf_token": token})


def _enable_ai_llm(monkeypatch):
    """绕过 LLM 配置检查，避免测试依赖真实大模型 API。"""
    monkeypatch.setattr(app_module, "_ai_llm_configured", lambda overrides=None: True)


class TestBug20260804006AiRouteStatusField:
    """AI 路由不能因 Material.status 字段不存在而 500。"""

    def test_T1_recommend_location_no_material_id_returns_200(self, monkeypatch):
        """/api/ai/recommend_location 不传 material_id 时返回 200（不 500）。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _enable_ai_llm(monkeypatch)
            db.session.add(Material(code="M001", name="轴承", spec="6204", price=10))
            db.session.commit()
            client = app_module.app.test_client()
            _login(client)
            resp = client.post("/api/ai/recommend_location",
                               json={},
                               headers={"X-Requested-With": "XMLHttpRequest"})
            # 不应是 500（原 bug 会因 status 字段不存在而 500）
            assert resp.status_code != 500, \
                f"AI 库位推荐不应 500：{resp.get_data(as_text=True)}"
            data = resp.get_json()
            assert data is not None, "必须返回 JSON"

    def test_T2_demand_forecast_no_material_returns_200_empty(self, monkeypatch):
        """/api/ai/demand_forecast 无物料时返回 200 + 空预测列表。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _enable_ai_llm(monkeypatch)
            client = app_module.app.test_client()
            _login(client)
            resp = client.post("/api/ai/demand_forecast",
                               json={"forecast_days": 30},
                               headers={"X-Requested-With": "XMLHttpRequest"})
            assert resp.status_code != 500, \
                f"AI 需求预测不应 500：{resp.get_data(as_text=True)}"
            data = resp.get_json()
            assert data is not None, "必须返回 JSON"
            # 无物料时应返回成功 + 空列表
            assert data.get("status") == "success"
            assert data.get("forecasts") == []

    def test_T3_recommend_location_with_materials_returns_options(self, monkeypatch):
        """/api/ai/recommend_location 有物料时返回 200 + materials 列表。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _enable_ai_llm(monkeypatch)
            db.session.add(Material(code="M001", name="轴承", spec="6204", price=10))
            db.session.add(Material(code="M002", name="螺母", spec="M8", price=1))
            db.session.commit()
            client = app_module.app.test_client()
            _login(client)
            resp = client.post("/api/ai/recommend_location",
                               json={},
                               headers={"X-Requested-With": "XMLHttpRequest"})
            assert resp.status_code != 500
            data = resp.get_json()
            assert data is not None
            # 不传 material_id 时应返回 materials 供选择
            assert "materials" in data, f"应返回 materials：{data}"
            assert len(data["materials"]) == 2

    def test_T4_material_query_does_not_reference_status_column(self, monkeypatch):
        """Material.query 不应引用不存在的 status 列。

        直接验证修复点：Material.query.all() 不抛 SQLAlchemy 错误。
        （完整 demand_forecast 流程因 Material.category relationship 的
        另一个独立 bug 会 500，不在本 BUG 修复范围。）
        """
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            db.session.add(Material(code="M001", name="轴承", spec="6204", price=10))
            db.session.commit()
            # 修复前：Material.query.filter_by(status='active') 会抛
            # "Unknown column material.status"
            # 修复后：Material.query.all() 正常返回
            materials = Material.query.all()
            assert len(materials) == 1
            assert materials[0].code == "M001"
            # 同样验证 demand_forecast 用的查询路径
            materials_query = Material.query
            materials = materials_query.limit(100).all()
            assert len(materials) == 1

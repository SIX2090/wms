# -*- coding: utf-8 -*-
"""BUG-2026-09-10-002 回归：/api/material/search 模糊命中全量语义显式化。

用户实测 Android 查库存输「电线」报「物料不存在」且候选被截断。后端配套：
①模糊匹配（编码/名称/规格/品牌）命中的物料全部返回名称/规格/品牌完整字段；
②返回上限从魔法数 100 显式化为 MATERIAL_SEARCH_API_LIMIT，响应新增
total/truncated（R1：调用方不得把默认上限当全量）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    MATERIAL_SEARCH_API_LIMIT,
    Material,
    MaterialCategory,
    Unit,
    User,
    db,
    set_system_setting,
)


@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        set_system_setting("location_management_enabled", "0")
        db.session.add_all([
            User(username="admin", password_hash=generate_password_hash("admin"),
                 role="admin", must_change_password=False),
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT"),
        ])
        db.session.commit()
    test_client = app_module.app.test_client()
    response = test_client.post("/login", data={"username": "admin", "password": "admin"})
    assert response.status_code in (302, 303)
    return test_client


def _add_material(code, name, spec="", brand=""):
    db.session.add(Material(
        code=code, name=name, spec=spec, brand=brand,
        category_id=1, unit_id=1, stock=0,
    ))


def test_fuzzy_search_returns_all_fields_complete(client):
    """「电线」按名称/规格/品牌模糊命中的物料全部返回，且名称/规格/品牌字段齐全。"""
    with app_module.app.app_context():
        _add_material("DX001", "电线 BV2.5", spec="2.5mm²", brand="远东")
        _add_material("DX002", "电缆线", spec="4mm²", brand="电线牌")
        _add_material("OTHER", "五金件", spec="电线槽配件", brand="杂牌")
        _add_material("NONE", " unrelated ", spec="", brand="")
        db.session.commit()

    resp = client.get("/api/material/search?kw=电线")
    body = resp.get_json()
    assert body["status"] == "success"
    codes = {row["code"] for row in body["data"]}
    assert codes == {"DX001", "DX002", "OTHER"}  # 名称/品牌/规格三处命中全部返回
    assert body["total"] == 3
    assert body["truncated"] is False
    by_code = {row["code"]: row for row in body["data"]}
    # 名称/规格/品牌必须原样齐全返回（不截断）
    assert by_code["DX001"]["name"] == "电线 BV2.5"
    assert by_code["DX001"]["spec"] == "2.5mm²"
    assert by_code["DX001"]["brand"] == "远东"
    assert by_code["DX002"]["brand"] == "电线牌"
    assert by_code["OTHER"]["spec"] == "电线槽配件"


def test_search_total_and_truncated_explicit(client):
    """命中数超过上限时：data 截断到上限、total 为真实全量、truncated=True（R1）。"""
    over = MATERIAL_SEARCH_API_LIMIT + 5
    with app_module.app.app_context():
        for i in range(over):
            _add_material(f"DXB{i:04d}", f"电线批量{i}", spec="", brand="")
        db.session.commit()

    resp = client.get("/api/material/search?kw=电线")
    body = resp.get_json()
    assert len(body["data"]) == MATERIAL_SEARCH_API_LIMIT
    assert body["total"] == over
    assert body["truncated"] is True


def test_search_without_keyword_also_reports_total(client):
    with app_module.app.app_context():
        for i in range(3):
            _add_material(f"M{i:03d}", f"物料{i}", spec="", brand="")
        db.session.commit()

    body = client.get("/api/material/search").get_json()
    assert body["total"] == 3
    assert body["truncated"] is False
    assert len(body["data"]) == 3


def test_material_info_exact_miss_contract_unchanged(client):
    """精确查询未命中仍返回「物料不存在」——Android 端据此回退模糊列表。"""
    with app_module.app.app_context():
        _add_material("DX001", "电线 BV2.5", spec="2.5mm²", brand="远东")
        db.session.commit()

    miss = client.get("/api/material/info?code=电线").get_json()
    assert miss["status"] == "error"
    assert "物料不存在" in miss["msg"]

    hit = client.get("/api/material/info?code=DX001").get_json()
    assert hit["status"] == "success"
    assert hit["data"]["name"] == "电线 BV2.5"
    assert hit["data"]["spec"] == "2.5mm²"
    assert hit["data"]["brand"] == "远东"

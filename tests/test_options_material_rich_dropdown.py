# -*- coding: utf-8 -*-
"""物料搜索下拉富展示回归测试（AI-WMS-FILTER-005，2026-09-05 用户需求）。

需求：库存台账等页面「物料搜索」输入「螺丝」时，下拉框要展开显示所有
包含螺丝的物料的 编码 / 名称 / 规格 / 品牌（此前仅显示编码 + 一段
截断的规格文本，看不到名称，规格品牌挤在一起无法区分）。

修复内容：
1. 后端 /api/options/material 候选项独立下发 spec / brand 字段（sub 保留兼容）；
2. 前端 quick-select.js 物料候选两行富展示：上行「编码 + 名称」、
   下行灰字「规格 · 品牌」，四字段均按关键词高亮；
3. 附随修复（同函数域 R6 同类点）：_sql_like_pool 大数据路径 sub='' 导致
   按规格/品牌关键词命中的行在 _score 阶段被误杀（_t 不含 extras），
   >5000 物料时按规格/品牌搜索永远空结果。

测试用例：
  T1. 物料候选项独立下发 spec / brand 字段，且 sub 保留（向后兼容）
  T2. 按规格关键词（螺丝）与按品牌关键词均可命中物料
  T3. 大数据 SQL 路径（_SQL_THRESHOLD=0 强制）按规格关键词仍命中（附随修复）
  T4. 前端 quick-select.js 物料分支富渲染 + 样式存在（静态装配契约）
  T5. 非物料实体（supplier）不下发 spec/brand 字段（不影响其他实体）
"""
from __future__ import annotations

import os
import re
import sys
import uuid
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
from app import Material, Supplier, User, db  # noqa: E402

import pytest  # noqa: E402

import routes.options_api as options_api  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

QUICK_SELECT_JS = (APP_DIR / "static" / "js" / "quick-select.js").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _app_ctx():
    with app_module.app.app_context():
        yield


@pytest.fixture(autouse=True)
def _clean_pool():
    options_api._POOL_CACHE.clear()
    yield
    options_api._POOL_CACHE.clear()


def _uid():
    return uuid.uuid4().hex[:8]


def _make_client():
    db.drop_all()
    db.create_all()
    u = User(username="qa-" + _uid(), password_hash="x")
    db.session.add(u)
    db.session.add(Material(code="207004", name="自攻螺丝", spec="3*25", brand="固力"))
    db.session.add(Material(code="108003", name="暗装插座", spec="220V 16A 固定螺丝孔位距56", brand="正泰"))
    db.session.add(Material(code="300001", name="电缆", spec="BV2.5", brand="远东"))
    db.session.add(Supplier(code="S001", name="华南电气"))
    db.session.commit()
    client = app_module.app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(u.id)
        sess["user_id"] = str(u.id)
        sess["_fresh"] = True
    return client


def _get(client, entity, **params):
    return client.get("/api/options/%s" % entity, query_string=params)


def test_t1_material_item_exposes_spec_brand_fields():
    client = _make_client()
    j = _get(client, "material", kw="207004").get_json()
    assert j["status"] == "success" and j["total"] == 1
    item = j["data"][0]
    assert item["code"] == "207004"
    assert item["name"] == "自攻螺丝"
    assert item["spec"] == "3*25", "候选项必须独立下发 spec 字段"
    assert item["brand"] == "固力", "候选项必须独立下发 brand 字段"
    assert "3*25" in item["sub"] and "固力" in item["sub"], "sub 拼接文本须保留兼容"
    # 内部索引字段仍不得下发
    assert not [k for k in item if k.startswith("_")]


def test_t2_match_by_spec_and_brand_keywords():
    client = _make_client()
    by_spec = _get(client, "material", kw="螺丝").get_json()
    codes = {x["code"] for x in by_spec["data"]}
    assert codes == {"207004", "108003"}, (
        "按「螺丝」应命中名称含螺丝与规格含螺丝的两个物料，实际 %s" % codes
    )

    by_brand = _get(client, "material", kw="正泰").get_json()
    assert {x["code"] for x in by_brand["data"]} == {"108003"}, "按品牌关键词应命中"


def test_t3_sql_path_spec_keyword_not_dropped(monkeypatch):
    """大数据 SQL 路径：按规格关键词命中的行不得在 _score 阶段被误杀。"""
    client = _make_client()
    # 强制走 _sql_like_pool（total > _SQL_THRESHOLD 且 kw 非空）
    monkeypatch.setattr(options_api, "_SQL_THRESHOLD", 0)
    options_api._POOL_CACHE.clear()
    j = _get(client, "material", kw="螺丝").get_json()
    codes = {x["code"] for x in j["data"]}
    assert "108003" in codes, (
        "SQL 路径按规格关键词「螺丝」应命中 108003（此前 sub='' 被 _score 误杀）"
    )
    item = next(x for x in j["data"] if x["code"] == "108003")
    assert item["spec"] and item["brand"], "SQL 路径同样须独立下发 spec/brand"


def test_t4_quick_select_material_rich_render_contract():
    """前端装配契约：物料富渲染分支、四字段、样式齐备。"""
    js = QUICK_SELECT_JS
    assert "entity === 'material'" in js, "renderMenu 缺少物料实体分支"
    assert "function renderMaterialItem(" in js, "缺少 renderMaterialItem 富渲染函数"
    for field in ("it.spec", "it.brand", "it.name", "it.code"):
        assert field in js, "富渲染未读取字段 %s" % field
    assert "规格 " in js and "品牌 " in js, "下行须标注 规格/品牌"
    assert "ks-item-rich" in js and "ks-rich-sub" in js and "ks-rich-name" in js, (
        "富展示样式类缺失"
    )
    # 名称/规格/品牌均走 highlight 高亮（编码在 ks-main 已高亮）
    assert re.search(r"highlight\(name, kw\)", js), "名称未参与关键词高亮"
    assert re.search(r"highlight\(spec, kw\)", js), "规格未参与关键词高亮"
    assert re.search(r"highlight\(brand, kw\)", js), "品牌未参与关键词高亮"


def test_t5_other_entities_not_affected():
    """非物料实体不附带 spec/brand 字段，渲染走原通用路径。"""
    client = _make_client()
    j = _get(client, "supplier", kw="S001").get_json()
    assert j["total"] == 1
    item = j["data"][0]
    assert "spec" not in item and "brand" not in item, (
        "非物料实体不应下发 spec/brand 字段"
    )

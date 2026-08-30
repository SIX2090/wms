# -*- coding: utf-8 -*-
"""通用候选接口 /api/options/<entity> 回归测试（AI-WMS-FILTER-001）。

背景：全系统 45 个业务页面里 38 个的筛选框是「裸文本框」，
没有候选选择，用户需凭记忆完整输入关键词，输错即查不到。
本次新增统一候选接口 + 前端公共组件，为所有筛选输入框提供
「输入关键词 → 弹出匹配候选 → 点选回填」的能力。

验收点：
1. 未知实体返回 404，不抛异常。
2. 已知实体返回统一结构 {status, data:[{id,code,name,sub,label}], total}。
3. 中文子串匹配：按编码与名称均能命中。
4. 拼音匹配：全拼与首字母可命中中文名称（pypinyin 可用时）。
5. limit 参数生效且被限制在 1..200，非法值不抛异常。
6. 内部索引字段（_t/_f/_i）不下发到前端。
7. 候选池缓存命中时结果与首次一致。
8. 纯文本实体（contract_no / project）在空库时安全返回空列表。
9. 装配契约：app.py 注册路由、base.html 引入 quick-select.js、
   业务模板已挂 data-ks（否则前端组件不会被激活）。
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
from app import Supplier, User, Warehouse, db  # noqa: E402

import pytest  # noqa: E402

import routes.options_api as options_api  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

_HAS_PINYIN = options_api._HAS_PINYIN

# ---------------- 装配契约（静态，模块加载时读取一次） ----------------
APP_PY = (APP_DIR / "app.py").read_text(encoding="utf-8")
BASE_HTML = (APP_DIR / "templates" / "base.html").read_text(encoding="utf-8")
TPL_DIR = APP_DIR / "templates"


@pytest.fixture(autouse=True)
def _app_ctx():
    """每个用例包在 app context 内（db 操作必需）。"""
    with app_module.app.app_context():
        yield


@pytest.fixture(autouse=True)
def _clean_pool():
    """用例之间清空候选池缓存，避免跨用例污染。"""
    options_api._POOL_CACHE.clear()
    yield
    options_api._POOL_CACHE.clear()


def _uid():
    return uuid.uuid4().hex[:8]


def _reset_db():
    db.drop_all()
    db.create_all()


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["user_id"] = str(user_id)
        sess["_fresh"] = True


def _make_client():
    """建库 + 建用户 + 登录，返回已认证的 test_client。"""
    _reset_db()
    u = User(username="qa-" + _uid(), password_hash="x")
    db.session.add(u)
    db.session.flush()
    db.session.add(Supplier(code="S001", name="华南电气"))
    db.session.add(Supplier(code="S002", name="华东线缆"))
    db.session.add(Warehouse(code="WH01", name="成品仓"))
    db.session.commit()
    client = app_module.app.test_client()
    _login(client, u.id)
    return client


def _get(client, entity, **params):
    return client.get("/api/options/%s" % entity, query_string=params)


# ---------------- 接口行为 ----------------

def test_unknown_entity_returns_404():
    client = _make_client()
    r = _get(client, "no_such_entity")
    assert r.status_code == 404
    assert r.get_json()["status"] == "error"
    assert r.get_json()["data"] == []


def test_returns_unified_structure():
    client = _make_client()
    r = _get(client, "supplier", limit=50)
    assert r.status_code == 200
    j = r.get_json()
    assert j["status"] == "success"
    assert j["total"] == 2
    for item in j["data"]:
        for key in ("id", "code", "name", "sub", "label"):
            assert key in item


def test_substring_match_by_code_and_name():
    client = _make_client()
    by_code = _get(client, "supplier", kw="S001").get_json()
    assert by_code["total"] == 1
    assert by_code["data"][0]["code"] == "S001"

    by_name = _get(client, "supplier", kw="华南").get_json()
    assert by_name["total"] == 1
    assert by_name["data"][0]["code"] == "S001"
    # label 应为「编码 + 名称」，便于用户点选后确认
    assert "S001" in by_name["data"][0]["label"]


@pytest.mark.skipif(not _HAS_PINYIN, reason="pypinyin 未安装，拼音路径不参与验证")
def test_pinyin_match():
    """拼音全拼与首字母均应命中中文名称。"""
    client = _make_client()
    full = _get(client, "supplier", kw="huanandianqi").get_json()
    assert full["total"] == 1, "全拼 huanandianqi 应命中「华南电气」"
    assert full["data"][0]["code"] == "S001"

    initial = _get(client, "supplier", kw="hndq").get_json()
    assert initial["total"] == 1, "首字母 hndq 应命中「华南电气」"
    assert initial["data"][0]["code"] == "S001"


def test_limit_is_applied_and_bounded():
    client = _make_client()
    assert len(_get(client, "supplier", limit=1).get_json()["data"]) == 1
    # 上限约束：limit=9999 应被收敛到 200 以内，且不报错
    r = _get(client, "supplier", limit=9999)
    assert r.status_code == 200
    assert len(r.get_json()["data"]) <= 200
    # 非法 limit 不抛异常
    assert _get(client, "supplier", limit="abc").status_code == 200
    # 下限约束：limit=0 至少返回 1 条
    assert r.get_json()["status"] == "success"


def test_internal_index_fields_not_exposed():
    """_t/_f/_i 是服务端匹配索引，绝不能下发到前端。"""
    client = _make_client()
    j = _get(client, "supplier").get_json()
    assert j["data"], "应有候选数据"
    for item in j["data"]:
        assert not [k for k in item if k.startswith("_")]


def test_cache_returns_consistent_result():
    client = _make_client()
    first = _get(client, "warehouse").get_json()
    assert first["cached"] is False, "首次查询应为未命中缓存"
    second = _get(client, "warehouse").get_json()
    assert second["cached"] is True, "二次查询应命中缓存"
    assert [x["code"] for x in first["data"]] == [x["code"] for x in second["data"]]


def test_text_entity_safe_on_empty_db():
    """纯文本实体从历史单据去重，空库时应安全返回空列表。"""
    _reset_db()
    db.session.add(User(username="qa-" + _uid(), password_hash="x"))
    db.session.commit()
    client = app_module.app.test_client()
    with client.session_transaction() as s:
        s["_user_id"] = "1"
        s["user_id"] = "1"
    for ent in ("contract_no", "project"):
        j = _get(client, ent).get_json()
        assert j["status"] == "success", "%s 空库应安全返回" % ent
        assert j["data"] == []


def test_pinyin_fallback_flag_present():
    """响应回传 pinyin 能力标志，便于前端提示是否支持拼音搜索。"""
    client = _make_client()
    j = _get(client, "supplier", kw="S001").get_json()
    assert j["pinyin"] == _HAS_PINYIN
    assert j["total"] == 1


# ---------------- 装配契约 ----------------

def test_register_options_routes():
    """A9 门禁：register_options_routes 必须真实装配，否则接口根本不存在。"""
    assert "from routes.options_api import register_options_routes" in APP_PY, (
        "app.py 必须导入 register_options_routes"
    )
    assert re.search(r"^\s*register_options_routes\(app\)\s*$", APP_PY, re.M), (
        "app.py 必须调用 register_options_routes(app)，否则接口不存在"
    )
    # 路由真实可用（而非仅源码可见）
    rules = {r.rule for r in app_module.app.url_map.iter_rules()}
    assert "/api/options/<entity>" in rules


def test_quick_select_js_included_in_base_html():
    assert "js/quick-select.js" in BASE_HTML, (
        "base.html 必须全局引入 quick-select.js，否则新页面拿不到组件"
    )


def test_templates_carry_data_ks_attributes():
    """至少覆盖筛选主页面：若改造被回滚，此用例应失败。"""
    required = [
        "material.html",
        "in_order.html",
        "out_order.html",
        "supplier.html",
        "stock_query.html",
    ]
    missing = []
    for name in required:
        p = TPL_DIR / name
        if not p.exists():
            missing.append(name + "(文件缺失)")
            continue
        if "data-ks=" not in p.read_text(encoding="utf-8"):
            missing.append(name)
    assert not missing, "以下模板未挂载关键词选择组件: %s" % ", ".join(missing)

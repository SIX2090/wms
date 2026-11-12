# -*- coding: utf-8 -*-
"""BUG-2026-11-12-001 回归测试：新建/编辑/停用/删除物料后，筛选下拉立即可见。

原 Bug（用户报障实录，2026-11-12）：
  新建物料档案「211008 号码管 10平方」，到物料搜索输入「10平方」，
  下拉不会立马显示该物料——最长要等 5 分钟才出现。

根因（三层缓存里唯一的服务端病灶）：
  前端 quick-select.js 的候选池随页面加载重建（物料新增/编辑/删除/停启用
  在前端全部以整页 reload 收尾，客户端缓存天然重置，证据：
  material-add.js:22 location.href='/material'、material-list.js:284/327/961
  location.reload()），真正拖后腿的是 options_api._POOL_CACHE——
  候选池 300 秒 TTL 内不回源、不校验主数据是否已变，新建物料最长
  300 秒进不了 /api/options/material 的返回。

修复（见 routes/options_api.py）：
  1. 缓存命中时做「表指纹」探测（行数 + 最大 id + 可入池行数，亚毫秒级），
     签名变化立即重建——自动覆盖一切改变行数的写入（新增/删除/停启用/
     导入/合并/批量导入），不逐写入点手工失效，天然免疫 R6 漂移；
  2. 不改行数的字段编辑（改名称/规格/品牌）探测感知不到，由
     routes/material.py 物料编辑路由显式调用 invalidate_options_pool() 补位；
  3. _py_keys 拼音记忆化，重建只回源数据库，下拉体感不变；
  4. 探测异常按「未变化」处理（fail-open），绝不把下拉打成 500。

为什么这些用例能捕获该缺陷（R8 判据）：
  每个「写入后立即查询」的用例都先预热候选池（等同用户刚用过下拉），
  修复前该查询命中 300 秒内的旧缓存 → 断言必红；把修复回退后
  T1-T4 分别按「新建不可见 / 停用仍显示 / 删除仍显示 / 新规格搜不到」
  复现原报障。
"""
from __future__ import annotations

import os
import re
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
from app import db, Material, User  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

import pytest  # noqa: E402

import routes.options_api as options_api  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


@pytest.fixture(autouse=True)
def _app_ctx():
    """每个用例包在 app context 内（db 操作必需）。"""
    with app_module.app.app_context():
        yield


@pytest.fixture(autouse=True)
def _clean_pool():
    """用例之间清空候选池缓存，避免跨用例污染（沿 test_options_api.py 惯例）。"""
    options_api._POOL_CACHE.clear()
    yield
    options_api._POOL_CACHE.clear()


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_and_login():
    """建库 + 建管理员 + 真实登录流程（编辑路由要求 warehouse 角色，admin 全通过）。"""
    _reset_db()
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    db.session.add(user)
    db.session.commit()
    client = app_module.app.test_client()
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post("/login", data={
        "username": "admin", "password": "admin", "csrf_token": token})
    return client


def _get_materials(client, kw=""):
    resp = client.get("/api/options/material",
                      query_string={"kw": kw, "limit": 200})
    assert resp.status_code == 200, "候选接口异常状态码: %s" % resp.status_code
    return resp.get_json()["data"]


def _codes(items):
    return [it["code"] for it in items]


def _warm_pool(client):
    """预热候选池：等同用户刚用过一次下拉（此后命中 300 秒 TTL 缓存）。"""
    _get_materials(client, kw="")


# ---------------- T1：报障主场景 —— 新建物料立即出现在候选 ----------------

def test_t1_new_material_searchable_immediately():
    """新建物料后（不经过任何失效调用），下拉立即能搜到。

    直连 ORM 写入 + commit 是刻意为之：签名探测的关键就是「不依赖写入方
    调失效」——生产里新增物料的入口再多（PC 新增/物料导入/批量导入/手机端），
    签名也兜得住。修复前该查询命中预热过的旧候选池 → 211008 不在返回里。
    """
    client = _seed_and_login()
    db.session.add(Material(code="201074", name="电线", spec="ZC-BV 10平方 红色"))
    db.session.commit()
    _warm_pool(client)  # 预热：此后 /api/options/material 走 300 秒 TTL 缓存

    db.session.add(Material(code="211008", name="号码管", spec="10平方"))
    db.session.commit()

    data = _get_materials(client, kw="10平方")
    assert "211008" in _codes(data), (
        "新建物料在候选池 TTL 内搜不到 → BUG-2026-11-12-001 未修复"
        "（新建物料必须立即出现在下拉，而不是等 300 秒）"
    )


# ---------------- T2：停用物料立即从候选消失 ----------------

def test_t2_disabled_material_leaves_candidates_immediately():
    """停用物料后，下拉立即不再提供它。

    总行数与最大 id 都不变，签名靠「可入池行数」（active 过滤）这一维感知
    停用/启用。修复前预热缓存仍含该物料 → 停用后 300 秒内还能选到已停用物料。
    """
    client = _seed_and_login()
    mat = Material(code="300001", name="试验品", spec="A1")
    db.session.add(mat)
    db.session.commit()
    _warm_pool(client)

    mat.status = "inactive"
    db.session.commit()

    assert "300001" not in _codes(_get_materials(client, kw="")), (
        "停用物料仍出现在候选池 TTL 内 → 签名的可入池行数维度未生效"
    )


# ---------------- T3：删除物料立即从候选消失 ----------------

def test_t3_deleted_material_leaves_candidates_immediately():
    """删除物料后，下拉立即不再显示它（行数维度）。"""
    client = _seed_and_login()
    keep = Material(code="400001", name="保留品", spec="B1")
    drop = Material(code="400002", name="淘汰品", spec="B2")
    db.session.add_all([keep, drop])
    db.session.commit()
    _warm_pool(client)

    db.session.delete(drop)
    db.session.commit()

    codes = _codes(_get_materials(client, kw=""))
    assert "400002" not in codes, "删除物料仍出现在候选池 TTL 内 → 表指纹探测未生效"
    assert "400001" in codes, "重建候选池把未删除的物料弄丢了"


# ---------------- T4：编辑物料 —— 新规格立即可搜（显式失效补位） ----------------

def test_t4_edited_spec_searchable_immediately():
    """编辑物料改规格后，下拉立即按新规格命中。

    字段编辑不改变行数/最大 id/可入池行数，签名探测感知不到，靠编辑路由
    里的 invalidate_options_pool('material') 补位。走真实 POST /material/edit
    路由验证接线（只测失效函数本身测不出「路由忘了调」）。
    修复前：旧池仍带旧规格 → 「20平方」永远搜不到，最长 300 秒。
    """
    client = _seed_and_login()
    mat = Material(code="500001", name="可编辑品", spec="10平方")
    db.session.add(mat)
    db.session.commit()
    mat_id = mat.id
    _warm_pool(client)

    resp = client.post(f"/material/edit/{mat_id}", data={
        "code": "500001", "name": "可编辑品", "spec": "20平方", "brand": "",
    })
    assert resp.status_code == 200, "编辑请求本身失败: %s" % resp.status_code
    assert resp.get_json()["status"] == "success", (
        "编辑失败: %s" % resp.get_json().get("msg")
    )

    assert "500001" in _codes(_get_materials(client, kw="20平方")), (
        "编辑后的新规格在候选池 TTL 内搜不到 → 编辑路由的显式失效未接线"
    )
    assert "500001" not in _codes(_get_materials(client, kw="10平方")), (
        "旧规格仍在候选 → 候选池没有按编辑后的数据重建"
    )


# ---------------- T5：探测异常 fail-open，绝不让下拉 500 ----------------

def test_t5_probe_failure_keeps_cached_pool(monkeypatch):
    """表指纹探测抛异常/返回 None 时，沿用旧缓存、不重建、不 500。

    探测是新鲜度优化，不是鉴权/正确性闸门：数据库瞬时异常时回退旧缓存
    （最多旧 300 秒），不能把用户的下拉打成空/错误。判别点不是「还能查到」
    （重建也能查到），而是「缓存条目对象原样保留、没有触发重建」。
    """
    client = _seed_and_login()
    db.session.add(Material(code="600001", name="探测品", spec="C1"))
    db.session.commit()
    _warm_pool(client)
    assert "material" in options_api._POOL_CACHE, "预热未生成缓存条目"
    entry_before = options_api._POOL_CACHE["material"]

    monkeypatch.setattr(options_api, "_entity_pool_signature",
                       lambda key: None)  # 模拟探测失败
    data = _get_materials(client, kw="C1")
    assert "600001" in _codes(data), "探测失败时下拉查询被破坏（fail-open 未生效）"
    assert options_api._POOL_CACHE.get("material") is entry_before, (
        "探测失败不应触发重建/清缓存——fail-open 语义被破坏，"
        "数据库瞬时异常会把每次下拉都拖成全量重建"
    )


# ---------------- T6：显式失效函数行为 ----------------

def test_invalidate_options_pool():
    """T6 invalidate_options_pool：指定实体只清该实体，None 清空全部。

    函数名与被测函数精确同名（A9 规则要求 test_invalidate_options_pool）。
    """
    client = _seed_and_login()
    db.session.add(Material(code="700001", name="失效品", spec="D1"))
    db.session.commit()
    _warm_pool(client)
    # 用户实体池独立预热（employee/warehouse 等同 ENTITY_CONFIG，此处用
    # material + supplier 两池验证作用域）
    client.get("/api/options/supplier", query_string={"kw": "", "limit": 50})

    options_api.invalidate_options_pool("material")
    assert "material" not in options_api._POOL_CACHE, "指定实体未被清除"
    assert "supplier" in options_api._POOL_CACHE, "不应连带清空其他实体"

    options_api.invalidate_options_pool()
    assert not options_api._POOL_CACHE, "None 未清空全部实体"

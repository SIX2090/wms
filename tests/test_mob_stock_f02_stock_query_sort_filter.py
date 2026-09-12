# -*- coding: utf-8 -*-
"""AI-MOB-STOCK-F02 回归：查库存列表按仓库级库存排序与筛选（清单 P1-1 / P1-2）。

背景：作业员在手机查库存只能按编码顺序翻，找"哪些快没货了""哪些是零库存"
只能人肉扫。本接口补 sort / stock_filter 两个参数。

关键风险（本测试重点拦截）：
1. **假排序**——若实现先 SQL 分页再排序，只排当前 20 条，用户看到的顺序
   依然是错的。T3 用「排序后跨页取全」验证顺序对全集成立，而非仅本页。
2. **口径分叉**——仓库级库存来自 LocationInventory/StockTransaction 聚合，
   若排序另写一套 SQL 聚合，会与响应里的 stock 值不一致（R6 / BUG-2026-09-12-005
   同根因）。T4 验证排序用的量与响应 stock 完全同源。
3. **默认行为回归**——不带参数时必须与改动前完全一致（走原 SQL 分页路径）。T1。

覆盖：
T1. 不带 sort/stock_filter：行为不变（编码升序、total 为全量）
T2. 参数非法 → 400，不静默忽略
T3. stock_asc / stock_desc：跨页全序正确，且分页不重不漏
T4. 排序所用的量 == 响应下发的 stock（同源，无分叉）
T5. stock_filter：nonzero / zero / low 的筛选语义与告警页口径一致
T6. 多仓隔离：B 仓的库存不串入 A 仓排序（R2-1）
T7. 次排序键：库存相同的物料按 code 稳定排序，翻页不抖动
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
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

_ctx = app_module.app.app_context()


import pytest as _pytest  # noqa: E402


@_pytest.fixture(autouse=True, scope="module")
def _release_app_ctx_after_module():
    _ctx.push()
    yield
    try:
        _ctx.pop()
    except Exception:
        pass


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    return app_module.app.test_client()


def _seed_user(username="sq", password="pw"):
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username=username,
             password_hash=generate_password_hash(password),
             role="warehouse", must_change_password=False)
    db.session.add(u)
    db.session.commit()
    return u


def _bearer(client, username="sq", password="pw"):
    r = client.post("/api/login", json={"username": username,
                                        "password": password})
    assert r.status_code == 200, r.get_data(as_text=True)
    return {"Authorization": f"Bearer {r.get_json()['data']['token']}"}


def _seed_warehouse(code, name, is_default=False):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active", is_default=is_default)
    db.session.add(w)
    db.session.commit()
    return w


def _seed_material(code, min_stock=0.0, name=None):
    from app import Material
    m = Material(code=code, name=name or f"物料{code}", stock=0.0,
                 min_stock=min_stock)
    db.session.add(m)
    db.session.commit()
    return m


def _seed_stock(material, warehouse, qty):
    """按仓库写入流水（StockTransaction.location = 仓库名）。"""
    from app import StockTransaction
    db.session.add(StockTransaction(
        material_id=material.id,
        transaction_type="in",
        quantity=qty,
        location=warehouse.name,
        warehouse_id=warehouse.id,
        created_at=datetime.now(),
    ))
    db.session.commit()


def _seed_scene():
    """A仓（默认）+ B仓，A 仓下 5 个物料，库存故意打乱编码顺序。"""
    _reset_db()
    _seed_user()
    wh_a = _seed_warehouse("SQA", "A仓", is_default=True)
    wh_b = _seed_warehouse("SQB", "B仓")
    # 编码升序 M1..M5，库存刻意乱序：50 / 0 / 30 / 0 / 10
    specs = [("M1", 50.0, 0.0), ("M2", 0.0, 0.0), ("M3", 30.0, 40.0),
             ("M4", 0.0, 0.0), ("M5", 10.0, 5.0)]
    materials = {}
    for code, qty_a, _qty_b in specs:
        m = _seed_material(code)
        if qty_a:
            _seed_stock(m, wh_a, qty_a)
        materials[code] = m
    # M3 设最低库存，用于 low 筛选；其在 A 仓 30 > 20，不应入选
    materials["M3"].min_stock = 20.0
    # M5 设最低库存，A 仓 10 <= 15，应入选 low
    materials["M5"].min_stock = 15.0
    db.session.commit()
    return wh_a, wh_b, materials


def _query(client, headers, qs=""):
    url = "/api/mobile/stock/query" + (("?" + qs) if qs else "")
    return client.get(url, headers=headers)


def test_t1_default_path_unchanged():
    """T1: 不带 sort/stock_filter 时行为与改动前一致（编码升序 + 全量 total）。"""
    _seed_scene()
    client = _make_client()
    h = _bearer(client)

    r = _query(client, h)
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()["data"]
    assert [it["code"] for it in data["items"]] == ["M1", "M2", "M3", "M4", "M5"]
    assert data["total"] == 5
    for key in ("items", "total", "page", "page_size", "total_pages"):
        assert key in data, f"R1 缺字段 {key}"


def test_t2_invalid_params_rejected():
    """T2: 非法 sort / stock_filter → 400（不静默忽略成"没排序"）。"""
    _seed_scene()
    client = _make_client()
    h = _bearer(client)

    r1 = _query(client, h, "sort=by_magic")
    assert r1.status_code == 400, f"非法 sort 应 400，实际 {r1.status_code}"
    r2 = _query(client, h, "stock_filter=whatever")
    assert r2.status_code == 400, f"非法 stock_filter 应 400，实际 {r2.status_code}"


def test_t3_sort_is_global_not_per_page():
    """T3: 排序必须对全集成立（拦截"先分页后排序"的假排序）。"""
    _seed_scene()
    client = _make_client()
    h = _bearer(client)

    # 每页 2 条，逐页取完；库存 0/0/10/30/50
    r = _query(client, h, "sort=stock_asc&page_size=2")
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()["data"]
    assert d["total"] == 5 and d["total_pages"] == 3

    seen_qty, seen_code = [], []
    for p in (1, 2, 3):
        dp = _query(client, h, f"sort=stock_asc&page_size=2&page={p}").get_json()["data"]
        seen_qty += [it["stock"] for it in dp["items"]]
        seen_code += [it["code"] for it in dp["items"]]
    assert seen_qty == [0.0, 0.0, 10.0, 30.0, 50.0], (
        f"升序应对全集成立，实际：{seen_qty}")
    assert sorted(seen_code) == ["M1", "M2", "M3", "M4", "M5"], "分页应不重不漏"

    r2 = _query(client, h, "sort=stock_desc&page_size=10")
    qty_desc = [it["stock"] for it in r2.get_json()["data"]["items"]]
    assert qty_desc == [50.0, 30.0, 10.0, 0.0, 0.0], f"降序错误：{qty_desc}"


def test_t4_sort_uses_same_quantity_as_response():
    """T4: 排序所用的量与响应里的 stock 同源（拦截口径分叉，R6）。"""
    _seed_scene()
    client = _make_client()
    h = _bearer(client)
    for sort in ("stock_asc", "stock_desc"):
        items = _query(client, h, f"sort={sort}&page_size=50").get_json()["data"]["items"]
        stock_seq = [it["stock"] for it in items]
        # 若排序另走一套聚合，序列对 stock 值就不会单调
        assert stock_seq == sorted(stock_seq, reverse=(sort == "stock_desc")), (
            f"{sort} 与响应 stock 不同源：{stock_seq}")


def test_t5_stock_filter_semantics():
    """T5: nonzero / zero / low 筛选语义（low 与告警页同为 <= min_stock）。"""
    _seed_scene()
    client = _make_client()
    h = _bearer(client)

    r = _query(client, h, "stock_filter=nonzero&page_size=50")
    codes = sorted(it["code"] for it in r.get_json()["data"]["items"])
    assert codes == ["M1", "M3", "M5"], codes

    r2 = _query(client, h, "stock_filter=zero&page_size=50")
    codes2 = sorted(it["code"] for it in r2.get_json()["data"]["items"])
    assert codes2 == ["M2", "M4"], codes2

    # low：min_stock>0 且 库存 <= min_stock。M5(10<=15) 入选，M3(30>20) 不入选，
    # M1/M2/M4 未设 min_stock 视为不启用告警，不入选
    r3 = _query(client, h, "stock_filter=low&page_size=50")
    codes3 = sorted(it["code"] for it in r3.get_json()["data"]["items"])
    assert codes3 == ["M5"], codes3

    # 筛选后 total 必须随之变化（R1：汇总与分页解耦）
    assert r3.get_json()["data"]["total"] == 1
    assert r.get_json()["data"]["total"] == 3


def test_t6_warehouse_isolation():
    """T6: B 仓库存不串入 A 仓排序（R2-1）。"""
    _seed_scene()
    client = _make_client()
    h = _bearer(client)

    # B 仓下所有物料均无库存（_seed_scene 只给 A 仓写了流水）
    r = _query(client, h, "warehouse_code=SQB&sort=stock_desc&page_size=50")
    assert r.status_code == 200, r.get_data(as_text=True)
    items = r.get_json()["data"]["items"]
    assert items, "B 仓应仍能列出物料（只是库存为 0）"
    assert all(it["stock"] == 0.0 for it in items), (
        f"B 仓不应出现 A 仓的库存：{[it['stock'] for it in items]}")

    r2 = _query(client, h, "warehouse_code=SQB&stock_filter=nonzero&page_size=50")
    assert r2.get_json()["data"]["total"] == 0, "B 仓无库存，nonzero 应为 0 条"


def test_t7_stable_tie_break():
    """T7: 库存相同的物料按 code 稳定排序，翻页不抖动。"""
    _seed_scene()
    client = _make_client()
    h = _bearer(client)

    # M2 / M4 库存同为 0：升序下必须固定为 M2 在 M4 前
    for _ in range(3):
        items = _query(client, h, "sort=stock_asc&page_size=50").get_json()["data"]["items"]
        zero_codes = [it["code"] for it in items if it["stock"] == 0.0]
        assert zero_codes == ["M2", "M4"], f"同库存顺序不稳定：{zero_codes}"

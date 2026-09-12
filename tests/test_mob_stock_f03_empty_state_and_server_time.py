# -*- coding: utf-8 -*-
"""AI-MOB-STOCK-F03 回归：空态可区分 + 数据截止时间（清单 P1-3 / P2-3）。

背景：查库存搜不到东西时，手机端只有一句「未找到包含「xx」的物料」。但这个
接口是**仓库级**语义，搜不到其实是两件完全不同的事：

1. 物料档案里根本没登记这个编码 → 该去建档；
2. 档案里有，但这个仓库没货 / 被当前筛选（如"仅有货"）排除 → 该换仓或改筛选。

原来两种情形给同一句话，作业员看到"未找到"就跑去建档，实际可能只是选错了
仓库。加上 AI-MOB-STOCK-F02 的 stock_filter 后，情形 2 是真实可达的：
keyword 命中 + stock_filter=nonzero + 本仓库存 0 → total=0 但档案里有。

修复：响应新增 keyword_material_total（物料档案命中数，不看仓库、不看库存），
手机端据此分流文案；新增 server_time（hh:mm）用于显示"数据截止"。

关键风险（本测试重点拦截）：
1. **口径分叉**——keyword_material_total 若顺手带上了仓库/库存条件，就在
   total=0 时与 total 一起变 0，等于没区分。T3/T4/T5 专门守这一点。
2. **关键词条件两处各写一遍**——主查询与命中数各写一份 LIKE 迟早漂移。实现
   里抽成 base_query 共用，T2/T3 用同一关键词交叉验证两者自洽。
3. **无关键词时的语义**——此时 total 已表达全部，不应多查一次 COUNT，字段
   为 null（T1），避免手机端把 null 当 0 显示成"没这个物料"。

覆盖：
T1. 无关键词：keyword_material_total=None，server_time 格式正确
T2. 关键词无命中：total=0 且命中数=0 → "档案里没有"
T3. 关键词命中但被筛选排除：total=0 但命中数>0 → "该仓无货"（P1-3 核心）
T4. 命中数与仓库无关：A/B 仓返回同一个值
T5. 命中数与库存无关：B 仓全 0 库存，命中数仍等于档案命中数
T6. server_time 严格 hh:mm
T7. 只读：查询不改变任何数据
"""
from __future__ import annotations

import os
import re
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
    """A仓（默认）有货，B仓全无货；物料 M1..M5 档案均存在。"""
    _reset_db()
    _seed_user()
    wh_a = _seed_warehouse("SQA", "A仓", is_default=True)
    wh_b = _seed_warehouse("SQB", "B仓")
    materials = {}
    for code in ("M1", "M2", "M3", "M4", "M5"):
        m = _seed_material(code)
        _seed_stock(m, wh_a, 10.0)   # 只给 A 仓写流水
        materials[code] = m
    return wh_a, wh_b, materials


def _query(client, headers, qs=""):
    url = "/api/mobile/stock/query" + (("?" + qs) if qs else "")
    return client.get(url, headers=headers)


def _data(resp):
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()["data"]


def test_t1_no_keyword_returns_null_hit_count():
    """T1: 无关键词时命中数为 null（total 已表达全部语义，不多查 COUNT）。"""
    _seed_scene()
    client = _make_client()
    h = _bearer(client)

    d = _data(_query(client, h))
    assert "keyword_material_total" in d, "响应缺少 keyword_material_total"
    assert d["keyword_material_total"] is None, (
        f"无关键词时应为 null，实际 {d['keyword_material_total']}")
    assert d["total"] == 5
    assert re.match(r"^\d{2}:\d{2}$", d["server_time"]), (
        f"server_time 应为 hh:mm，实际 {d['server_time']!r}")


def test_t2_keyword_miss_means_no_such_material():
    """T2: 档案里没有 → total=0 且命中数=0，手机端应提示去建档。"""
    _seed_scene()
    client = _make_client()
    h = _bearer(client)

    d = _data(_query(client, h, "keyword=ZZZ-NOPE"))
    assert d["total"] == 0
    assert d["keyword_material_total"] == 0, (
        f"档案无此物料时命中数应为 0，实际 {d['keyword_material_total']}")


def test_t3_filtered_out_is_not_no_such_material():
    """T3（P1-3 核心）: 档案有但被筛选排除 → total=0 而命中数>0。

    这正是原实现无法区分的那一类：B 仓 M1..M5 档案都在，但库存全为 0，
    勾了"仅有货"以后 total=0。若命中数也跟着变 0，手机端仍会说"没这个物料"，
    作业员就会跑去建档——而正确动作是换个仓库。
    """
    _seed_scene()
    client = _make_client()
    h = _bearer(client)

    d = _data(_query(client, h,
                     "warehouse_code=SQB&keyword=M&stock_filter=nonzero"))
    assert d["total"] == 0, "B 仓无库存，勾了仅有货应为 0 条"
    assert d["keyword_material_total"] == 5, (
        f"档案里明明有 5 个 M* 物料，命中数却为 {d['keyword_material_total']}")


def test_t4_hit_count_is_warehouse_independent():
    """T4: 命中数只看档案，A/B 仓必须返回同一个值（否则又是一条口径分叉）。"""
    _seed_scene()
    client = _make_client()
    h = _bearer(client)

    a = _data(_query(client, h, "warehouse_code=SQA&keyword=M"))
    b = _data(_query(client, h, "warehouse_code=SQB&keyword=M"))
    assert a["keyword_material_total"] == b["keyword_material_total"] == 5
    # 两边 total 也应一致（物料不按仓库分，都没被筛选）
    assert a["total"] == b["total"] == 5


def test_t5_hit_count_is_stock_independent():
    """T5: 命中数与库存无关——B 仓库存全 0，命中数仍等于档案命中数。"""
    _seed_scene()
    client = _make_client()
    h = _bearer(client)

    d = _data(_query(client, h, "warehouse_code=SQB&keyword=M1"))
    items = d["items"]
    assert items and all(it["stock"] == 0.0 for it in items), (
        "B 仓应列出物料但库存为 0")
    assert d["keyword_material_total"] == 1, (
        f"命中数不应受库存影响，实际 {d['keyword_material_total']}")


def test_t6_server_time_format():
    """T6: server_time 严格 hh:mm，可直接拼进"数据截止 hh:mm"文案。"""
    _seed_scene()
    client = _make_client()
    h = _bearer(client)

    for qs in ("", "keyword=M1", "warehouse_code=SQB&stock_filter=nonzero"):
        d = _data(_query(client, h, qs))
        st = d["server_time"]
        assert isinstance(st, str) and re.match(r"^\d{2}:\d{2}$", st), (
            f"{qs!r} 下 server_time 非法：{st!r}")
        hh, mm = st.split(":")
        assert 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59


def test_t7_read_only():
    """T7: 查询是只读的，不改变物料与流水。"""
    _seed_scene()
    client = _make_client()
    h = _bearer(client)

    from app import Material, StockTransaction
    before_m = Material.query.count()
    before_t = StockTransaction.query.count()

    _data(_query(client, h, "keyword=M&stock_filter=nonzero"))
    _data(_query(client, h, "warehouse_code=SQB&keyword=ZZZ"))

    assert Material.query.count() == before_m, "查询不应改动物料"
    assert StockTransaction.query.count() == before_t, "查询不应改动流水"

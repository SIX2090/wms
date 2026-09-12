# -*- coding: utf-8 -*-
"""AI-MOB-CHECK-F01 回归：Android 盘点记录回查（GET /api/mobile/stocktake/list）。

背景（用户视角的真实缺口）：手机盘点提交后记录"失联"——native_api_stocktake
返回的 check_no 之外，作业员本人无从回看自己盘过哪些单、差异多少、关联批次与
调整草稿是否被采纳，出错时无处对账。

覆盖：
T1. 仅返回本人记录（他人 operator_id 的记录不可见）
T2. 未认证（无 Bearer）→ 401
T3. 仓库筛选：命中 / 不存在的仓库 → 400（不静默返回空列表）
T4. 分页字段齐全（R1：total/page/page_size/total_pages）且跨页不重不漏
T5. 行级字段：item_count / diff_count / batch_no / batch_status /
    adjustment_status（pending → completed 随批次完成与调整单审核而变）
T6. 状态筛选：默认只见 completed，void 记录需显式 status=void 才能看到，
    非法状态值 → 400
T7. 只读性：本接口不产生任何写操作（CS / 调整草稿 / 批次行数均不变）
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime
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


def _seed_user(username, role="warehouse", password="pw"):
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username=username,
             password_hash=generate_password_hash(password),
             role=role, must_change_password=False)
    db.session.add(u)
    db.session.commit()
    return u


def _bearer(client, username, password):
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


def _seed_material(code, stock=0.0):
    from app import Material
    m = Material(code=code, name=f"物料{code}", stock=stock)
    db.session.add(m)
    db.session.commit()
    return m


def _seed_scan(check_no, warehouse, operator, status="completed",
               check_id=None, lines=None, created_at=None):
    """建一张扫码盘点单（含明细）。lines = [(material, system, actual)]。"""
    from app import InventoryCheckScan, InventoryCheckScanItem
    scan = InventoryCheckScan(
        check_no=check_no,
        date=date.today(),
        warehouse=warehouse,
        remark="Android盘点：all",
        status=status,
        check_id=check_id,
        operator_id=operator.id,
        created_at=created_at or datetime.now(),
    )
    db.session.add(scan)
    db.session.commit()
    for material, system_stock, actual_stock in (lines or []):
        db.session.add(InventoryCheckScanItem(
            check_scan_id=scan.id,
            material_id=material.id,
            system_stock=system_stock,
            actual_stock=actual_stock,
            difference=round(actual_stock - system_stock, 2),
        ))
    db.session.commit()
    return scan


def _seed_batch(check_no, warehouse, status="pending"):
    from app import InventoryCheck
    b = InventoryCheck(check_no=check_no, warehouse=warehouse, status=status,
                       frozen_at=None)
    db.session.add(b)
    db.session.commit()
    return b


def _seed_adjustment(adj_no, source_type, source_id, warehouse,
                     status="pending"):
    from app import AdjustmentOrder
    o = AdjustmentOrder(adjustment_no=adj_no, date=date.today(),
                        adjustment_type="loss", warehouse=warehouse,
                        source_type=source_type, source_id=source_id,
                        status=status)
    db.session.add(o)
    db.session.commit()
    return o


def _seed_scene():
    """A仓/B仓 + 两个作业员，me 有 5 条记录，other 有 1 条。"""
    _reset_db()
    me = _seed_user("mo_me", role="warehouse", password="me")
    other = _seed_user("mo_other", role="warehouse", password="other")
    wh_a = _seed_warehouse("MOA", "A仓", is_default=True)
    wh_b = _seed_warehouse("MOB", "B仓")
    m1 = _seed_material("M-MO-1", 100.0)
    m2 = _seed_material("M-MO-2", 50.0)
    return me, other, wh_a, wh_b, m1, m2


def _list(client, headers, query=""):
    url = "/api/mobile/stocktake/list" + (("?" + query) if query else "")
    return client.get(url, headers=headers)


def test_t1_only_own_records():
    """T1: 只返回本人提交的盘点记录。"""
    me, other, wh_a, wh_b, m1, m2 = _seed_scene()
    client = _make_client()
    h = _bearer(client, "mo_me", "me")
    _seed_scan("MO-CS-ME-1", "A仓", me, lines=[(m1, 100.0, 98.0)])
    _seed_scan("MO-CS-OTHER-1", "A仓", other, lines=[(m1, 100.0, 97.0)])

    r = _list(client, h)
    assert r.status_code == 200, r.get_data(as_text=True)
    codes = {it["check_no"] for it in r.get_json()["data"]["items"]}
    assert codes == {"MO-CS-ME-1"}, f"不应看到他人记录，实际：{codes}"


def test_t2_requires_bearer():
    """T2: 无 Bearer → 401。"""
    _seed_scene()
    r = app_module.app.test_client().get("/api/mobile/stocktake/list")
    assert r.status_code == 401, f"未认证应 401，实际 {r.status_code}"


def test_t3_warehouse_filter():
    """T3: 仓库筛选命中 / 非法仓库 400。"""
    me, other, wh_a, wh_b, m1, m2 = _seed_scene()
    client = _make_client()
    h = _bearer(client, "mo_me", "me")
    _seed_scan("MO-CS-A", "A仓", me, lines=[(m1, 100.0, 99.0)])
    _seed_scan("MO-CS-B", "B仓", me, lines=[(m2, 50.0, 49.0)])

    r = _list(client, h, "warehouse_code=MOB")
    assert r.status_code == 200, r.get_data(as_text=True)
    codes = {it["check_no"] for it in r.get_json()["data"]["items"]}
    assert codes == {"MO-CS-B"}, codes

    r2 = _list(client, h, "warehouse=A仓")
    assert r2.status_code == 200
    assert {it["check_no"] for it in r2.get_json()["data"]["items"]} == {"MO-CS-A"}

    # 非法仓库必须显式报错，不能静默返回空列表（否则用户以为没盘过）
    r3 = _list(client, h, "warehouse=不存在的仓")
    assert r3.status_code == 400, f"非法仓库应 400，实际 {r3.status_code}"
    msg = (r3.get_json().get("msg") or "") + (r3.get_json().get("message") or "")
    assert "不存在" in msg or "停用" in msg, msg


def test_t4_pagination_contract():
    """T4: R1 分页字段齐全，跨页不重不漏。"""
    me, other, wh_a, wh_b, m1, m2 = _seed_scene()
    client = _make_client()
    h = _bearer(client, "mo_me", "me")
    for i in range(5):
        _seed_scan(f"MO-CS-P{i}", "A仓", me,
                   lines=[(m1, 100.0, 90.0 + i)],
                   created_at=datetime(2026, 9, 1, 10, i, 0))

    r = _list(client, h, "page=1&page_size=2")
    assert r.status_code == 200
    data = r.get_json()["data"]
    for key in ("items", "total", "page", "page_size", "total_pages"):
        assert key in data, f"R1：缺字段 {key}，实际 {sorted(data)}"
    assert data["total"] == 5 and data["page"] == 1 and data["page_size"] == 2
    assert data["total_pages"] == 3
    assert len(data["items"]) == 2

    seen = []
    for p in (1, 2, 3):
        rp = _list(client, h, f"page={p}&page_size=2")
        seen += [it["check_no"] for it in rp.get_json()["data"]["items"]]
    assert sorted(seen) == [f"MO-CS-P{i}" for i in range(5)], (
        f"分页应不重不漏，实际：{seen}"
    )

    # page_size 上限护栏
    r_big = _list(client, h, "page=1&page_size=9999")
    assert r_big.get_json()["data"]["page_size"] <= 100


def test_t5_row_fields_and_adjustment_status():
    """T5: 行级字段与调整草稿审核状态联动。"""
    me, other, wh_a, wh_b, m1, m2 = _seed_scene()
    client = _make_client()
    h = _bearer(client, "mo_me", "me")
    batch = _seed_batch("MO-CK-1", "A仓", status="pending")
    _seed_scan("MO-CS-RICH", "A仓", me, check_id=batch.id,
               lines=[(m1, 100.0, 98.0), (m2, 50.0, 50.0)])

    r = _list(client, h)
    assert r.status_code == 200, r.get_data(as_text=True)
    row = r.get_json()["data"]["items"][0]
    assert row["check_no"] == "MO-CS-RICH"
    assert row["warehouse"] == "A仓"
    assert row["status"] == "completed"
    assert row["batch_no"] == "MO-CK-1"
    assert row["batch_status"] == "pending"
    assert row["item_count"] == 2
    assert row["diff_count"] == 1, f"只有 1 行有差异，实际 {row['diff_count']}"
    # 批次未完成 → 尚无调整草稿
    assert row["adjustment_status"] == "", row["adjustment_status"]

    # 批次完成并生成待审核草稿 → pending
    _seed_adjustment("MO-ADJ-1", "check", batch.id, "A仓", status="pending")
    r2 = _list(client, h)
    row2 = r2.get_json()["data"]["items"][0]
    assert row2["adjustment_status"] == "pending", row2["adjustment_status"]

    # 草稿审核通过（库存已真实调整）→ completed
    from app import AdjustmentOrder
    adj = AdjustmentOrder.query.filter_by(adjustment_no="MO-ADJ-1").one()
    adj.status = "completed"
    batch.status = "completed"
    db.session.commit()
    r3 = _list(client, h)
    row3 = r3.get_json()["data"]["items"][0]
    assert row3["adjustment_status"] == "completed", row3["adjustment_status"]
    assert row3["batch_status"] == "completed"
    assert row3["batch_status_label"] == "已完成"


def test_t6_status_filter():
    """T6: 默认只见正常记录；void 需显式查询；非法值 400。"""
    me, other, wh_a, wh_b, m1, m2 = _seed_scene()
    client = _make_client()
    h = _bearer(client, "mo_me", "me")
    _seed_scan("MO-CS-OK", "A仓", me, lines=[(m1, 100.0, 99.0)])
    _seed_scan("MO-CS-VOID", "A仓", me, status="void",
               lines=[(m1, 100.0, 88.0)])

    r = _list(client, h)
    assert {it["check_no"] for it in r.get_json()["data"]["items"]} == {"MO-CS-OK"}

    r2 = _list(client, h, "status=void")
    assert {it["check_no"] for it in r2.get_json()["data"]["items"]} == {"MO-CS-VOID"}

    r3 = _list(client, h, "status=all")
    assert {it["check_no"] for it in r3.get_json()["data"]["items"]} == {
        "MO-CS-OK", "MO-CS-VOID"}

    r4 = _list(client, h, "status=bogus")
    assert r4.status_code == 400, f"非法状态应 400，实际 {r4.status_code}"


def test_t7_read_only():
    """T7: 回查是只读接口，不产生任何写操作。"""
    from app import AdjustmentOrder, InventoryCheck, InventoryCheckScan
    me, other, wh_a, wh_b, m1, m2 = _seed_scene()
    client = _make_client()
    h = _bearer(client, "mo_me", "me")
    batch = _seed_batch("MO-CK-RO", "A仓")
    _seed_scan("MO-CS-RO", "A仓", me, check_id=batch.id,
               lines=[(m1, 100.0, 95.0)])

    before = (InventoryCheckScan.query.count(),
              InventoryCheck.query.count(),
              AdjustmentOrder.query.count(),
              batch.status)
    for _ in range(3):
        assert _list(client, h).status_code == 200
    after = (InventoryCheckScan.query.count(),
             InventoryCheck.query.count(),
             AdjustmentOrder.query.count(),
             db.session.get(InventoryCheck, batch.id).status)
    assert before == after, f"回查接口不应写入数据：{before} → {after}"
    # 也不应因回查而给批次冻结账面（frozen_at 只由首笔盘点写入）
    assert db.session.get(InventoryCheck, batch.id).frozen_at is None

# -*- coding: utf-8 -*-
"""BUG-2026-09-06-002 回归：完成盘点前冻结期间动销校验。

业务背景：盘点按"冻结口径"过账——差异 = 实盘 − 冻结账面（save_table 首
次写入时点的系统账面），adjustment 草稿提交后库存 = 实盘 − 期间净变动。
若冻结后到完成前之间本盘点单物料发生过外部出入库（采购入库/销售出库/
调拨/其他调整等），账面与实物会出现无法回溯的偏差，系统此前对这种期
间动销完全无感知，盘点结果可信度受损。

覆盖：
T1 无动销 → 直接完成，无 confirm
T2 期间有出入库 → status='confirm' code='period_movement'，列出变动物料
T3 期间动销 force=1 → 跳过确认完成成功
T4 跨仓库流水 → 不计入本盘点单动销
T5 frozen_at 为空（历史脏数据）→ 放行不拦截
T6 自身盘点单 reference_type='check' 的流水 → 不计入（防御）
T7 _check_period_movement_alerts 直接调用：三种口径
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
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


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()
    return u


def _login_web(client):
    r = client.post("/login", data={"username": "admin", "password": "admin"})
    assert r.status_code in (302, 303), f"Web 登录失败：{r.status_code}"


def _seed_warehouse(code, name):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active", is_default=(code == "WA"))
    db.session.add(w)
    db.session.commit()
    return w


def _seed_material(code, warehouse, qty):
    from app import Material, StockTransaction
    m = Material(code=code, name=f"物料{code}", stock=qty)
    db.session.add(m)
    db.session.commit()
    # 期初流水放在 frozen 之前，frozen 之后的动销校验不应包含
    db.session.add(StockTransaction(
        material_id=m.id, transaction_type="in", quantity=qty,
        location=warehouse.name, warehouse_id=warehouse.id,
        created_at=datetime.now() - timedelta(hours=1),
    ))
    db.session.commit()
    return m


def _seed_scene():
    _reset_db()
    _seed_admin()
    wh_a = _seed_warehouse("WA", "A仓")
    wh_b = _seed_warehouse("WB", "B仓")
    m1 = _seed_material("M001", wh_a, 60.0)
    m2 = _seed_material("M002", wh_a, 30.0)
    return wh_a, wh_b, m1, m2


def _new_check(client, codes, warehouse="A仓"):
    """建盘点单。save_table 首次写入即设 frozen_at=now。"""
    items = [{"code": c, "actual_stock": c == "M001" and 58 or 30} for c in codes]
    r = client.post("/check/save_table", json={
        "order_id": None, "check_no": "",
        "header": {"warehouse": warehouse, "remark": ""},
        "items": items,
    })
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body.get("status") == "success", body
    return body["id"]


def _items_of(check_id):
    from app import InventoryCheckItem
    return (InventoryCheckItem.query
            .filter_by(inventory_check_id=check_id)
            .order_by(InventoryCheckItem.id.asc()).all())


def _count_as_counted(client, check_id, item_id, actual):
    """走 update_check_item 标记该行已盘（写入 counted_by/counted_at）。"""
    r = client.post(f"/check/{check_id}/item/{item_id}",
                    data={"actual_stock": actual})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json().get("status") == "success", r.get_json()


def _write_txn(material, warehouse, qty, txn_type="out", when=None,
               reference_type=None, reference_id=None):
    """写一笔 StockTransaction。qty 是带符号的（出库负）。"""
    from app import StockTransaction
    when = when or datetime.now()
    db.session.add(StockTransaction(
        material_id=material.id,
        transaction_type=txn_type,
        quantity=qty,
        location=warehouse.name,
        warehouse_id=warehouse.id,
        created_at=when,
        reference_type=reference_type,
        reference_id=reference_id,
    ))
    db.session.commit()


def test_t1_no_period_movement_completes_directly():
    """T1: 期间无动销 → 直接完成（无 confirm）。"""
    wh_a, wh_b, m1, m2 = _seed_scene()
    client = _make_client()
    _login_web(client)
    cid = _new_check(client, ["M001", "M002"])
    items = _items_of(cid)
    # 两行都标记为已盘（actual = system，无差异）
    _count_as_counted(client, cid, items[0].id, 60)
    _count_as_counted(client, cid, items[1].id, 30)

    r = client.post(f"/check/{cid}/complete", json={})
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body.get("status") == "success", body
    assert "无库存差异" in body.get("msg", ""), body


def test_t2_period_movement_returns_confirm():
    """T2: 期间有出入库 → confirm + period_movement code + samples。"""
    wh_a, wh_b, m1, m2 = _seed_scene()
    client = _make_client()
    _login_web(client)
    cid = _new_check(client, ["M001", "M002"])
    items = _items_of(cid)
    _count_as_counted(client, cid, items[0].id, 60)
    _count_as_counted(client, cid, items[1].id, 30)

    # 期间：M001 出库 10（账面 60→50），M002 入库 5（账面 30→35）
    _write_txn(m1, wh_a, -10, "out")
    _write_txn(m2, wh_a, +5, "in")

    r = client.post(f"/check/{cid}/complete", json={})
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body.get("status") == "confirm", body
    assert body.get("code") == "period_movement", body
    assert body.get("count") == 2, body
    samples = {s["code"]: s for s in body.get("samples") or []}
    assert "M001" in samples and samples["M001"]["net"] == -10, samples
    assert "M002" in samples and samples["M002"]["net"] == 5, samples
    # 不落库存调整
    from app import AdjustmentOrder, InventoryCheck
    assert InventoryCheck.query.get(cid).status == "pending"
    assert AdjustmentOrder.query.filter_by(source_type="check").count() == 0


def test_t3_force_skips_movement_confirm():
    """T3: force=1 跳过动销确认完成成功。"""
    wh_a, wh_b, m1, m2 = _seed_scene()
    client = _make_client()
    _login_web(client)
    cid = _new_check(client, ["M001", "M002"])
    items = _items_of(cid)
    _count_as_counted(client, cid, items[0].id, 58)  # 差异 -2

    _write_txn(m1, wh_a, -10, "out")  # 期间动销

    r = client.post(f"/check/{cid}/complete", json={"force": 1})
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body.get("status") == "success", body

    from app import AdjustmentOrder, AdjustmentOrderItem
    drafts = AdjustmentOrder.query.filter_by(source_type="check").all()
    assert len(drafts) == 1, f"应只生成 1 张盘亏草稿，实际 {len(drafts)}"
    lines = AdjustmentOrderItem.query.filter_by(
        adjustment_order_id=drafts[0].id).all()
    assert len(lines) == 1, lines
    assert abs((lines[0].quantity or 0) - (-2)) < 1e-6, lines[0].quantity


def test_t4_cross_warehouse_txn_excluded():
    """T4: 跨仓库流水（warehouse_id 不同于本盘点单仓库）不计入。"""
    wh_a, wh_b, m1, m2 = _seed_scene()
    client = _make_client()
    _login_web(client)
    cid = _new_check(client, ["M001", "M002"])
    items = _items_of(cid)
    _count_as_counted(client, cid, items[0].id, 60)
    _count_as_counted(client, cid, items[1].id, 30)

    # B 仓动销：不属于本盘点单仓库
    _write_txn(m1, wh_b, -10, "out")

    r = client.post(f"/check/{cid}/complete", json={})
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    # 无动销 → 直接 success
    assert body.get("status") == "success", body


def test_t5_no_frozen_at_passes_through():
    """T5: frozen_at 为 NULL（历史脏数据）→ 不拦截。"""
    wh_a, wh_b, m1, m2 = _seed_scene()
    client = _make_client()
    _login_web(client)
    cid = _new_check(client, ["M001"])
    items = _items_of(cid)
    _count_as_counted(client, cid, items[0].id, 60)

    # 手动清空 frozen_at 模拟历史脏数据
    from app import InventoryCheck
    check = InventoryCheck.query.get(cid)
    check.frozen_at = None
    db.session.commit()

    _write_txn(m1, wh_a, -10, "out")

    r = client.post(f"/check/{cid}/complete", json={})
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body.get("status") == "success", body


def test_t6_own_reference_excluded():
    """T6: reference_type='check' 且 reference_id=本单 → 不计入（防御）。"""
    wh_a, wh_b, m1, m2 = _seed_scene()
    client = _make_client()
    _login_web(client)
    cid = _new_check(client, ["M001"])
    items = _items_of(cid)
    _count_as_counted(client, cid, items[0].id, 60)

    # 理论上盘点不写自身流水，模拟一条以确认排除逻辑
    _write_txn(m1, wh_a, -10, "out",
               reference_type="check", reference_id=cid)

    r = client.post(f"/check/{cid}/complete", json={})
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body.get("status") == "success", body


def test_t7_helper_directly_three_cases():
    """T7: _check_period_movement_alerts 直接调用：无动销/有动销/跨仓库。"""
    wh_a, wh_b, m1, m2 = _seed_scene()
    client = _make_client()
    _login_web(client)
    cid = _new_check(client, ["M001", "M002"])

    from app import InventoryCheck
    from routes.check import _check_period_movement_alerts
    check = InventoryCheck.query.get(cid)
    has_m, count, samples = _check_period_movement_alerts(check)
    assert (has_m, count) == (False, 0), (has_m, count, samples)

    _write_txn(m1, wh_a, -10, "out")
    db.session.expire_all()
    check = InventoryCheck.query.get(cid)
    has_m, count, samples = _check_period_movement_alerts(check)
    assert has_m is True
    assert count == 1
    assert samples[0]["code"] == "M001"
    assert samples[0]["net"] == -10

    _write_txn(m2, wh_b, +5, "in")  # 跨仓库，不计入
    db.session.expire_all()
    check = InventoryCheck.query.get(cid)
    has_m, count, samples = _check_period_movement_alerts(check)
    assert has_m is True
    assert count == 1  # 仍是 M001

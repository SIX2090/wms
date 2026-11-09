# -*- coding: utf-8 -*-
"""BUG-2026-09-06-001 回归：完成盘点前的未盘（漏盘）校验。

背景：分类建单（FEATURE-2026-09-05-001）预生成的待盘行 actual_stock =
system_stock、difference = 0、counted_by/counted_at 为空；完成盘点时这些
行既不生成库存调整也不提示，与"盘了没有差异"在系统里完全同形。结果是
一单 500 行只盘 50 行也能直接「完成」，事后无法与真实无差异区分——漏盘
是盘点最大的风险源。

修复：complete_check 前置统计 counted_at 为空的行，未盘行数 > 0 时返回
status='confirm' 二次确认（列前 10 条物料编码），用户确认后带 force=1
及当前风险快照令牌放行；软拦截而非硬阻断，账面 0 无实物等合法未盘场景仍可完成。

覆盖（A仓 M001 账面 60 / M002 账面 30）：
T1. 全部已盘 → 直接完成成功，不返回 confirm
T2. 存在未盘行 → 返回 status='confirm'/code='check_risks'，风险数量与 samples 正确
T3. 裸 force 不放行；确认风险令牌后完成，仅已盘行生成调整草稿
T4. 未盘行差异恒 0 → 不产生该物料的调整明细
T5. 旧客户端不带 JSON body 调用 → 仍走确认分支，不报错（向后兼容）
"""
from __future__ import annotations

from tests.document_revision_client import document_post
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

# BUG-2026-09-03-004(测试污染)：模块顶层常驻 app context 在模块结束后必须 pop
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
    r = document_post(client,"/login", data={"username": "admin", "password": "admin"})
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
    db.session.add(StockTransaction(
        material_id=m.id, transaction_type="in", quantity=qty,
        location=warehouse.name, warehouse_id=warehouse.id,
        created_at=datetime.now(),
    ))
    db.session.commit()
    return m


def _seed_scene():
    _reset_db()
    _seed_admin()
    wh = _seed_warehouse("WA", "A仓")
    _seed_warehouse("WB", "B仓")
    m1 = _seed_material("M001", wh, 60.0)
    m2 = _seed_material("M002", wh, 30.0)
    return wh, m1, m2


def _new_check(client, codes):
    """建盘点单并预生成待盘行（save_table 写入的行 counted_at 为空）。"""
    items = [{"code": c, "actual_stock": ""} for c in codes]
    r = document_post(client,"/check/save_table", json={
        "order_id": None, "check_no": "",
        "header": {"warehouse": "A仓", "remark": ""},
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
    r = document_post(client,f"/check/{check_id}/item/{item_id}",
                    data={"actual_stock": actual})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json().get("status") == "success", r.get_json()


def test_t1_all_counted_completes_without_confirm():
    """T1: 全部行已盘 → 直接完成成功，不返回 confirm。"""
    wh, m1, m2 = _seed_scene()
    client = _make_client()
    _login_web(client)
    cid = _new_check(client, ["M001", "M002"])
    items = _items_of(cid)
    assert len(items) == 2
    # 两行都按账面实盘（无差异），但都标记了 counted_at
    _count_as_counted(client, cid, items[0].id, 60)
    _count_as_counted(client, cid, items[1].id, 30)

    r = document_post(client,f"/check/{cid}/complete", json={})
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body.get("status") == "success", body
    assert "无库存差异" in (body.get("msg") or ""), body


def test_t2_uncounted_rows_return_confirm():
    """T2: 存在未盘行 → check_risks，风险数量和 samples 正确且不落库存调整。"""
    wh, m1, m2 = _seed_scene()
    client = _make_client()
    _login_web(client)
    cid = _new_check(client, ["M001", "M002"])
    items = _items_of(cid)
    _count_as_counted(client, cid, items[0].id, 58)

    r = document_post(client,f"/check/{cid}/complete", json={})
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body.get("status") == "confirm", body
    assert body.get("code") == "check_risks", body
    assert "共 2 行，其中 1 行未盘" in body.get("msg", ""), body
    assert body["risks"]["uncounted"] == 1 and body["risks"]["total"] == 2, body
    samples = body.get("samples") or []
    assert samples and samples[0]["code"] == "M002", body
    # 未完成：状态仍为草稿，且不生成调整草稿
    from app import AdjustmentOrder, InventoryCheck
    assert InventoryCheck.query.get(cid).status == "pending"
    assert AdjustmentOrder.query.filter_by(source_type="check").count() == 0


def test_t3_force_requires_token_and_generates_draft():
    """T3: 裸 force 不放行，持风险令牌确认后仅已盘行生成调整草稿。"""
    wh, m1, m2 = _seed_scene()
    client = _make_client()
    _login_web(client)
    cid = _new_check(client, ["M001", "M002"])
    items = _items_of(cid)
    _count_as_counted(client, cid, items[0].id, 58)

    warning = document_post(client,f"/check/{cid}/complete", json={"force": True})
    assert warning.status_code == 200
    alert = warning.get_json()
    assert alert.get("status") == "confirm" and alert.get("code") == "check_risks", alert
    assert "1 行未盘" in alert.get("msg", ""), alert
    assert alert.get("confirmation_token"), alert
    r = document_post(client,f"/check/{cid}/complete", json={"force": True, "confirmation_token": alert["confirmation_token"]})
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body.get("status") == "success", body
    from app import InventoryCheck
    assert InventoryCheck.query.get(cid).status == "completed"

    from app import AdjustmentOrder, AdjustmentOrderItem
    drafts = AdjustmentOrder.query.filter_by(source_type="check").all()
    assert len(drafts) == 1, f"应只生成 1 张盘亏草稿，实际 {len(drafts)}"
    assert drafts[0].adjustment_type == "loss"
    lines = AdjustmentOrderItem.query.filter_by(
        adjustment_order_id=drafts[0].id).all()
    assert len(lines) == 1, lines
    assert abs((lines[0].quantity or 0) - (-2)) < 1e-6, lines[0].quantity


def test_t4_uncounted_row_never_generates_adjustment():
    """T4: 未盘行差异恒 0 → 不出现该物料的调整明细。"""
    wh, m1, m2 = _seed_scene()
    client = _make_client()
    _login_web(client)
    cid = _new_check(client, ["M001", "M002"])

    warning = document_post(client,f"/check/{cid}/complete", json={"force": True})
    alert = warning.get_json()
    assert alert.get("status") == "confirm" and alert.get("code") == "check_risks", alert
    assert "2 行未盘" in alert.get("msg", ""), alert
    assert alert.get("confirmation_token"), alert
    r = document_post(client,f"/check/{cid}/complete", json={"force": True, "confirmation_token": alert["confirmation_token"]})
    body = r.get_json()
    assert body.get("status") == "success", body
    from app import AdjustmentOrder
    assert AdjustmentOrder.query.filter_by(source_type="check").count() == 0


def test_t5_legacy_call_without_body_still_confirms():
    """T5: 旧客户端不带 JSON body → 走确认分支，不 500。"""
    wh, m1, m2 = _seed_scene()
    client = _make_client()
    _login_web(client)
    cid = _new_check(client, ["M001"])

    r = document_post(client,f"/check/{cid}/complete")
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body.get("status") == "confirm", body
    assert body.get("code") == "check_risks", body
    assert "1 行未盘" in body.get("msg", ""), body
    assert body["risks"]["uncounted"] == 1 and body["risks"]["total"] == 1, body
    assert body.get("confirmation_token"), body


def test_t6_uncounted_helper_counts_accurately():
    """T6: _check_uncounted_alerts 直接调用——全盘/全未盘/混合三种口径。"""
    wh, m1, m2 = _seed_scene()
    client = _make_client()
    _login_web(client)
    cid = _new_check(client, ["M001", "M002"])

    from app import InventoryCheck
    from routes.check import _check_uncounted_alerts
    check = InventoryCheck.query.get(cid)
    unc, total, samples = _check_uncounted_alerts(check)
    assert (unc, total) == (2, 2), (unc, total)
    assert len(samples) == 2

    items = _items_of(cid)
    _count_as_counted(client, cid, items[0].id, 58)
    db.session.expire_all()
    check = InventoryCheck.query.get(cid)
    unc, total, samples = _check_uncounted_alerts(check)
    assert (unc, total) == (1, 2), (unc, total)
    assert samples[0]["code"] == "M002"


def test_reset_releases_rows_from_previous_synthetic_schema():
    from sqlalchemy import inspect
    from app import Material
    _reset_db()
    old = Material(code="SYN-RESET-OLD", name="旧合成行", stock=11)
    db.session.add(old)
    db.session.commit()
    ident = old.id
    assert inspect(old).persistent
    _reset_db()
    assert inspect(old).detached, "重建 schema 后旧 ORM 行不能继续属于当前会话"
    fresh = Material(id=ident, code="SYN-RESET-NEW", name="新合成行", stock=22)
    db.session.add(fresh)
    db.session.commit()
    found = db.session.get(Material, ident)
    assert found is not old and found.code == "SYN-RESET-NEW" and found.stock == 22

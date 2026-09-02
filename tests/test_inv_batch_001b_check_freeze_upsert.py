# -*- coding: utf-8 -*-
"""INV-BATCH-001-B / BUG-2026-09-02-004 回归：盘点明细行级 upsert 与冻结快照。

背景：save_check_table 保存盘点明细时全删重建（delete + 逐行 insert），
且每行 system_stock 默认取**保存时点**的仓库级账面。多人轮流保存同一
盘点单时，每次保存都把全部行的账面基准刷新到最新值——例：A 上午盘点
M001（账面 60，实盘 58，差 -2），期间出库 30（账面变 30），B 下午补充
一行再保存 → A 的行 system_stock 被刷新为 30，差异从 -2 变 +28，账面
基准漂移，差异含义被悄悄改变且无任何提示。

修复（冻结快照语义）：
- 首次写入明细时设置 check.frozen_at（冻结时点）；
- 行级 upsert 替换全删重建：已有行（按物料匹配）保留 system_stock
  冻结值、仅更新 actual/reason/difference；新增行取当前账面；提交集
  之外的旧行删除；
- complete 时差异 = 实盘 − 冻结账面（不随后续出入库漂移）；
- update_check_item 写入 counted_by/counted_at 行级归属并加单据写锁。

覆盖（多仓库场景，A仓 M001=60/M002=30，B仓 M001=40/M002=20）：
T1. 首次保存设 frozen_at，行 system_stock 取当前账面
T2. 期间出库后二次保存：已有行 system_stock 冻结不变、actual 更新；
    新增行取当前账面；frozen_at 不变
T3. 提交集移除某行 → 该行删除，其余行冻结值保留
T4. 账面变化后 complete → 调整草稿差异按冻结口径（actual − 冻结值）
T5. update_check_item 写 counted_by/counted_at 行级归属
T6. 响应格式兼容（status/id/order_no），completed 单保存仍拒绝
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


# BUG-2026-09-03-004(测试污染)：模块顶层常驻 app context 在模块结束后必须 pop，
# 否则残留 ctx 会使后续模块的请求内事务/系统设置读取异常（顺序依赖假失败）。
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


def _seed_warehouse(code, name, is_default=False):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active", is_default=is_default)
    db.session.add(w)
    db.session.commit()
    return w


def _seed_material_with_warehouse_stock(code, global_stock, per_warehouse):
    """建物料并按仓库写入流水（global_stock = 各仓之和，数据自洽）。"""
    from app import Material, StockTransaction
    m = Material(code=code, name=f"物料{code}", stock=global_stock)
    db.session.add(m)
    db.session.commit()
    for wh, qty in per_warehouse.items():
        db.session.add(StockTransaction(
            material_id=m.id,
            transaction_type="in",
            quantity=qty,
            location=wh.name,
            warehouse_id=wh.id,
            created_at=datetime.now(),
        ))
    db.session.commit()
    return m


def _seed_scene():
    _reset_db()
    admin = _seed_admin()
    wh_a = _seed_warehouse("WA", "A仓")
    wh_b = _seed_warehouse("WB", "B仓")
    m1 = _seed_material_with_warehouse_stock("M001", 100.0, {wh_a: 60.0, wh_b: 40.0})
    m2 = _seed_material_with_warehouse_stock("M002", 50.0, {wh_a: 30.0, wh_b: 20.0})
    return admin, wh_a, wh_b, m1, m2


def _save_table(client, items, order_id=None, check_no=None, warehouse="A仓"):
    payload = {
        "order_id": order_id,
        "check_no": check_no or "",
        "header": {"warehouse": warehouse, "remark": ""},
        "items": items,
    }
    return client.post("/check/save_table", json=payload)


def _write_out_flow(material, warehouse, qty):
    """写一笔出库流水（quantity 负数，对齐 SUM 净额聚合口径）。"""
    from app import StockTransaction
    db.session.add(StockTransaction(
        material_id=material.id,
        transaction_type="out",
        quantity=-abs(qty),
        location=warehouse.name,
        warehouse_id=warehouse.id,
        created_at=datetime.now(),
    ))
    db.session.commit()


def _get_item(check, material_id):
    from app import InventoryCheckItem
    return InventoryCheckItem.query.filter_by(
        inventory_check_id=check.id, material_id=material_id).first()


def test_t1_first_save_sets_frozen_at():
    """T1: 首次保存写明细 → 设 frozen_at，行 system_stock 取当前账面。"""
    from app import InventoryCheck
    _seed_scene()
    client = _make_client()
    _login_web(client)

    r = _save_table(client, [{"code": "M001", "actual_stock": 58}])
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body.get("status") == "success", body

    check = InventoryCheck.query.get(body["id"])
    assert check.frozen_at is not None, "首次写入明细必须设置冻结时点"
    item = _get_item(check, _material_id("M001"))
    assert item.system_stock == 60.0, f"首次保存账面应取当前值 60，实际 {item.system_stock}"
    assert item.actual_stock == 58.0
    assert item.difference == -2.0


def test_t2_resave_preserves_frozen_system_stock():
    """T2: 期间出库后二次保存——已有行账面冻结不变、actual 更新、新行取当前账面。"""
    from app import InventoryCheck
    admin, wh_a, wh_b, m1, m2 = _seed_scene()
    client = _make_client()
    _login_web(client)

    r1 = _save_table(client, [{"code": "M001", "actual_stock": 58}])
    check_id = r1.get_json()["id"]
    check = InventoryCheck.query.get(check_id)
    frozen_at_t0 = check.frozen_at
    assert frozen_at_t0 is not None

    # 期间出库 30：A仓 M001 账面 60 → 30
    _write_out_flow(m1, wh_a, 30)

    # 二次保存：修改 M001 实盘，新增 M002 行
    r2 = _save_table(client, [
        {"code": "M001", "actual_stock": 57},
        {"code": "M002", "actual_stock": 20},
    ], order_id=check_id, check_no=check.check_no)
    assert r2.status_code == 200, r2.get_data(as_text=True)

    db.session.expire_all()
    item1 = _get_item(check, m1.id)
    assert item1.system_stock == 60.0, (
        f"已有行账面必须冻结在 60（首次保存时点），不得漂移为出库后的 30；实际 {item1.system_stock}"
    )
    assert item1.actual_stock == 57.0, "已有行实盘数应被更新"
    assert item1.difference == -3.0
    item2 = _get_item(check, m2.id)
    assert item2 is not None, "新增行必须落库"
    assert item2.system_stock == 30.0, (
        f"新增行账面取当前值 30（A仓 M002），实际 {item2.system_stock}"
    )
    assert check.frozen_at == frozen_at_t0, "冻结时点一经设置不得变更"


def test_t3_removed_item_deleted_others_frozen():
    """T3: 提交集移除某行 → 该行删除；保留行冻结值不动。"""
    from app import InventoryCheck, InventoryCheckItem
    admin, wh_a, wh_b, m1, m2 = _seed_scene()
    client = _make_client()
    _login_web(client)

    r1 = _save_table(client, [
        {"code": "M001", "actual_stock": 58},
        {"code": "M002", "actual_stock": 29},
    ])
    check_id = r1.get_json()["id"]
    check = InventoryCheck.query.get(check_id)

    _write_out_flow(m1, wh_a, 30)

    r2 = _save_table(client, [{"code": "M001", "actual_stock": 58}],
                     order_id=check_id, check_no=check.check_no)
    assert r2.status_code == 200, r2.get_data(as_text=True)

    db.session.expire_all()
    assert _get_item(check, m2.id) is None, "提交集之外的旧行必须被删除"
    item1 = _get_item(check, m1.id)
    assert item1.system_stock == 60.0, "保留行冻结账面不得漂移"
    assert InventoryCheckItem.query.filter_by(inventory_check_id=check.id).count() == 1


def test_t4_complete_uses_frozen_baseline():
    """T4: 账面变化后 complete → 调整草稿差异 = 实盘 − 冻结账面（非当前账面）。"""
    from app import AdjustmentOrder, AdjustmentOrderItem, InventoryCheck
    admin, wh_a, wh_b, m1, m2 = _seed_scene()
    client = _make_client()
    _login_web(client)

    r1 = _save_table(client, [{"code": "M001", "actual_stock": 57}])
    check_id = r1.get_json()["id"]

    # 期间出库 30：账面 60 → 30。冻结口径差异 = 57 − 60 = -3；
    # 若错误地用当前账面则差异 = 57 − 30 = +27（方向都反了）。
    _write_out_flow(m1, wh_a, 30)

    r2 = client.post(f"/check/{check_id}/complete")
    assert r2.status_code == 200, r2.get_data(as_text=True)
    body = r2.get_json()
    assert body.get("status") == "success", body

    order = AdjustmentOrder.query.filter_by(source_type="check", source_id=check_id).one()
    adj_item = AdjustmentOrderItem.query.filter_by(
        adjustment_order_id=order.id, material_id=m1.id).one()
    assert adj_item.quantity == -3.0, (
        f"调整数量必须按冻结口径 57−60=-3，实际 {adj_item.quantity}"
        "（若为 +27 则说明用了漂移后的当前账面）"
    )
    assert order.adjustment_type == "loss"


def test_t5_update_check_item_writes_counted_attribution():
    """T5: update_check_item 更新实盘 → 写入 counted_by/counted_at 行级归属。"""
    from app import InventoryCheck
    admin, wh_a, wh_b, m1, m2 = _seed_scene()
    client = _make_client()
    _login_web(client)

    r1 = _save_table(client, [{"code": "M001", "actual_stock": 58}])
    check = InventoryCheck.query.get(r1.get_json()["id"])
    item = _get_item(check, m1.id)

    r2 = client.post(f"/check/{check.id}/item/{item.id}",
                     data={"actual_stock": "56"})
    assert r2.status_code == 200, r2.get_data(as_text=True)

    db.session.expire_all()
    item = _get_item(check, m1.id)
    assert item.actual_stock == 56.0
    assert item.counted_by == admin.id, "行级归属必须记录盘点人"
    assert item.counted_at is not None, "行级归属必须记录盘点时间"


def test_t6_response_format_compatible():
    """T6: 响应格式兼容（status/id/order_no）；completed 单保存仍拒绝。"""
    from app import InventoryCheck
    _seed_scene()
    client = _make_client()
    _login_web(client)

    r1 = _save_table(client, [{"code": "M001", "actual_stock": 58}])
    body = r1.get_json()
    assert body.get("status") == "success"
    assert isinstance(body.get("id"), int)
    assert body.get("order_no"), "响应必须携带盘点单号"

    check = InventoryCheck.query.get(body["id"])
    check.status = "completed"
    db.session.commit()
    r2 = _save_table(client, [{"code": "M001", "actual_stock": 58}],
                     order_id=check.id, check_no=check.check_no)
    body2 = r2.get_json()
    assert body2.get("status") == "error", "completed 单保存必须被拒绝"


def _material_id(code):
    from app import Material
    return Material.query.filter_by(code=code).one().id

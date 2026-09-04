# -*- coding: utf-8 -*-
"""INV-GUARD-001 / BUG-2026-09-02-002（INV-BATCH-001-E 重构版）回归：盘点重复与跨仓隔离。

历史语义：旧版扫码盘点（独立模式）每扫一次即生成一个 CS 单并立即生成
库存调整草稿（pending），重复盘同一物料会基于同一账面叠出多张草稿，
提交后库存被重复调整（静默双重计数），故有跨 CS 的 pending 草稿护栏。

INV-BATCH-001-E（BUG-2026-09-04-005）强制选单重构后，CS 不再独立生成
草稿——所有扫码差异统一 upsert 进所选进行中盘点单（批次），仅 PC
「完成盘点」按批次生成一次调整草稿，旧的双重计数窗口结构性关闭。
本回归改为锁定重构后的重复/隔离不变式：
T1. 同一批次内重复盘同物料 → 400 拒绝，提示含"已由"（防两人互覆），CS 不增
T2. 同一批次内不同物料 → 放行，各自成行
T3. 批次 complete 恰生成一次调整草稿；再次 complete 被拒
T4. 跨仓库隔离：A/B 各建批次，同物料各自盘各自批次 → 都放行、行落各自批次
T5. Android(/api/stocktake) 与 H5(/mobile/api/scan_submit) 两个入口对同批次
    重复盘走同一"已由"护栏
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


def _bearer(client):
    r = client.post("/api/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, r.get_data(as_text=True)
    return {"Authorization": f"Bearer {r.get_json()['data']['token']}"}


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


def _seed_check_order(warehouse_name, check_no):
    """预置进行中（pending）盘点单。"""
    from app import InventoryCheck
    check = InventoryCheck(check_no=check_no, warehouse=warehouse_name,
                           status="pending")
    db.session.add(check)
    db.session.commit()
    return check


def _post_stocktake(client, headers, warehouse, lines, check_id):
    payload = {"mode": "scan", "warehouse": warehouse, "lines": lines,
               "check_id": check_id}
    return client.post("/api/stocktake", json=payload, headers=headers)


def _post_scan_submit(client, headers, warehouse, code, actual, check_id):
    return client.post("/mobile/api/scan_submit", headers=headers, json={
        "mode": "check", "code": code, "warehouse": warehouse,
        "actual_stock": actual, "check_id": check_id,
    })


def _seed_two_warehouse_scene():
    _reset_db()
    _seed_admin()
    wh_a = _seed_warehouse("WA", "A仓")
    wh_b = _seed_warehouse("WB", "B仓")
    _seed_material_with_warehouse_stock("M001", 100.0, {wh_a: 60.0, wh_b: 40.0})
    _seed_material_with_warehouse_stock("M002", 50.0, {wh_a: 30.0, wh_b: 20.0})
    return wh_a, wh_b


def test_t1_duplicate_scan_in_same_batch_rejected():
    """T1: 同批次重复盘同物料 → 400 且提示已盘信息，CS 不增。"""
    from app import InventoryCheckScan
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)
    batch = _seed_check_order("B仓", "CK-G1")

    r1 = _post_stocktake(client, h, "B仓",
                         [{"material_code": "M001", "actual_stock": 38}], batch.id)
    assert r1.status_code == 200, r1.get_data(as_text=True)

    r2 = _post_stocktake(client, h, "B仓",
                         [{"material_code": "M001", "actual_stock": 38}], batch.id)
    assert r2.status_code == 400, (
        f"同批次重复盘应拒绝，实际 {r2.status_code}：{r2.get_data(as_text=True)}"
    )
    msg = (r2.get_json().get("msg") or "") + (r2.get_json().get("message") or "")
    assert "已由" in msg, f"提示应含已盘人信息，实际：{msg}"
    assert InventoryCheckScan.query.count() == 1, "被拒的重复盘点不得落 CS 单"


def test_t2_different_material_allowed():
    """T2: 同批次不同物料放行，各自成行；批次未完成不生成草稿。"""
    from app import AdjustmentOrder, InventoryCheckItem, InventoryCheckScan
    wh_a, wh_b = _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)
    batch = _seed_check_order("B仓", "CK-G2")

    r1 = _post_stocktake(client, h, "B仓",
                         [{"material_code": "M001", "actual_stock": 38}], batch.id)
    assert r1.status_code == 200
    r2 = _post_stocktake(client, h, "B仓",
                         [{"material_code": "M002", "actual_stock": 18}], batch.id)
    assert r2.status_code == 200, r2.get_data(as_text=True)

    assert InventoryCheckScan.query.count() == 2
    assert InventoryCheckItem.query.filter_by(inventory_check_id=batch.id).count() == 2
    # 未完成批次前不产生任何调整草稿（草稿统一由批次 complete 生成）
    assert AdjustmentOrder.query.filter_by(source_type="check").count() == 0
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 0


def test_t3_batch_complete_generates_single_draft_once():
    """T3: 批次 complete 恰生成一次调整草稿；重复 complete 被拒。"""
    from app import AdjustmentOrder
    wh_a, wh_b = _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)
    batch = _seed_check_order("B仓", "CK-G3")

    r = _post_stocktake(client, h, "B仓",
                        [{"material_code": "M001", "actual_stock": 38}], batch.id)
    assert r.status_code == 200
    # 另一物料也进同批次
    r = _post_stocktake(client, h, "B仓",
                        [{"material_code": "M002", "actual_stock": 18}], batch.id)
    assert r.status_code == 200

    _login_web(client)
    rc = client.post(f"/check/{batch.id}/complete")
    assert rc.status_code == 200 and rc.get_json().get("status") == "success", rc.get_data(as_text=True)
    # 恰好一张 check 来源调整草稿（含两行），CS 不产生独立草稿
    orders = AdjustmentOrder.query.filter_by(source_type="check", source_id=batch.id).all()
    assert len(orders) == 1, f"批次完成应只生成一次调整草稿，实际 {len(orders)}"
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 0
    # 重复完成同一批次 → 拒绝
    rc2 = client.post(f"/check/{batch.id}/complete")
    assert rc2.status_code == 400, f"重复完成应被拒，实际 {rc2.status_code}"


def test_t4_cross_warehouse_isolation():
    """T4: 跨仓库隔离——A/B 各建批次，同物料各盘各自批次均放行。"""
    from app import InventoryCheckItem, InventoryCheckScan
    wh_a, wh_b = _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)
    batch_a = _seed_check_order("A仓", "CK-GA")
    batch_b = _seed_check_order("B仓", "CK-GB")

    r1 = _post_stocktake(client, h, "B仓",
                         [{"material_code": "M001", "actual_stock": 38}], batch_b.id)
    assert r1.status_code == 200
    r2 = _post_stocktake(client, h, "A仓",
                         [{"material_code": "M001", "actual_stock": 58}], batch_a.id)
    assert r2.status_code == 200, r2.get_data(as_text=True)

    assert InventoryCheckScan.query.count() == 2
    assert InventoryCheckItem.query.filter_by(inventory_check_id=batch_a.id).count() == 1
    assert InventoryCheckItem.query.filter_by(inventory_check_id=batch_b.id).count() == 1


def test_t5_mobile_web_and_native_share_duplicate_guard():
    """T5: Android 与 H5 两入口对同批次重复盘走同一"已由"护栏。"""
    from app import InventoryCheckScan
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)
    batch = _seed_check_order("B仓", "CK-G5")

    # 第一次：Android 入口盘 B仓 M001（账面 40，实盘 38）
    r1 = _post_stocktake(client, h, "B仓",
                         [{"material_code": "M001", "actual_stock": 38}], batch.id)
    assert r1.status_code == 200
    # 第二次：Web 手机端入口盘同一物料（同批次）→ 同样被拒
    r2 = _post_scan_submit(client, h, "B仓", "M001", 38, batch.id)
    assert r2.status_code == 400, (
        f"Web 手机端重复盘应被同一护栏拦截，实际返回 {r2.status_code}"
    )
    msg = (r2.get_json().get("msg") or "") + (r2.get_json().get("message") or "")
    assert "已由" in msg, f"提示应含已盘信息，实际：{msg}"
    assert InventoryCheckScan.query.count() == 1

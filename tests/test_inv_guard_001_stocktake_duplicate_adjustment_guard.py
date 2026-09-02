# -*- coding: utf-8 -*-
"""INV-GUARD-001 / BUG-2026-09-02-002 回归：扫码盘点重复调整护栏。

背景：扫码盘点（mobile.py scan_submit / native_api.py /api/stocktake）每扫
一次就生成一个 CS 盘点单并立即生成库存调整草稿（pending，不动库存）。
调整草稿从生成到人工审核提交之间存在时间窗，窗口内账面库存不变，于是
同一物料被重复扫码盘点时，每次都基于同一账面值生成一张调整草稿：
两张 -5 的草稿都提交 → 库存被扣两次，全程无报错（静默双重计数）。
现有幂等只按 source_id=check.id 判重，防同一盘点单重复生成，防不住
跨盘点单对同一物料的正常重复盘点。

护栏：_create_adjustment_drafts_from_check_scan 生成新草稿前检查——同仓库
同物料若已存在未提交（pending）的扫码盘点调整草稿，拒绝生成并提示先
处理存量草稿。不误伤：不同物料、不同仓库、已提交草稿（库存已真实
调整、账面已更新）均放行。

覆盖（多仓库场景，A仓 60 / B仓 40 / 全局 100，数据自洽）：
T1. 同仓库同物料重复盘点 → 400 拒绝，提示含物料与调整单号，草稿数不增
T2. 同仓库不同物料 → 放行，正常生成
T3. 已提交（completed）的存量草稿 → 放行（账面已更新，属合法二次盘点）
T4. 不同仓库同物料 → 放行（仓库级账面互不影响）
T5. 手机端 Web 入口 /mobile/api/scan_submit 同样被护栏保护
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
_ctx.push()


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


def _post_stocktake(client, headers, warehouse, lines):
    payload = {"mode": "scan", "warehouse": warehouse, "lines": lines}
    return client.post("/api/stocktake", json=payload, headers=headers)


def _seed_two_warehouse_scene():
    _reset_db()
    _seed_admin()
    wh_a = _seed_warehouse("WA", "A仓")
    wh_b = _seed_warehouse("WB", "B仓")
    _seed_material_with_warehouse_stock("M001", 100.0, {wh_a: 60.0, wh_b: 40.0})
    _seed_material_with_warehouse_stock("M002", 50.0, {wh_a: 30.0, wh_b: 20.0})
    return wh_a, wh_b


def test_t1_duplicate_stocktake_rejected():
    """T1: 同仓库同物料重复盘点必须被拒绝，调整草稿不得叠加。"""
    from app import AdjustmentOrder
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)

    # 第一次盘 B仓 M001：账面 40，实盘 38 → 差异 -2，生成 pending 草稿
    r1 = _post_stocktake(client, h, "B仓", [{"material_code": "M001", "actual_stock": 38}])
    assert r1.status_code == 200, r1.get_data(as_text=True)
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 1

    # 第二次盘 B仓 M001：必须被拒绝——否则两张 -2 草稿都提交会扣 4
    r2 = _post_stocktake(client, h, "B仓", [{"material_code": "M001", "actual_stock": 38}])
    assert r2.status_code == 400, (
        f"重复盘点应被拒绝，实际返回 {r2.status_code}：{r2.get_data(as_text=True)}"
    )
    msg = r2.get_json()["message"]
    assert "M001" in msg, f"提示应包含冲突物料编码，实际：{msg}"
    assert "ADJ" in msg, f"提示应包含存量调整单号，实际：{msg}"

    # 调整草稿数量不增（仍是 1 张）
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 1, (
        "重复盘点不得新增调整草稿，否则审核提交后库存被重复调整"
    )


def test_t2_different_material_allowed():
    """T2: 同仓库不同物料不受护栏影响。"""
    from app import AdjustmentOrder
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)

    r1 = _post_stocktake(client, h, "B仓", [{"material_code": "M001", "actual_stock": 38}])
    assert r1.status_code == 200
    # M002 与 M001 不冲突 → 放行（实盘 18 vs B仓账面 20，差异 -2 会生成草稿）
    r2 = _post_stocktake(client, h, "B仓", [{"material_code": "M002", "actual_stock": 18}])
    assert r2.status_code == 200, r2.get_data(as_text=True)
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 2


def test_t3_completed_draft_not_blocking():
    """T3: 已提交的存量草稿不拦截——库存已真实调整、账面已更新，再盘属合法。"""
    from app import AdjustmentOrder
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)

    r1 = _post_stocktake(client, h, "B仓", [{"material_code": "M001", "actual_stock": 38}])
    assert r1.status_code == 200
    # 模拟人工已审核提交第一张草稿（M001 差异 -2 已作用于库存，B仓账面 40→38）
    draft = AdjustmentOrder.query.filter_by(source_type="check_scan").one()
    draft.status = "completed"
    db.session.commit()

    r2 = _post_stocktake(client, h, "B仓", [{"material_code": "M001", "actual_stock": 38}])
    assert r2.status_code == 200, (
        f"存量草稿已提交后应放行合法二次盘点，实际：{r2.get_data(as_text=True)}"
    )
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 2


def test_t4_different_warehouse_allowed():
    """T4: 不同仓库同物料放行——仓库级账面互不影响。"""
    from app import AdjustmentOrder
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)

    r1 = _post_stocktake(client, h, "B仓", [{"material_code": "M001", "actual_stock": 38}])
    assert r1.status_code == 200
    # M001 换到 A仓盘点（账面 60，实盘 58，差异 -2），与 B仓的 pending 草稿不冲突
    r2 = _post_stocktake(client, h, "A仓", [{"material_code": "M001", "actual_stock": 58}])
    assert r2.status_code == 200, r2.get_data(as_text=True)
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 2


def test_t5_mobile_web_scan_submit_also_guarded():
    """T5: 手机端 Web 入口 /mobile/api/scan_submit 走同一护栏。"""
    from app import AdjustmentOrder
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)

    # 第一次：Android 入口盘 B仓 M001（账面 40，实盘 38）
    r1 = _post_stocktake(client, h, "B仓", [{"material_code": "M001", "actual_stock": 38}])
    assert r1.status_code == 200
    # 第二次：Web 手机端入口盘同一物料 → 同样被拒
    r2 = client.post("/mobile/api/scan_submit", headers=h, json={
        "mode": "check",
        "code": "M001",
        "warehouse": "B仓",
        "actual_stock": 38,
    })
    assert r2.status_code == 400, (
        f"Web 手机端重复盘点应被同一护栏拦截，实际返回 {r2.status_code}"
    )
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 1

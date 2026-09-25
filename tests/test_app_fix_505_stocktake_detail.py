# -*- coding: utf-8 -*-
"""AI-APP-FIX-505 回归：Android 盘点记录差异明细下钻
（GET /api/mobile/stocktake/detail）。

背景：盘点记录回查列表只有 item_count/diff_count 汇总，作业员对账时
看不到"具体哪个物料、账面多少、实盘多少、差多少"，下钻链路中断。

覆盖：
T1. 明细字段齐全（编码/名称/账面/实盘/差异/is_diff），差异行排在前面
T2. 仅本人记录可下钻（他人 id → 404，不暴露存在性）；缺 id → 400
T3. 未认证（无 Bearer）→ 401
T4. 只读性：不产生任何写操作
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
               lines=None):
    """建一张扫码盘点单（含明细）。lines = [(material, system, actual)]。"""
    from app import InventoryCheckScan, InventoryCheckScanItem
    scan = InventoryCheckScan(
        check_no=check_no,
        date=date.today(),
        warehouse=warehouse,
        remark="Android盘点：all",
        status=status,
        operator_id=operator.id,
        created_at=datetime.now(),
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


def _seed_scene():
    _reset_db()
    me = _seed_user("fx_me", role="warehouse", password="me")
    other = _seed_user("fx_other", role="warehouse", password="other")
    _seed_warehouse("FXA", "A仓", is_default=True)
    m1 = _seed_material("M-FX-1", 100.0)
    m2 = _seed_material("M-FX-2", 50.0)
    return me, other, m1, m2


def _detail(client, headers, scan_id):
    return client.get(f"/api/mobile/stocktake/detail?id={scan_id}",
                      headers=headers)


def test_t1_detail_fields_and_diff_first():
    """T1: 明细字段齐全，差异行排在前面。"""
    me, other, m1, m2 = _seed_scene()
    client = _make_client()
    h = _bearer(client, "fx_me", "me")
    scan = _seed_scan("FX-CS-1", "A仓", me,
                      lines=[(m1, 100.0, 100.0), (m2, 50.0, 47.0)])

    r = _detail(client, h, scan.id)
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()["data"]
    assert data["check_no"] == "FX-CS-1"
    assert data["warehouse"] == "A仓"
    assert data["status"] == "completed"
    items = data["items"]
    assert len(items) == 2
    # 差异行（M-FX-2，差 -3）必须排在无差异行之前
    assert items[0]["material_code"] == "M-FX-2", items
    assert items[0]["is_diff"] is True
    assert items[0]["system_stock"] == 50.0
    assert items[0]["actual_stock"] == 47.0
    assert items[0]["difference"] == -3.0
    assert items[1]["material_code"] == "M-FX-1"
    assert items[1]["is_diff"] is False
    for key in ("material_code", "material_name", "spec", "brand", "unit",
                "area", "system_stock", "actual_stock", "difference",
                "is_diff"):
        assert key in items[0], f"缺字段 {key}"


def test_t2_scope_and_param_guard():
    """T2: 他人记录 404；缺 id 400；不存在的 id 404。"""
    me, other, m1, m2 = _seed_scene()
    client = _make_client()
    h = _bearer(client, "fx_me", "me")
    other_scan = _seed_scan("FX-CS-OTHER", "A仓", other,
                            lines=[(m1, 100.0, 99.0)])

    r = _detail(client, h, other_scan.id)
    assert r.status_code == 404, f"他人记录应 404，实际 {r.status_code}"

    r2 = client.get("/api/mobile/stocktake/detail", headers=h)
    assert r2.status_code == 400, f"缺 id 应 400，实际 {r2.status_code}"

    r3 = _detail(client, h, 999999)
    assert r3.status_code == 404, f"不存在的 id 应 404，实际 {r3.status_code}"


def test_t3_requires_bearer():
    """T3: 无 Bearer → 401。"""
    _seed_scene()
    r = app_module.app.test_client().get("/api/mobile/stocktake/detail?id=1")
    assert r.status_code == 401, f"未认证应 401，实际 {r.status_code}"


def test_t4_read_only():
    """T4: 下钻是只读接口，不产生任何写操作。"""
    from app import AdjustmentOrder, InventoryCheckScan
    me, other, m1, m2 = _seed_scene()
    client = _make_client()
    h = _bearer(client, "fx_me", "me")
    scan = _seed_scan("FX-CS-RO", "A仓", me, lines=[(m1, 100.0, 95.0)])

    before = (InventoryCheckScan.query.count(),
              AdjustmentOrder.query.count())
    for _ in range(3):
        assert _detail(client, h, scan.id).status_code == 200
    after = (InventoryCheckScan.query.count(),
             AdjustmentOrder.query.count())
    assert before == after, f"下钻接口不应写入数据：{before} → {after}"

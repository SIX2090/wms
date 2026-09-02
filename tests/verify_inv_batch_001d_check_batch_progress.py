# -*- coding: utf-8 -*-
"""INV-BATCH-001-D 回归：盘点批次（PC 盘点单）进度与行级归属回查。

背景：INV-BATCH-001-A/C 之后批次机制已通——手机扫码盘点自动挂靠到
同仓库最新 pending 的 PC 盘点单（批次），行级记录 counted_by/counted_at，
Web 完成盘点单即批次关闭。但 Web 盘点单详情页看不到批次视角：主管无法
回查"谁在何时盘了哪一行"、批次账面冻结时点、已盘进度、挂入了哪些扫码单。
本任务给盘点单详情页补上批次进度与回查能力：
- 行级归属列「盘点人 / 时间」（counted_by_user.username + counted_at）；
- 批次进度卡（frozen_at 冻结时点 / 已盘物料数 / 有差异行数 / 挂入的
  扫码盘点单列表：单号、日期、盘点人、提交时间、条数）。

覆盖：
T1. 空批次（pending 未扫）详情渲染：批次进度卡可见、未冻结提示、
    无扫码记录；归属列存在（order_id 非空）
T2. 手机扫码挂批次后详情回查：冻结时点已写入、已盘物料数=1、行级
    归属 counted_by_name=admin 出现在 existingItems JSON、挂入的扫码
    单号与"扫码提交 1 次"可见
T3. 批次完成（readonly）后详情仍可回查，行级归属与扫码记录不丢
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

from werkzeug.security import generate_password_hash  # noqa: E402

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


def _login_web(client):
    r = client.post("/login", data={"username": "admin", "password": "admin"})
    assert r.status_code in (302, 303), f"Web 登录失败：{r.status_code}"


def _seed_admin():
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()
    return u


def _seed_warehouse(code, name):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active")
    db.session.add(w)
    db.session.commit()
    return w


def _seed_material_with_warehouse_stock(code, global_stock, per_warehouse):
    """M001 全局 100；A 仓 60 / B 仓 40（双仓场景避免单仓全局兼容分支）。"""
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


def _seed_batch(admin, warehouse_name, check_no):
    """造一个活动批次（pending 的 PC 盘点单，未冻结、无明细）。"""
    from app import InventoryCheck
    check = InventoryCheck(
        check_no=check_no, warehouse=warehouse_name, status="pending",
        operator_id=admin.id, frozen_at=None,
    )
    db.session.add(check)
    db.session.commit()
    return check


def _scan_check(client, code, warehouse, actual):
    return client.post("/mobile/api/scan_submit", json={
        "mode": "check", "code": code, "warehouse": warehouse,
        "actual_stock": actual,
    })


def _scene():
    _reset_db()
    admin = _seed_admin()
    wh_a = _seed_warehouse("WA", "A仓")
    wh_b = _seed_warehouse("WB", "B仓")
    m1 = _seed_material_with_warehouse_stock("M001", 100.0, {wh_a: 60.0, wh_b: 40.0})
    return admin, m1


def test_t1_empty_batch_detail_shows_progress_card():
    """T1：空批次（pending 未扫）详情渲染批次进度卡与归属列。"""
    admin, _m1 = _scene()
    from app import InventoryCheck
    with app_module.app.app_context():
        batch = _seed_batch(admin, "A仓", "CK20260903-0001")
        batch_id = batch.id
    client = _make_client()
    _login_web(client)
    html = client.get(f"/check/{batch_id}").get_data(as_text=True)
    assert "批次进度" in html, "详情页必须展示批次进度卡"
    assert "尚未冻结账面" in html, "空批次未扫时应提示未冻结"
    assert "盘点人 / 时间" in html, "既有盘点单必须展示行级归属列表头"
    assert "扫码提交 0 次" in html
    assert "已盘 0 个物料" in html
    # 空批次不应有扫码单表格
    assert "CK20260903-0001" in html  # 盘点单号本身


def test_t2_scan_then_detail_shows_ownership_and_scan_log():
    """T2：手机扫码挂批次后，详情回查冻结时点/行级归属/扫码记录。"""
    admin, m1 = _scene()
    with app_module.app.app_context():
        batch = _seed_batch(admin, "A仓", "CK20260903-0002")
        batch_id, batch_no = batch.id, batch.check_no
    client = _make_client()
    _login_web(client)
    # 手机扫码挂批次（A 仓账面 60，实盘 8 → 差异 -52 行级归属 admin）
    r = _scan_check(client, "M001", "A仓", 8)
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body["status"] == "success", body
    assert body["data"].get("batch_no") == batch_no, "扫码应挂靠活动批次"

    html = client.get(f"/check/{batch_id}").get_data(as_text=True)
    assert "批次进度" in html
    assert "账面冻结于" in html, "扫码写入明细后批次应已冻结账面"
    assert "已盘 1 个物料" in html
    assert "扫码提交 1 次" in html
    assert f'"counted_by_name": "admin"' in html, "行级盘点人必须回传到详情页 JSON"
    assert '"counted_at": "' in html, "行级盘点时间必须回传到详情页 JSON"
    assert "盘点人 / 时间" in html
    assert m1.code in html
    # 扫码单留痕表格：CS 单号出现在批次进度卡
    from app import InventoryCheckScan
    with app_module.app.app_context():
        scan = InventoryCheckScan.query.filter_by(check_id=batch_id).first()
        assert scan is not None, "扫码应留痕 CS 单"
        scan_no = scan.check_no
    assert scan_no in html, f"挂入批次扫码单 {scan_no} 应在进度卡中可见"


def test_t3_completed_batch_detail_keeps_ownership():
    """T3：批次完成（只读）后，详情仍可回查行级归属与扫码记录。"""
    admin, _m1 = _scene()
    with app_module.app.app_context():
        batch = _seed_batch(admin, "A仓", "CK20260903-0003")
        batch_id = batch.id
    client = _make_client()
    _login_web(client)
    _scan_check(client, "M001", "A仓", 8)
    # 完成批次（统一生成调整草稿）
    complete = client.post(f"/check/{batch_id}/complete")
    assert complete.status_code == 200, complete.get_data(as_text=True)
    assert complete.get_json()["status"] == "success", complete.get_json()

    html = client.get(f"/check/{batch_id}").get_data(as_text=True)
    assert "批次进度" in html
    assert "查看库存盘点单" in html, "完成后为只读查看态"
    assert "账面冻结于" in html
    assert "已盘 1 个物料" in html
    assert f'"counted_by_name": "admin"' in html, "完成后行级盘点人仍可回查"
    assert "扫码提交 1 次" in html

# -*- coding: utf-8 -*-
"""FEATURE-2026-09-05-001 回归：新建盘点单支持按分类生成待盘明细。

业务背景：手机盘点必须挂 PC 端进行中盘点单（BUG-2026-09-04-005），但
"只盘某一类（如电线）"时没有一键建单手段，靠人工逐行加明细或 Excel
导入，且漏盘无法核对。本特性在新建盘点单时支持选择分类，后端按分类
（含子分类）为该分类下全部物料预生成"未盘"明细行：

- system_stock = 所选仓库的仓库级账面（与导入/表格同一口径）；
- actual_stock = system_stock、difference = 0、counted_at 为空 →
  未盘行完成盘点时不生成调整，详情页可按盘点人/时间列核对漏盘；
- 账面 0 的物料同样建行（账面 0 实物有货正是要盘出的盘盈）；
- 建行即冻结账面（frozen_at，与 save_check_table 首次写入语义一致）；
- 分类不存在 → 报错不落单；物料数超过 import_max_rows → 报错提示细分；
- 不选分类 → 保持原行为（空单，手机扫码自动加行）。

覆盖：
T1. 不选分类建单：无明细、无 frozen_at、返回无 msg（原行为不变）
T2. 选父分类建单：含子分类物料全部生成明细（含账面 0），账面取仓库级、
    未盘行语义（actual=system/diff=0/counted_at 空）、frozen_at 冻结
T3. 分类不存在 → 400，不落单
T4. 物料数超过 import_max_rows 上限 → 报错，不落单
T5. 未盘行完成盘点不生成调整；手机盘一行后完成盘点只对该行生成调整
T6. 模板静态契约：check.html 弹窗含 data-ks="category" 选择器与
    hidden category_id、提示文案
T7. 分类 parent_id 成环时 _expand_check_category_ids 不死循环
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


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


def _web_login(client):
    r = client.post("/login", data={"username": "admin", "password": "admin"},
                    follow_redirects=False)
    assert r.status_code in (302, 303), r.get_data(as_text=True)


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


def _seed_category(code, name, parent=None):
    from app import MaterialCategory
    c = MaterialCategory(code=code, name=name, parent_id=parent.id if parent else None)
    db.session.add(c)
    db.session.commit()
    return c


def _seed_material(code, category, stock_in_wh=None, warehouse=None):
    """建物料；stock_in_wh 非空时按仓库写流水（账面 = 仓库级聚合）。"""
    from app import Material, StockTransaction
    m = Material(code=code, name=f"物料{code}", stock=stock_in_wh or 0,
                 category_id=category.id if category else None)
    db.session.add(m)
    db.session.commit()
    if stock_in_wh and warehouse is not None:
        db.session.add(StockTransaction(
            material_id=m.id, transaction_type="in", quantity=stock_in_wh,
            location=warehouse.name, warehouse_id=warehouse.id,
            created_at=datetime.now()))
        db.session.commit()
    return m


def _seed_scene():
    """分类树：电线(父) → 电缆(子)；其他(独立)。仓库：A仓。"""
    _reset_db()
    _seed_admin()
    wh_a = _seed_warehouse("WA", "A仓", is_default=True)
    cat_wire = _seed_category("DX", "电线")
    cat_cable = _seed_category("DL", "电缆", parent=cat_wire)
    cat_other = _seed_category("QT", "其他")
    m1 = _seed_material("W001", cat_wire, stock_in_wh=10.0, warehouse=wh_a)
    m2 = _seed_material("W002", cat_cable, stock_in_wh=0, warehouse=None)  # 账面 0
    m3 = _seed_material("Q001", cat_other, stock_in_wh=5.0, warehouse=wh_a)
    return wh_a, cat_wire, cat_cable, cat_other, m1, m2, m3


def _post_add_check(client, warehouse="A仓", category_id=None, remark=""):
    data = {"warehouse": warehouse, "remark": remark}
    if category_id is not None:
        data["category_id"] = str(category_id)
    return client.post("/check/add", data=data)


# T1 ───────────────────────────────────────────────────────────────
def test_t1_no_category_keeps_legacy_behavior():
    """不选分类：建空单、无明细、无 frozen_at、响应无 msg 字段（原行为）。"""
    from app import InventoryCheck
    _seed_scene()
    client = _make_client()
    _web_login(client)
    r = _post_add_check(client, remark="抽盘")
    assert r.status_code == 200, r.get_data(as_text=True)
    payload = r.get_json()
    assert payload["status"] == "success"
    assert "msg" not in payload
    check = db.session.get(InventoryCheck, payload["id"])
    assert check is not None and check.status == "pending"
    assert len(check.items) == 0
    assert check.frozen_at is None


# T2 ───────────────────────────────────────────────────────────────
def test_t2_category_generates_items_including_children():
    """选父分类「电线」：含子分类「电缆」物料全部建行（含账面 0），
    账面取仓库级、未盘行语义正确、frozen_at 冻结、响应带行数提示。"""
    from app import InventoryCheck
    wh_a, cat_wire, _cat_cable, _cat_other, m1, m2, m3 = _seed_scene()
    client = _make_client()
    _web_login(client)
    r = _post_add_check(client, category_id=cat_wire.id, remark="电线月度盘点")
    assert r.status_code == 200, r.get_data(as_text=True)
    payload = r.get_json()
    assert payload["status"] == "success"
    assert "2 行待盘明细" in payload["msg"]
    check = db.session.get(InventoryCheck, payload["id"])
    by_mid = {it.material_id: it for it in check.items}
    # 电线 + 子分类电缆入选，其他分类不入选
    assert set(by_mid) == {m1.id, m2.id}
    assert m3.id not in by_mid
    # 仓库级账面：W001 在 A仓 10；W002 账面 0 也建行
    assert by_mid[m1.id].system_stock == 10.0
    assert by_mid[m2.id].system_stock == 0
    # 未盘行语义：actual=system、diff=0、无盘点人/时间
    for it in by_mid.values():
        assert it.actual_stock == it.system_stock
        assert abs(it.difference or 0) <= 1e-9
        assert it.counted_at is None
        assert it.counted_by is None
    # 建行即冻结账面
    assert check.frozen_at is not None


# T3 ───────────────────────────────────────────────────────────────
def test_t3_category_not_found_rejected():
    """category_id 不存在 → 报错，不落单。"""
    from app import InventoryCheck
    _seed_scene()
    client = _make_client()
    _web_login(client)
    before = InventoryCheck.query.count()
    r = _post_add_check(client, category_id=999999)
    assert r.status_code == 400, r.get_data(as_text=True)
    assert "分类不存在" in r.get_json()["msg"]
    assert InventoryCheck.query.count() == before


# T4 ───────────────────────────────────────────────────────────────
def test_t4_over_limit_rejected(monkeypatch):
    """分类物料数超过 import_max_rows → 报错提示细分，不落单。"""
    from app import InventoryCheck
    _seed_scene()
    monkeypatch.setattr(app_module, "import_max_rows", lambda: 1)
    client = _make_client()
    _web_login(client)
    before = InventoryCheck.query.count()
    cat_wire = app_module.MaterialCategory.query.filter_by(code="DX").one()
    r = _post_add_check(client, category_id=cat_wire.id)
    assert r.status_code == 400, r.get_data(as_text=True)
    msg = r.get_json()["msg"]
    assert "超过单次建单上限" in msg and "电线" in msg
    assert InventoryCheck.query.count() == before


# T5 ───────────────────────────────────────────────────────────────
def test_t5_uncounted_rows_no_adjustment_counted_row_adjusts():
    """未盘行（actual=system）完成盘点不生成调整；手机扫码盘一行后
    完成盘点只对该行生成调整草稿，其余未盘行不动。"""
    from app import AdjustmentOrder, InventoryCheck
    wh_a, cat_wire, _c, _o, m1, m2, _m3 = _seed_scene()
    client = _make_client()
    _web_login(client)
    r = _post_add_check(client, category_id=cat_wire.id)
    check = db.session.get(InventoryCheck, r.get_json()["id"])

    # 5a：全部未盘 → 完成盘点：成功、无调整草稿（BUG-2026-09-06-001
    # 修复后纯 PC 录入需 force=1 显式确认；手机补盘行写 counted_at 后
    # 无需 force，本测试 5b 步骤验证该路径）
    r_done = client.post(f"/check/{check.id}/complete", json={"force": 1})
    assert r_done.status_code == 200, r_done.get_data(as_text=True)
    assert "无库存差异" in r_done.get_json()["msg"]
    assert AdjustmentOrder.query.filter_by(source_type="check", source_id=check.id).count() == 0

    # 5b：反提交回 pending，手机扫码盘 m1（实盘 7，账面 10）→ 完成只调 m1
    # （m2 未盘，新设计下应弹 confirm；本步用 force=1 模拟用户确认放过）
    r_revert = client.post(f"/check/{check.id}/revert")
    assert r_revert.status_code == 200, r_revert.get_data(as_text=True)
    h = _bearer(client)
    r_scan = client.post("/mobile/api/scan_submit", headers=h, json={
        "mode": "check", "code": m1.code, "warehouse": "A仓",
        "actual_stock": 7, "check_id": check.id,
    })
    assert r_scan.status_code == 200, r_scan.get_data(as_text=True)
    # 不带 force 应弹 confirm（仅 m2 未盘）
    r_confirm = client.post(f"/check/{check.id}/complete")
    assert r_confirm.get_json().get("status") == "confirm"
    assert r_confirm.get_json().get("count") == 1
    r_done2 = client.post(f"/check/{check.id}/complete", json={"force": 1})
    assert r_done2.status_code == 200, r_done2.get_data(as_text=True)
    adjs = AdjustmentOrder.query.filter_by(source_type="check", source_id=check.id).all()
    assert len(adjs) == 1
    assert adjs[0].adjustment_type == "loss"
    adj_mids = {it.material_id for it in adjs[0].items}
    assert adj_mids == {m1.id}
    # 未盘的 m2 不进入任何调整
    assert m2.id not in adj_mids


# T6 ───────────────────────────────────────────────────────────────
def test_t6_template_contract():
    """check.html 新建弹窗含分类选择器契约（data-ks=category + hidden
    category_id + 用途提示），且提交处理使用后端 msg。"""
    tpl = (ROOT / "app" / "templates" / "check.html").read_text(encoding="utf-8")
    assert 'data-ks="category"' in tpl
    assert 'data-ks-id="#addCategoryId"' in tpl
    assert 'name="category_id" id="addCategoryId"' in tpl
    assert "自动生成全部物料的待盘明细" in tpl
    assert "res.msg || '盘点单已创建'" in tpl


# T7 ───────────────────────────────────────────────────────────────
def test_t7_category_cycle_no_deadloop():
    """parent_id 脏数据成环（A→B→A）时展开不死循环且收敛。"""
    from app.routes.check import _expand_check_category_ids
    _reset_db()
    _seed_admin()
    a = _seed_category("CA", "环A")
    b = _seed_category("CB", "环B", parent=a)
    a.parent_id = b.id  # 成环：A→B→A
    db.session.commit()
    ids = _expand_check_category_ids(a.id)
    assert set(ids) == {a.id, b.id}

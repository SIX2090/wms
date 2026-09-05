# -*- coding: utf-8 -*-
"""BUG-2026-09-05-005 / FEATURE-2026-09-05-002 回归：新建盘点单支持整仓全盘。

背景：FEATURE-2026-09-05-001 只支持"按一个分类"生成待盘明细，季度/年度
整仓大盘点需逐分类建单或退回 Excel 导入。本特性在新建盘点单弹窗加
「盘点范围」：不预生成（空单）/ 整仓全部物料 / 按分类，scope=all 时
为全部物料（含无分类物料）生成"未盘"明细行，行语义与按分类完全一致
（system=仓库账面、actual=system、diff=0、counted_at 空、建行即冻结）。

覆盖：
T1. scope=all：全部物料（含无分类）建行，仓库级账面、未盘语义、冻结、msg
T2. scope=all 超 import_max_rows → 400 不落单
T3. scope=all 但系统无物料 → 空单 + 明确提示
T4. scope=all 与 category_id 同时给出 → scope 优先（整仓，不受分类约束）
T5. 模板契约：范围三选项 + 分类容器默认隐藏 + 联动清空 JS
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


def _client():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()
    c = app_module.app.test_client()
    r = c.post("/login", data={"username": "admin", "password": "admin"})
    assert r.status_code in (302, 303), r.get_data(as_text=True)
    return c


def _seed_base():
    from app import Warehouse
    _reset_db()
    wh = Warehouse(code="WA", name="A仓", status="active", is_default=True)
    db.session.add(wh)
    db.session.commit()
    return wh


def _seed_material(code, category_id=None, stock_in_wh=0, warehouse=None):
    from app import Material, StockTransaction
    m = Material(code=code, name=f"物料{code}", stock=stock_in_wh,
                 category_id=category_id)
    db.session.add(m)
    db.session.commit()
    if stock_in_wh and warehouse is not None:
        db.session.add(StockTransaction(
            material_id=m.id, transaction_type="in", quantity=stock_in_wh,
            location=warehouse.name, warehouse_id=warehouse.id,
            created_at=datetime.now()))
        db.session.commit()
    return m


def _post_add(client, **form):
    data = {"warehouse": "A仓", "remark": ""}
    data.update({k: str(v) for k, v in form.items()})
    return client.post("/check/add", data=data)


# T1 ───────────────────────────────────────────────────────────────
def test_t1_scope_all_generates_rows_for_every_material():
    from app import InventoryCheck
    wh = _seed_base()
    client = _client()
    m1 = _seed_material("A001", stock_in_wh=10.0, warehouse=wh)
    m2 = _seed_material("B002")  # 账面 0 无分类
    m3 = _seed_material("C003", stock_in_wh=3.0, warehouse=wh)
    r = _post_add(client, scope="all")
    assert r.status_code == 200, r.get_data(as_text=True)
    payload = r.get_json()
    assert "整仓全部物料生成 3 行待盘明细" in payload["msg"]
    check = db.session.get(InventoryCheck, payload["id"])
    by_mid = {it.material_id: it for it in check.items}
    assert set(by_mid) == {m1.id, m2.id, m3.id}
    assert by_mid[m1.id].system_stock == 10.0
    assert by_mid[m2.id].system_stock == 0
    assert by_mid[m3.id].system_stock == 3.0
    for it in by_mid.values():
        assert it.actual_stock == it.system_stock
        assert abs(it.difference or 0) <= 1e-9
        assert it.counted_at is None
    assert check.frozen_at is not None


# T2 ───────────────────────────────────────────────────────────────
def test_t2_scope_all_over_limit_rejected(monkeypatch):
    from app import InventoryCheck
    wh = _seed_base()
    _client()
    _seed_material("A001", stock_in_wh=1.0, warehouse=wh)
    _seed_material("B002")
    monkeypatch.setattr(app_module, "import_max_rows", lambda: 1)
    client = app_module.app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"})
    before = InventoryCheck.query.count()
    r = _post_add(client, scope="all")
    assert r.status_code == 400, r.get_data(as_text=True)
    assert "超过单次建单上限" in r.get_json()["msg"]
    assert InventoryCheck.query.count() == before


# T3 ───────────────────────────────────────────────────────────────
def test_t3_scope_all_no_materials_empty_order():
    from app import InventoryCheck
    _seed_base()
    client = _client()
    r = _post_add(client, scope="all")
    assert r.status_code == 200, r.get_data(as_text=True)
    payload = r.get_json()
    assert "当前无任何物料，已创建空盘点单" in payload["msg"]
    check = db.session.get(InventoryCheck, payload["id"])
    assert len(check.items) == 0
    assert check.frozen_at is None


# T4 ───────────────────────────────────────────────────────────────
def test_t4_scope_all_wins_over_category():
    from app import InventoryCheck, MaterialCategory
    wh = _seed_base()
    client = _client()
    cat = MaterialCategory(code="DX", name="电线")
    db.session.add(cat)
    db.session.commit()
    m1 = _seed_material("W001", category_id=cat.id, stock_in_wh=5.0, warehouse=wh)
    m2 = _seed_material("Q001", stock_in_wh=2.0, warehouse=wh)  # 其他类
    r = _post_add(client, scope="all", category_id=cat.id)
    assert r.status_code == 200, r.get_data(as_text=True)
    check = db.session.get(InventoryCheck, r.get_json()["id"])
    assert {it.material_id for it in check.items} == {m1.id, m2.id}


# T5 ───────────────────────────────────────────────────────────────
def test_t5_template_contract():
    tpl = (ROOT / "app" / "templates" / "check.html").read_text(encoding="utf-8")
    assert 'name="scope" id="addScopeSelect"' in tpl
    assert 'value="all"' in tpl and "整仓全部物料（全盘）" in tpl
    assert 'value="category"' in tpl and "按分类生成（含子分类）" in tpl
    assert 'id="addCategoryWrap"' in tpl and "d-none" in tpl
    # 联动：切到按分类才显示，切走清空分类值
    assert "this.value === 'category'" in tpl
    assert "hid.value = ''" in tpl

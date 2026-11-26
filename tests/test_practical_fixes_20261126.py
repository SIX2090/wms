# -*- coding: utf-8 -*-
"""2026-11-26 轻量实用问题 6 项修复回归测试。

遵守 A12 / R7：禁止模块顶层裸 app_context().push()；全部在函数级隔离内存库夹具中运行。
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import sys

import pytest
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _prepare_clean_env():
    import app as wms

    wms.app.config["TESTING"] = True
    wms.app.config["WTF_CSRF_ENABLED"] = False
    wms.db.session.remove()
    wms.db.drop_all()
    wms.db.create_all()
    user = wms.User(
        username="fix20261126_admin",
        password_hash=generate_password_hash("fixture-only"),
        role="admin",
        must_change_password=False,
    )
    wh1 = wms.Warehouse(code="WH-F1", name="一号主仓", status="active", is_default=True)
    wh2 = wms.Warehouse(code="WH-F2", name="二号分仓", status="active", is_default=False)
    unit = wms.Unit(code="PCS", name="个")
    supplier = wms.Supplier(code="SUP-F1", name="一号供应商")
    wms.db.session.add_all([user, wh1, wh2, unit, supplier])
    wms.db.session.flush()
    mat = wms.Material(code="MAT-F1", name="测试物料A", spec="S1", unit_id=unit.id, price=10.0, stock=0.0)
    wms.db.session.add(mat)
    wms.db.session.commit()
    return wms, {"user": user, "wh1": wh1, "wh2": wh2, "unit": unit, "supplier": supplier, "mat": mat}


def _login_client(wms, user):
    client = wms.app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True
    return client


@pytest.fixture
def env():
    import app as wms

    with wms.app.app_context():
        _, ctx = _prepare_clean_env()
        ctx["client"] = _login_client(wms, ctx["user"])
        yield wms, ctx
        wms.db.session.remove()


def test_fix1_balance_rounding_footnote_and_ledger_untouched(env):
    """修复 1：造 2 位舍入产生 0.01 尾差数据，报表显著展示尾差脚注且底层三账数值不变。"""
    wms, ctx = env
    wh1, mat, user = ctx["wh1"], ctx["mat"], ctx["user"]
    # 期初 0.004 + 本期入库 0.004 = 期末 0.008：
    # 两位显示舍入下 round(0.004,2)+round(0.004,2)=0.00 != round(0.008,2)=0.01（0.01 尾差）
    mat.stock = 0.008
    wms.db.session.add_all([
        wms.StockTransaction(
            material_id=mat.id,
            transaction_type="opening",
            quantity=0.004,
            warehouse_id=wh1.id,
            location=wh1.name,
            operator_id=user.id,
            created_at=datetime(2026, 10, 1, 10, 0, 0),
        ),
        wms.StockTransaction(
            material_id=mat.id,
            transaction_type="in",
            quantity=0.004,
            warehouse_id=wh1.id,
            location=wh1.name,
            operator_id=user.id,
            created_at=datetime(2026, 11, 5, 10, 0, 0),
        ),
    ])
    wms.db.session.commit()

    footnote = "期初+本期入库−本期出库 与期末可能存在 ≤0.01 的舍入尾差，属显示口径，非账务错误"
    for report_type in ("ledger", "material_movement", "warehouse_monthly"):
        resp = ctx["client"].get(f"/report/view/{report_type}")
        assert resp.status_code == 200
        assert footnote in resp.get_data(as_text=True), f"{report_type} 页面缺少舍入尾差脚注"

    api_resp = ctx["client"].get(
        "/report/api/ledger",
        query_string={
            "warehouse_id": wh1.id,
            "material_code": mat.code,
            "start_date": "2026-11-01",
            "end_date": "2026-11-30",
        },
    )
    assert api_resp.status_code == 200
    payload = api_resp.get_json()
    closing = next(row for row in payload["data"] if row["reference_type"] == "本期合计")
    assert "期初 + 本期入库 − 本期出库 = 期末结存" in closing["remark"]
    assert footnote in closing["remark"]
    # 底层数值不得被改动以掩盖尾差
    assert round(closing["opening_quantity"], 2) + round(closing["in_quantity"], 2) == 0.0
    assert round(closing["balance_quantity"], 2) == 0.01
    assert closing["balance_quantity"] == pytest.approx(0.008)
    assert wms.db.session.get(wms.Material, mat.id).stock == pytest.approx(0.008)
    assert wms.StockTransaction.query.count() == 2


def test_fix2_check_complete_notice_without_stock_change(env):
    """修复 2：完成有差异的盘点单后页面和盘点报表可见提示，且此时库存账未变动。"""
    wms, ctx = env
    wh1, mat, user = ctx["wh1"], ctx["mat"], ctx["user"]
    mat.stock = 100.0
    wms.db.session.add(
        wms.StockTransaction(
            material_id=mat.id,
            transaction_type="opening",
            quantity=100.0,
            warehouse_id=wh1.id,
            location=wh1.name,
            operator_id=user.id,
            created_at=datetime(2026, 11, 20, 9, 0, 0),
        )
    )
    check = wms.InventoryCheck(
        check_no="CK-FIX2-001",
        date=date(2026, 11, 25),
        warehouse=wh1.name,
        status="pending",
        operator_id=user.id,
        frozen_at=datetime(2026, 11, 25, 10, 0, 0),
    )
    wms.db.session.add(check)
    wms.db.session.flush()
    wms.db.session.add(
        wms.InventoryCheckItem(
            inventory_check_id=check.id,
            material_id=mat.id,
            system_stock=100.0,
            actual_stock=115.0,
            difference=15.0,
            counted_by=user.id,
            counted_at=datetime(2026, 11, 25, 10, 5, 0),
        )
    )
    wms.db.session.commit()

    notice = "盘点自身不改动库存；差异需待生成的调整单提交后才体现在库存。"
    resp = ctx["client"].post(f"/check/{check.id}/complete", json={})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["status"] == "success", body
    assert notice in body["msg"]
    assert wms.AdjustmentOrder.query.filter_by(source_type="check", source_id=check.id).count() == 1
    assert wms.db.session.get(wms.Material, mat.id).stock == pytest.approx(100.0)
    assert wms.StockTransaction.query.count() == 1

    detail_resp = ctx["client"].get(f"/check/{check.id}")
    assert detail_resp.status_code == 200
    assert notice in detail_resp.get_data(as_text=True)

    report_resp = ctx["client"].get("/report/view/check")
    assert report_resp.status_code == 200
    assert notice in report_resp.get_data(as_text=True)


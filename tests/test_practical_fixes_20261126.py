# -*- coding: utf-8 -*-
"""2026-11-26 轻量实用问题 6 项修复回归测试。

遵守 A12 / R7：禁止模块顶层裸 app_context().push()；全部在函数级隔离内存库夹具中运行。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
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


def test_count_null_warehouse_transactions(env):
    """修复 3（A9 对应函数锁）：只读统计 warehouse_id 为空的历史流水条数。"""
    from services.warehouse_stock_service import count_null_warehouse_transactions

    wms, ctx = env
    wh1, mat, user = ctx["wh1"], ctx["mat"], ctx["user"]
    assert count_null_warehouse_transactions() == 0
    wms.db.session.add(
        wms.StockTransaction(
            material_id=mat.id,
            transaction_type="in",
            quantity=50.0,
            warehouse_id=wh1.id,
            location=wh1.name,
            operator_id=user.id,
            created_at=datetime(2026, 11, 10, 9, 0, 0),
        )
    )
    wms.db.session.commit()
    assert count_null_warehouse_transactions() == 0

    null_txn = wms.StockTransaction(
        material_id=mat.id,
        transaction_type="in",
        quantity=25.0,
        warehouse_id=None,
        location=None,
        operator_id=user.id,
        created_at=datetime(2026, 11, 12, 9, 0, 0),
    )
    wms.db.session.add(null_txn)
    wms.db.session.commit()
    assert count_null_warehouse_transactions() == 1
    assert wms.db.session.get(wms.StockTransaction, null_txn.id).warehouse_id is None


def test_fix3_null_warehouse_txn_notice_keeps_numbers_unchanged(env):
    """修复 3：造一条 NULL 仓流水，按仓查询数字不变且显示提示，NULL 保持不回填。"""
    wms, ctx = env
    wh1, mat, user = ctx["wh1"], ctx["mat"], ctx["user"]
    mat.stock = 50.0
    wms.db.session.add(
        wms.StockTransaction(
            material_id=mat.id,
            transaction_type="in",
            quantity=50.0,
            warehouse_id=wh1.id,
            location=wh1.name,
            operator_id=user.id,
            created_at=datetime(2026, 11, 10, 9, 0, 0),
        )
    )
    wms.db.session.commit()

    notice = "存在 warehouse_id 为空的历史流水，按仓统计不包含这部分"
    clean_html = ctx["client"].get(f"/stock_query?warehouse_id={wh1.id}").get_data(as_text=True)
    assert "50.00" in clean_html
    assert notice not in clean_html

    # 造一条 warehouse_id IS NULL 且无归属的历史流水
    mat.stock = 75.0
    null_txn = wms.StockTransaction(
        material_id=mat.id,
        transaction_type="in",
        quantity=25.0,
        warehouse_id=None,
        location=None,
        operator_id=user.id,
        created_at=datetime(2026, 11, 12, 9, 0, 0),
    )
    wms.db.session.add(null_txn)
    wms.db.session.commit()

    # 按仓查询页：数字仍为 50.00（不猜归属、不回填），但可见明确提示
    after_html = ctx["client"].get(f"/stock_query?warehouse_id={wh1.id}").get_data(as_text=True)
    assert "50.00" in after_html
    assert "75.00" not in after_html
    assert notice in after_html

    all_wh_html = ctx["client"].get("/stock_query?warehouse_id=0").get_data(as_text=True)
    assert "50.00" in all_wh_html
    assert notice in all_wh_html

    for report_type in ("inventory", "warehouse_monthly", "material_movement", "ledger"):
        r_html = ctx["client"].get(f"/report/view/{report_type}").get_data(as_text=True)
        assert notice in r_html, f"{report_type} 缺少空仓库历史流水提示"

    monthly_api = ctx["client"].get(
        "/report/api/warehouse_monthly",
        query_string={"warehouse_id": wh1.id, "start_month": "2026-11", "end_month": "2026-11"},
    ).get_json()
    row = next(r for r in monthly_api["data"] if r["material_code"] == mat.code)
    assert row["ending_quantity"] == pytest.approx(50.0)
    # 确认 NULL 未被猜测回填
    assert wms.db.session.get(wms.StockTransaction, null_txn.id).warehouse_id is None


def test_is_within_duplicate_check_window():
    """修复 4（A9 对应函数锁）：近 7 天窗口边界校验（含当天与第 7 天前，不含第 8 天及未来）。"""
    from services.document_duplicate import DUPLICATE_ORDER_LOOKBACK_DAYS, is_within_duplicate_check_window

    assert DUPLICATE_ORDER_LOOKBACK_DAYS == 7
    anchor = date(2026, 11, 26)
    assert is_within_duplicate_check_window(anchor, anchor) is True
    assert is_within_duplicate_check_window(anchor - timedelta(days=1), anchor) is True
    assert is_within_duplicate_check_window(anchor - timedelta(days=3), anchor) is True
    assert is_within_duplicate_check_window(anchor - timedelta(days=7), anchor) is True
    assert is_within_duplicate_check_window(anchor - timedelta(days=8), anchor) is False
    assert is_within_duplicate_check_window(anchor + timedelta(days=1), anchor) is False
    assert is_within_duplicate_check_window(None, anchor) is False


def test_format_duplicate_order_warning_msg():
    """修复 4（A9 对应函数锁）：当天提示今天单据，补录历史单据明确标注同日日期。"""
    from types import SimpleNamespace
    from services.document_duplicate import format_duplicate_order_warning_msg

    anchor = date(2026, 11, 26)
    today_order = SimpleNamespace(date=anchor, items=[1, 2])
    backdated_order = SimpleNamespace(date=anchor - timedelta(days=3), items=[1])
    other = SimpleNamespace(order_no="IN-DUP-001")
    msg_today = format_duplicate_order_warning_msg(today_order, other, anchor)
    assert "与今天单据 IN-DUP-001 一致" in msg_today and "疑似重复录入" in msg_today
    msg_back = format_duplicate_order_warning_msg(backdated_order, other, anchor)
    assert "与2026-11-23 同日单据 IN-DUP-001 一致" in msg_back and "疑似重复录入" in msg_back


def test_fix4_backdated_duplicate_orders_warn_within_7_days(env):
    """修复 4：昨天与 3 天前的重复入/出库单完成前均弹疑似重复录入提示；超 7 天或明细不同不误报。"""
    wms, ctx = env
    wh1, mat, user, supplier = ctx["wh1"], ctx["mat"], ctx["user"], ctx["supplier"]
    today = date.today()
    yesterday = today - timedelta(days=1)
    three_days_ago = today - timedelta(days=3)
    eight_days_ago = today - timedelta(days=8)

    # 预置库存供出库单完成前检测
    mat.stock = 500.0
    wms.db.session.add(
        wms.StockTransaction(
            material_id=mat.id,
            transaction_type="opening",
            quantity=500.0,
            warehouse_id=wh1.id,
            location=wh1.name,
            operator_id=user.id,
            created_at=datetime.combine(today - timedelta(days=15), datetime.min.time()),
        )
    )

    def _make_in(order_no, order_date, qty, status="pending"):
        order = wms.InOrder(
            order_no=order_no,
            date=order_date,
            business_type="采购入库",
            supplier_id=supplier.id,
            warehouse=wh1.name,
            status=status,
            operator_id=user.id,
        )
        wms.db.session.add(order)
        wms.db.session.flush()
        wms.db.session.add(
            wms.InOrderItem(
                in_order_id=order.id,
                material_id=mat.id,
                quantity=qty,
                price=10.0,
                amount=qty * 10.0,
            )
        )
        wms.db.session.commit()
        return order

    def _make_out(order_no, order_date, qty, status="pending"):
        order = wms.OutOrder(
            order_no=order_no,
            date=order_date,
            business_type="其他出库",
            customer="测试客户甲",
            warehouse=wh1.name,
            status=status,
            operator_id=user.id,
        )
        wms.db.session.add(order)
        wms.db.session.flush()
        wms.db.session.add(
            wms.OutOrderItem(
                out_order_id=order.id,
                material_id=mat.id,
                quantity=qty,
                price=10.0,
                amount=qty * 10.0,
            )
        )
        wms.db.session.commit()
        return order

    # 昨天入库单重复
    _make_in("IN-YEST-1", yesterday, 20, status="completed")
    in_yest_dup = _make_in("IN-YEST-2", yesterday, 20, status="pending")
    r_yest = ctx["client"].post(f"/in_order/{in_yest_dup.id}/check_anomalies").get_json()
    assert r_yest["has_anomalies"] is True
    assert r_yest["anomalies"][0]["existing_order"] == "IN-YEST-1"
    assert "疑似重复录入" in r_yest["anomalies"][0]["msg"]

    # 3 天前入库单重复：完成前阻断并弹疑似重复提示
    _make_in("IN-3D-1", three_days_ago, 30, status="completed")
    in_3d_dup = _make_in("IN-3D-2", three_days_ago, 30, status="pending")
    r_3d_complete = ctx["client"].post(f"/in_order/{in_3d_dup.id}/complete", json={}).get_json()
    assert r_3d_complete["status"] == "warning"
    assert "疑似重复录入" in r_3d_complete["anomalies"][0]["msg"]
    assert wms.db.session.get(wms.InOrder, in_3d_dup.id).status == "pending"

    # 3 天前明细数量不同不误报
    in_3d_diff = _make_in("IN-3D-DIFF", three_days_ago, 35, status="pending")
    assert wms._check_in_order_anomalies(in_3d_diff) == []

    # 8 天前超出 7 天窗口不提醒
    _make_in("IN-8D-1", eight_days_ago, 40, status="completed")
    in_8d_dup = _make_in("IN-8D-2", eight_days_ago, 40, status="pending")
    assert wms._check_in_order_anomalies(in_8d_dup) == []

    # R6 同类：3 天前出库单重复同样拦截提示
    _make_out("OUT-3D-1", three_days_ago, 15, status="completed")
    out_3d_dup = _make_out("OUT-3D-2", three_days_ago, 15, status="pending")
    r_out_complete = ctx["client"].post(f"/out_order/{out_3d_dup.id}/complete", json={}).get_json()
    assert r_out_complete["status"] == "warning"
    assert "疑似重复录入" in r_out_complete["anomalies"][0]["msg"]
    assert wms.db.session.get(wms.OutOrder, out_3d_dup.id).status == "pending"


def test_fix5_transfer_removes_dead_cancelled_and_adjustment_keeps_active_withdrawn(env):
    """修复 5：调拨单下拉与后端过滤移除永不写入的 cancelled；调整单已撤回(cancelled)为真实活跃状态，保持可查。"""
    wms, ctx = env
    wh1, wh2, mat, user = ctx["wh1"], ctx["wh2"], ctx["mat"], ctx["user"]

    # 1. 调拨单：创建一条草稿调拨单，验证筛选下拉不再含 cancelled，且传 status=cancelled 与全部一致
    transfer = wms.TransferOrder(
        transfer_no="TF-FIX5-001",
        date=date(2026, 11, 25),
        from_warehouse=wh1.name,
        to_warehouse=wh2.name,
        from_location=wh1.name,
        to_location=wh2.name,
        status="pending",
        operator_id=user.id,
    )
    wms.db.session.add(transfer)
    wms.db.session.commit()

    page_html = ctx["client"].get("/transfer").get_data(as_text=True)
    assert 'value="cancelled"' not in page_html
    assert "已取消" not in page_html
    assert "TF-FIX5-001" in page_html

    # 传入已移除的 status=cancelled 时被 _get_order_list_filters 忽略，列表行为与下拉一致
    ignored_html = ctx["client"].get("/transfer?status=cancelled").get_data(as_text=True)
    assert "TF-FIX5-001" in ignored_html

    # 2. 调整单：验证 cancelled(已撤回) 为真实可达状态（盘点完成->调整入账->调整反提交->盘点反提交）
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
        check_no="CK-FIX5-001",
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
            actual_stock=105.0,
            difference=5.0,
            counted_by=user.id,
            counted_at=datetime(2026, 11, 25, 10, 5, 0),
        )
    )
    wms.db.session.commit()

    assert ctx["client"].post(f"/check/{check.id}/complete", json={}).get_json()["status"] == "success"
    adj = wms.AdjustmentOrder.query.filter_by(source_type="check", source_id=check.id).one()
    assert ctx["client"].post(f"/adjustment/{adj.id}/complete", json={}).get_json()["status"] == "success"
    assert ctx["client"].post(f"/adjustment/{adj.id}/revert", json={}).get_json()["status"] == "success"
    assert ctx["client"].post(f"/check/{check.id}/revert", json={}).get_json()["status"] == "success"
    assert wms.db.session.get(wms.AdjustmentOrder, adj.id).status == "cancelled"

    adj_html = ctx["client"].get(f"/adjustment?warehouse_id={wh1.id}&status=cancelled").get_data(as_text=True)
    assert adj.adjustment_no in adj_html
    assert "已撤回" in adj_html


def test_fix6_revert_flow_footnote_preserves_ending_balance(env):
    """修复 6：造一张反提交入库单，月报与收发存明确标注含反冲流水，且期末结存与底层流水不变。"""
    wms, ctx = env
    wh1, mat, user, supplier = ctx["wh1"], ctx["mat"], ctx["user"], ctx["supplier"]
    mat.stock = 100.0
    wms.db.session.add(
        wms.StockTransaction(
            material_id=mat.id,
            transaction_type="opening",
            quantity=100.0,
            warehouse_id=wh1.id,
            location=wh1.name,
            operator_id=user.id,
            created_at=datetime(2026, 10, 15, 9, 0, 0),
        )
    )
    order = wms.InOrder(
        order_no="IN-FIX6-001",
        date=date(2026, 11, 10),
        business_type="采购入库",
        supplier_id=supplier.id,
        warehouse=wh1.name,
        status="pending",
        operator_id=user.id,
    )
    wms.db.session.add(order)
    wms.db.session.flush()
    wms.db.session.add(
        wms.InOrderItem(
            in_order_id=order.id,
            material_id=mat.id,
            quantity=20.0,
            price=10.0,
            amount=200.0,
        )
    )
    wms.db.session.commit()

    # 完成后再反提交，生成 in(+20) 与 revert_in(-20) 配对流水
    assert ctx["client"].post(f"/in_order/{order.id}/complete", json={"force": True}).get_json()["status"] == "success"
    assert ctx["client"].post(f"/in_order/{order.id}/revert", json={}).get_json()["status"] == "success"
    txns = wms.StockTransaction.query.filter_by(material_id=mat.id).order_by(wms.StockTransaction.id).all()
    assert [(t.transaction_type, t.quantity) for t in txns] == [
        ("opening", 100.0),
        ("in", 20.0),
        ("revert_in", -20.0),
    ]
    assert wms.db.session.get(wms.Material, mat.id).stock == pytest.approx(100.0)

    footnote = "含反冲流水，如需净额口径请按 revert_* 配对抵销后查看"
    for report_type in ("warehouse_monthly", "material_movement"):
        page_html = ctx["client"].get(f"/report/view/{report_type}").get_data(as_text=True)
        assert footnote in page_html, f"{report_type} 页面缺少反冲流水说明"

    monthly = ctx["client"].get(
        "/report/api/warehouse_monthly",
        query_string={"warehouse_id": wh1.id, "start_month": "2026-11", "end_month": "2026-11"},
    ).get_json()
    m_row = next(r for r in monthly["data"] if r["material_code"] == mat.code)
    assert m_row["beginning_quantity"] == pytest.approx(100.0)
    assert m_row["in_quantity"] == pytest.approx(20.0)
    assert m_row["out_quantity"] == pytest.approx(20.0)
    assert m_row["ending_quantity"] == pytest.approx(100.0)
    assert footnote in m_row["remark"]

    movement = ctx["client"].get(
        "/report/api/material_movement",
        query_string={
            "warehouse_id": wh1.id,
            "start_date": "2026-11-01",
            "end_date": "2026-11-30",
        },
    ).get_json()
    mv_row = next(r for r in movement["data"] if r["material_code"] == mat.code)
    assert mv_row["opening_quantity"] == pytest.approx(100.0)
    assert mv_row["in_quantity"] == pytest.approx(20.0)
    assert mv_row["out_quantity"] == pytest.approx(20.0)
    assert mv_row["balance_quantity"] == pytest.approx(100.0)






# -*- coding: utf-8 -*-
"""P0 批次/有效期捕获 —— Excel 批量导入（batch_import）端到端落库。

背景：仓库大量入库单是从 Excel 导进来的（用户提供现成表格）。若批量导入
不支持批次/有效期列，用户就必须手改单子，P0 的「批次捕获」在真实业务里
等于没落地。本测试用真实 xlsx 走完整导入链路，验证：

  T1. Excel 含「批次」「有效期」两列时，导入后明细行两列正确落库
  T2. 不提供这两列时导入照常成功（向后兼容，存量模板不受影响）
  T3. 有效期列写法非法时该行被跳过并给出原因（不静默写脏数据）

Excel 单元格里的日期既可能是文本（2026-09-01），也可能是真实日期单元格；
T1 同时覆盖「文本写法」与 date 对象两种来源，防止 datetime 带时间写库。
"""
from __future__ import annotations

import io
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import db, Warehouse, User, Material, InOrder, InOrderItem  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    from werkzeug.security import generate_password_hash
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    db.session.add_all([wh, user])
    db.session.commit()


def _make_client():
    client = app_module.app.test_client()
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post(
        "/login",
        data={"username": "admin", "password": "admin", "csrf_token": token},
    )
    return client


def _build_xlsx(header, rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(header)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _post_import(client, header, rows, name="in.xlsx"):
    buf = _build_xlsx(header, rows)
    return client.post(
        "/import/in_order",
        data={"file": (buf, name)},
        content_type="multipart/form-data",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )


BASE_HEADER = ["单据编号", "日期", "仓库", "供应商", "物料编码", "物料名称", "数量", "单价"]


def test_T1_batch_and_expiry_columns_persist():
    """含批次/有效期列（文本写法 + 真实日期单元格）→ 正确落库。"""
    with app_module.app.app_context():
        _reset_db()
        _seed()

    header = BASE_HEADER + ["批次号", "有效期"]
    rows = [
        ["IN-XLS-001", "2026-09-01", "仓库A", "供应商甲", "M100", "物料甲", 10, 5.5, "B20260901", "2027/6/30"],
        ["IN-XLS-001", "2026-09-01", "仓库A", "供应商甲", "M101", "物料乙", 3, 2.0, "B20260902", date(2027, 12, 31)],
    ]
    resp = _post_import(_make_client(), header, rows)
    assert resp.status_code == 200, f"导入接口返回 {resp.status_code}"

    with app_module.app.app_context():
        order = InOrder.query.filter_by(order_no="IN-XLS-001").first()
        assert order is not None, "应生成入库单 IN-XLS-001"
        items = {i.material.code: i for i in InOrderItem.query.filter_by(in_order_id=order.id).all()}
        assert items["M100"].batch_no == "B20260901"
        assert items["M100"].expiry_date == date(2027, 6, 30), \
            f"文本日期应归一化，实际 {items['M100'].expiry_date}"
        assert items["M101"].batch_no == "B20260902"
        assert items["M101"].expiry_date == date(2027, 12, 31)
        assert type(items["M101"].expiry_date) is date, "日期单元格不应带时间部分"


def test_T2_import_without_batch_columns_still_works():
    """不含批次/有效期列 → 导入照常成功，两列为 NULL（向后兼容）。"""
    with app_module.app.app_context():
        _reset_db()
        _seed()

    rows = [["IN-XLS-002", "2026-09-01", "仓库A", "供应商甲", "M200", "物料丙", 5, 1.0]]
    resp = _post_import(_make_client(), BASE_HEADER, rows)
    assert resp.status_code == 200, f"导入接口返回 {resp.status_code}"

    with app_module.app.app_context():
        order = InOrder.query.filter_by(order_no="IN-XLS-002").first()
        assert order is not None, "存量模板（无批次列）应仍能导入"
        item = InOrderItem.query.filter_by(in_order_id=order.id).first()
        assert item is not None
        assert item.batch_no is None and item.expiry_date is None


def test_T3_invalid_expiry_row_is_skipped_with_reason():
    """有效期非法 → 该行被跳过并给出原因，不写脏数据。"""
    with app_module.app.app_context():
        _reset_db()
        _seed()

    header = BASE_HEADER + ["批次号", "有效期"]
    rows = [
        ["IN-XLS-003", "2026-09-01", "仓库A", "供应商甲", "M300", "物料丁", 5, 1.0, "B001", "2026-02-31"],
        ["IN-XLS-003", "2026-09-01", "仓库A", "供应商甲", "M301", "物料戊", 2, 1.0, "B002", "2027-01-31"],
    ]
    resp = _post_import(_make_client(), header, rows)
    assert resp.status_code == 200, f"导入接口返回 {resp.status_code}"

    with app_module.app.app_context():
        order = InOrder.query.filter_by(order_no="IN-XLS-003").first()
        assert order is not None
        codes = {i.material.code for i in InOrderItem.query.filter_by(in_order_id=order.id).all()}
        assert "M300" not in codes, "非法有效期的行不应落库"
        assert "M301" in codes, "合法行应正常落库"

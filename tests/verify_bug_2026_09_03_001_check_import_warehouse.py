# -*- coding: utf-8 -*-
"""BUG-2026-09-03-001 回归：Excel 导入盘点单支持仓库并统一账面口径。

修复前：/check/import 完全不处理仓库——Excel 模板没有"仓库"列，导入
新建的盘点单 warehouse 为空，complete_check 直接拒绝完结（"盘点单未
指定仓库，无法完成"），Excel 盘点导入功能实际不可用；且导入明细缺省
账面取全局 Material.stock，多仓库下把别仓库存算进本仓账面。

修复后：
1. Excel 可选"仓库"列（仓库名或编码均可）：提供时校验存在且 active，
   导入单据以行值为准；同一单据内多行仓库必须一致，否则跳行并提示。
2. Excel 未提供仓库列时自动带入系统默认仓库；无默认仓库则跳行并提示
   （整文件可被跳过，导入结果返回 warnings）。
3. 明细未提供"系统库存"列/单元格时，账面取该单据仓库的仓库级库存
   （get_warehouse_stock_quantities），不再用全局 Material.stock；
   Excel 显式提供账面值时以文件为准。

覆盖：
T1. 带仓库列导入 → 单 warehouse=A仓、账面取 A 仓库存 10、差异 −2，
    且 complete_check 可正常完结（生成调整草稿）
T2. 无仓库列 + 有默认仓库 → 自动带入默认仓库，完结成功
T3. 无仓库列 + 无默认仓库 → 单据被跳过，warnings 提示缺仓库
T4. Excel 显式给系统库存 999 → 以文件为准（不覆盖为仓库级）
T5. 同一单据内仓库不一致 → 冲突行跳过并提示，其余行正常
T6. 仓库列写编码（WA）→ 解析为仓库名 A仓
"""
from __future__ import annotations

import io
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

from openpyxl import Workbook  # noqa: E402
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

HEADER = ['单据编号', '日期', '仓库', '物料编码', '物料名称', '规格', '单位', '系统库存', '实际库存', '备注']


def _reset_db():
    db.drop_all()
    db.create_all()


def _login_web(client):
    r = client.post("/login", data={"username": "admin", "password": "admin"})
    assert r.status_code in (302, 303), f"Web 登录失败：{r.status_code}"


def _seed_admin():
    from app import User
    db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
    db.session.commit()


def _seed_warehouse(code, name, is_default=False):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active", is_default=is_default)
    db.session.add(w)
    db.session.commit()
    return w


def _seed_material_with_stock(code, global_stock, per_warehouse):
    """M001 全局 100；A 仓 10 / B 仓 40（双仓避免单仓全局兼容分支）。"""
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


def _scene(has_default=True):
    _reset_db()
    _seed_admin()
    wa = _seed_warehouse("WA", "A仓", is_default=has_default)
    wb = _seed_warehouse("WB", "B仓")
    m = _seed_material_with_stock("M001", 100.0, {wa: 10.0, wb: 40.0})
    return wa, wb, m


def _xlsx(rows, header=HEADER):
    wb = Workbook()
    ws = wb.active
    ws.title = "盘点"
    ws.append(header)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _post_import(client, buf):
    buf.seek(0)
    return client.post("/check/import", data={"file": (buf, "盘点导入.xlsx")},
                       content_type="multipart/form-data")


def test_t1_import_with_warehouse_column_and_can_complete():
    """T1：带仓库列导入 → 仓库与仓库级账面正确，且盘点单可正常完结。"""
    wa, _wb, _m = _scene()
    client = app_module.app.test_client()
    _login_web(client)
    rows = [['CK26090301', '2026-09-03', 'A仓', 'M001', '', '', '', None, 8, '']]
    r = _post_import(client, _xlsx(rows))
    body = r.get_json()
    assert body["status"] == "success", body
    assert body["count"] == 1 and body["item_count"] == 1, body

    from app import AdjustmentOrder, InventoryCheck, InventoryCheckItem
    with app_module.app.app_context():
        check = InventoryCheck.query.filter_by(check_no="CK26090301").first()
        assert check is not None
        assert check.warehouse == "A仓", "导入单必须带仓库"
        item = InventoryCheckItem.query.filter_by(inventory_check_id=check.id).first()
        assert item.system_stock == 10, "未填账面时应取 A 仓仓库级库存 10，而非全局 100"
        assert item.difference == -2
        check_id = check.id
    # 完成盘点（旧行为在此被拒：warehouse 为空）→ 必须成功
    complete = client.post(f"/check/{check_id}/complete")
    assert complete.status_code == 200, complete.get_data(as_text=True)
    assert complete.get_json()["status"] == "success", complete.get_json()
    with app_module.app.app_context():
        drafts = AdjustmentOrder.query.filter_by(source_type="check", source_id=check_id).all()
        assert drafts, "差异应生成调整草稿"
        assert drafts[0].adjustment_type == "loss"


def test_t2_no_warehouse_column_falls_back_to_default():
    """T2：Excel 无仓库列时自动带入默认仓库，可正常完结。"""
    wa, _wb, _m = _scene(has_default=True)
    client = app_module.app.test_client()
    _login_web(client)
    header_no_wh = [h for h in HEADER if h != "仓库"]
    rows = [['CK26090302', '2026-09-03', 'M001', '', '', '', None, 8, '']]
    r = _post_import(client, _xlsx(rows, header=header_no_wh))
    body = r.get_json()
    assert body["status"] == "success" and body["count"] == 1, body

    from app import InventoryCheck
    with app_module.app.app_context():
        check = InventoryCheck.query.filter_by(check_no="CK26090302").first()
        assert check is not None
        assert check.warehouse == wa.name, "未提供仓库列应带入默认仓库"


def test_t3_no_warehouse_and_no_default_rejected_with_warning():
    """T3：无仓库列且无默认仓库 → 单据被跳过并提示缺仓库。"""
    _scene(has_default=False)
    client = app_module.app.test_client()
    _login_web(client)
    header_no_wh = [h for h in HEADER if h != "仓库"]
    rows = [['CK26090303', '2026-09-03', 'M001', '', '', '', None, 8, '']]
    r = _post_import(client, _xlsx(rows, header=header_no_wh))
    body = r.get_json()
    assert body["status"] == "success", body
    assert body["count"] == 0, "无仓库且无默认仓库时不应导入任何单据"
    assert "仓库" in (body.get("warnings") or ""), body


def test_t4_explicit_book_stock_wins():
    """T4：Excel 显式填写系统库存时以文件为准，不做仓库级覆盖。"""
    _scene()
    client = app_module.app.test_client()
    _login_web(client)
    rows = [['CK26090304', '2026-09-03', 'A仓', 'M001', '', '', '', 999, 8, '']]
    r = _post_import(client, _xlsx(rows))
    assert r.get_json()["status"] == "success", r.get_json()

    from app import InventoryCheckItem
    with app_module.app.app_context():
        item = InventoryCheckItem.query.first()
        assert item.system_stock == 999, "显式账面值必须保留（文件优先）"
        assert item.difference == 8 - 999


def test_t5_conflicting_warehouse_rows_skipped():
    """T5：同一盘点单内仓库列不一致 → 冲突行跳过并提示，其余行正常导入。"""
    _scene()
    client = app_module.app.test_client()
    _login_web(client)
    rows = [
        ['CK26090305', '2026-09-03', 'A仓', 'M001', '', '', '', None, 8, ''],
        ['CK26090305', '2026-09-03', 'B仓', 'M001', '', '', '', None, 9, ''],
    ]
    r = _post_import(client, _xlsx(rows))
    body = r.get_json()
    assert body["status"] == "success", body
    assert body["count"] == 1 and body["item_count"] == 1, body
    assert "不一致" in (body.get("warnings") or ""), body

    from app import InventoryCheck, InventoryCheckItem
    with app_module.app.app_context():
        check = InventoryCheck.query.filter_by(check_no="CK26090305").first()
        assert check.warehouse == "A仓"
        assert InventoryCheckItem.query.filter_by(inventory_check_id=check.id).count() == 1


def test_t6_warehouse_code_alias_accepted():
    """T6：仓库列填写编码 WA 也能解析为仓库名 A仓。"""
    _scene()
    client = app_module.app.test_client()
    _login_web(client)
    rows = [['CK26090306', '2026-09-03', 'WA', 'M001', '', '', '', None, 8, '']]
    r = _post_import(client, _xlsx(rows))
    assert r.get_json()["status"] == "success", r.get_json()

    from app import InventoryCheck
    with app_module.app.app_context():
        check = InventoryCheck.query.filter_by(check_no="CK26090306").first()
        assert check is not None
        assert check.warehouse == "A仓", "仓库编码应解析为仓库名落库"

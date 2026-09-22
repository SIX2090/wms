# -*- coding: utf-8 -*-
"""BUG-2026-09-22-013 回归测试：出库明细报表按业务类型隔离。

问题：
  `_filtered_out_detail_query`（领料明细报表 / 出入库汇总报表 / 导出共用的
  唯一 WHERE 口径）**完全没有 business_type 条件**，所有出库单混在一份
  「领料明细」里返回：
    - 采购退货出库（退货给供应商，不是领用）出现在「领料明细报表」中，
      虚增领料数量与金额 → 成本归集、领料对账、部门领用统计全部失真；
    - `_build_report_filters` 的业务类型白名单只列了入库类型，
      `business_type=采购退货出库` 会被**静默重置为空**，用户连筛都筛不掉；
    - 报表也没有类型列，肉眼无法分辨哪行是采购退货。

修复：`_filtered_out_detail_query` 补业务类型隔离——不传类型时按「领料口径」
      过滤（领料单 + 历史脏数据 Android扫码出库 + 空类型，与出库单列表页
      及移动端日报口径一致），显式传类型时按该类型过滤；白名单补出库类型；
      出库明细报表增加业务类型列与排序。

测试用例：
  T1. 默认查询：领料单在、采购退货出库不在（核心修复点）
  T2. 显式 business_type=采购退货出库：能查到（修复前会被静默重置为空而查不到）
  T3. 显式 business_type=领料单：只返回领料单
  T4. 空类型的历史单据按领料口径计入（不得因加条件而漏数）
  T5. 'Android扫码出库' 历史脏数据按领料口径计入（与移动端日报一致）
  T6. 报表返回 business_type 字段与「业务类型」列
  T7. 汇总报表出库侧同步隔离（共用同一 query，防只修一处）
  T8. 白名单：非法类型被重置为空并按领料口径返回，不报错、不返回空集
"""
from __future__ import annotations

import os
import sys
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

import datetime  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    db, User, Material, MaterialCategory, Unit, Warehouse, Department,
    OutOrder, OutOrderItem, OUT_LEGACY_SCAN_BUSINESS_TYPE,
    OUT_NON_REQUISITION_BUSINESS_TYPES,
    REPORT_BUSINESS_TYPE_WHITELIST,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

TODAY = datetime.date.today().strftime("%Y-%m-%d")
_IDS = {}


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    from werkzeug.security import generate_password_hash
    unit = Unit(code="PCS", name="个")
    cat = MaterialCategory(code="CAT1", name="默认分类")
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    dept = Department(code="DEPT-PROD1", name="生产一部")
    user = User(username="admin", password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False)
    db.session.add_all([unit, cat, wh, dept, user])
    db.session.flush()
    mat = Material(code="M-REPORT-1", name="报表物料", category_id=cat.id,
                   unit_id=unit.id, stock=0, price=10)
    db.session.add(mat)
    db.session.commit()
    _IDS.update(wh=wh.name, mat=mat.id, dept=dept.id)


def _make_out_order(order_no, business_type, qty=4.0):
    order = OutOrder(
        order_no=order_no,
        date=datetime.date.today(),
        business_type=business_type,
        warehouse=_IDS["wh"],
        department_id=_IDS["dept"],
        status="completed",
        total_amount=qty * 10,
    )
    db.session.add(order)
    db.session.flush()
    db.session.add(OutOrderItem(
        out_order_id=order.id, material_id=_IDS["mat"],
        quantity=qty, price=10, amount=qty * 10,
    ))
    db.session.commit()
    return order


def _client():
    client = app_module.app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"})
    return client


def _query(client, report_type="out_detail", **params):
    query = {"warehouse_id": "", "date_start": TODAY, "date_end": TODAY}
    query.update(params)
    resp = client.get(f"/report/api/{report_type}", query_string=query)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()


class TestOutDetailBusinessTypeIsolation:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed()
            _make_out_order("OUT-REQ-1", "领料单", 7.0)
            _make_out_order("PR-RET-1", "采购退货出库", 4.0)
        return _client()

    def test_default_excludes_purchase_return(self):
        """T1：核心——采购退货出库不得出现在领料明细报表。"""
        with app_module.app.app_context():
            client = self._setup()
            body = _query(client)
        nos = [row["order_no"] for row in body["data"]]
        assert "OUT-REQ-1" in nos, body["data"]
        assert "PR-RET-1" not in nos, f"采购退货出库混入领料报表: {nos}"
        # 汇总也必须是领料口径（只 7 件）
        assert abs(float(body["summary"]["quantity"]) - 7.0) < 1e-6, body["summary"]

    def test_explicit_purchase_return_queryable(self):
        """T2：显式传采购退货出库必须能查到（修复前被静默重置为空 → 查不到）。"""
        with app_module.app.app_context():
            client = self._setup()
            body = _query(client, business_type="采购退货出库")
        nos = [row["order_no"] for row in body["data"]]
        assert nos == ["PR-RET-1"], body["data"]
        assert abs(float(body["summary"]["quantity"]) - 4.0) < 1e-6

    def test_explicit_requisition_only(self):
        """T3：显式传领料单只返回领料单。"""
        with app_module.app.app_context():
            client = self._setup()
            body = _query(client, business_type="领料单")
        assert [row["order_no"] for row in body["data"]] == ["OUT-REQ-1"]

    def test_null_type_counted_as_requisition(self):
        """T4：历史空类型单据按领料口径计入。"""
        with app_module.app.app_context():
            client = self._setup()
            _make_out_order("OUT-NULL-1", None, 3.0)
            body = _query(client)
        nos = [row["order_no"] for row in body["data"]]
        assert "OUT-NULL-1" in nos, nos

    def test_legacy_scan_type_counted_as_requisition(self):
        """T5：Android扫码出库 历史脏数据按领料口径计入（与移动端日报一致）。"""
        with app_module.app.app_context():
            client = self._setup()
            _make_out_order("OUT-ANDROID-1", OUT_LEGACY_SCAN_BUSINESS_TYPE, 2.0)
            body = _query(client)
        nos = [row["order_no"] for row in body["data"]]
        assert "OUT-ANDROID-1" in nos, nos

    def test_unknown_business_type_not_dropped(self):
        """T5-b：未知/非标准的 business_type 不得被静默漏数。

        CI 实测 `verify_bug_2026_08_02_018` 中存在 `business_type='requisition'`
        这类非系统标准中文类型的出库单。默认口径若用「只放行领料类型」的
        放行式，这类单据会凭空消失——比「采购退货混进来」更严重。
        故默认口径采用排除式：只挡确定非领料的类型，未知值一律保留。
        """
        with app_module.app.app_context():
            client = self._setup()
            _make_out_order("OUT-UNKNOWN-1", "requisition", 2.0)
            _make_out_order("OUT-UNKNOWN-2", "某个未来新增的类型", 1.0)
            body = _query(client)
        nos = [row["order_no"] for row in body["data"]]
        assert "OUT-UNKNOWN-1" in nos, f"未知类型被静默漏数: {nos}"
        assert "OUT-UNKNOWN-2" in nos, f"未知类型被静默漏数: {nos}"
        # 但已知非领料类型仍必须被排除
        assert "PR-RET-1" not in nos, nos

    def test_row_and_columns_expose_business_type(self):
        """T6：行数据与列定义都要有业务类型。"""
        with app_module.app.app_context():
            client = self._setup()
            body = _query(client)
        row = next(r for r in body["data"] if r["order_no"] == "OUT-REQ-1")
        assert row["business_type"] == "领料单", row
        fields = [col["field"] for col in body["columns"]]
        assert "business_type" in fields, fields

    def test_summary_report_isolated_too(self):
        """T7：汇总报表出库侧共用同一 query，必须同步隔离。"""
        with app_module.app.app_context():
            client = self._setup()
            body = _query(client, report_type="summary")
        out_qty = sum(float(row.get("out_quantity") or 0) for row in body["data"])
        assert abs(out_qty - 7.0) < 1e-6, f"汇总出库侧含采购退货: {body['rows']}"

    def test_invalid_type_falls_back_to_requisition(self):
        """T8：非法类型被重置为空（= 领料口径），不报错也不返回空集。"""
        with app_module.app.app_context():
            client = self._setup()
            body = _query(client, business_type="不存在的类型")
        nos = [row["order_no"] for row in body["data"]]
        assert "OUT-REQ-1" in nos, nos
        assert "PR-RET-1" not in nos, nos


class TestWhitelistAndConstants:
    def test_whitelist_covers_out_types(self):
        assert "采购退货出库" in REPORT_BUSINESS_TYPE_WHITELIST
        assert "领料单" in REPORT_BUSINESS_TYPE_WHITELIST
        assert "其他出库" in REPORT_BUSINESS_TYPE_WHITELIST
        assert "销售出库" in REPORT_BUSINESS_TYPE_WHITELIST
        # 入库类型不得被移出（BUG-2026-08-18-004 的能力要保住）
        assert "采购入库" in REPORT_BUSINESS_TYPE_WHITELIST
        assert "产品入库" in REPORT_BUSINESS_TYPE_WHITELIST
        assert "其他入库" in REPORT_BUSINESS_TYPE_WHITELIST

    def test_legacy_scan_constant(self):
        assert OUT_LEGACY_SCAN_BUSINESS_TYPE == "Android扫码出库"
        # 该历史值属领料口径，不得出现在排除名单里
        assert OUT_LEGACY_SCAN_BUSINESS_TYPE not in OUT_NON_REQUISITION_BUSINESS_TYPES

    def test_non_requisition_exclusion_list(self):
        """T9：默认口径排除名单必须覆盖已知非领料类型（防漏配导致隔离失效）。"""
        for bt in ("采购退货出库", "其他出库", "销售出库"):
            assert bt in OUT_NON_REQUISITION_BUSINESS_TYPES, f"排除名单缺少 {bt}"
        # 领料单本身绝不能被排除
        assert "领料单" not in OUT_NON_REQUISITION_BUSINESS_TYPES

    def test_report_view_page_renders_out_detail_filter(self):
        with app_module.app.app_context():
            _reset_db()
            _seed()
        client = _client()
        html = client.get("/report/view/out_detail").get_data(as_text=True)
        assert "全部领料类型" in html, "出库明细报表缺少业务类型筛选控件"
        assert "采购退货出库" in html

# -*- coding: utf-8 -*-
"""
BUG-2026-08-02-014 回归测试：报表仓库必填筛选

测试目标（来自 AGENTS.md）：
  - 规则一（未开启库位）：库存查询 / 出入库报表 / 库存台帐 仓库必填筛选项；不指定仓库时不得返回数据
  - 规则二（开启库位）：仓库必填筛选（库位可选）；不指定仓库时不得返回数据

具体断言：
  T1. report_view 页面渲染：应包含 warehouse 下拉框且有 required
  T2. report_view 页面默认预选 default_warehouse
  T3. report_api 不传 warehouse_id 时，自动带入默认仓库
  T4. 无默认仓库 + 无 warehouse_id 参数时，builder 返回 []
  T5-A. in_detail 按 warehouse_id 过滤
  T5-B. out_detail 按 warehouse_id 过滤
  T5-C. ledger 按 warehouse_id 过滤（StockTransaction.location == 仓库名）
  T6. stock_query / inventory 报告：不传 warehouse_id 且无默认时返回空

使用方法：
  cd /workspace && python -m pytest tests/verify_bug_2026_08_02_018_report.py -xvs
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

# 强制使用内存 SQLite，避免污染真实库
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")


import app as app_module  # noqa: E402
from app import (  # noqa: E402
    Warehouse, User, Material, MaterialCategory, Unit, Supplier,
    InOrder, InOrderItem, OutOrder, OutOrderItem, StockTransaction, SystemSetting, db,
)

# 必须在 app import 之后设置 TESTING=True，使 guarded_drop_all 放行
app_module.app.config["TESTING"] = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_common(app_ctx):
    unit = Unit(name="个", code="PCS")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    sup = Supplier(code="SUP001", name="测试供应商")
    wh_a = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    wh_b = Warehouse(code="WHB", name="仓库B", is_default=False, status="active")
    from werkzeug.security import generate_password_hash
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    mat = Material(
        code="M001", name="测试物料", spec="S1",
        category=cat, unit=unit, supplier=sup,
        stock=0, price=10, min_stock=0, max_stock=9999, reorder_point=0,
    )
    db.session.add_all([unit, cat, sup, wh_a, wh_b, user, mat])
    db.session.commit()
    return {
        "unit": unit, "cat": cat, "sup": sup,
        "wh_a": wh_a, "wh_b": wh_b,
        "user": user, "mat": mat,
    }


def _make_client(app_ctx):
    import re
    client = app_module.app.test_client()
    # 先 GET 登录页取 csrf token，再 POST 登录
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post(
        "/login",
        data={"username": "admin", "password": "admin", "csrf_token": token},
    )
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestBug20260802014:
    # -------------------------------------------------------------- T1
    def test_T1_report_view_contains_required_warehouse(self):
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed_common(app_module.app)
            client = _make_client(app_module.app)
            resp = client.get("/report/view/in_detail", follow_redirects=True)
            assert resp.status_code == 200
            text = resp.get_data(as_text=True)
            assert 'id="warehouse_id"' in text
            seg = text.split('id="warehouse_id"')[1][:200]
            assert "required" in seg, "仓库字段 required 属性缺失"
            assert "请选择仓库" in text

    # -------------------------------------------------------------- T2
    def test_T2_default_warehouse_selected_in_view(self):
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed_common(app_module.app)
            client = _make_client(app_module.app)
            resp = client.get("/report/view/in_detail", follow_redirects=True)
            text = resp.get_data(as_text=True)
            assert f'value="{seeds["wh_a"].id}" selected' in text, "默认仓库 WHA 未预选"

    # -------------------------------------------------------------- T3
    def test_T3_report_api_auto_use_default_wh(self):
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed_common(app_module.app)
            # 插入仓库 A 的入库
            from datetime import date
            order = InOrder(
                order_no="IN-TEST-001", date=date.today(),
                status="completed", purpose="采购入库",
                supplier=seeds["sup"],
                warehouse=seeds["wh_a"].name,
                operator=seeds["user"],
            )
            db.session.add(order); db.session.flush()
            db.session.add(InOrderItem(
                in_order_id=order.id, material_id=seeds["mat"].id,
                quantity=10, price=10, amount=100,
            ))
            db.session.commit()

            client = _make_client(app_module.app)
            # 不传 warehouse_id -> 自动带默认（wh_a），应该查到
            resp = client.get("/report/api/in_detail", query_string={"page": 1, "page_size": 20})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "success"
            assert data["total"] >= 1
            codes = [r.get("material_code") for r in data.get("data", [])]
            assert "M001" in codes

    # -------------------------------------------------------------- T4
    def test_T4_no_default_no_param_returns_empty(self):
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed_common(app_module.app)
            # 取消所有默认
            for w in Warehouse.query.all():
                w.is_default = False
            db.session.commit()

            client = _make_client(app_module.app)
            resp = client.get("/report/api/in_detail", query_string={"page": 1, "page_size": 20})
            data = resp.get_json()
            assert data["status"] == "success"
            assert data["total"] == 0, "无默认+不传warehouse_id 时应返回 0 条"

    # -------------------------------------------------------------- T5-A
    def test_T5A_in_detail_filters_by_warehouse(self):
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed_common(app_module.app)
            from datetime import date
            oa = InOrder(order_no="IN-A-01", date=date.today(), status="completed", purpose="采购入库",
                supplier=seeds["sup"], warehouse=seeds["wh_a"].name,
                operator=seeds["user"])
            ob = InOrder(order_no="IN-B-01", date=date.today(), status="completed", purpose="采购入库",
                supplier=seeds["sup"], warehouse=seeds["wh_b"].name,
                operator=seeds["user"])
            db.session.add_all([oa, ob]); db.session.flush()
            db.session.add_all([
                InOrderItem(in_order_id=oa.id, material_id=seeds["mat"].id, quantity=5, price=10, amount=50),
                InOrderItem(in_order_id=ob.id, material_id=seeds["mat"].id, quantity=3, price=10, amount=30),
            ])
            db.session.commit()

            client = _make_client(app_module.app)
            resp = client.get("/report/api/in_detail", query_string={
                "warehouse_id": seeds["wh_b"].id, "page": 1, "page_size": 20,
            })
            data = resp.get_json()
            order_nos = [r.get("order_no") for r in data.get("data", [])]
            assert "IN-B-01" in order_nos
            assert "IN-A-01" not in order_nos

    # -------------------------------------------------------------- T5-B
    def test_T5B_out_detail_filters_by_warehouse(self):
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed_common(app_module.app)
            from datetime import date
            oa = OutOrder(order_no="OUT-A-01", date=date.today(), status="completed",
                business_type="requisition",
                warehouse=seeds["wh_a"].name,
                operator=seeds["user"])
            ob = OutOrder(order_no="OUT-B-01", date=date.today(), status="completed",
                business_type="requisition",
                warehouse=seeds["wh_b"].name,
                operator=seeds["user"])
            db.session.add_all([oa, ob]); db.session.flush()
            db.session.add_all([
                OutOrderItem(out_order_id=oa.id, material_id=seeds["mat"].id, quantity=2, price=10, amount=20),
                OutOrderItem(out_order_id=ob.id, material_id=seeds["mat"].id, quantity=7, price=10, amount=70),
            ])
            db.session.commit()

            client = _make_client(app_module.app)
            resp = client.get("/report/api/out_detail", query_string={
                "warehouse_id": seeds["wh_a"].id, "page": 1, "page_size": 20,
            })
            data = resp.get_json()
            order_nos = [r.get("order_no") for r in data.get("data", [])]
            assert "OUT-A-01" in order_nos
            assert "OUT-B-01" not in order_nos

    # -------------------------------------------------------------- T5-C
    def test_T5C_ledger_filters_by_warehouse(self):
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed_common(app_module.app)
            from datetime import datetime
            tx1 = StockTransaction(material_id=seeds["mat"].id, transaction_type="in",
                quantity=11, location=seeds["wh_a"].name, reference_type="in_order",
                reference_id=9001, operator_id=seeds["user"].id,
                created_at=datetime.now())
            tx2 = StockTransaction(material_id=seeds["mat"].id, transaction_type="in",
                quantity=22, location=seeds["wh_b"].name, reference_type="in_order",
                reference_id=9002, operator_id=seeds["user"].id,
                created_at=datetime.now())
            db.session.add_all([tx1, tx2]); db.session.commit()

            client = _make_client(app_module.app)
            resp = client.get("/report/api/ledger", query_string={
                "warehouse_id": seeds["wh_a"].id,
                "material_code": "M001",
                "page": 1, "page_size": 50,
            })
            data = resp.get_json()
            in_qtys = [r.get("in_quantity") for r in data.get("data", [])]
            assert 11 in in_qtys, "按仓库A查询台账应返回数量=11的交易"
            assert 22 not in in_qtys, "按仓库A查询台账不应返回数量=22的交易(仓库B)"

    # -------------------------------------------------------------- T6
    def test_T6_inventory_report_requires_warehouse(self):
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed_common(app_module.app)
            # 取消所有默认 -> 无默认仓库
            for w in Warehouse.query.all():
                w.is_default = False
            db.session.commit()

            client = _make_client(app_module.app)
            resp = client.get("/report/api/inventory", query_string={"page": 1, "page_size": 20})
            data = resp.get_json()
            assert data["status"] == "success"
            assert data["total"] == 0, "库存查询报告无默认+无warehouse_id 参数应返回 0 条"

# -*- coding: utf-8 -*-
"""BUG-2026-10-06-002 回归锁：AI 库存工具两级告警口径 + value 500。

背景：AI 工具（low_stock_report / inventory_health / material_query）只判
``qty <= min_stock``，漏 reorder_point 的 danger 档；stock_value_analysis 把
MaterialCategory 对象当 dict key 导致 /api/ai/v2/tools/inventory/value 必 500。

口径基准（AI-CI-GREEN-005-F04/F05）：low（≤min_stock）+ danger（≤reorder_point）
两级都算告警；AI 工具与 dashboard / alert 列表必须对同一数据给出同一答案。

用例：
- A1 danger 档进 AI low-stock 报告（status=danger, shortage 按 safety_stock）
- A2 inventory_health.low_stock_count 统计 danger 档
- A3 material_query 的 alert_status 输出 danger
- A4 stock_value_analysis by_category 键为分类名字符串（原 500）
- A5 v2 value 路由 200（原必 500）
- A6 两级判定与 app._alert_status_for 等价（同入参同输出，含边界）
- A7 disabled 语义：min_stock/reorder_point 全空 → disabled，不计入低库存
- A8 low 档 shortage 语义不回退（qty ≤ min_stock 时按 min_stock 计缺口）
"""
import os
import sys
import json

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_ALLOW_INSECURE_COOKIE"] = "1"

import app as app_module  # noqa: E402
app_module.__path__ = [str(APP_DIR)]

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

from app import db, Material, User, Warehouse, MaterialCategory, Unit  # noqa: E402


def _reset():
    with db.engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
    db.session.remove()
    db.drop_all()
    db.create_all()
    db.session.commit()


def _login(client):
    client.get("/login")
    r = client.post("/login", data={"username": "admin", "password": "admin"},
                    follow_redirects=True)
    assert r.status_code == 200


class TestBug20261006002AiToolsAlertStatus:
    def setup_method(self):
        app_module.app.config["TESTING"] = True
        with app_module.app.app_context():
            _reset()
            from werkzeug.security import generate_password_hash
            admin = User(username="admin",
                         password_hash=generate_password_hash("admin"),
                         role="admin", must_change_password=False)
            db.session.add(admin)
            wh = Warehouse(code="WHA", name="A仓", is_default=True)
            db.session.add(wh)
            cat = MaterialCategory(code="C1", name="铜排类")
            db.session.add(cat)
            db.session.add(Unit(code="PCS", name="个"))
            db.session.commit()
            app_module.set_system_setting("inventory_alert_enabled", "1")
            # set_system_setting 不会自动提交；不 commit 的话退出 app_context
            # 时该事务回滚，inventory_alert_enabled 回落默认 0（告警关），
            # 所有 AI 工具判定都会变 disabled（历史踩坑，勿删）。
            db.session.commit()
            self.cat_id = cat.id
            self.admin_id = admin.id

    def _seed(self, min_stock=5.0, reorder_point=10.0, qty=8.0):
        """造一个 danger 档物料：5 < qty <= 10。"""
        cat_id = self.cat_id
        admin_id = self.admin_id
        mat = Material(code="M001", name="铜排", spec="T2",
                       min_stock=min_stock, reorder_point=reorder_point,
                       price=10.0, category_id=cat_id, unit_id=1)
        db.session.add(mat)
        db.session.commit()
        if qty:
            from app import add_stock
            admin = db.session.get(User, admin_id)
            with app_module.app.test_request_context("/"):
                from flask_login import login_user
                login_user(admin)
                ok, err = add_stock(mat, qty, transaction_type="in", warehouse="A仓")
                assert ok, err
                db.session.commit()
        return mat

    def test_a1_danger_in_low_stock_report(self):
        with app_module.app.app_context():
            self._seed()
            from app.ai.tools.inventory import low_stock_report
            rows = low_stock_report()
            assert len(rows) == 1, rows
            assert rows[0]["code"] == "M001"
            assert rows[0]["alert_status"] == "danger"
            # shortage 按 safety_stock（max(reorder_point, min_stock)）= 10 - 8 = 2
            assert rows[0]["shortage"] == 2, rows[0]

    def test_a2_health_counts_danger(self):
        with app_module.app.app_context():
            self._seed()
            from app.ai.tools.inventory import inventory_health
            r = inventory_health(30, 200)
            assert r["low_stock_count"] == 1, r
            statuses = [m["issues"] for m in r["materials"] if m["code"] == "M001"]
            assert statuses and "danger" in statuses[0], statuses

    def test_a3_material_query_alert_status(self):
        with app_module.app.app_context():
            self._seed()
            from app.ai.tools.inventory import material_query
            rows = material_query("M001")
            assert len(rows) == 1, rows
            assert rows[0]["alert_status"] == "danger", rows[0]
            assert rows[0]["category"] == "铜排类", rows[0]

    def test_a4_value_by_category_str_keys(self):
        with app_module.app.app_context():
            self._seed()
            from app.ai.tools.inventory import stock_value_analysis
            r = stock_value_analysis()
            assert r["total_value"] == 80.0, r
            assert list(r["by_category"].keys()) == ["铜排类"], r
            json.dumps(r)  # 原 BUG：MaterialCategory 对象不可 JSON 序列化

    def test_a5_v2_value_route_200(self):
        with app_module.app.app_context():
            self._seed()
        client = app_module.app.test_client()
        _login(client)
        r = client.get("/api/ai/v2/tools/inventory/value")
        assert r.status_code == 200, (r.status_code, r.get_data(as_text=True)[:200])
        j = json.loads(r.get_data(as_text=True))
        assert j["data"]["total_value"] == 80.0, j

    def test_a6_equivalent_to_app_alert_status_for(self):
        with app_module.app.app_context():
            from app import _alert_status_for
            from app.ai.tools.inventory import _ai_inventory_alert_status

            class _M:  # 最小 Material 桩
                def __init__(self, min_stock, reorder_point):
                    self.min_stock = min_stock
                    self.reorder_point = reorder_point

            cases = [
                (0, 0, 0, None), (5, 10, 3, "low"), (5, 10, 8, "danger"),
                (5, 10, 10, "danger"), (5, 10, 11, "normal"), (5, 10, 5, "low"),
                (0, 10, 8, "danger"), (5, 0, 8, "normal"), (5, 0, 5, "low"),
                (None, 10, 8, "danger"), (5, None, 8, "normal"),
            ]
            for mn, rp, qty, want in cases:
                got = _ai_inventory_alert_status(_M(mn, rp), qty)
                ref = _alert_status_for(qty, mn, rp)
                assert got == ref, (mn, rp, qty, got, ref)
                if want is not None:
                    assert got == want, (mn, rp, qty, got, want)

    def test_a7_disabled_not_low_stock(self):
        with app_module.app.app_context():
            mat = self._seed(min_stock=None, reorder_point=None, qty=8.0)
            from app.ai.tools.inventory import (low_stock_report,
                                                inventory_health)
            assert low_stock_report() == []
            r = inventory_health(30, 200)
            assert r["low_stock_count"] == 0, r

    def test_a8_low_tier_shortage_by_min_stock(self):
        with app_module.app.app_context():
            self._seed(min_stock=5.0, reorder_point=10.0, qty=4.0)  # low 档
            from app.ai.tools.inventory import low_stock_report
            rows = low_stock_report()
            assert rows[0]["alert_status"] == "low", rows
            # shortage 统一按 safety_stock（max(reorder_point, min_stock)）=10-4=6，
            # 与手机端 alert/list 的 gap 字段同口径（danger/low 一律按安全库存缺口）
            assert rows[0]["shortage"] == 6, rows[0]

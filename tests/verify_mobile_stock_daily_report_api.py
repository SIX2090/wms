# -*- coding: utf-8 -*-
"""
移动端库存日报 API 回归测试（AI-MOB-RPT-F02）。

GET /api/mobile/report/stock_daily：按仓库查看当天各物料结存明细（只读）。

覆盖：
S1. 端点已注册。
S2. 未登录访问返回 401。
S3. 仓库必填：未配置默认仓且未传仓库参数 → 400（AGENTS.md §二）。
S4. 多仓库隔离：A/B 两仓各有库存，查 A 仓只见 A 仓数量（R2）。
S5. 汇总与分页解耦：page_size=2 时 summary 仍反映过滤后全集（R1）。
S6. 分页元数据完整：total / page / page_size / total_pages（R1）。
S7. 结存口径为仓库级数量，不回退全局 Material.stock（A11/R2）。
S8. 非法 sort 参数 → 400；keyword 过滤生效；零库存物料仍在明细中（每个物料都要能看到）。
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

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ENDPOINT = "mobile_api_report_stock_daily"
URL = "/api/mobile/report/stock_daily"


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    return app_module.app.test_client()


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


def _seed_warehouse(code, name):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active")
    db.session.add(w)
    db.session.commit()
    return w.id


def _seed_material(code, name, stock=0):
    from app import Material
    m = Material(code=code, name=name, stock=stock)
    db.session.add(m)
    db.session.commit()
    return m.id


def _seed_txn(material_id, warehouse_id, quantity):
    """造一条仓库级库存流水（库位管理关闭时按 warehouse_id 聚合）。"""
    from app import StockTransaction
    txn = StockTransaction(
        material_id=material_id,
        transaction_type="in",
        quantity=quantity,
        warehouse_id=warehouse_id,
    )
    db.session.add(txn)
    db.session.commit()


class TestMobileStockDailyReportApi:
    def _setup(self, with_default_warehouse=False):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            wh_a = _seed_warehouse("WHA", "A仓")
            wh_b = _seed_warehouse("WHB", "B仓")
            if with_default_warehouse:
                from app import Warehouse
                w = db.session.get(Warehouse, wh_a)
                w.is_default = True
                db.session.commit()
        return _make_client(), wh_a, wh_b

    def test_endpoint_registered(self):
        """S1：端点已注册。"""
        assert ENDPOINT in app_module.app.view_functions, f"{ENDPOINT} 未注册"

    def test_unauthorized_401(self):
        """S2：未登录返回 401。"""
        client, _, _ = self._setup()
        r = client.get(URL)
        assert r.status_code == 401, r.get_data(as_text=True)

    def test_warehouse_required_400(self):
        """S3：无默认仓且未传仓库 → 400 请选择仓库。"""
        client, _, _ = self._setup()
        _login(client)
        r = client.get(URL)
        assert r.status_code == 400, r.get_data(as_text=True)
        body = r.get_json()
        assert "仓库" in (body.get("msg") or body.get("message") or "")

    def test_multi_warehouse_isolation(self):
        """S4：A/B 两仓隔离——查 A 仓只见 A 仓结存，查 B 仓只见 B 仓结存。"""
        client, wh_a, wh_b = self._setup()
        with app_module.app.app_context():
            m1 = _seed_material("M001", "6204轴承")
            _seed_txn(m1, wh_a, 100)
            _seed_txn(m1, wh_b, 30)
        _login(client)

        r = client.get(f"{URL}?warehouse_id={wh_a}")
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        assert data["warehouse"]["id"] == wh_a
        item = next(i for i in data["items"] if i["code"] == "M001")
        assert item["stock"] == 100, f"A仓结存应为 100，实际 {item['stock']}"
        assert data["summary"]["total_quantity"] == 100

        r = client.get(f"{URL}?warehouse_id={wh_b}")
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        item = next(i for i in data["items"] if i["code"] == "M001")
        assert item["stock"] == 30, f"B仓结存应为 30，实际 {item['stock']}"

    def test_summary_decoupled_from_pagination(self):
        """S5：page_size=2 时 summary 仍覆盖全集（汇总与分页解耦，R1）。"""
        client, wh_a, _ = self._setup()
        with app_module.app.app_context():
            for idx in range(5):
                mid = _seed_material(f"M{idx:03d}", f"物料{idx}")
                _seed_txn(mid, wh_a, 10 + idx)
        _login(client)

        r = client.get(f"{URL}?warehouse_id={wh_a}&page_size=2&page=1")
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        assert len(data["items"]) == 2
        summary = data["summary"]
        assert summary["total_materials"] == 5
        assert summary["in_stock_materials"] == 5
        assert summary["zero_materials"] == 0
        # 全集合计 10+11+12+13+14 = 60，不受分页影响
        assert summary["total_quantity"] == 60

    def test_pagination_metadata_complete(self):
        """S6：分页元数据完整且正确（R1）。"""
        client, wh_a, _ = self._setup()
        with app_module.app.app_context():
            for idx in range(5):
                mid = _seed_material(f"M{idx:03d}", f"物料{idx}")
                _seed_txn(mid, wh_a, 1)
        _login(client)

        r = client.get(f"{URL}?warehouse_id={wh_a}&page_size=2&page=2")
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        assert data["total"] == 5
        assert data["page"] == 2
        assert data["page_size"] == 2
        assert data["total_pages"] == 3
        assert len(data["items"]) == 2
        # 翻页合并后应为全集：第 3 页剩 1 条
        r = client.get(f"{URL}?warehouse_id={wh_a}&page_size=2&page=3")
        assert len(r.get_json()["data"]["items"]) == 1

    def test_no_fallback_to_global_stock(self):
        """S7：结存用仓库级口径，绝不回退全局 Material.stock（A11/R2）。"""
        client, wh_a, wh_b = self._setup()
        with app_module.app.app_context():
            # 全局账 999，但 A 仓流水只有 7；B 仓无流水
            m1 = _seed_material("M001", "6204轴承", stock=999)
            _seed_txn(m1, wh_a, 7)
        _login(client)

        r = client.get(f"{URL}?warehouse_id={wh_a}")
        data = r.get_json()["data"]
        item = next(i for i in data["items"] if i["code"] == "M001")
        assert item["stock"] == 7, f"应为仓库口径 7，实际 {item['stock']}（疑似回退全局账）"

        r = client.get(f"{URL}?warehouse_id={wh_b}")
        data = r.get_json()["data"]
        item = next(i for i in data["items"] if i["code"] == "M001")
        assert item["stock"] == 0, f"B仓无流水应为 0，实际 {item['stock']}（疑似回退全局账）"

    def test_sort_validation_and_keyword_and_zero_stock(self):
        """S8：非法 sort → 400；keyword 过滤；零库存物料仍出现在明细。"""
        client, wh_a, _ = self._setup()
        with app_module.app.app_context():
            m1 = _seed_material("M001", "6204轴承")
            _seed_material("M002", "M8螺母")  # 无库存流水 → 结存 0
            _seed_txn(m1, wh_a, 50)
        _login(client)

        r = client.get(f"{URL}?warehouse_id={wh_a}&sort=bogus")
        assert r.status_code == 400, r.get_data(as_text=True)

        r = client.get(f"{URL}?warehouse_id={wh_a}&keyword=螺母")
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["code"] == "M002"
        assert data["items"][0]["stock"] == 0  # 零库存也列出（每个物料的明细）

        r = client.get(f"{URL}?warehouse_id={wh_a}&sort=stock_desc")
        codes = [i["code"] for i in r.get_json()["data"]["items"]]
        assert codes == ["M001", "M002"]

        # 响应基础字段齐全：当天日期 / 仓库信息 / 数据截止时间
        data = r.get_json()["data"]
        assert data["date"]
        assert data["warehouse"]["name"] == "A仓"
        assert data["generated_at"]


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))

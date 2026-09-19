# -*- coding: utf-8 -*-
"""移动端出入库明细 API 测试（AI-MOB-RPT-F01 缺口项）。

GET /api/mobile/report/in_out_detail：按仓库查看指定日期范围的出入库流水明细（只读）。

覆盖：
S1. 端点已注册。
S2. 未登录访问返回 401。
S3. 仓库必填：未配置默认仓且未传仓库参数 → 400（AGENTS.md §二）。
S4. 多仓库隔离：A/B 两仓流水互不串仓（R2）。
S5. 汇总与分页解耦：page_size=2 时 summary 仍反映过滤后全集（R1）。
S6. 分页元数据完整：total / page / page_size / total_pages（R1）。
S7. 方向过滤：direction=in 只列入库、direction=out 只列出库。
S8. 日期校验：非法格式 / 未来日期 / 起 > 止 → 400；自定义历史范围生效。
S9. keyword 过滤 + sort 校验（非法 sort → 400；编码升序排序正确）。
"""
from __future__ import annotations

import os
import sys
from datetime import datetime as _dt, timedelta as _td
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

ENDPOINT = "mobile_api_report_in_out_detail"
URL = "/api/mobile/report/in_out_detail"


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


def _seed_material(code, name):
    from app import Material
    m = Material(code=code, name=name)
    db.session.add(m)
    db.session.commit()
    return m.id


def _seed_txn(material_id, warehouse_id, quantity, created_at=None, txn_type="in"):
    """造一条仓库级库存流水（warehouse_id 精确归属，R2 治本 B1 口径）。"""
    from app import StockTransaction
    txn = StockTransaction(
        material_id=material_id,
        transaction_type=txn_type,
        quantity=quantity,
        warehouse_id=warehouse_id,
        created_at=created_at or _dt.now(),
    )
    db.session.add(txn)
    db.session.commit()


class TestMobileInOutDetailApi:
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
        """S4：A/B 两仓隔离——查 A 仓只见 A 仓流水，查 B 仓只见 B 仓流水（R2）。"""
        client, wh_a, wh_b = self._setup()
        with app_module.app.app_context():
            m1 = _seed_material("M001", "6204轴承")
            _seed_txn(m1, wh_a, 100)   # A 仓入库
            _seed_txn(m1, wh_b, 30)    # B 仓入库
        _login(client)

        r = client.get(f"{URL}?warehouse_id={wh_a}")
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        assert data["warehouse"]["id"] == wh_a
        assert data["summary"]["total_count"] == 1, "A仓应只见 1 条流水"
        assert data["items"][0]["material_code"] == "M001"
        assert data["items"][0]["quantity"] == 100
        assert data["summary"]["total_in_quantity"] == 100

        r = client.get(f"{URL}?warehouse_id={wh_b}")
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        assert data["summary"]["total_in_quantity"] == 30, "B仓应只见 30"

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
        assert data["summary"]["total_count"] == 5
        # 全集合计 10+11+12+13+14 = 60，不受分页影响
        assert data["summary"]["total_in_quantity"] == 60

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

    def test_direction_filter(self):
        """S7：direction=in 只列入库、direction=out 只列出库。"""
        client, wh_a, _ = self._setup()
        with app_module.app.app_context():
            m1 = _seed_material("M001", "6204轴承")
            _seed_txn(m1, wh_a, 50, txn_type="in")    # 入库
            _seed_txn(m1, wh_a, -20, txn_type="out")  # 出库
        _login(client)

        r = client.get(f"{URL}?warehouse_id={wh_a}&direction=in")
        data = r.get_json()["data"]
        assert data["summary"]["total_count"] == 1
        assert data["items"][0]["direction"] == "in"
        assert data["summary"]["total_in_quantity"] == 50
        assert data["summary"]["total_out_quantity"] == 0

        r = client.get(f"{URL}?warehouse_id={wh_a}&direction=out")
        data = r.get_json()["data"]
        assert data["summary"]["total_count"] == 1
        assert data["items"][0]["direction"] == "out"
        assert data["summary"]["total_out_quantity"] == 20

    def test_date_range_and_validation(self):
        """S8：默认今天命中；非法格式 / 未来日期 / 起 > 止 → 400；历史范围生效。"""
        client, wh_a, _ = self._setup()
        with app_module.app.app_context():
            m1 = _seed_material("M001", "6204轴承")
            _seed_txn(m1, wh_a, 100, created_at=_dt.now())
        _login(client)

        # 默认今天范围应命中
        r = client.get(f"{URL}?warehouse_id={wh_a}")
        assert r.status_code == 200 and r.get_json()["data"]["summary"]["total_count"] == 1

        # 非法格式 → 400
        r = client.get(f"{URL}?warehouse_id={wh_a}&start_date=2026-13-01")
        assert r.status_code == 400, r.get_data(as_text=True)

        # 未来日期 → 400
        future = (_dt.now().date() + _td(days=1)).isoformat()
        r = client.get(f"{URL}?warehouse_id={wh_a}&end_date={future}")
        assert r.status_code == 400, r.get_data(as_text=True)

        # 起 > 止 → 400
        r = client.get(f"{URL}?warehouse_id={wh_a}&start_date=2026-09-10&end_date=2026-09-01")
        assert r.status_code == 400, r.get_data(as_text=True)

        # 自定义历史范围（昨天）应无命中
        yesterday = (_dt.now().date() - _td(days=1)).isoformat()
        r = client.get(f"{URL}?warehouse_id={wh_a}&start_date={yesterday}&end_date={yesterday}")
        assert r.status_code == 200
        assert r.get_json()["data"]["summary"]["total_count"] == 0

    def test_keyword_and_sort_validation(self):
        """S9：非法 sort → 400；keyword 命中 M8螺母；code_asc 排序正确。"""
        client, wh_a, _ = self._setup()
        with app_module.app.app_context():
            m1 = _seed_material("M001", "6204轴承")
            m2 = _seed_material("M002", "M8螺母")
            _seed_txn(m1, wh_a, 50)
            _seed_txn(m2, wh_a, 7)
        _login(client)

        # 非法 sort → 400
        r = client.get(f"{URL}?warehouse_id={wh_a}&sort=bogus")
        assert r.status_code == 400, r.get_data(as_text=True)

        # keyword 命中 M8螺母
        r = client.get(f"{URL}?warehouse_id={wh_a}&keyword=螺母")
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        assert data["summary"]["total_count"] == 1
        assert data["items"][0]["material_code"] == "M002"

        # code_asc 排序
        r = client.get(f"{URL}?warehouse_id={wh_a}&sort=code_asc")
        codes = [i["material_code"] for i in r.get_json()["data"]["items"]]
        assert codes == ["M001", "M002"]


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))

# -*- coding: utf-8 -*-
"""移动端库存日报 API 历史日期与 >0 明细口径回归测试（AI-MOB-RPT-F03）。

GET /api/mobile/report/stock_daily（需求 2026-09-17）：
用户选择仓库 → 手机端自动显示该仓**结存 > 0** 的物料库存；支持 date 参数
翻日期回看历史某天的收市结存（当前结存 − 该日之后归属该仓的流水增量）。

覆盖：
H1. 显式传 date=今天 → 与不传一致（向后兼容 F02 契约）。
H2. date 非法格式 → 400；date 晚于今天 → 400。
H3. 历史回推正确：流水按天分布时，各天收市结存逐日还原。
H4. 只出结存 > 0 明细：零库存/净额归零物料不进 items，计入 summary.zero_materials。
H5. 历史日期多仓隔离：A/B 两仓各自回推，互不串仓（R2）。
H6. 汇总与分页解耦在 >0 口径下仍成立（R1）。
H7. 历史日期 generated_at = 23:59（收市语义）；今天 = 当前时刻。
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, time, timedelta
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

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

URL = "/api/mobile/report/stock_daily"
TODAY = date.today()
D1 = TODAY - timedelta(days=1)
D2 = TODAY - timedelta(days=2)


def _reset_db():
    db.drop_all()
    db.create_all()


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _seed_admin():
    from app import User
    db.session.add(User(username="admin",
                        password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
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


def _seed_txn(material_id, warehouse_id, quantity, on_day=TODAY):
    """造一条指定日期的仓库级库存流水（正午，远离日界）。"""
    from app import StockTransaction
    txn = StockTransaction(
        material_id=material_id,
        transaction_type="in" if quantity >= 0 else "out",
        quantity=quantity,
        warehouse_id=warehouse_id,
        created_at=datetime.combine(on_day, time(12, 0)),
    )
    db.session.add(txn)
    db.session.commit()


@pytest.fixture()
def client():
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
    return app_module.app.test_client()


@pytest.fixture()
def warehouses(client):
    # 依赖 client 保证建表（client 夹具负责 _reset_db）后再播种仓库
    with app_module.app.app_context():
        return _seed_warehouse("WHA", "A仓"), _seed_warehouse("WHB", "B仓")


class TestStockDailyDateParam:
    def test_explicit_today_same_as_default(self, client, warehouses):
        """H1：date=今天 与不传 date 结果一致。"""
        wh_a, _ = warehouses
        with app_module.app.app_context():
            m1 = _seed_material("M001", "6204轴承")
            _seed_txn(m1, wh_a, 100, on_day=TODAY)
        _login(client)
        d0 = client.get(f"{URL}?warehouse_id={wh_a}").get_json()["data"]
        d1 = client.get(f"{URL}?warehouse_id={wh_a}&date={TODAY.isoformat()}").get_json()["data"]
        assert d0["date"] == d1["date"] == TODAY.isoformat()
        assert [i["code"] for i in d0["items"]] == [i["code"] for i in d1["items"]]

    def test_invalid_date_format_400(self, client, warehouses):
        """H2a：date 非法格式 → 400。"""
        wh_a, _ = warehouses
        _login(client)
        r = client.get(f"{URL}?warehouse_id={wh_a}&date=2026/09/17")
        assert r.status_code == 400, r.get_data(as_text=True)

    def test_future_date_400(self, client, warehouses):
        """H2b：date 晚于今天 → 400。"""
        wh_a, _ = warehouses
        _login(client)
        future = (TODAY + timedelta(days=1)).isoformat()
        r = client.get(f"{URL}?warehouse_id={wh_a}&date={future}")
        assert r.status_code == 400, r.get_data(as_text=True)


class TestStockDailyHistory:
    def test_historical_closing_reconstruction(self, client, warehouses):
        """H3：逐日收市结存正确回推（当前结存 − 该日之后流水增量）。"""
        wh_a, _ = warehouses
        with app_module.app.app_context():
            m1 = _seed_material("M001", "6204轴承")
            _seed_txn(m1, wh_a, 100, on_day=D2)   # 前天 +100
            _seed_txn(m1, wh_a, -40, on_day=D1)   # 昨天 −40
            _seed_txn(m1, wh_a, 10, on_day=TODAY)  # 今天 +10
        _login(client)

        def stock_on(day):
            r = client.get(f"{URL}?warehouse_id={wh_a}&date={day.isoformat()}")
            assert r.status_code == 200, r.get_data(as_text=True)
            item = next(i for i in r.get_json()["data"]["items"] if i["code"] == "M001")
            return item["stock"]

        assert stock_on(TODAY) == 70    # 100 − 40 + 10
        assert stock_on(D1) == 60       # 截至昨天收市：100 − 40
        assert stock_on(D2) == 100      # 截至前天收市：100

    def test_historical_generated_at_2359(self, client, warehouses):
        """H7：历史日期 generated_at = 23:59；今天为当前时刻 hh:mm。"""
        wh_a, _ = warehouses
        with app_module.app.app_context():
            m1 = _seed_material("M001", "6204轴承")
            _seed_txn(m1, wh_a, 100, on_day=D1)
        _login(client)
        data_h = client.get(f"{URL}?warehouse_id={wh_a}&date={D1.isoformat()}").get_json()["data"]
        assert data_h["generated_at"] == "23:59"
        data_t = client.get(f"{URL}?warehouse_id={wh_a}").get_json()["data"]
        assert data_t["generated_at"] != "23:59"
        assert len(data_t["generated_at"]) == 5  # hh:mm


class TestStockDailyPositiveOnly:
    def test_only_positive_stock_listed(self, client, warehouses):
        """H4：零库存与净额归零物料不进 items，计入 summary.zero_materials。"""
        wh_a, _ = warehouses
        with app_module.app.app_context():
            m1 = _seed_material("M001", "6204轴承")
            _seed_material("M002", "M8螺母")        # 无流水 → 结存 0
            m3 = _seed_material("M003", "平垫圈")
            _seed_txn(m1, wh_a, 50, on_day=TODAY)
            _seed_txn(m3, wh_a, 50, on_day=D1)      # +50 −50 → 净额 0
            _seed_txn(m3, wh_a, -50, on_day=D1)
        _login(client)
        data = client.get(f"{URL}?warehouse_id={wh_a}").get_json()["data"]
        codes = [i["code"] for i in data["items"]]
        assert codes == ["M001"], f"只应列出结存>0 的 M001，实际 {codes}"
        summary = data["summary"]
        assert summary["total_materials"] == 1
        assert summary["in_stock_materials"] == 1
        assert summary["zero_materials"] == 2
        assert summary["total_quantity"] == 50

    def test_positive_filter_applies_to_history(self, client, warehouses):
        """H4b：历史日期同样按当天结存 > 0 过滤（昨天结存 0 的物料昨天不出现）。"""
        wh_a, _ = warehouses
        with app_module.app.app_context():
            m1 = _seed_material("M001", "6204轴承")
            _seed_txn(m1, wh_a, 100, on_day=D1)    # 昨天 +100
            _seed_txn(m1, wh_a, -100, on_day=TODAY)  # 今天 −100 → 今天结存 0
        _login(client)
        today_items = client.get(f"{URL}?warehouse_id={wh_a}").get_json()["data"]["items"]
        assert today_items == [], "今天结存已归零，不应出现"
        d1_data = client.get(f"{URL}?warehouse_id={wh_a}&date={D1.isoformat()}").get_json()["data"]
        assert [i["code"] for i in d1_data["items"]] == ["M001"]


class TestStockDailyHistoryIsolation:
    def test_multi_warehouse_history_isolation(self, client, warehouses):
        """H5：历史日期下 A/B 两仓各自回推，互不串仓（R2）。"""
        wh_a, wh_b = warehouses
        with app_module.app.app_context():
            m1 = _seed_material("M001", "6204轴承")
            _seed_txn(m1, wh_a, 100, on_day=D2)
            _seed_txn(m1, wh_b, 30, on_day=D2)
            _seed_txn(m1, wh_a, -40, on_day=TODAY)  # 今天只有 A 仓出库
        _login(client)
        # 今天：A=60，B=30
        a_today = client.get(f"{URL}?warehouse_id={wh_a}").get_json()["data"]["items"]
        b_today = client.get(f"{URL}?warehouse_id={wh_b}").get_json()["data"]["items"]
        assert next(i for i in a_today if i["code"] == "M001")["stock"] == 60
        assert next(i for i in b_today if i["code"] == "M001")["stock"] == 30
        # 前天收市：A=100，B=30（B 仓不受 A 仓今天的出库影响）
        a_d2 = client.get(f"{URL}?warehouse_id={wh_a}&date={D2.isoformat()}").get_json()["data"]["items"]
        b_d2 = client.get(f"{URL}?warehouse_id={wh_b}&date={D2.isoformat()}").get_json()["data"]["items"]
        assert next(i for i in a_d2 if i["code"] == "M001")["stock"] == 100
        assert next(i for i in b_d2 if i["code"] == "M001")["stock"] == 30


class TestStockDailySummaryDecoupled:
    def test_summary_decoupled_from_pagination_positive_only(self, client, warehouses):
        """H6：page_size=2 时 summary 仍覆盖 >0 过滤后全集（R1）。"""
        wh_a, _ = warehouses
        with app_module.app.app_context():
            for idx in range(5):
                mid = _seed_material(f"M{idx:03d}", f"物料{idx}")
                _seed_txn(mid, wh_a, 10 + idx, on_day=TODAY)
            _seed_material("M999", "零库存物料")  # 不进 items，只进 zero_materials
        _login(client)
        r = client.get(f"{URL}?warehouse_id={wh_a}&page_size=2&page=1")
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        assert len(data["items"]) == 2
        summary = data["summary"]
        assert summary["total_materials"] == 5
        assert summary["in_stock_materials"] == 5
        assert summary["zero_materials"] == 1
        assert summary["total_quantity"] == 60  # 10+11+12+13+14
        assert data["total"] == 5
        assert data["total_pages"] == 3


class TestWarehouseTxnDeltaMap:
    """A9：get_warehouse_txn_delta_map 直接单测（归属口径与边界时刻）。"""

    def test_get_warehouse_txn_delta_map(self, warehouses):
        """A9 同名用例：since 起的流水净增量按仓库归属聚合；边界时刻（次日 00:00）之前的流水不计。"""
        from app import Warehouse, get_warehouse_txn_delta_map
        wh_a, wh_b = warehouses
        with app_module.app.app_context():
            m1 = _seed_material("M001", "6204轴承")
            _seed_txn(m1, wh_a, 100, on_day=D2)
            _seed_txn(m1, wh_a, -40, on_day=D1)
            _seed_txn(m1, wh_a, 10, on_day=TODAY)
            _seed_txn(m1, wh_b, 30, on_day=TODAY)  # 他仓流水不得混入
            warehouse = db.session.get(Warehouse, wh_a)

            # since = 今天 00:00 → 只含今天的 +10
            since_today = datetime.combine(TODAY, time(0, 0))
            assert get_warehouse_txn_delta_map(warehouse, since_today) == {m1: 10.0}

            # since = 昨天 00:00 → −40 + 10 = −30
            since_d1 = datetime.combine(D1, time(0, 0))
            assert get_warehouse_txn_delta_map(warehouse, since_d1) == {m1: -30.0}

            # since = 前天 00:00 → 全部 A 仓流水 = 70
            since_d2 = datetime.combine(D2, time(0, 0))
            assert get_warehouse_txn_delta_map(warehouse, since_d2) == {m1: 70.0}

    def test_delta_map_empty_warehouse_and_none(self, warehouses):
        """无流水仓库返回空；warehouse 为 None 返回空（调用方按 0 处理）。"""
        from app import Warehouse, get_warehouse_txn_delta_map
        wh_a, _ = warehouses
        with app_module.app.app_context():
            warehouse = db.session.get(Warehouse, wh_a)
            since = datetime.combine(TODAY, time(0, 0))
            assert get_warehouse_txn_delta_map(warehouse, since) == {}
            assert get_warehouse_txn_delta_map(None, since) == {}

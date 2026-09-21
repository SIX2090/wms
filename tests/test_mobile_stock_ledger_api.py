# -*- coding: utf-8 -*-
"""移动端库存台账 API 测试（AI-MOB-LDG-F01）。

GET /api/mobile/report/stock_ledger：按单一物料查看库存流水账（只读）——
期初结存、逐笔入/出、行级结存、期末结存，口径与电脑端库存台账
（app.py _collect_ledger_rows）同源。

覆盖：
L1. 端点已注册。
L2. 未登录访问返回 401。
L3. material_code 缺失 → 400（单一物料口径，AI-OS-LD-001）。
L4. 物料不存在 → 400；编码精确匹配（M001 不串 M0012）。
L5. 全部流水（默认）：opening=0、逐笔 balance 递增链、勾稽 opening+in−out=ending。
L6. marker 行（期初结存/本期合计）不下发到 items。
L7. 指定 start_date：期初=开始日期前累计，items 只含范围内流水。
L8. 双仓隔离（R2）：A 仓流水不出现在 B 仓台账。
L9. summary 与分页解耦 + 分页元数据完整（R1）。
L10. 日期非法 / 倒置 / 未来 → 400。
L11. 仓库缺省回退默认仓（AGENTS.md §二），响应 warehouse 信息正确。
L12. material.warehouse_stock 为仓库级口径（不回退全局 material.stock，A11）。
L13. 历史空 location 流水按来源归属计入（warehouse_id=NULL + location=仓库名，R2 兼容）。
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

ENDPOINT = "mobile_api_report_stock_ledger"
URL = "/api/mobile/report/stock_ledger"


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


def _seed_warehouse(code, name, is_default=False):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active", is_default=is_default)
    db.session.add(w)
    db.session.commit()
    return w.id


def _seed_material(code, name="测试物料"):
    from app import Material
    m = Material(code=code, name=name)
    db.session.add(m)
    db.session.commit()
    return m.id


def _seed_txn(material_id, warehouse_id, quantity, created_at=None, txn_type="in",
              location=None):
    from app import StockTransaction
    txn = StockTransaction(
        material_id=material_id,
        transaction_type=txn_type,
        quantity=quantity,
        warehouse_id=warehouse_id,
        location=location,
        created_at=created_at or _dt.now(),
    )
    db.session.add(txn)
    db.session.commit()


def _get(client, **params):
    return client.get(URL, query_string=params)


class TestMobileStockLedgerApi:
    def _setup(self, with_default_warehouse=False):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            wh_a = _seed_warehouse("WHA", "A仓", is_default=with_default_warehouse)
            wh_b = _seed_warehouse("WHB", "B仓")
            m1 = _seed_material("M001", "轴承")
            m2 = _seed_material("M0012", "螺母")
            return wh_a, wh_b, m1, m2

    def test_L1_endpoint_registered(self):
        assert ENDPOINT in app_module.app.view_functions

    def test_L2_unauthorized_401(self):
        self._setup()
        client = _make_client()
        r = _get(client, material_code="M001")
        assert r.status_code == 401

    def test_L3_material_code_required(self):
        self._setup(with_default_warehouse=True)
        client = _make_client()
        _login(client)
        r = _get(client)
        assert r.status_code == 400
        assert 'material_code' in (r.get_json().get('msg') or '')

    def test_L4_material_exact_match(self):
        wh_a, wh_b, m1, m2 = self._setup(with_default_warehouse=True)
        with app_module.app.app_context():
            _seed_txn(m1, wh_a, 10)
            _seed_txn(m2, wh_a, 99)
        client = _make_client()
        _login(client)
        # 不存在的物料 → 400
        r = _get(client, material_code="NOPE")
        assert r.status_code == 400
        # 精确匹配：M001 的台账不得混入 M0012 的流水（相似编码不串）
        r = _get(client, material_code="M001")
        assert r.status_code == 200
        data = r.get_json()['data']
        assert data['material']['code'] == 'M001'
        assert data['summary']['count'] == 1
        assert data['summary']['total_in_quantity'] == 10

    def test_L5_full_ledger_running_balance_and_reconciliation(self):
        wh_a, wh_b, m1, m2 = self._setup(with_default_warehouse=True)
        with app_module.app.app_context():
            base = _dt.now() - _td(days=3)
            _seed_txn(m1, wh_a, 10, created_at=base)
            _seed_txn(m1, wh_a, 5, created_at=base + _td(days=1))
            _seed_txn(m1, wh_a, -3, created_at=base + _td(days=2), txn_type="out")
        client = _make_client()
        _login(client)
        r = _get(client, material_code="M001")
        assert r.status_code == 200
        data = r.get_json()['data']
        s = data['summary']
        # 默认全部流水：期初=0
        assert s['opening_balance'] == 0
        assert s['total_in_quantity'] == 15
        assert s['total_out_quantity'] == 3
        assert s['ending_balance'] == 12
        assert s['count'] == 3
        # 勾稽：期初 + 入 − 出 = 期末
        assert abs(s['opening_balance'] + s['total_in_quantity']
                   - s['total_out_quantity'] - s['ending_balance']) < 1e-9
        # 行级结存链
        balances = [it['balance_quantity'] for it in data['items']]
        assert balances == [10, 15, 12]

    def test_L6_marker_rows_not_in_items(self):
        wh_a, wh_b, m1, m2 = self._setup(with_default_warehouse=True)
        with app_module.app.app_context():
            _seed_txn(m1, wh_a, 10)
        client = _make_client()
        _login(client)
        r = _get(client, material_code="M001")
        labels = [it['reference_type'] for it in r.get_json()['data']['items']]
        assert '期初结存' not in labels
        assert '本期合计' not in labels

    def test_L7_start_date_opening_balance(self):
        wh_a, wh_b, m1, m2 = self._setup(with_default_warehouse=True)
        with app_module.app.app_context():
            old = _dt.now() - _td(days=10)
            _seed_txn(m1, wh_a, 20, created_at=old)                      # 期前累计
            _seed_txn(m1, wh_a, 5, created_at=_dt.now() - _td(days=1))   # 期内
        client = _make_client()
        _login(client)
        start = (_dt.now() - _td(days=2)).date().isoformat()
        r = _get(client, material_code="M001", start_date=start)
        assert r.status_code == 200
        data = r.get_json()['data']
        s = data['summary']
        assert s['opening_balance'] == 20
        assert s['total_in_quantity'] == 5
        assert s['ending_balance'] == 25
        assert s['count'] == 1
        assert len(data['items']) == 1

    def test_L8_warehouse_isolation(self):
        wh_a, wh_b, m1, m2 = self._setup()
        with app_module.app.app_context():
            _seed_txn(m1, wh_a, 10)
            _seed_txn(m1, wh_b, 777)
        client = _make_client()
        _login(client)
        r = _get(client, material_code="M001", warehouse_id=wh_a)
        data = r.get_json()['data']
        assert data['summary']['total_in_quantity'] == 10
        assert data['summary']['ending_balance'] == 10
        r = _get(client, material_code="M001", warehouse_id=wh_b)
        data = r.get_json()['data']
        assert data['summary']['total_in_quantity'] == 777

    def test_L9_summary_decoupled_from_pagination(self):
        wh_a, wh_b, m1, m2 = self._setup(with_default_warehouse=True)
        with app_module.app.app_context():
            for i in range(5):
                _seed_txn(m1, wh_a, 2, created_at=_dt.now() - _td(days=5 - i))
        client = _make_client()
        _login(client)
        r = _get(client, material_code="M001", page=2, page_size=2)
        assert r.status_code == 200
        data = r.get_json()['data']
        # summary 基于全集（R1）
        assert data['summary']['count'] == 5
        assert data['summary']['total_in_quantity'] == 10
        # 分页元数据完整
        assert data['total'] == 5
        assert data['page'] == 2
        assert data['page_size'] == 2
        assert data['total_pages'] == 3
        assert len(data['items']) == 2

    def test_L10_date_validation(self):
        self._setup(with_default_warehouse=True)
        client = _make_client()
        _login(client)
        r = _get(client, material_code="M001", start_date="2026/01/01")
        assert r.status_code == 400
        yesterday = (_dt.now() - _td(days=1)).date().isoformat()
        r = _get(client, material_code="M001", start_date=yesterday,
                 end_date=(_dt.now() - _td(days=2)).date().isoformat())
        assert r.status_code == 400
        future = (_dt.now() + _td(days=1)).date().isoformat()
        r = _get(client, material_code="M001", end_date=future)
        assert r.status_code == 400

    def test_L11_default_warehouse_fallback(self):
        wh_a, wh_b, m1, m2 = self._setup(with_default_warehouse=True)
        with app_module.app.app_context():
            _seed_txn(m1, wh_a, 8)
        client = _make_client()
        _login(client)
        r = _get(client, material_code="M001")
        assert r.status_code == 200
        data = r.get_json()['data']
        assert data['warehouse']['id'] == wh_a
        assert data['warehouse']['name'] == 'A仓'

    def test_L12_material_warehouse_stock_scoped(self):
        wh_a, wh_b, m1, m2 = self._setup()
        with app_module.app.app_context():
            _seed_txn(m1, wh_a, 12)
            _seed_txn(m1, wh_b, 30)
        client = _make_client()
        _login(client)
        r = _get(client, material_code="M001", warehouse_id=wh_a)
        assert r.get_json()['data']['material']['warehouse_stock'] == 12
        r = _get(client, material_code="M001", warehouse_id=wh_b)
        assert r.get_json()['data']['material']['warehouse_stock'] == 30

    def test_L13_legacy_empty_warehouse_id_attributed_by_location(self):
        wh_a, wh_b, m1, m2 = self._setup()
        with app_module.app.app_context():
            # 历史脏数据：warehouse_id 为 NULL，仅 location 记仓库名（R2 兼容）
            _seed_txn(m1, None, 6, location='A仓')
            _seed_txn(m1, None, 100, location='B仓')
        client = _make_client()
        _login(client)
        r = _get(client, material_code="M001", warehouse_id=wh_a)
        data = r.get_json()['data']
        assert data['summary']['total_in_quantity'] == 6
        r = _get(client, material_code="M001", warehouse_id=wh_b)
        data = r.get_json()['data']
        assert data['summary']['total_in_quantity'] == 100

# -*- coding: utf-8 -*-
"""BUG-2026-09-10-006 回归：手机原生端出库业务类型统一为「领料单」。

背景：POST /api/outbound 固定写 business_type='Android扫码出库'，与 PC 领料单
（'领料单'）不是同一业务类型，导致：
- 手机出的库进不了每日报表「领料单」口径（首页今日出库却有数）；
- PC 领料单列表也看不到手机单据（列表默认只显示 领料单 / 类型为空）。

修复：手机原生端出库统一写 '领料单'，来源由 purpose/remark 区分；
历史 'Android扫码出库' 单据由 daily_detail 报表口径兼容。

验收：
- T1 /api/outbound 生成的出库单 business_type 必须是 '领料单'
- T2 手机出的库当日即出现在每日报表 requisition 明细
- T3 手机出的库出现在 PC 领料单列表默认口径（business_type in (领料单, NULL)）
- T4 Android OutboundRequest 默认 business_type 同步为「领料单」（契约一致）
"""
from __future__ import annotations

import os
import sys
from datetime import date
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

TODAY = date.today()
SCAN_REQUESTS_KT = (ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/"
                    "data/model/ScanRequests.kt")


def _seed():
    from app import Material, Unit, User, Warehouse

    db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
    wh = Warehouse(code="WH01", name="材料仓", status="active", is_default=True)
    unit = Unit(code="U1", name="个")
    db.session.add_all([wh, unit])
    db.session.flush()
    db.session.add(Material(code="MAT001", name="6204轴承", spec="20*47*14",
                            stock=100, price=1.5, unit=unit))
    db.session.commit()


@pytest.fixture()
def client():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        _seed()
        db.session.remove()
    c = app_module.app.test_client()
    yield c
    with app_module.app.app_context():
        db.session.remove()


def _bearer(c):
    resp = c.post("/api/login", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return {"Authorization": f"Bearer {resp.get_json()['data']['token']}"}


def _post_outbound(c, headers):
    return c.post("/api/outbound", json={
        "warehouse_code": "WH01",
        "lines": [{"material_code": "MAT001", "quantity": 2}],
    }, headers=headers)


class TestOutboundBusinessType:
    def test_t1_outbound_writes_requisition_type(self, client):
        resp = _post_outbound(client, _bearer(client))
        assert resp.status_code == 200, resp.get_json()
        from app import OutOrder
        with app_module.app.app_context():
            order = OutOrder.query.order_by(OutOrder.id.desc()).first()
            assert order.business_type == "领料单"

    def test_t2_visible_in_daily_report_same_day(self, client):
        _post_outbound(client, _bearer(client))
        resp = client.get(
            f"/api/mobile/report/daily_detail?type=requisition&date={TODAY.isoformat()}",
            headers=_bearer(client),
        )
        data = resp.get_json()["data"]
        assert data["summary"]["order_count"] == 1, "手机出库必须当日出现在领料日报"
        assert data["items"][0]["material_code"] == "MAT001"

    def test_t3_visible_in_pc_requisition_list(self, client):
        _post_outbound(client, _bearer(client))
        from app import OutOrder, db as _db
        with app_module.app.app_context():
            # PC 领料单列表默认口径：business_type == '领料单' or is None
            rows = OutOrder.query.filter(
                _db.or_(OutOrder.business_type == "领料单",
                        OutOrder.business_type.is_(None))
            ).all()
            assert len(rows) == 1 and rows[0].business_type == "领料单"

    def test_t4_android_request_default_type(self):
        src = SCAN_REQUESTS_KT.read_text(encoding="utf-8")
        assert 'businessType: String = "领料单"' in src, "Android 出库请求默认类型需与服务端一致"
        assert '= "Android扫码出库"' not in src, "Android 出库请求不得再以 Android扫码出库 为默认类型"

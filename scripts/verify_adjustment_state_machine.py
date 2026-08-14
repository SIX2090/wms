#!/usr/bin/env python3
"""Verify positive and negative inventory adjustments are reversible."""
from __future__ import annotations
import os
import sys
from datetime import date
from pathlib import Path
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    sys.path.insert(0, str(ROOT / "app"))
    os.environ.setdefault("FLASK_ENV", "testing")
    os.environ.setdefault("WMS_SKIP_DB_UPGRADE", "1")
    import app as wms
    wms.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with wms.app.app_context():
        wms.db.create_all()
        user = wms.User.query.filter_by(username="adjustment_state_machine").first()
        if not user:
            user = wms.User(username="adjustment_state_machine", role="warehouse", status="normal", password_hash=generate_password_hash("Password123!")); wms.db.session.add(user)
        material = wms.Material.query.filter_by(code="ADJUSTMENT-STATE-MAT").first()
        if not material:
            material = wms.Material(code="ADJUSTMENT-STATE-MAT", name="Adjustment state material", stock=10); wms.db.session.add(material)
        wms.db.session.commit()
        orders = []
        for no, quantity in (("ADJUST-PLUS-001", 5), ("ADJUST-MINUS-001", -8), ("ADJUST-TOO-MUCH-001", -20)):
            # BUG-2026-08-02-010：调整单是出入库单据，仓库为必填，完成时要求 warehouse 非空。
            order = wms.AdjustmentOrder(adjustment_no=no, date=date.today(), adjustment_type="manual", status="pending", warehouse="默认测试仓", operator_id=user.id)
            wms.db.session.add(order); wms.db.session.flush()
            wms.db.session.add(wms.AdjustmentOrderItem(adjustment_order_id=order.id, material_id=material.id, quantity=quantity))
            orders.append(order.id)
        wms.db.session.commit()
    client = wms.app.test_client()
    assert client.post("/login", data={"username":"adjustment_state_machine","password":"Password123!"}).status_code in (302,303)
    plus, minus, too_much = orders
    assert client.post(f"/adjustment/{plus}/complete").status_code == 200
    assert client.post(f"/adjustment/{plus}/complete").status_code == 400
    assert client.post(f"/adjustment/{minus}/complete").status_code == 200
    with wms.app.app_context(): assert wms.Material.query.filter_by(code="ADJUSTMENT-STATE-MAT").first().stock == 7
    assert client.post(f"/adjustment/{too_much}/complete").status_code == 400
    assert client.post(f"/adjustment/{minus}/revert").status_code == 200
    assert client.post(f"/adjustment/{plus}/revert").status_code == 200
    with wms.app.app_context(): assert wms.Material.query.filter_by(code="ADJUSTMENT-STATE-MAT").first().stock == 10
    print("PASS: adjustment state machine preserves stock through completion and reversal")


if __name__ == "__main__": main()

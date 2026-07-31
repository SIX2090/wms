#!/usr/bin/env python3
# AI_TASK: AI-STAB-F03
"""Regression test for outbound stock protection and reversal."""
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
        user = wms.User.query.filter_by(username="out_state_machine_warehouse").first()
        if not user:
            user = wms.User(username="out_state_machine_warehouse", role="warehouse", status="normal", password_hash=generate_password_hash("Password123!"))
            wms.db.session.add(user)
        material = wms.Material.query.filter_by(code="OUT-STATE-MACHINE-MAT").first()
        if not material:
            material = wms.Material(code="OUT-STATE-MACHINE-MAT", name="Outbound state machine material", stock=5)
            wms.db.session.add(material)
        wms.db.session.commit()
        order = wms.OutOrder(order_no="OUT-STATE-MACHINE-001", date=date.today(), business_type="领料出库", status="pending", operator_id=user.id)
        wms.db.session.add(order)
        wms.db.session.flush()
        wms.db.session.add(wms.OutOrderItem(out_order_id=order.id, material_id=material.id, quantity=10, price=1, amount=10))
        wms.db.session.commit()
        order_id, material_id = order.id, material.id

    client = wms.app.test_client()
    assert client.post("/login", data={"username": "out_state_machine_warehouse", "password": "Password123!"}).status_code in (302, 303)
    assert client.post(f"/out_order/{order_id}/complete").status_code == 400
    with wms.app.app_context():
        assert wms.db.session.get(wms.OutOrder, order_id).status == "pending"
        material = wms.db.session.get(wms.Material, material_id)
        material.stock = 20
        wms.db.session.commit()
    assert client.post(f"/out_order/{order_id}/complete").status_code == 200
    with wms.app.app_context():
        assert wms.db.session.get(wms.Material, material_id).stock == 10
    assert client.post(f"/out_order/{order_id}/delete").status_code == 400
    assert client.post(f"/out_order/{order_id}/revert").status_code == 200
    with wms.app.app_context():
        assert wms.db.session.get(wms.Material, material_id).stock == 20
    assert client.post(f"/out_order/{order_id}/delete").status_code == 200
    print("PASS: outbound state machine protects stock and restores it on reversal")


if __name__ == "__main__":
    main()

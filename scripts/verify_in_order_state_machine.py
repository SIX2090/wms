#!/usr/bin/env python3
# AI_TASK: AI-STAB-F02
"""Regression test for inbound completion, reversal, and deletion boundaries."""
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
        user = wms.User.query.filter_by(username="state_machine_warehouse").first()
        if not user:
            user = wms.User(username="state_machine_warehouse", role="warehouse", status="normal",
                            password_hash=generate_password_hash("Password123!"))
            wms.db.session.add(user)
        material = wms.Material.query.filter_by(code="STATE-MACHINE-MAT").first()
        if not material:
            material = wms.Material(code="STATE-MACHINE-MAT", name="State machine material", stock=0)
            wms.db.session.add(material)
        wms.db.session.commit()
        order = wms.InOrder(order_no="STATE-MACHINE-IN-001", date=date.today(), business_type="采购入库",
                            status="pending", operator_id=user.id)
        wms.db.session.add(order)
        wms.db.session.flush()
        wms.db.session.add(wms.InOrderItem(in_order_id=order.id, material_id=material.id,
                                           quantity=10, price=1, amount=10))
        wms.db.session.commit()
        order_id, material_id = order.id, material.id

    client = wms.app.test_client()
    assert client.post("/login", data={"username": "state_machine_warehouse", "password": "Password123!"}).status_code in (302, 303)
    assert client.post(f"/in_order/{order_id}/complete?force=1").status_code == 200
    with wms.app.app_context():
        assert wms.db.session.get(wms.InOrder, order_id).status == "completed"
        assert wms.db.session.get(wms.Material, material_id).stock == 10
    assert client.post(f"/in_order/{order_id}/delete").status_code == 409
    assert client.post(f"/in_order/{order_id}/revert").status_code == 200
    with wms.app.app_context():
        assert wms.db.session.get(wms.InOrder, order_id).status == "pending"
        assert wms.db.session.get(wms.Material, material_id).stock == 0
    assert client.post(f"/in_order/{order_id}/delete").status_code == 200
    with wms.app.app_context():
        assert wms.db.session.get(wms.InOrder, order_id) is None
    print("PASS: inbound state machine preserves inventory and deletion boundary")


if __name__ == "__main__":
    main()

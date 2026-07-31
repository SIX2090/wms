#!/usr/bin/env python3
"""Verify transfer completion and reversal preserve location balances."""
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
        user = wms.User.query.filter_by(username="transfer_state_machine").first()
        if not user:
            user = wms.User(username="transfer_state_machine", role="warehouse", status="normal", password_hash=generate_password_hash("Password123!"))
            wms.db.session.add(user)
        material = wms.Material.query.filter_by(code="TRANSFER-STATE-MAT").first()
        if not material:
            material = wms.Material(code="TRANSFER-STATE-MAT", name="Transfer state material", stock=10)
            wms.db.session.add(material)
        wms.db.session.commit()
        wms.db.session.merge(wms.LocationInventory(material_id=material.id, location="FROM", quantity=10))
        order = wms.TransferOrder(transfer_no="TRANSFER-STATE-001", date=date.today(), from_location="FROM", to_location="TO", status="pending", operator_id=user.id)
        wms.db.session.add(order)
        wms.db.session.flush()
        wms.db.session.add(wms.TransferOrderItem(transfer_order_id=order.id, material_id=material.id, quantity=4, price=0, amount=0))
        wms.db.session.commit()
        order_id, material_id = order.id, material.id

    client = wms.app.test_client()
    assert client.post("/login", data={"username": "transfer_state_machine", "password": "Password123!"}).status_code in (302, 303)
    assert client.post(f"/transfer/{order_id}/complete").status_code == 200
    assert client.post(f"/transfer/{order_id}/complete").status_code == 400
    with wms.app.app_context():
        rows = {row.location: row.quantity for row in wms.LocationInventory.query.filter_by(material_id=material_id)}
        assert rows == {"FROM": 6, "TO": 4}
        assert wms.db.session.get(wms.Material, material_id).stock == 10
    assert client.post(f"/transfer/{order_id}/revert").status_code == 200
    assert client.post(f"/transfer/{order_id}/revert").status_code == 400
    with wms.app.app_context():
        rows = {row.location: row.quantity for row in wms.LocationInventory.query.filter_by(material_id=material_id)}
        assert rows == {"FROM": 10, "TO": 0}
    print("PASS: transfer state machine preserves total and location inventory")


if __name__ == "__main__":
    main()

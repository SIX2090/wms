#!/usr/bin/env python3
"""Verify inventory checks create reversible adjustment drafts."""
from __future__ import annotations
import os, sys
from datetime import date
from pathlib import Path
from werkzeug.security import generate_password_hash
ROOT = Path(__file__).resolve().parents[1]

def main() -> None:
    sys.path.insert(0, str(ROOT / "app")); os.environ.setdefault("FLASK_ENV", "testing"); os.environ.setdefault("WMS_SKIP_DB_UPGRADE", "1")
    import app as wms
    wms.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with wms.app.app_context():
        wms.db.create_all()
        user=wms.User.query.filter_by(username="check_state_machine").first()
        if not user: user=wms.User(username="check_state_machine",role="warehouse",status="normal",password_hash=generate_password_hash("Password123!")); wms.db.session.add(user)
        material=wms.Material.query.filter_by(code="CHECK-STATE-MAT").first()
        if not material: material=wms.Material(code="CHECK-STATE-MAT",name="Check state material",stock=10); wms.db.session.add(material)
        wms.db.session.commit()
        check=wms.InventoryCheck(check_no="CHECK-STATE-001",date=date.today(),status="pending",operator_id=user.id); wms.db.session.add(check); wms.db.session.flush()
        wms.db.session.add(wms.InventoryCheckItem(inventory_check_id=check.id,material_id=material.id,system_stock=10,actual_stock=12,difference=2)); wms.db.session.commit(); check_id=check.id
    client=wms.app.test_client(); assert client.post("/login",data={"username":"check_state_machine","password":"Password123!"}).status_code in (302,303)
    assert client.post(f"/check/{check_id}/complete").status_code==200
    assert client.post(f"/check/{check_id}/complete").status_code==400
    with wms.app.app_context():
        drafts=wms.AdjustmentOrder.query.filter_by(source_type="check",source_id=check_id).all(); assert len(drafts)==1 and drafts[0].status=="pending"
    assert client.post(f"/check/{check_id}/revert").status_code==200
    with wms.app.app_context(): assert wms.AdjustmentOrder.query.filter_by(source_type="check",source_id=check_id).count()==0
    print("PASS: inventory check creates and reverses adjustment drafts")
if __name__=="__main__": main()

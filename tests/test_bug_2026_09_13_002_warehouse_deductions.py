import pytest

import app as wms


@pytest.fixture
def scene(monkeypatch):
    monkeypatch.setitem(wms.app.config, "TESTING", True)
    monkeypatch.setitem(wms.app.config, "WTF_CSRF_ENABLED", False)
    with wms.app.app_context():
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()
        wms.set_system_setting("location_management_enabled", "0")
        wms.set_system_setting("allow_negative_stock", "0")
        user = wms.User(username="reviewer", password_hash="unused-test-hash",
                        role="admin", must_change_password=False)
        source = wms.Warehouse(code="WA", name="Warehouse A", status="active", is_default=True)
        other = wms.Warehouse(code="WB", name="Warehouse B", status="active")
        material = wms.Material(code="M-REVIEW", name="Review material", stock=100)
        wms.db.session.add_all([user, source, other, material])
        wms.db.session.flush()
        wms.db.session.add(wms.StockTransaction(
            material_id=material.id, transaction_type="in", quantity=100,
            warehouse_id=other.id, location=other.name))
        wms.db.session.commit()
        client = wms.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True
        yield client, source, other, material
        wms.db.session.remove()


def _stock(material, warehouse, quantity, legacy=False):
    material.stock += quantity
    wms.db.session.add(wms.StockTransaction(
        material_id=material.id, transaction_type="in", quantity=quantity,
        warehouse_id=None if legacy else warehouse.id, location=warehouse.code if legacy else warehouse.name))
    wms.db.session.commit()


@pytest.mark.parametrize("kind", ["after_sale", "adjustment_loss", "adjustment_revert"])
@pytest.mark.parametrize("available", [0, 10])
def test_warehouse_deduction_routes(scene, kind, available):
    client, source, other, material = scene
    if available:
        _stock(material, source, available, legacy=True)
    if kind == "after_sale":
        order = wms.AfterSaleOutOrder(order_no="AS-REVIEW", warehouse=source.name, status="pending")
        wms.db.session.add(order)
        wms.db.session.flush()
        wms.db.session.add(wms.AfterSaleOutOrderItem(
            after_sale_out_order_id=order.id, material_id=material.id, quantity=10, price=1, amount=10))
        endpoint = f"/after_sale_out/{order.id}/complete"
    else:
        reverting = kind == "adjustment_revert"
        order = wms.AdjustmentOrder(adjustment_no="ADJ-REVIEW", warehouse=source.name,
                                    adjustment_type="surplus" if reverting else "loss",
                                    status="completed" if reverting else "pending")
        wms.db.session.add(order)
        wms.db.session.flush()
        wms.db.session.add(wms.AdjustmentOrderItem(
            adjustment_order_id=order.id, material_id=material.id, quantity=10 if reverting else -10))
        endpoint = f"/adjustment/{order.id}/{'revert' if reverting else 'complete'}"
    original_status = order.status
    wms.db.session.commit()
    result = client.post(endpoint).get_json()
    assert result["status"] == ("success" if available else "error"), result
    wms.db.session.expire_all()
    assert wms.get_warehouse_stock_quantities(source).get(material.id, 0) == 0
    assert wms.get_warehouse_stock_quantities(other)[material.id] == 100
    assert material.stock == 100
    if not available:
        assert order.status == original_status
        assert wms.StockTransaction.query.count() == 1


@pytest.mark.parametrize("reverting", [False, True])
@pytest.mark.parametrize("available", [10, 14])
def test_transfer_aggregates_duplicate_materials(scene, reverting, available):
    client, source, other, material = scene
    _stock(material, other, -100)
    debit = other if reverting else source
    _stock(material, debit, available)
    order = wms.TransferOrder(transfer_no="TR-REVIEW", from_warehouse=source.name,
                              to_warehouse=other.name, from_location=source.name,
                              to_location=other.name, status="completed" if reverting else "pending")
    wms.db.session.add(order)
    wms.db.session.flush()
    for quantity in (7, 7):
        wms.db.session.add(wms.TransferOrderItem(
            transfer_order_id=order.id, material_id=material.id, quantity=quantity, price=1, amount=quantity))
    wms.db.session.commit()
    original_status = order.status
    txn_count = wms.StockTransaction.query.count()
    result = client.post(f"/transfer/{order.id}/{'revert' if reverting else 'complete'}").get_json()
    assert result["status"] == ("success" if available == 14 else "error"), result
    wms.db.session.expire_all()
    balance = wms.get_warehouse_stock_quantities(debit).get(material.id, 0)
    assert balance == (0 if available == 14 else available)
    assert material.stock == available
    assert sum(wms.get_warehouse_stock_quantities(warehouse).get(material.id, 0)
               for warehouse in (source, other)) == material.stock
    if available < 14:
        assert order.status == original_status
        assert wms.StockTransaction.query.count() == txn_count

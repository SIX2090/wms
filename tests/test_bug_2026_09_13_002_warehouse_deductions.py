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


@pytest.mark.parametrize('available, sibling_quantity, legacy, negative, succeeds', [
    (0, 0, False, False, False),
    (10, 0, False, False, True),
    (10, 0, True, False, True),
    (10, 7, False, False, False),
    (17, 7, True, False, True),
    (0, 0, False, True, True),
])
def test_transfer_item_edit_warehouse_stock(scene, available, sibling_quantity, legacy, negative, succeeds):
    client, source, other, material = scene
    _stock(material, source, available, legacy=legacy)
    wms.set_system_setting('allow_negative_stock', '1' if negative else '0')
    order = wms.TransferOrder(transfer_no='TR-EDIT', status='pending',
                              from_warehouse=None if legacy else source.name,
                              from_location=source.code if legacy else source.name,
                              to_warehouse=other.name, to_location=other.name)
    wms.db.session.add(order)
    wms.db.session.flush()
    item = wms.TransferOrderItem(transfer_order_id=order.id, material_id=material.id,
                                 quantity=1, price=1, amount=1)
    wms.db.session.add(item)
    if sibling_quantity:
        wms.db.session.add(wms.TransferOrderItem(
            transfer_order_id=order.id, material_id=material.id,
            quantity=sibling_quantity, price=1, amount=sibling_quantity))
    wms.db.session.commit()
    transaction_count = wms.StockTransaction.query.count()
    result = client.post(f'/transfer/{order.id}/item/{item.id}/update',
                         data={'quantity': 10, 'price': 2}).get_json()
    assert result['status'] == ('success' if succeeds else 'error'), result
    wms.db.session.expire_all()
    assert item.quantity == (10 if succeeds else 1)
    assert item.amount == (20 if succeeds else 1)
    assert wms.get_warehouse_stock_quantities(source).get(material.id, 0) == available
    assert wms.get_warehouse_stock_quantities(other)[material.id] == 100
    assert material.stock == available + 100
    assert wms.StockTransaction.query.count() == transaction_count


@pytest.mark.parametrize('entry', ['add', 'batch', 'save'])
@pytest.mark.parametrize('available', [0, 10, 17])
def test_transfer_draft_entry_cumulative_stock(scene, entry, available):
    client, source, other, material = scene
    _stock(material, source, available, legacy=True)
    order = wms.TransferOrder(transfer_no='TR-ADD', status='pending',
                              from_warehouse=source.name, from_location=source.name,
                              to_warehouse=other.name, to_location=other.name)
    wms.db.session.add(order)
    wms.db.session.flush()
    wms.db.session.add(wms.TransferOrderItem(
        transfer_order_id=order.id, material_id=material.id, quantity=7, price=1, amount=7))
    wms.db.session.commit()
    order_id = order.id
    if entry == 'save':
        result = client.post('/transfer/save_table', json={
            'order_id': order_id, 'order_no': 'TR-ADD',
            'header': {'from_warehouse': source.name, 'to_warehouse': other.name},
            'items': [{'code': material.code, 'quantity': 7},
                      {'code': material.code, 'quantity': 10}],
        }).get_json()
    elif entry == 'batch':
        result = client.post(f'/transfer/{order_id}/batch_add_items',
                             json={'content': f'{material.code},10,1'}).get_json()
    else:
        result = client.post(f'/transfer/{order_id}/item/add',
                             data={'material_code': material.code, 'quantity': 10}).get_json()
    assert result['status'] == ('success' if available == 17 else 'error'), result
    wms.db.session.expire_all()
    items = wms.TransferOrderItem.query.filter_by(transfer_order_id=order_id).all()
    assert sum(item.quantity for item in items) == (17 if available == 17 else 7)
    assert wms.get_warehouse_stock_quantities(source).get(material.id, 0) == available
    assert wms.get_warehouse_stock_quantities(other)[material.id] == 100
    assert material.stock == available + 100


def test_transfer_batch_counts_accepted_rows(scene):
    client, source, other, material = scene
    _stock(material, source, 10)
    order = wms.TransferOrder(transfer_no='TR-BATCH', status='pending',
                              from_warehouse=source.name, to_warehouse=other.name,
                              from_location=source.name, to_location=other.name)
    wms.db.session.add(order)
    wms.db.session.commit()
    result = client.post(f'/transfer/{order.id}/batch_add_items', json={
        'content': f'{material.code},7,1\n{material.code},7,1',
    }).get_json()
    assert result['status'] == 'success', result
    items = wms.TransferOrderItem.query.filter_by(transfer_order_id=order.id).all()
    assert len(items) == 1
    assert items[0].quantity == 7


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

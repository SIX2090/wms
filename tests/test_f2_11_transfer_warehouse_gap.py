# -*- coding: utf-8 -*-
"""F2.11 回归：调拨仓库缺口（审计报告 §8.2 / §一）。

修复前：
  - `complete_transfer` 对空 `from_warehouse`/`to_warehouse` **整段跳过**仓库校验，
    `apply_transfer_pair` 照常写出一对无仓库归属的 transfer_out/transfer_in 流水
    （多仓库下不计入任何仓、污染台账归属），且完成操作返回成功。
  - `copy_transfer` 构造新单时**丢弃** from_warehouse/to_warehouse，复制出的草稿
    缺仓库，不可用（完成时会被拒绝）。

修复后：
  - 空仓库完成调拨返回 400；
  - 复制单带上 from_warehouse/to_warehouse 且可正常完成；
  - 不再产生无仓库归属的调拨流水。
"""
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
        material = wms.Material(code="M-TF", name="Transfer material", stock=100)
        wms.db.session.add_all([user, source, other, material])
        wms.db.session.flush()
        wms.db.session.add(wms.StockTransaction(
            material_id=material.id, transaction_type="in", quantity=100,
            warehouse_id=source.id, location=source.name))
        wms.db.session.commit()
        client = wms.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True
        yield client, source, other, material
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()


def _pending_transfer(material, from_warehouse, to_warehouse, quantity=5):
    order = wms.TransferOrder(
        transfer_no=wms.generate_order_no("TF"), status="pending",
        from_warehouse=from_warehouse, to_warehouse=to_warehouse,
        from_location=from_warehouse, to_location=to_warehouse)
    wms.db.session.add(order)
    wms.db.session.flush()
    wms.db.session.add(wms.TransferOrderItem(
        transfer_order_id=order.id, material_id=material.id,
        quantity=quantity, price=1, amount=quantity))
    wms.db.session.commit()
    return order.id


@pytest.mark.parametrize("missing", ["from", "to"])
def test_complete_transfer_rejects_empty_warehouse(scene, missing):
    """空调出/调入仓库时完成必须被拒绝，且不写任何调拨流水。"""
    client, source, other, material = scene
    order_id = _pending_transfer(
        material,
        from_warehouse="" if missing == "from" else source.name,
        to_warehouse="" if missing == "to" else other.name)
    txn_before = wms.StockTransaction.query.count()

    resp = client.post(f"/transfer/{order_id}/complete")
    assert resp.status_code == 400, resp.get_json()
    body = resp.get_json()
    assert body["status"] == "error"
    assert "仓库" in body["msg"]

    wms.db.session.expire_all()
    assert wms.db.session.get(wms.TransferOrder, order_id).status == "pending"
    # 未产生任何无仓库归属流水
    assert wms.StockTransaction.query.count() == txn_before


def test_copy_transfer_carries_warehouses_and_can_complete(scene):
    """复制单必须带上仓库，且复制出的草稿可正常完成。"""
    client, source, other, material = scene
    order_id = _pending_transfer(material, source.name, other.name)

    cp = client.post(f"/transfer/{order_id}/copy")
    assert cp.get_json()["status"] == "success", cp.get_json()
    with wms.app.app_context():
        orig_no = wms.db.session.get(wms.TransferOrder, order_id).transfer_no
        new_order = (wms.TransferOrder.query
                     .filter(wms.TransferOrder.transfer_no != orig_no)
                     .order_by(wms.TransferOrder.id.desc()).first())
        assert new_order is not None
        assert new_order.from_warehouse == source.name
        assert new_order.to_warehouse == other.name
        assert len(new_order.items) == 1
        new_id = new_order.id

    done = client.post(f"/transfer/{new_id}/complete")
    assert done.get_json()["status"] == "success", done.get_json()
    wms.db.session.expire_all()
    assert wms.db.session.get(wms.TransferOrder, new_id).status == "completed"

    # 调拨流水必须带仓库归属（不再有无仓库流水）
    txns = wms.StockTransaction.query.filter_by(
        reference_type="transfer", reference_id=new_id).all()
    assert txns, "调拨应写出双向流水"
    for t in txns:
        assert t.warehouse_id is not None, f"调拨流水缺仓库归属: {t.id}"

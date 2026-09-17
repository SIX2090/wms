from datetime import date

import pytest

import app as wms
from routes import sales


@pytest.fixture
def scene(monkeypatch):
    monkeypatch.setitem(wms.app.config, "TESTING", True)
    monkeypatch.setitem(wms.app.config, "LOGIN_DISABLED", True)
    with wms.app.app_context():
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()
        wms.set_system_setting("location_management_enabled", "0")
        source = wms.Warehouse(code="WA", name="Warehouse A", status="active")
        other = wms.Warehouse(code="WB", name="Warehouse B", status="active")
        customer = wms.Customer(code="C015", name="Customer")
        material = wms.Material(code="M015", name="Material", stock=103)
        wms.db.session.add_all([source, other, customer, material])
        wms.db.session.flush()
        wms.db.session.add_all([
            wms.StockTransaction(material_id=material.id, quantity=3,
                                 transaction_type="in", location=source.code),
            wms.StockTransaction(material_id=material.id, quantity=100,
                                 transaction_type="in", warehouse_id=other.id,
                                 location=other.name),
        ])
        orders = []
        for warehouse in (source, other):
            order = wms.SalesOrder(order_no=warehouse.code, customer_id=customer.id,
                                  warehouse=warehouse.name, warehouse_id=warehouse.id,
                                  status="confirmed", shipment_status="pending",
                                  delivery_date=date.today())
            wms.db.session.add(order)
            wms.db.session.flush()
            wms.db.session.add(wms.SalesOrderItem(sales_order_id=order.id,
                               material_id=material.id, quantity=10,
                               shipped_quantity=2, price=1))
            orders.append(order)
        wms.db.session.commit()
        context = {}

        def capture(template, **values):
            context.update(values)
            return "ok"

        monkeypatch.setattr(sales, "render_template", capture)
        yield wms.app.test_client(), context, orders, material, source, other
        # 污染治理（AI-CI-GREEN-001）：与 002 的 scene fixture 同根因——
        # sales_order_item 残留行引用 material，泄漏给后续测试文件。
        # teardown 与 setup 对称：重建空 schema，交还干净数据库。
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()


@pytest.mark.parametrize("endpoint", ["dashboard", "exceptions"])
@pytest.mark.parametrize("legacy", [False, True])
def test_pages_isolate_warehouse_and_keep_legacy_stock(scene, endpoint, legacy):
    client, context, orders, material, source, other = scene
    if legacy:
        orders[0].warehouse_id = None
        orders[0].warehouse = source.code
    else:
        orders[0].warehouse = "old warehouse name"
    wms.db.session.commit()
    assert client.get(f"/sales/{endpoint}").status_code == 200
    rows = context.get("shortage_items", context.get("exceptions"))
    assert [row["order"].id for row in rows] == [orders[0].id]
    if endpoint == "dashboard":
        assert rows[0]["stock"] == 3
        assert rows[0]["remaining"] == 8
    else:
        assert context["counts"]["shortage"] == 1
    assert wms.get_warehouse_stock_quantities(source)[material.id] == 3
    assert wms.get_warehouse_stock_quantities(other)[material.id] == 100
    assert material.stock == 103
    assert wms.StockTransaction.query.count() == 2


@pytest.mark.parametrize("endpoint", ["dashboard", "exceptions"])
@pytest.mark.parametrize("warehouse", ["", "missing", "inactive"])
def test_invalid_warehouse_is_unknown_not_shortage(scene, endpoint, warehouse):
    client, context, orders, material, source, other = scene
    orders[0].warehouse_id = None
    orders[0].warehouse = warehouse
    if warehouse == "inactive":
        source.status = "inactive"
        orders[0].warehouse_id = source.id
    wms.db.session.commit()
    assert client.get(f"/sales/{endpoint}").status_code == 200
    assert not context.get("shortage_items", context.get("exceptions"))
    assert context["stock_scope_incomplete"] is True


def test_analysis_cache_reuses_warehouse_id_across_aliases(scene, monkeypatch):
    client, context, orders, material, source, other = scene
    calls = []
    original = wms.get_warehouse_stock_quantities

    def counted(warehouse):
        calls.append(warehouse.id)
        return original(warehouse)

    monkeypatch.setattr(wms, "get_warehouse_stock_quantities", counted)
    with wms.app.test_request_context():
        cache = {}
        stock = sales._sales_analysis_stock(orders[0], cache)
        orders[0].warehouse_id = None
        orders[0].warehouse = source.code
        assert sales._sales_analysis_stock(orders[0], cache) is stock
        assert calls == [source.id]
        assert stock[material.id] == 3
        assert sales._sales_analysis_stock(orders[0], {})[material.id] == 3
        assert calls == [source.id, source.id]
    wms.db.session.rollback()


@pytest.mark.parametrize("endpoint", ["dashboard", "exceptions"])
def test_sales_pages_render_unknown_warehouse_warning(scene, monkeypatch, endpoint):
    from flask import render_template

    client, context, orders, material, source, other = scene
    orders[0].warehouse = ""
    orders[0].warehouse_id = None
    wms.db.session.commit()
    monkeypatch.setattr(sales, "render_template", render_template)
    with client.get(f"/sales/{endpoint}") as response:
        assert response.status_code == 200
        assert "库存待人工确认" in response.get_data(as_text=True)

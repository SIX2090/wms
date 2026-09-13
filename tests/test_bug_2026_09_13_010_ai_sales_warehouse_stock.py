from pathlib import Path


def test_sales_ai_shortage_uses_warehouse_stock_and_full_count():
    source = (Path(__file__).parents[1] / "app" / "app.py").read_text(encoding="utf-8")
    short = source.split("def _ai_sf_query_short_stock():", 1)[1].split("def _ai_sf_query_customer_urgency():", 1)[0]
    follow = source.split("def _ai_sf_query_customer_followup_list():", 1)[1].split("def _ai_kv_query_all_versions():", 1)[0]
    assert "get_warehouse_stock_quantities" in short
    assert "validate_sales_warehouse" in short
    assert ".limit(50)" not in short
    assert "material.stock" not in short
    assert "get_warehouse_stock_quantities" in follow
    assert "validate_sales_warehouse" in follow
    assert "material.stock" not in follow

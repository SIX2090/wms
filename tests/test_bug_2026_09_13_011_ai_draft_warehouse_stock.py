from pathlib import Path


def test_ai_draft_check_uses_warehouse_stock_for_outbound_and_transfer():
    source = (Path(__file__).parents[1] / "app" / "app.py").read_text(encoding="utf-8")
    block = source.split("def _ai_check_draft(module_key, order):", 1)[1].split("def _ai_draft_check_response", 1)[0]
    assert "validate_inventory_warehouse" in block
    assert "get_warehouse_stock_quantities" in block
    assert "material.stock" not in block

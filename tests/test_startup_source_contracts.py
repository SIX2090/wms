from pathlib import Path
import pytest
from tests.startup_source_contracts import startup_dispatch_positions

def test_actual_dispatch_count_and_critical_order():
    source=(Path(__file__).resolve().parents[1]/'app/app.py').read_text(encoding='utf-8')
    positions=startup_dispatch_positions(source)
    assert len(positions)==18
    assert positions['ensure_print_job_columns']<positions['ensure_stock_transaction_warehouse_id_column']
    assert positions['ensure_opening_stock_doc_columns']<positions['ensure_opening_stock_doc_table']<positions['cleanup_dangling_opening_stock_transactions']

def test_uncontrolled_direct_call_does_not_satisfy_contract():
    assert startup_dispatch_positions('ensure_print_job_columns()')=={}

def test_comment_or_string_does_not_satisfy_contract():
    assert startup_dispatch_positions('# _run_startup_db_maintenance(fake)\nx="_run_startup_db_maintenance(fake)"')=={}

def test_function_definition_is_not_a_module_dispatch():
    assert startup_dispatch_positions('def other():\n    _run_startup_db_maintenance(fake)')=={}

def test_duplicate_dispatch_is_rejected():
    with pytest.raises(ValueError,match='Duplicate'):
        startup_dispatch_positions('_run_startup_db_maintenance(fake)\n_run_startup_db_maintenance(fake)')

def test_unknown_dispatch_shape_is_rejected():
    with pytest.raises(ValueError,match='shape'):
        startup_dispatch_positions('_run_startup_db_maintenance(callback=fake)')

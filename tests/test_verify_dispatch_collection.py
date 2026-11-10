"""A standalone verification must run its main, including nested test suites."""
from pathlib import Path
import runpy

import pytest


ROOT = Path(__file__).resolve().parents[1]
classify = runpy.run_path(str(ROOT / 'scripts/run_verify_parallel.py'))['_is_pytest_style']


@pytest.mark.parametrize(('source', 'expected'), [
    ('def test_top_level():\n    assert True\n', True),
    ('class TestExample:\n    def test_method(self):\n        assert True\n', True),
    ('class Example(unittest.TestCase):\n    def test_method(self):\n        assert True\n', True),
    ('# def test_example(): is only documentation\nassert True\n', False),
    ('CASES = "def test_embedded(): pass"\nassert CASES\n', False),
    ('def main():\n    class Example:\n        def test_nested(self):\n            assert True\n'
     'if __name__ == "__main__":\n    main()\n', False),
])
def test_classification_matches_collectable_scope(tmp_path, source, expected):
    script = tmp_path / 'verify_synthetic.py'
    script.write_text(source, encoding='utf-8')
    assert classify(str(script)) is expected


@pytest.mark.parametrize('name', [
    'verify_check_legacy_contract_20261109.py',
    'verify_purchase_receipt_candidate_20261109.py',
    'verify_native_atomic_candidate_20261109.py',
])
def test_existing_standalone_suites_reach_their_main(name):
    assert classify(str(ROOT / 'tests' / name)) is False


def test_invalid_source_is_an_error_not_an_empty_success(tmp_path):
    script = tmp_path / 'verify_invalid.py'
    script.write_text('def test_invalid(:', encoding='utf-8')
    with pytest.raises(SyntaxError):
        classify(str(script))

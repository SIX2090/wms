"""Full A9 scans must retain missing-test findings without repeated test-file I/O."""
from pathlib import Path
import runpy
from unittest import mock


def test_full_a9_reads_each_test_once_and_refreshes_next_scan(tmp_path):
    namespace = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/lint_wms_rules.py'))
    rule = namespace['RuleA9NewFuncMustTest']()
    source = tmp_path / 'app' / 'service.py'
    source.parent.mkdir()
    source.write_text('def save_alpha():\n    return 1\ndef save_beta():\n    return 2\n', encoding='utf-8')
    tests = tmp_path / 'tests'
    tests.mkdir()
    first = tests / 'test_service.py'
    first.write_text('def test_save_alpha():\n    assert True\n', encoding='utf-8')
    second = tests / 'test_other.py'
    second.write_text('def test_other():\n    assert True\n', encoding='utf-8')
    original = Path.read_text
    reads = []

    def read(path, *args, **kwargs):
        if path.parent == tests:
            reads.append(path)
        return original(path, *args, **kwargs)

    with mock.patch.dict(rule.scan.__globals__, {
        '_STAGED_SCAN_ACTIVE': False,
        'get_staged_added_lines': lambda *_: set(range(1, 10)),
    }), mock.patch.object(Path, 'read_text', read):
        findings = rule.scan([source], tmp_path)
        assert len(findings) == 1 and 'save_beta' in str(findings[0])
        assert len(reads) == len(set(reads)) == 2, reads
        first.write_text('def test_save_alpha():\n    assert True\ndef test_save_beta():\n    assert True\n', encoding='utf-8')
        reads.clear()
        assert rule.scan([source], tmp_path) == []
        assert len(reads) == len(set(reads)) == 2, reads

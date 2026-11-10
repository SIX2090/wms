"""The numbering gate follows real behavior and rejects truncated suffixes."""
from pathlib import Path
import runpy

import pytest

ROOT = Path(__file__).resolve().parents[1]
check = runpy.run_path(str(ROOT / 'scripts/verify_wms_bugs.py'))['check_numbering_complete_suffix']
SOURCE = (ROOT / 'app/app.py').read_text(encoding='utf-8-sig')


def test_check_numbering_complete_suffix():
    assert check(SOURCE)


@pytest.mark.parametrize('before,after', [
    ('number[len(base):]', 'number[-4:]'),
    ('sequence = int(suffix)', 'sequence = int(suffix[-4:])'),
    ('sequence > maximum', 'sequence < maximum'),
    ('return maximum', 'return 0'),
    ('maximum = max((_numbering_existing_max(model, field, base)', 'maximum = max((0'),
])
def test_gate_rejects_broken_reader_or_disconnected_allocator(before, after):
    assert before in SOURCE
    assert not check(SOURCE.replace(before, after, 1))

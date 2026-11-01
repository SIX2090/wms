"""Exercise the real JS receipt handoff and existing generation checks."""
from pathlib import Path
import json
import shutil
import subprocess
import pytest

@pytest.mark.parametrize('mode', ['valid','no-receipt','late-preview'])
def test_material_merge_receipt_handoff(mode):
    root=Path(__file__).resolve().parents[1]
    node=shutil.which('node')
    assert node, 'Node is required for this frontend interaction contract'
    result=subprocess.run([node,str(root/'tests/js/material_merge_receipt.cjs'),
                           str(root/'app/static/js/material_merge.js'),mode],
                          capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert result.returncode == 0, result.stderr
    proof=json.loads(result.stdout)
    assert proof == {'mode':mode,'passed':True,'actual_merges':0,'network_requests':0}

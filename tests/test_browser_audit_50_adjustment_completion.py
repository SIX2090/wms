from tests.audit_regressions.conftest import audit_boundaries
from tests.audit_regressions.support import evidence_dir
"""Finite 044 actual-code transport simulation. No Flask calls or SQL fixtures."""
from pathlib import Path
import shutil,subprocess
import pytest

SOURCE=Path(__file__).resolve().parents[1]
ROOT=SOURCE.parent
SCENARIOS=['business','http400','http500','network','save_error','save_network','success','plain_save']

@pytest.mark.parametrize('scenario',SCENARIOS)
def test_saved_adjustment_completion_contract(scenario):
    node=shutil.which('node')
    assert node,'Node required; do not silently skip runtime proof'
    result=subprocess.run([node,'--max-old-space-size=96','--require',str(SOURCE/'tests/audit_regressions/network_guard.cjs'),
        str(SOURCE/'tests/audit_regressions/js/round50_adjustment_completion.cjs'),str(SOURCE),scenario,
        str(evidence_dir()/(scenario+'.json'))],capture_output=True,text=True,encoding='utf-8',timeout=12)
    assert result.returncode==0,result.stdout+result.stderr

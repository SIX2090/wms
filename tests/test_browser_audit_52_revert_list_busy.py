from tests.audit_regressions.conftest import audit_boundaries
from tests.audit_regressions.support import evidence_dir
"""Two deferred phases for both actual stock-list reversion handlers; no HTTP/DB."""
from pathlib import Path
import json,re,shutil,subprocess
import pytest
SOURCE=Path(__file__).resolve().parents[1]
ROOT=SOURCE.parent

@pytest.mark.parametrize('page',['transfer','adjustment'])
@pytest.mark.parametrize('scenario',['pending-double-click','success-navigation-double-click'])
def test_list_reversion_stays_locked_for_its_request_and_navigation(page,scenario):
    source=(SOURCE/'app/templates'/(page+'.html')).read_text(encoding='utf-8')
    scripts='\n'.join(re.findall(r'<script\b[^>]*>([\s\S]*?)</script>',source))
    node=shutil.which('node');assert node
    result=subprocess.run([node,'--max-old-space-size=96','--require',str(SOURCE/'tests/audit_regressions/network_guard.cjs'),
        str(SOURCE/'tests/audit_regressions/js/round52_revert_list_busy.cjs'),str(SOURCE),page,scenario,
        str(evidence_dir()/(page+'-'+scenario+'.json'))],input=json.dumps({'script':scripts}),
        capture_output=True,text=True,encoding='utf-8',timeout=12)
    assert result.returncode==0,result.stdout+result.stderr

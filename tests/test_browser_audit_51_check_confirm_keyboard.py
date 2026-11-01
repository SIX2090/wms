from tests.audit_regressions.conftest import audit_boundaries
from tests.audit_regressions.support import evidence_dir
"""Two finite integrations: actual period-risk modal and actual Ctrl+S handler."""
from pathlib import Path
import json,re,shutil,subprocess
import pytest
from bs4 import BeautifulSoup
from tests.test_document_table_transport_runtime import render

SOURCE=Path(__file__).resolve().parents[1]
ROOT=SOURCE.parent

@pytest.mark.parametrize('scenario',['open-risk-dialog','after-cancel'])
def test_risk_dialog_controls_actual_ordinary_save_shortcut(scenario):
    html=render('check')
    scripts=re.findall(r'<script>(.*?)</script>',html,re.S)
    assert len(scripts)==1
    soup=BeautifulSoup(html,'html.parser')
    controls=[dict(node.attrs) for node in soup.select('.doc-header button')]
    assert any('data-wms-save' in node and node.get('onclick')=='submitForm(false)' for node in controls)
    node=shutil.which('node');assert node
    result=subprocess.run([node,'--max-old-space-size=96','--require',str(SOURCE/'tests/audit_regressions/network_guard.cjs'),
        str(SOURCE/'tests/audit_regressions/js/round51_check_confirm_keyboard.cjs'),str(SOURCE),scenario,
        str(evidence_dir()/(scenario+'.json'))],input=json.dumps({'script':scripts[0],'controls':controls}),
        capture_output=True,text=True,encoding='utf-8',timeout=12)
    assert result.returncode==0,result.stdout+result.stderr

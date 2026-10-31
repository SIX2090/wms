"""Execute failure handlers, not string-only feature claims."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]
SCENARIOS=['photo-cancel-empty','photo-read-error','photo-close-before-read','photo-close-pending',
 'scanner-missing','scanner-permission','printer-whitespace','printer-no-station','rule-whitespace',
 'rule-priority-zero','rule-priority-fraction','rule-bad-event','checkbox-resizer','quality-improved-color',
 'quality-card','quality-low-correction','quality-high-correction','acceptance-invalid','acceptance-valid',
 'material-empty-error','material-empty-success']

@pytest.mark.parametrize('scenario',SCENARIOS)
def test_audit_frontend_failure_paths(scenario):
    result=subprocess.run([shutil.which('node'),str(ROOT/'tests/frontend_audit_failure_runtime.cjs'),str(ROOT),scenario],
        capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


def test_acceptance_snapshot_action_does_not_shrink_button():
    from html.parser import HTMLParser
    class Actions(HTMLParser):
        def __init__(self):super().__init__();self.parents=[];self.valid=False
        def handle_starttag(self,tag,attrs):
            a=dict(attrs)
            if a.get('id')=='collectButton':
                self.valid='flex-shrink-0' in a.get('class','') and 'text-nowrap' in a.get('class','') and any('flex-wrap' in p.get('class','') for p in self.parents)
            if tag not in ('input','meta','link','img','br'):self.parents.append(a)
        def handle_endtag(self,tag):
            if self.parents:self.parents.pop()
    parser=Actions();parser.feed((ROOT/'app/templates/ai_acceptance.html').read_text(encoding='utf-8'))
    assert parser.valid

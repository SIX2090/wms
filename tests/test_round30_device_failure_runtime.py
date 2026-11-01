"""Shared H5 hardware paths executed with synthetic DOM/media/network only."""
from pathlib import Path
import shutil
import subprocess
import pytest
from html.parser import HTMLParser
from tests.test_round26_input_http import http_case

ROOT=Path(__file__).resolve().parents[1]
SCENARIOS=['scanner-no-device','scanner-busy','scanner-sync-throw','scanner-init-throw',
 'scanner-disconnect','scanner-duplicate','scanner-cancel-before-open','scanner-late-callback',
 'scanner-pagehide','scanner-track-stop-failure','photo-timeout','photo-network',
 'photo-business-error','photo-superseded']

@pytest.mark.parametrize('scenario',SCENARIOS)
def test_device_failures_without_devices(scenario):
    node=shutil.which('node')
    assert node, 'Node required for actual handler execution'
    result=subprocess.run([node,str(ROOT/'tests/js/round30_device_failure.cjs'),str(ROOT),scenario],
        capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert result.returncode==0,result.stdout+result.stderr

@pytest.mark.parametrize('mode',['in','out','check','query'])
def test_eight_device_entrances_render_shared_safe_handlers(http_case,mode):
    clients,_,state=http_case
    before=state()
    response=clients('warehouse').get('/mobile/scan',query_string={'mode':mode})
    assert response.status_code==200
    class Elements(HTMLParser):
        def __init__(self):super().__init__();self.ids={};self.modes=[]
        def handle_starttag(self,tag,attrs):
            attrs=dict(attrs)
            if 'id' in attrs:self.ids[attrs['id']]=(tag,attrs)
            if 'data-mode' in attrs:self.modes.append(attrs['data-mode'])
    parsed=Elements();parsed.feed(response.get_data(as_text=True))
    assert mode in parsed.modes
    for button in ('cameraBtn','barcodeBtn'):
        tag,attrs=parsed.ids[button]
        assert tag=='button' and attrs['type']=='button'
    assert parsed.ids['cameraFileInput'][1]['capture']=='environment'
    assert state()==before

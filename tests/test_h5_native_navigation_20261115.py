"""Real synthetic Flask rendering; no live server, camera, provider or inventory action."""
from pathlib import Path
import json
import re
import shutil
import subprocess

from scripts.verify_db_guard import require_isolated_test_runtime
require_isolated_test_runtime()
import pytest
from tests.audit_regressions.conftest import audit_boundaries
from tests.audit_regressions.http_fixture import http_case

ROOT = Path(__file__).resolve().parents[1]


def test_mobile_home(http_case):
    client = http_case[0]()
    before = http_case[2]()
    response = client.get('/mobile')
    assert response.status_code == 200, response.get_data(as_text=True)[:500]
    text = response.get_data(as_text=True)
    assert '手机端主导航' in text
    assert re.findall(r'data-mobile-tab="([^"]+)"', text) == ['home', 'in', 'out', 'query', 'me']
    assert '摄像头扫码' in text
    assert 'mobile-app-page' in re.search(r'<body[^>]+>', text).group()
    assert 'user-scalable=no' not in re.search(r'<meta name="viewport"[^>]+>', text).group()
    assert http_case[2]() == before


def test_mobile_profile(http_case):
    response = http_case[0]().get('/mobile/me')
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert 'QA27-admin' in text and '当前服务器' in text
    assert '连接二维码' in text and '退出登录' in text
    assert 'data-mobile-desktop' in text


@pytest.mark.parametrize('path', ['/mobile', '/mobile/', '/mobile/me'])
def test_h5_entry_requires_real_login(http_case, path):
    response = http_case[0](role=None).get(path)
    assert response.status_code in (302, 401), response.status_code


@pytest.mark.parametrize('mode, title', [('in', '入库'), ('out', '出库'), ('query', '查库存'), ('check', '盘点'), ('confirm', '待确认')])
def test_h5_scan_preserves_controls_and_business_boundaries(http_case, mode, title):
    response = http_case[0]().get('/mobile/scan?mode=' + mode)
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert '<title>' + title + '</title>' in text
    assert '手机端主导航' in text
    assert '浏览器不做摄像头扫码' not in text
    assert '手机摄像头扫码请安装APP' not in text
    if mode != 'confirm':
        assert 'id="barcodeBtn"' in text and 'id="cameraBtn"' in text
        assert "window.addEventListener('pagehide', stopBarcodeScanner)" in text
        assert 'window.isSecureContext === false' in text
    if mode in ('in', 'out'):
        assert '草稿' in text and '确认' in text


def test_h5_does_not_add_chrome_inside_desktop_tab(http_case):
    text = http_case[0]().get('/mobile/scan?mode=query&embedded=1').get_data(as_text=True)
    assert '<nav class="h5-app-nav' not in text
    assert 'mobile-app-page' not in re.search(r'<body[^>]+>', text).group()


def test_h5_mode_wraps_existing_report_without_replacing_it(http_case):
    response = http_case[0]().get('/report?mobile=1')
    assert response.status_code == 200
    assert '手机端主导航' in response.get_data(as_text=True)
    ordinary = http_case[0]().get('/report')
    assert ordinary.status_code == 200
    assert '<nav class="h5-app-nav' not in ordinary.get_data(as_text=True)


def test_browser_camera_rejects_insecure_origin_before_acquisition():
    source = (ROOT / 'app/templates/mobile_scan.html').read_text(encoding='utf-8')
    body = source.split('    function startBarcodeScanner() {', 1)[1].split('    if (barcodeBtn)', 1)[0]
    program = '''const vm=require('vm');let messages=[],opened=0;
const context={window:{isSecureContext:false},barcodeScanner:{hidden:true},barcodeVideo:{},zxingCodeReader:null,
 stopBarcodeScanner:()=>{},scanCode:{focus:()=>{}},
 setStatus:(message)=>messages.push(message),ZXing:{BarcodeFormat:new Proxy({},{get:(_,key)=>key}),
 DecodeHintType:new Proxy({},{get:(_,key)=>key}),BrowserMultiFormatReader:function(){opened++;throw Error('synthetic acquisition reached')}}};
vm.createContext(context);vm.runInContext(SOURCE+';startBarcodeScanner();',context);
if(opened!==0||messages.length!==1||!messages[0].includes('HTTPS'))throw Error(JSON.stringify({opened,messages}));
'''.replace('SOURCE', json.dumps('function startBarcodeScanner() {' + body))
    result = subprocess.run([shutil.which('node'), '--require', str(ROOT / 'tests/audit_regressions/network_guard.cjs'), '-'],
                            input=program, capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_h5_navigation_only_propagates_to_ordinary_same_origin_gets():
    assert (ROOT / 'app/static/js/pages/mobile-app-shell.js').is_file(), '手机端导航模块尚未实现'
    program = r'''
const fs=require('fs'),vm=require('vm');let click;
const context={URL,window:{location:{href:'https://wms.invalid/mobile',origin:'https://wms.invalid'}},
 document:{body:{classList:{contains:()=>true}},addEventListener:(kind,handler)=>{if(kind==='click')click=handler},querySelectorAll:()=>[]}};
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),context);
function link(href,options={}){return {target:'',href,getAttribute:()=>href,hasAttribute:(name)=>Boolean(options[name])};}
for(const href of ['/api/mobile/me','/report/inout/export','/report/stock/print_preview','https://other.invalid/path']){
 const anchor=link(href);click({target:{closest:()=>anchor}});if(anchor.href!==href)throw Error('Changed protected or external link '+href);
}
const desktop=link('/',{'data-mobile-desktop':true});click({target:{closest:()=>desktop}});if(desktop.href!=='/')throw Error('Desktop opt-out ignored');
const page=link('/material?keyword=hello#list');click({target:{closest:()=>page}});
const target=new URL(page.href,context.window.location.href);
if(target.searchParams.get('mobile')!=='1'||target.searchParams.get('keyword')!=='hello'||target.hash!=='#list')throw Error('Navigation state lost');
'''
    result = subprocess.run([shutil.which('node'), '--require', str(ROOT / 'tests/audit_regressions/network_guard.cjs'),
                             '-', str(ROOT / 'app/static/js/pages/mobile-app-shell.js')],
                            input=program, capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr

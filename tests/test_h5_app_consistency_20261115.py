"""Synthetic H5/native naming, layout and phone-entry contracts; no live server."""
from pathlib import Path
import json,re,shutil,subprocess
from scripts.verify_db_guard import require_isolated_test_runtime
require_isolated_test_runtime()
import pytest
from tests.audit_regressions.conftest import audit_boundaries
from tests.audit_regressions.http_fixture import http_case
ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('path,title',[('/mobile','首页'),('/mobile/me','我的'),('/mobile/scan?mode=in','入库'),('/mobile/scan?mode=out','出库'),('/mobile/scan?mode=query','查库存'),('/mobile/scan?mode=check','盘点')])
def test_real_h5_title_and_visible_brand_match_installed_app(http_case,path,title):
    before=http_case[2]()
    response=http_case[0]().get(path)
    assert response.status_code==200
    html=response.get_data(as_text=True)
    import xml.etree.ElementTree as ET
    app_name=ET.parse(ROOT/'app/android-native-wms/app/src/main/AndroidManifest.xml').getroot().find('application').attrib['{http://schemas.android.com/apk/res/android}label']
    if app_name.startswith('@string/'):
        key=app_name.split('/',1)[1]
        app_name=ET.parse(ROOT/'app/android-native-wms/app/src/main/res/values/strings.xml').getroot().find("string[@name='"+key+"']").text
    assert app_name == 'WMS' 
    assert '<title>'+app_name+' · '+title+'</title>' in html
    header=html.split('<header class="h5-app-header',1)[1].split('</header>',1)[0]
    assert '<span>'+app_name+'</span>' in header
    assert 'WMS扫码' not in header
    assert http_case[2]()==before

def test_home_uses_native_workbench_groups_and_keeps_existing_usable_entrances(http_case):
    html=http_case[0]().get('/mobile').get_data(as_text=True)
    main=html.split('<main class="h5-home">',1)[1].split('</main>',1)[0]
    assert '<h1>仓库工作台</h1>' in main
    sections=re.findall(r'<h2[^>]*>([^<]+)</h2>',main)
    assert sections==['开始作业','查询与报表','资料与工具']
    native=(ROOT/'app/android-native-wms/app/src/main/java/com/factory/wms/ui/screens/HomeScreen.kt').read_text()
    names=re.findall(r'title = "([^"]+)"',native.split('@Composable',1)[0])
    cards=re.findall(r'<strong>([^<]+)</strong>',main)
    assert set(['入库','出库','查库存','盘点','期初库存','物料档案','识别单据','识物','库存台账']).issubset(cards)
    assert all(name in names for name in cards if name!='报表中心')
    assert cards[:5]==['入库','出库','查库存','盘点','期初库存']
    assert '/report/view/ledger?mobile=1' in main
    assert '摄像头扫码' in main
    assert 'h5-primary-tasks' in main and 'h5-stock-entry' in main

def test_restricted_role_does_not_gain_write_entrances_or_ocr(http_case):
    html=http_case[0]('finance').get('/mobile').get_data(as_text=True)
    main=html.split('<main class="h5-home">',1)[1].split('</main>',1)[0]
    cards=re.findall(r'<strong>([^<]+)</strong>',main)
    assert '查库存' in cards and '库存台账' in cards and '报表中心' in cards
    assert not set(['入库','出库','盘点','期初库存','物料档案','识别单据']).intersection(cards)
    assert '/mobile/scan?mode=in' not in main

def test_mobile_desktop_optout_and_login_brand_are_explicit(http_case):
    client=http_case[0]()
    profile=client.get('/mobile/me').get_data(as_text=True)
    assert 'href="/?desktop=1" data-mobile-desktop' in profile
    login=http_case[0](role=None).get('/login?next=/mobile').get_data(as_text=True)
    assert '<title>WMS · 登录</title>' in login
    assert 'name="next" value="/mobile"' in login
    assert 'js/pages/mobile-entry.js' in login
    desktop=client.get('/?desktop=1').get_data(as_text=True)
    assert '<title>WMS · 首页</title>' in desktop
    assert '打开仓库工作台' in desktop
    assert 'js/pages/mobile-entry.js' in desktop

@pytest.mark.parametrize('url,narrow,embedded,old_next,expected_redirect,expected_next',[
    ('https://wms.invalid/',True,False,'', '/mobile',''),
    ('https://wms.invalid/?desktop=1',True,False,'',None,''),
    ('https://wms.invalid/?embedded=1',True,False,'',None,''),
    ('https://wms.invalid/?alert_warehouse_id=7',True,False,'',None,''),
    ('https://wms.invalid/',False,False,'',None,''),
    ('https://wms.invalid/',True,True,'',None,''),
    ('https://wms.invalid/login',True,False,'',None,'/mobile'),
    ('https://wms.invalid/login?next=/report',True,False,'/report',None,'/report'),
    ('https://wms.invalid/login',False,False,'',None,''),
    ('https://wms.invalid/login?desktop=1',True,False,'',None,''),
    ('https://wms.invalid/material',True,False,'',None,''),
])
def test_real_entry_module_preserves_desktop_embedded_next_and_filter_intent(url,narrow,embedded,old_next,expected_redirect,expected_next):
    script=ROOT/'app/static/js/pages/mobile-entry.js'
    assert script.is_file(),'缺少手机登录及首页进入H5的真实入口'
    case=dict(url=url,narrow=narrow,embedded=embedded,next=old_next)
    program='''const vm=require('vm'),fs=require('fs'); const c=CASE;
let redirected=null,next={value:c.next};let top={};
let context={URL,window:{top,self:c.embedded?{}:top,matchMedia:()=>({matches:c.narrow}),location:{href:c.url,replace:(v)=>redirected=v}},document:{querySelector:(s)=>{if(s!=='form input[name="next"]')throw Error(s);return next}}};
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),context);
process.stdout.write(JSON.stringify({redirected,next:next.value}));
'''.replace('CASE',json.dumps(case))
    result=subprocess.run([shutil.which('node'),'--require',str(ROOT/'tests/audit_regressions/network_guard.cjs'),'-',str(script)],input=program,capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert result.returncode==0,result.stdout+result.stderr
    assert json.loads(result.stdout)==dict(redirected=expected_redirect,next=expected_next)

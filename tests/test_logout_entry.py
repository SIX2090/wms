"""BUG-2026-10-24-012: reachable logout leaves the whole tab workspace."""
import json
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]


def _shell(authenticated=True, role='viewer'):
    return Environment(autoescape=True).from_string((ROOT/'app/templates/base.html').read_text(encoding='utf-8')).render(
        current_user=SimpleNamespace(is_authenticated=authenticated, role=role, username='<操作员>', id=1),
        csrf_token=lambda:'fixture', config={}, request=SimpleNamespace(args={}),
        url_for=lambda name,**kw:'/static/'+kw['filename'] if name=='static' else '/'+name)


@pytest.mark.parametrize('role', ['admin','warehouse','purchase','production','sales','viewer','finance','manager'])
def test_every_role_has_top_level_logout(role):
    html=_shell(role=role)
    links=re.findall(r'<a\b[^>]*href="/logout"[^>]*>.*?</a>',html,re.S)
    assert len(links)==1
    assert '退出登录' in links[0] and 'target="_top"' in links[0]
    # User-requested menu order: logout is the final primary navigation item.
    primary = html.split('<ul class="nav flex-column legacy-menu d-none">', 1)[0]
    trailing = primary.split('href="/logout"', 1)[1]
    assert '<li ' not in trailing
    assert primary.index('手机扫码') < primary.index('href="/logout"')
    if role == 'admin':
        assert primary.index('系统管理') < primary.index('href="/logout"')
    assert '<操作员>' not in links[0]


def test_anonymous_shell_has_no_logout():
    assert 'href="/logout"' not in _shell(authenticated=False)


def test_menu_initializer_does_not_turn_logout_into_tab():
    html=_shell()
    match=re.search(r'<a\b[^>]*href="/logout"[^>]*>',html)
    assert match, 'Visible logout entry is missing'
    target=re.search(r'target="([^"]+)"',match.group(0)).group(1)
    source=(ROOT/'app/static/js/app.js').read_text(encoding='utf-8')
    handler=source[source.index('function enableMultiOpenMenus()'):source.index('// 标签页管理')]
    program=r"""
const vm=require('node:vm'),assert=require('node:assert/strict'),fs=require('node:fs');
const p=JSON.parse(fs.readFileSync(0,'utf8')),opened=[];
function link(href,target){return {dataset:{},innerHTML:'original',textContent:'Menu',events:{},
 getAttribute:k=>k==='href'?href:k==='target'?target:null,
 classList:{add(){}},setAttribute(){},querySelector:s=>s==='i'?null:{classList:{add(){}},addEventListener(){}},
 addEventListener(name,fn){this.events[name]=fn}}}
const logout=link('/logout',p.target),normal=link('/material','');
const document={body:{classList:{contains:()=>false}},querySelectorAll:()=>[logout,normal]};
const window={WmsTabs:{open:(...args)=>opened.push(args)}};
const ctx=vm.createContext({document,window,isWmsEmbeddedPage:()=>false,isMobileViewport:()=>false});
vm.runInContext(p.handler,ctx);ctx.enableMultiOpenMenus();
assert.equal(logout.innerHTML,'original');assert.deepEqual(Object.keys(logout.events),[]);
assert.equal(logout.dataset.multiOpenReady,undefined);
let prevented=false;normal.events.click({preventDefault(){prevented=true}});
assert(prevented);assert.deepEqual(opened,[['/material','Menu']]);
process.stdout.write('ok');
"""
    result=subprocess.run([shutil.which('node'),'-e',program],input=json.dumps({'handler':handler,'target':target}),
                          text=True,encoding='utf-8',capture_output=True,timeout=15)
    assert result.returncode==0,result.stderr
    assert result.stdout=='ok'


@pytest.mark.parametrize('remember', [False,True])
def test_rendered_entry_logs_out_and_requires_login(remember,monkeypatch):
    from app import app,db,User
    from werkzeug.security import generate_password_hash
    monkeypatch.setitem(app.config,'TESTING',True)
    monkeypatch.setitem(app.config,'WTF_CSRF_ENABLED',False)
    with app.app_context():
        assert str(db.engine.url)=='sqlite:///:memory:'
        db.session.remove();db.drop_all();db.create_all()
        user=User(username='logout-fixture',password_hash=generate_password_hash('fixture-only'),role='admin',must_change_password=False)
        db.session.add(user);db.session.commit()
        original_hash=user.password_hash
    try:
        client=app.test_client()
        data={'username':'logout-fixture','password':'fixture-only'}
        if remember:data['remember']='1'
        assert client.post('/login',data=data).status_code==302
        response=client.get('/profile/edit')
        assert response.status_code==200
        html=response.get_data(as_text=True)
        match=re.search(r'<a\b[^>]*href="(/logout)"[^>]*>',html)
        assert match,'Authenticated page has no logout action'
        response=client.get(match.group(1))
        assert response.status_code==302 and response.headers['Location'].endswith('/login')
        assert client.get_cookie('remember_token') is None
        with client.session_transaction() as session:
            assert '_user_id' not in session
        assert client.get('/profile/edit').status_code==302
        with app.app_context():
            assert User.query.one().password_hash==original_hash
    finally:
        with app.app_context():db.session.remove();db.drop_all()

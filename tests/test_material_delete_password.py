"""Only the literal admin account may remove an archive, with fresh password verification."""
import json

import pytest


@pytest.fixture
def guarded_material(bom_case):
    from app import db, User, Material
    client, ids = bom_case
    db.session.get(User, ids['user']).username = 'admin'
    material = Material(code='DELETE-GUARD', name='删除保护测试', unit_id=ids['unit'], stock=0)
    db.session.add(material)
    db.session.commit()
    return client, material.id, ids['user']


@pytest.mark.parametrize('username,role', [('warehouse-a','warehouse'), ('other-admin','admin'), ('Admin','admin'), ('admin','warehouse')])
def test_authorize_material_removal(guarded_material, username, role):
    from app import db, User, Material, OperationAudit
    client, mid, uid = guarded_material
    user = db.session.get(User, uid)
    user.username, user.role = username, role
    db.session.commit()
    response = client.post('/material/delete', json={'ids':[mid], 'admin_password':'fixture-only'})
    assert response.status_code == 403
    assert db.session.get(Material, mid) is not None
    assert OperationAudit.query.filter_by(operation='delete_material').count() == 0


@pytest.mark.parametrize('password', [None, '', 'wrong', ['fixture-only'], 123])
def test_delete_material_requires_password_in_each_request(guarded_material, password):
    from app import db, Material
    client, mid, _ = guarded_material
    body = {'ids':[mid]}
    if password is not None:
        body['admin_password'] = password
    response = client.post('/material/delete', json=body)
    assert response.status_code in (400,403)
    assert db.session.get(Material, mid) is not None
    assert 'fixture-only' not in response.get_data(as_text=True)


def test_delete_material_password_is_checked_again_after_success(guarded_material):
    from app import db, Material, OperationAudit
    client, mid, _ = guarded_material
    response = client.post('/material/delete', json={'ids':[mid], 'admin_password':'fixture-only'})
    assert response.status_code == 200
    assert db.session.get(Material, mid) is None
    audit = OperationAudit.query.filter_by(operation='delete_material').one()
    snapshot = json.loads(audit.old_data)[0]
    assert snapshot['unit_id'] is not None and snapshot['created_at'] and snapshot['status']=='active'
    assert 'fixture-only' not in audit.old_data
    other = Material(code='DELETE-GUARD-2', name='第二次', stock=0)
    db.session.add(other); db.session.commit()
    other_id = other.id
    assert client.post('/material/delete',json={'ids':[other_id]}).status_code in (400,403)
    assert db.session.get(Material,other_id) is not None


def test_delete_material_preserves_password_whitespace_and_never_echoes_it(guarded_material):
    from werkzeug.security import generate_password_hash
    from app import db, User
    client, mid, uid = guarded_material
    password = '  synthetic &+ password  '
    db.session.get(User,uid).password_hash = generate_password_hash(password)
    db.session.commit()
    response = client.post('/material/delete',data={'ids':json.dumps([mid]), 'admin_password':password})
    assert response.status_code==200
    assert password not in response.get_data(as_text=True)


def test_delete_material_failed_passwords_are_rate_limited(guarded_material):
    from app import db, Material
    client, mid, _ = guarded_material
    for _ in range(5):
        assert client.post('/material/delete',json={'ids':[mid],'admin_password':'wrong'}).status_code==403
    assert client.post('/material/delete',json={'ids':[mid],'admin_password':'fixture-only'}).status_code==429
    assert db.session.get(Material,mid) is not None


def test_delete_material_uses_current_password_after_account_change(guarded_material):
    from werkzeug.security import generate_password_hash
    from app import db, User, Material
    client, mid, uid=guarded_material
    db.session.get(User,uid).password_hash=generate_password_hash('changed-fixture')
    db.session.commit()
    assert client.post('/material/delete',json={'ids':[mid],'admin_password':'fixture-only'}).status_code==403
    assert db.session.get(Material,mid) is not None
    assert client.post('/material/delete',json={'ids':[mid],'admin_password':'changed-fixture'}).status_code==200


@pytest.mark.parametrize('password', ['', 'wrong'])
def test_merge_material_cannot_bypass_delete_password(guarded_material,password):
    from app import db, Material
    client, mid, _ = guarded_material
    target=Material(code='DELETE-KEEP',name='删除保护测试',stock=0,
        unit_id=db.session.get(Material,mid).unit_id)
    db.session.add(target);db.session.commit()
    preview=client.post('/material/merge_preview',json={'source_code':'DELETE-GUARD',
        'target_code':target.code,'manual_review':True})
    assert preview.status_code==200
    response=client.post(f'/material/{mid}/merge',json={'target_code':target.code,'confirm':True,
        'identity_confirmed':True,'admin_password':password,'preview_token':preview.json['data']['preview_token']})
    assert response.status_code==403
    assert db.session.get(Material,mid) is not None


def test_material_delete_password_dialog_runtime(tmp_path):
    import subprocess
    import shutil
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    node=shutil.which('node')
    assert node, 'Node is required for password dialog coverage'
    result=subprocess.run([node,str(root/'tests/frontend_material_unused_delete.cjs'),str(root)],
        capture_output=True,text=True,encoding='utf-8',timeout=90)
    assert result.returncode==0,result.stdout+result.stderr
    assert json.loads(result.stdout)['passed']>=15


@pytest.mark.parametrize('username,allowed',[('admin',True),('other-admin',False)])
def test_material_page_masks_password_and_reports_admin_permission(guarded_material,username,allowed):
    import re
    from app import db, User
    client, _, uid=guarded_material
    db.session.get(User,uid).username=username
    db.session.commit()
    response=client.get('/material')
    assert response.status_code==200
    html=response.get_data(as_text=True)
    assert 'type="password" id="materialDeletePassword"' in html
    assert 'type="password" id="materialMergePassword"' in html
    data=json.loads(re.search(r'id="material-list-data">([\s\S]*?)</script>',html).group(1))
    assert data['canDelete'] is allowed
    assert 'fixture-only' not in html


def test_initialization_cannot_bypass_material_admin_account(guarded_material, monkeypatch):
    from app import app, db, User, Material, INIT_CONFIRM_PHRASE
    client, mid, uid=guarded_material
    monkeypatch.setenv('WMS_ALLOW_BUSINESS_INIT','1')
    db.session.get(User,uid).username='other-admin'
    db.session.commit()
    response=client.post('/system_settings/init_business_data/execute',data={
        'admin_password':'fixture-only','confirm_phrase':INIT_CONFIRM_PHRASE,
        'include_master_data':'1','preview_token':'synthetic-no-execution'})
    assert response.status_code==403
    assert db.session.get(Material,mid) is not None


def test_merge_material_cannot_bypass_admin_account(guarded_material):
    from app import db, User, Material
    client, mid, uid=guarded_material
    db.session.get(User,uid).username='other-admin'
    target=Material(code='DELETE-KEEP',name='删除保护测试',stock=0,
        unit_id=db.session.get(Material,mid).unit_id)
    db.session.add(target);db.session.commit()
    preview=client.post('/material/merge_preview',json={'source_code':'DELETE-GUARD',
        'target_code':target.code,'manual_review':True})
    assert preview.status_code==200
    response=client.post(f'/material/{mid}/merge',json={'target_code':target.code,'confirm':True,
        'identity_confirmed':True,'admin_password':'fixture-only','preview_token':preview.json['data']['preview_token']})
    assert response.status_code==403
    assert db.session.get(Material,mid) is not None

"""B4: password events revoke only synthetic users' existing mobile credentials."""
from datetime import datetime, timedelta

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

import app as w


OLD = 'SyntheticOld-123!'
NEW = 'SyntheticNew-456!'
RESET = 'SyntheticReset-789!'


@pytest.fixture
def accounts(monkeypatch):
    monkeypatch.setitem(w.app.config,'TESTING',True)
    monkeypatch.setitem(w.app.config,'WTF_CSRF_ENABLED',False)
    monkeypatch.setattr('routes.print_queue.enqueue_auto_print_job',lambda *a,**k:None)
    with w.app.app_context():
        w.db.session.remove()
        w.db.drop_all()
        w.db.create_all()
        users={name:w.User(username=name,role=role,password_hash=generate_password_hash(OLD),
                           status='normal',must_change_password=False)
               for name,role in [('b4-admin','admin'),('b4-a','warehouse'),('b4-b','warehouse')]}
        warehouse=w.Warehouse(code='B4-W',name='B4合成仓',status='active',is_default=True)
        material=w.Material(code='B4-M',name='B4合成物料',stock=0,price=0)
        w.db.session.add_all([*users.values(),warehouse,material])
        w.db.session.flush()
        ids={name:user.id for name,user in users.items()}
        tokens={label:'b4-synthetic-'+label for label in ('a1','a2','b1')}
        for label,token in tokens.items():
            w.db.session.add(w.ApiToken(user_id=ids['b4-b' if label=='b1' else 'b4-a'],
                token=w.hash_access_token(token),revoked=False,expires_at=datetime.now()+timedelta(days=3)))
        w.db.session.commit()
    yield dict(ids=ids,tokens=tokens)
    with w.app.app_context():
        w.db.session.rollback()
        w.db.session.remove()


def _web(uid):
    client=w.app.test_client()
    client.environ_base['HTTP_X_REQUESTED_WITH']='XMLHttpRequest'
    with client.session_transaction() as state:
        state['_user_id']=str(uid)
        state['_fresh']=True
    return client


def _bearer(token):
    with w.app.test_request_context(headers={'Authorization':'Bearer '+token}):
        user=w.get_bearer_user()
        return user.id if user else None


def _flags():
    with w.app.app_context():
        return {row.token:row.revoked for row in w.ApiToken.query.all()}


def test_password_change_invalidates_all_old_mobile_tokens_only_for_actor(accounts):
    client=_web(accounts['ids']['b4-a'])
    response=client.post('/user/change_password',data=dict(current_password=OLD,new_password=NEW,confirm_password=NEW))
    assert response.status_code==200 and response.get_json()['status']=='success'
    assert _bearer(accounts['tokens']['a1']) is None
    assert _bearer(accounts['tokens']['a2']) is None
    assert _bearer(accounts['tokens']['b1'])==accounts['ids']['b4-b']
    flags=_flags()
    assert all(flags[w.hash_access_token(accounts['tokens'][key])] for key in ('a1','a2'))
    with w.app.app_context():
        user=w.db.session.get(w.User,accounts['ids']['b4-a'])
        assert check_password_hash(user.password_hash,NEW) and user.must_change_password is False
    # Existing Web session policy is retained; mobile credentials require fresh login.
    assert client.get('/user/change_password').status_code==200
    fresh=w.app.test_client().post('/api/login',json=dict(username='b4-a',password=NEW))
    assert fresh.status_code==200
    assert _bearer(fresh.get_json()['data']['token'])==accounts['ids']['b4-a']


def test_admin_reset_rejects_old_tokens_until_human_changes_password(accounts):
    response=_web(accounts['ids']['b4-admin']).post('/user/reset_password',data=dict(
        user_id=accounts['ids']['b4-a'],new_password=RESET))
    assert response.status_code==200 and response.get_json()['status']=='success'
    assert _bearer(accounts['tokens']['a1']) is None
    assert _bearer(accounts['tokens']['a2']) is None
    assert _bearer(accounts['tokens']['b1'])==accounts['ids']['b4-b']
    assert w.app.test_client().post('/api/login',json=dict(username='b4-a',password=RESET)).status_code==403
    response=_web(accounts['ids']['b4-a']).post('/user/change_password',data=dict(
        current_password=RESET,new_password=NEW,confirm_password=NEW))
    assert response.status_code==200
    fresh=w.app.test_client().post('/api/login',json=dict(username='b4-a',password=NEW))
    assert fresh.status_code==200 and _bearer(fresh.get_json()['data']['token'])==accounts['ids']['b4-a']
    assert _bearer(accounts['tokens']['a1']) is None


@pytest.mark.parametrize('legacy',[False,True])
def test_get_bearer_user_forced_change_does_not_refresh_or_migrate(accounts,legacy):
    token=accounts['tokens']['a1']
    with w.app.app_context():
        user=w.db.session.get(w.User,accounts['ids']['b4-a'])
        user.must_change_password=True
        row=w.ApiToken.query.filter_by(token=w.hash_access_token(token)).one()
        row.last_used_at=None
        row.expires_at=datetime.now()+timedelta(seconds=45)
        if legacy:row.token=token
        w.db.session.commit()
        before=(row.token,row.last_used_at,row.expires_at,row.revoked)
    assert _bearer(token) is None
    with w.app.app_context():
        row=w.ApiToken.query.filter_by(user_id=accounts['ids']['b4-a']).order_by(w.ApiToken.id).first()
        assert (row.token,row.last_used_at,row.expires_at,row.revoked)==before
    client=w.app.test_client()
    response=client.post('/api/inbound',headers={'Authorization':'Bearer '+token},json=dict(
        warehouse_code='B4-W',request_id='forced-attempt',lines=[dict(material_code='B4-M',quantity=1)]))
    assert response.status_code==401
    with w.app.app_context():
        assert w.InOrder.query.count()==0 and w.StockTransaction.query.count()==0


@pytest.mark.parametrize('event',['self','admin'])
def test_password_and_token_revocation_rollback_together(accounts,monkeypatch,event):
    actor='b4-a' if event=='self' else 'b4-admin'
    path='/user/change_password' if event=='self' else '/user/reset_password'
    data=dict(current_password=OLD,new_password=NEW,confirm_password=NEW) if event=='self' else dict(
        user_id=accounts['ids']['b4-a'],new_password=RESET)
    before=_flags()
    client=_web(accounts['ids'][actor])
    with monkeypatch.context() as patch:
        commits=[]
        def fail():
            commits.append(True)
            raise RuntimeError('synthetic commit failure')
        patch.setattr(w.db.session,'commit',fail)
        assert client.post(path,data=data).status_code==500
        assert len(commits)==1
    assert _flags()==before
    with w.app.app_context():
        user=w.db.session.get(w.User,accounts['ids']['b4-a'])
        assert check_password_hash(user.password_hash,OLD) and user.must_change_password is False
    assert _bearer(accounts['tokens']['a1'])==accounts['ids']['b4-a']


@pytest.mark.parametrize('mode',['bad_current','mismatch','weak','nonadmin','self_reset'])
def test_rejected_password_events_never_revoke_tokens(accounts,mode):
    client=_web(accounts['ids']['b4-a'])
    data=dict(current_password=OLD,new_password=NEW,confirm_password=NEW)
    path='/user/change_password'
    if mode=='bad_current':data['current_password']='wrong-synthetic'
    elif mode=='mismatch':data['confirm_password']='mismatch-synthetic'
    elif mode=='weak':data.update(new_password='weak',confirm_password='weak')
    else:
        path='/user/reset_password'
        data=dict(user_id=accounts['ids']['b4-a'],new_password=RESET)
        if mode=='self_reset':
            client=_web(accounts['ids']['b4-admin'])
            data['user_id']=accounts['ids']['b4-admin']
    before=_flags()
    response=client.post(path,data=data)
    assert response.status_code in (400,403) or response.get_json().get('status')=='error'
    assert _flags()==before


@pytest.mark.parametrize('state',['disabled','expired','revoked'])
def test_existing_native_rejection_controls(accounts,state):
    token=accounts['tokens']['a1']
    with w.app.app_context():
        row=w.ApiToken.query.filter_by(token=w.hash_access_token(token)).one()
        if state=='disabled':w.db.session.get(w.User,accounts['ids']['b4-a']).status='disabled'
        elif state=='expired':row.expires_at=datetime.now()-timedelta(seconds=1)
        else:row.revoked=True
        w.db.session.commit()
    assert _bearer(token) is None
    assert _bearer(accounts['tokens']['b1'])==accounts['ids']['b4-b']


def test_cached_native_receipt_requires_fresh_credentials_after_password_change(accounts):
    client=w.app.test_client()
    token=accounts['tokens']['a1']
    payload=dict(warehouse_code='B4-W',request_id='credential-replay',lines=[dict(material_code='B4-M',quantity=2)])
    headers={'Authorization':'Bearer '+token}
    first=client.post('/api/inbound',json=payload,headers=headers)
    assert first.status_code==200,first.get_json()
    response=_web(accounts['ids']['b4-a']).post('/user/change_password',data=dict(
        current_password=OLD,new_password=NEW,confirm_password=NEW))
    assert response.status_code==200
    assert client.post('/api/inbound',json=payload,headers=headers).status_code==401
    fresh=w.app.test_client().post('/api/login',json=dict(username='b4-a',password=NEW))
    assert fresh.status_code==200
    replay=client.post('/api/inbound',json=payload,headers={'Authorization':'Bearer '+fresh.get_json()['data']['token']})
    assert replay.status_code==200 and replay.get_json()==first.get_json()
    with w.app.app_context():
        assert w.InOrder.query.count()==1 and w.Material.query.one().stock==pytest.approx(2)
        assert w.MobileApiRequest.query.count()==1

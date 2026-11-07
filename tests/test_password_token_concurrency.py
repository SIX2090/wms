"""Real synthetic file connections: stale credentials cannot mint a late token."""
import threading
from pathlib import Path

import pytest
from sqlalchemy import event as sa_event
from werkzeug import security

import app as w
from tests.test_password_token_lifecycle import OLD, NEW, RESET, _web


@pytest.mark.parametrize('event',['self','admin'])
def test_password_event_fences_an_already_verified_login(monkeypatch,event,request):
    monkeypatch.setitem(w.app.config,'TESTING',True)
    monkeypatch.setitem(w.app.config,'WTF_CSRF_ENABLED',False)
    with w.app.app_context():
        if w.db.engine.url.database==':memory:':
            pytest.skip('requires explicitly allowlisted fresh synthetic SQLite file; not a memory concurrency claim')
        assert w.db.engine.url.database
        database=Path(w.db.engine.url.database)
        assert database.resolve().is_relative_to(Path(r'C:\Users\Administrator\Documents\Codex\2026-11-07\wms-improvement-90\lab').resolve())
        assert database.name=='synthetic.sqlite'
        w.db.session.remove()
        w.db.create_all()
        username='b4-race-'+event
        user=w.User(username=username,role='warehouse',status='normal',must_change_password=False,
                    password_hash=security.generate_password_hash(OLD))
        admin=w.User(username='b4-race-admin-'+event,role='admin',status='normal',must_change_password=False,
                     password_hash=security.generate_password_hash(OLD))
        w.db.session.add_all([user,admin])
        w.db.session.commit()
        uid,aid=user.id,admin.id
        engine=w.db.engine
    verified=threading.Event()
    proceed=threading.Event()
    connections=set()
    def observe(connection,*args):
        connections.add(id(connection.connection.driver_connection))
    sa_event.listen(engine,'before_cursor_execute',observe)
    request.addfinalizer(lambda:sa_event.remove(engine,'before_cursor_execute',observe))
    outcomes=[]
    original=security.check_password_hash
    def check(password_hash,password):
        valid=original(password_hash,password)
        if threading.current_thread().name=='b4-stale-login' and valid:
            verified.set()
            if not proceed.wait(10):raise RuntimeError('synthetic login barrier timed out')
        return valid
    monkeypatch.setattr(security,'check_password_hash',check)
    def login():
        try:outcomes.append(w.app.test_client().post('/api/login',json=dict(username=username,password=OLD)))
        except Exception as error:outcomes.append(error)
    thread=threading.Thread(target=login,name='b4-stale-login')
    thread.start()
    try:
        assert verified.wait(10),'login did not reach credential verification'
        if event=='self':
            response=_web(uid).post('/user/change_password',data=dict(current_password=OLD,new_password=NEW,confirm_password=NEW))
        else:
            response=_web(aid).post('/user/reset_password',data=dict(user_id=uid,new_password=RESET))
        assert response.status_code==200 and response.get_json()['status']=='success'
    finally:
        proceed.set()
        thread.join(10)
    assert not thread.is_alive() and len(outcomes)==1
    assert len(connections)>=2,'must use two real DBAPI connections'
    result=outcomes[0]
    assert not isinstance(result,Exception),repr(result)
    assert result.status_code in (401,403,409),result.get_json()
    with w.app.app_context():
        assert w.ApiToken.query.filter_by(user_id=uid,revoked=False).count()==0
        user=w.db.session.get(w.User,uid)
        assert original(user.password_hash,NEW if event=='self' else RESET)

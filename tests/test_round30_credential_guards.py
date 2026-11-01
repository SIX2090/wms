"""Five credential entrances, only guards; no credential creation or mutation."""
import pytest
import app as m
import routes.print_routing as routing
import werkzeug.security
from tests.test_round26_input_http import http_case

PATHS=[('/print_routing/workstations','json'),('/print_routing/workstations/999999/reset_token','json'),
       ('/user/add','form'),('/user/reset_password','form'),('/user/change_password','form')]

@pytest.mark.parametrize('path,kind',PATHS)
def test_credential_guards_never_create_or_change_credentials(http_case,monkeypatch,path,kind):
    clients,_,state=http_case
    calls=[]
    def refuse(*a,**k):calls.append('credential generator');raise AssertionError('No credentials generated')
    monkeypatch.setattr(routing.secrets,'token_urlsafe',refuse)
    monkeypatch.setattr(werkzeug.security,'generate_password_hash',refuse)
    # Current-password rejection is a stand-in; no real password or hash is checked.
    monkeypatch.setattr(werkzeug.security,'check_password_hash',lambda *a,**k:False)
    def accounts():
        with m.app.app_context():
            return [(u.id,u.username,u.password_hash,u.role,u.must_change_password) for u in m.User.query.order_by(m.User.id)],m.PrintWorkstation.query.count()
    before=accounts(),state()
    def post(client):return client.post(path,**({'json':{}} if kind=='json' else {'data':{}}))
    assert post(clients(None)).status_code in (302,401)
    assert post(clients('admin',csrf=False)).status_code==400
    if path!='/user/change_password':assert post(clients('finance')).status_code==403
    expected=404 if path.endswith('/reset_token') else 400
    response=post(clients('admin'))
    assert response.status_code==expected,response.get_data(as_text=True)
    assert response.json['status']=='error'
    assert (accounts(),state())==before and calls==[]

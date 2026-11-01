"""BTN-PENDING-022: real CSRF, master stays off, new HTTP session rereads values."""
from html.parser import HTMLParser
import app as m
from tests.test_round26_input_http import http_case

class Inputs(HTMLParser):
    def __init__(self):
        super().__init__();self.fields={}
    def handle_starttag(self,tag,attrs):
        data=dict(attrs)
        if tag=='input' and data.get('name') in {'master_enabled','receiver_name','share_time','helper_url'}:
            self.fields[data['name']]=data

def test_master_off_save_reopen_with_real_csrf_no_delivery(http_case,monkeypatch):
    clients,_,state=http_case
    calls=[]
    def forbidden(*a,**k):
        calls.append('unexpected delivery');raise AssertionError('No external share in this case')
    monkeypatch.setattr(m,'_wechat_share_deliver',forbidden)
    monkeypatch.setattr(m,'_build_order_share_image',forbidden)
    # Explicit non-I/O health stand-in. This is not an actual assistant health test.
    monkeypatch.setattr(m,'_wechat_share_get_helper_health',lambda *a,**k:{'online':False,'ok':False,'message':'QA offline'})
    with m.app.app_context():
        m.db.session.add(m.WechatShareConfig(receiver_name='QA30 BEFORE',share_time='07:35',
            enabled=False,auto_send=False,immediate_on_complete=False,helper_url='http://127.0.0.1:9/send'))
        m.set_system_setting('wechat_share_enabled','0');m.db.session.commit()
    before=state()
    payload={'receiver_name':'QA30 AFTER','receiver_type':'person','share_time':'09:12',
             'helper_url':'http://127.0.0.1:9/send','share_in_order':'1'}
    response=clients('admin').post('/wechat_share/save',data=payload)
    assert response.status_code==200 and response.json['status']=='success'
    assert '已保存' in response.json['msg']
    reopened=clients('admin').get('/wechat_share')
    assert reopened.status_code==200
    parser=Inputs();parser.feed(reopened.get_data(as_text=True))
    assert 'checked' not in parser.fields['master_enabled']
    assert parser.fields['receiver_name']['value']=='QA30 AFTER'
    assert parser.fields['share_time']['value']=='09:12'
    assert parser.fields['helper_url']['value']=='http://127.0.0.1:9/send'
    with m.app.app_context():
        assert m.get_system_setting('wechat_share_enabled')=='0'
        config=m.WechatShareConfig.query.one()
        assert not config.enabled and not config.auto_send and not config.immediate_on_complete
        assert m.WechatShareLog.query.count()==0
    assert state()==before and calls==[]

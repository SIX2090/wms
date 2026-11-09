"""Token and receipt predicates from the actual service, using synthetic rows."""
from pathlib import Path
import runpy
from types import SimpleNamespace

SERVICE=runpy.run_path(str(Path(__file__).resolve().parents[1]/'app/services/wechat_poll_claim.py'))

def test_digest_token():
    import hashlib
    token='a'*64
    assert SERVICE['digest_token'](token)==hashlib.sha256(token.encode('ascii')).hexdigest()
    for bad in (None,False,[], 'a'*63,'g'*64,'A'*64):
        assert SERVICE['digest_token'](bad) is None

def test_claimed_message():
    token='a'*64;digest=SERVICE['digest_token'](token)
    row=SimpleNamespace(status='sending',message='synthetic diagnosis'+chr(10)+'[claim-sha256:'+digest+']')
    assert SERVICE['claimed_message'](row,token)=='synthetic diagnosis'
    assert SERVICE['claimed_message'](row,'b'*64) is None
    row.status='delivery_started'
    assert SERVICE['claimed_message'](row,token)=='synthetic diagnosis'
    row.status='sent'
    assert SERVICE['claimed_message'](row,token) is None

def test_finish_alert():
    service=runpy.run_path(str(Path(__file__).resolve().parents[1]/'app/services/print_alert_reserve.py'))
    try:
        service['finish_alert'](None,None,1,'pending','synthetic')
    except ValueError:
        pass
    else:
        raise AssertionError('unknown result must fail before accessing a database')

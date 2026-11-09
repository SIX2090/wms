"""Actual registered WMS routes, synthetic memory rows and owned image files only."""
import pytest

from tests.test_money_route_synthetic_20261109 import money_case, unchanged_inventory


@pytest.fixture
def claim_case(money_case, tmp_path, monkeypatch):
    case = money_case
    w = case.w
    monkeypatch.setitem(w.app.config, 'WECHAT_HELPER_TOKEN', 'synthetic-claim-token')
    monkeypatch.setattr(w, '_wechat_share_output_dir', lambda: str(tmp_path))
    image = tmp_path / 'synthetic.png'
    image.write_bytes(b'synthetic-image-content')
    cfg = w.WechatShareConfig(enabled=True, receiver_name='synthetic recipient', auto_send=False)
    w.db.session.add(cfg)
    w.db.session.flush()
    rows = [w.WechatShareLog(config_id=cfg.id, module_key='in_order', order_id=i + 1,
                            order_no='SYNTHETIC-' + str(i), status=status,
                            message='synthetic original diagnosis', image_path=str(image))
            for i, status in enumerate(('queued_v2', 'queued_v2', 'pending'))]
    w.db.session.add_all(rows)
    w.db.session.commit()
    case.claim_ids = [row.id for row in rows]
    case.claim_headers = {'X-Wechat-Helper-Token': 'synthetic-claim-token',
                          'X-Wechat-Helper-Protocol': '2'}
    yield case
    unchanged_inventory(case)
    assert w.PrintJob.query.count() == 0


def test_two_helpers_do_not_receive_same_task(claim_case):
    c = claim_case
    clients = [c.w.app.test_client(), c.w.app.test_client()]
    replies = [client.get('/api/wechat_helper/tasks', headers=c.claim_headers) for client in clients]
    assert all(reply.status_code == 200 for reply in replies)
    tasks = [reply.json['tasks'][0] for reply in replies]
    assert [task['id'] for task in tasks] == c.claim_ids[:2]
    assert all(reply.cache_control.no_store for reply in replies), [dict(reply.headers) for reply in replies]
    assert clients[1].get('/api/wechat_helper/tasks', headers=c.claim_headers).json['tasks'] == []
    task = tasks[0]
    url = task['image_url']
    assert clients[0].get(url, headers=c.claim_headers).status_code == 404
    headers = {**c.claim_headers, 'X-Wechat-Task-Claim': task['claim_token']}
    delivered = clients[0].get(url, headers=headers)
    assert delivered.status_code == 200 and delivered.data == b'synthetic-image-content'
    assert clients[1].get(url, headers=headers).status_code == 404
    assert clients[0].post(task['report_url'], json={'status': 'sent'}, headers=c.claim_headers).status_code == 409
    report = clients[0].post(task['report_url'], json={'status': 'ready', 'msg': 'synthetic pasted'}, headers=headers)
    assert report.status_code == 200
    c.w.db.session.expire_all()
    row = c.w.db.session.get(c.w.WechatShareLog, task['id'])
    assert row.status == 'uncertain' and 'synthetic pasted' in row.message
    assert 'synthetic original diagnosis' in row.message and task['claim_token'] not in row.message
    assert clients[0].post(task['report_url'], json={'status': 'sent'}, headers=headers).status_code == 409
    assert c.w.db.session.get(c.w.WechatShareLog, c.claim_ids[2]).status == 'pending'


def test_old_helper_and_wrong_shared_credential_do_not_claim(claim_case):
    c = claim_case
    before = [(row.id, row.status, row.message) for row in c.w.WechatShareLog.query.order_by(c.w.WechatShareLog.id)]
    assert c.client.get('/api/wechat_helper/tasks').status_code == 401
    assert c.client.get('/api/wechat_helper/tasks', headers={'X-Wechat-Helper-Token': 'synthetic-claim-token'}).status_code == 426
    assert c.client.get('/api/wechat_helper/tasks', headers={**c.claim_headers, 'X-Wechat-Helper-Token': 'wrong'}).status_code == 401
    assert [(row.id, row.status, row.message) for row in c.w.WechatShareLog.query.order_by(c.w.WechatShareLog.id)] == before

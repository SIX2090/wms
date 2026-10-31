"""Existing read-only agents must persist and show an honest failure state."""
import pytest
import app as wms


@pytest.mark.parametrize('kind',['warehouse_patrol','purchase_followup'])
def test_agent_step_failure_is_persisted_and_not_reported_completed(kind,monkeypatch):
    wms.app.config.update(TESTING=True,WTF_CSRF_ENABLED=False)
    with wms.app.app_context():
        wms.db.drop_all();wms.db.create_all()
        user=wms.User(username='SYNTHETIC-AGENT',password_hash='unusable-test-hash',role='admin',must_change_password=False)
        wms.db.session.add(user);wms.db.session.commit()
        monkeypatch.setattr(wms,'_ai_capability_allowed',lambda *_:True)
        monkeypatch.setattr(wms,'inventory_alert_enabled',lambda:False)
        monkeypatch.setattr(wms,'build_purchase_order_todo_summary',lambda:{})
        def fail(*_,**__):raise RuntimeError('SYNTHETIC STEP FAILURE')
        monkeypatch.setattr(wms,'_ai_add_agent_step',fail)
        client=wms.app.test_client()
        with client.session_transaction() as session:
            session['_user_id']=str(user.id);session['_fresh']=True
        try:
            response=client.post('/ai/agent_tasks/run/'+kind)
            assert response.status_code==302
            task=wms.AIAgentTask.query.one()
            assert task.status=='failed' and task.completed_at
            assert '失败' in task.summary
            with client.session_transaction() as session:
                messages=session.get('_flashes',[])
            assert any(level=='danger' and '失败' in text for level,text in messages)
            assert not any('已完成' in text for _,text in messages)
            assert wms.StockTransaction.query.count()==0
        finally:
            wms.db.session.remove();wms.db.drop_all()

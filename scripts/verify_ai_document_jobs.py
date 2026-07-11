from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-document-jobs-secret'
sys.path.insert(0, str(APP_DIR))

import app as wms_app


def main() -> int:
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        wms_app.db.create_all()
        username = 'document-job-verifier'
        wms_app.User.query.filter_by(username=username).delete()
        wms_app.db.session.commit()
        user = wms_app.User(
            username=username,
            password_hash='not-used',
            role='warehouse',
            status='normal',
        )
        wms_app.db.session.add(user)
        wms_app.db.session.commit()
        user_id = user.id

        job = wms_app.AIDocumentJob(
            user_id=user_id,
            source='vision',
            document_type='in_order',
            status='pending_confirmation',
            supplier='Supplier A',
            order_no='DN-001',
            source_text_summary='Supplier A sends material A001 x 2',
            confirmation_token='verify-token',
        )
        wms_app.db.session.add(job)
        wms_app.db.session.flush()
        wms_app.db.session.add(wms_app.AIDocumentItem(
            job_id=job.id,
            line_no=1,
            raw_text='A001 2',
            code='A001',
            name='Material A',
            quantity=2,
            confidence=0.91,
            match_status='matched',
        ))
        wms_app.db.session.commit()
        job_id = job.id

    client = app.test_client()
    with client.session_transaction() as session_data:
        session_data['_user_id'] = str(user_id)
        session_data['_fresh'] = True

    response = client.get('/ai/document_jobs')
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'AI文档任务' in page
    assert 'pending_confirmation' in page
    assert 'Supplier A sends material A001 x 2' in page
    assert f'/ai/document_jobs/{job_id}' in page
    assert '待确认' in page

    detail = client.get(f'/ai/document_jobs/{job_id}')
    assert detail.status_code == 200
    detail_page = detail.get_data(as_text=True)
    assert 'AI文档任务详情' in detail_page
    assert 'A001 2' in detail_page
    assert 'Material A' in detail_page
    assert '/ai/document_confirm/verify-token' in detail_page
    assert f'/ai/document_jobs/{job_id}/confirm' in detail_page
    assert f'/ai/document_jobs/{job_id}/retry' in detail_page
    assert f'/ai/document_jobs/{job_id}/feedback' in detail_page
    assert '识别尝试' in detail_page

    feedback = client.post(
        f'/ai/document_jobs/{job_id}/feedback',
        data={'rating': 'not_helpful', 'error_type': 'quantity_error', 'note': 'quantity should be 3'},
        follow_redirects=True,
    )
    assert feedback.status_code == 200
    feedback_page = feedback.get_data(as_text=True)
    assert 'not_helpful' in feedback_page
    assert 'quantity_error' in feedback_page
    assert 'quantity should be 3' in feedback_page

    reopened = client.post(f'/ai/document_jobs/{job_id}/confirm', follow_redirects=False)
    assert reopened.status_code == 302
    assert '/ai/document_confirm/' in (reopened.headers.get('Location') or '')
    with client.session_transaction() as session_data:
        confirmations = session_data.get('_ai_document_confirmations') or {}
        assert confirmations
        latest_payload = list(confirmations.values())[-1]
        assert latest_payload['document_job_id'] == job_id
        assert latest_payload['rows'][0]['name'] == 'Material A'

    retry = client.post(f'/ai/document_jobs/{job_id}/retry', follow_redirects=False)
    assert retry.status_code in (200, 302)

    with app.app_context():
        assert wms_app.AIDocumentFeedback.query.filter_by(job_id=job_id).count() == 1
        assert wms_app.AIDocumentAttempt.query.filter_by(job_id=job_id).count() >= 1
        wms_app._ai_update_document_job(
            job_id,
            'draft_created',
            generated_document_type='in_order',
            generated_document_id=123,
            generated_document_no='IN-001',
        )
        updated = wms_app.db.session.get(wms_app.AIDocumentJob, job_id)
        assert updated.status == 'draft_created'
        assert updated.generated_document_type == 'in_order'
        assert updated.generated_document_id == 123
        assert updated.generated_document_no == 'IN-001'
        assert updated.completed_at is not None

    print('PASS AI-DOCUMENT-JOBS: document recognition jobs, items, status updates, list page, and detail page are tracked')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""BUG-2026-10-17-011-F05：低置信度人工确认门禁必须真正接线。

- OCR 保存 job 时写入 low_confidence_fields；
- 门禁在读"有无确认记录"之前先看风险标记，且异常时 fail-closed。
"""
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import app as wms  # noqa: E402
from app import db  # noqa: E402
from models.ai import AIDocumentFieldConfirmation, AIDocumentJob  # noqa: E402

wms.app.config['TESTING'] = True
wms.app.config['WTF_CSRF_ENABLED'] = False


@pytest.fixture(autouse=True)
def _ctx():
    with wms.app.app_context():
        db.drop_all()
        db.create_all()
        yield
        db.session.remove()


def test_low_confidence_names_only_for_unknown_or_low():
    f = wms._ai_low_confidence_field_names
    assert f([{'item': {'confidence': 0.5}}]) == ['material_id', 'quantity']
    assert f([{'item': {'confidence': 0}}]) == []
    assert f([{'item': {}}]) == []
    assert f([{'item': {'confidence': 0.99}}]) == []


def _job(low='[]'):
    job = AIDocumentJob(user_id=1, source='text', document_type='in_order',
                        status='recognized', low_confidence_fields=low)
    db.session.add(job)
    db.session.commit()
    return job


def test_gate_blocks_low_confidence_without_confirmation():
    job = _job('["quantity"]')
    allowed, reasons = wms._ai_check_draft_creation_gate(job.id)
    assert allowed is False
    assert any('低置信度' in r for r in reasons), reasons


def test_gate_allows_after_field_confirmed():
    job = _job('["quantity"]')
    db.session.add(AIDocumentFieldConfirmation(
        job_id=job.id, field_name='quantity', confirmation_status='confirmed_original',
        original_value='1', confirmed_value='1', evidence_source='ocr',
        model='m', prompt_version='p', schema_version='s', confirmed_by=1, confirmed_at=datetime.now(),
        created_at=datetime.now()))
    db.session.commit()
    allowed, reasons = wms._ai_check_draft_creation_gate(job.id)
    assert allowed is True, reasons


def test_gate_rejects_missing_job_and_allows_text_drafts():
    allowed, reasons = wms._ai_check_draft_creation_gate(999999)
    assert allowed is False
    assert reasons
    assert wms._ai_check_draft_creation_gate(None) == (True, [])

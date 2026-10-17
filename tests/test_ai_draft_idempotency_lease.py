# -*- coding: utf-8 -*-
"""BUG-2026-10-17-011-F04：草稿幂等 processing 槽位必须有租约超时。

旧实现只写 processing 不设超时：进程崩溃后同一业务键永久返回"正在处理中"。
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import app as app_module  # noqa: E402
from app import db  # noqa: E402
from ai.draft_idempotency import (  # noqa: E402
    AIDraftIdempotencyService, DRAFT_STATUS_PROCESSING,
)
from models.ai import AIDraftIdempotency  # noqa: E402

app_module.app.config['TESTING'] = True
app_module.app.config['WTF_CSRF_ENABLED'] = False


@pytest.fixture()
def service():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        yield AIDraftIdempotencyService(db, AIDraftIdempotency)
        db.session.remove()


def _seed(service, age_seconds):
    key = service.compute_key(1, 'check_draft', 'text', {'a': 1})
    stamp = datetime.now() - timedelta(seconds=age_seconds)
    row = AIDraftIdempotency(user_id=1, capability='check_draft',
                             idempotency_key=key, source='text',
                             status=DRAFT_STATUS_PROCESSING,
                             created_at=stamp, updated_at=stamp)
    db.session.add(row)
    db.session.commit()
    return key


def _acquire(service):
    return service.acquire(capability='check_draft', source='text',
                           business_fields={'a': 1}, draft_type='check',
                           user_id=1)


def test_stale_processing_slot_is_taken_over(service):
    _seed(service, age_seconds=3600)
    slot = _acquire(service)
    assert slot.acquired is True
    assert slot.record.status == DRAFT_STATUS_PROCESSING


def test_fresh_processing_slot_still_conflicts(service):
    _seed(service, age_seconds=1)
    slot = _acquire(service)
    assert slot.acquired is False
    assert '处理中' in slot.conflict_reason


def test_lease_can_be_tuned_by_env(service, monkeypatch):
    monkeypatch.setenv('WMS_AI_DRAFT_LEASE_SECONDS', '60')
    _seed(service, age_seconds=120)
    assert _acquire(service).acquired is True

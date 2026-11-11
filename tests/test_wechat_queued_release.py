"""CI-side pytest wrapper for BUG-2026-11-11-004.

Runs the same offline regression lock as ``scripts/verify_wechat_queued_release.py``.
The lock only reads source files and uses a synthetic ``sqlite:///:memory:``
database; it never imports the WMS application or opens a product database.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    'verify_wechat_queued_release', ROOT / 'scripts' / 'verify_wechat_queued_release.py')
_guard = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_guard)

CORE = (
    'release_cas_on_status_and_message',
    'safe_codes_has_released_queued_v2',
    'route_release_precedes_execute_share',
    'template_queued_v2_no_longer_disabled',
    'behaviour_refuses_sending',
    'behaviour_refuses_delivery_started',
    'behaviour_deadlock_blocks_even_force',
    'behaviour_release_unblocks_forced_resend',
    'route_queued_v2_releases_then_resends',
    'route_release_failure_returns_409_no_send',
)


@pytest.fixture(scope='module')
def results():
    return _guard.run_checks()


def test_all_queued_release_checks_pass(results):
    assert all(results.values()), [name for name, ok in results.items() if not ok]


def test_core_guards_are_present_and_green(results):
    missing = [name for name in CORE if name not in results]
    assert not missing, f'missing checks: {missing}'
    assert all(results[name] for name in CORE), [name for name in CORE if not results[name]]


def test_release_queued_share():
    """A9 failure-path test for the new business function itself.

    A claimed record (``sending`` / ``delivery_started``) may already have
    produced an external effect, and an unsupported dialect must never be
    touched: both must be refused without rewriting the row.
    """
    rel = _guard._release_namespace()
    assert rel is not None
    release = rel['release_queued_share']

    fake_db = types.SimpleNamespace(
        engine=types.SimpleNamespace(dialect=types.SimpleNamespace(name='postgresql')))
    ok, reason = release(fake_db, object(), 1)
    assert ok is False and '不支持' in reason

    engine, Session, Log, _Dispatch, db, _env = _guard._build_db()
    for status in ('sending', 'delivery_started', 'uncertain', 'sent'):
        with Session(engine) as session:
            session.query(Log).delete()
            session.add(Log(id=1, module_key='in_order', order_id=1,
                            share_date=_guard._dt.date(2026, 11, 11),
                            status=status, message='原始消息'))
            session.commit()
        ok, reason = release(db, Log, 1)
        assert ok is False, f'{status} must be refused'
        with Session(engine) as session:
            row = session.query(Log).filter_by(id=1).one()
            assert (row.status, row.message) == (status, '原始消息')

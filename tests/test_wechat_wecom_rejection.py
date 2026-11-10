"""BUG-2026-11-10-012: structured WeCom rejection is retryable, transport stays uncertain.

Delegates to scripts/verify_wechat_wecom_rejection.py, which executes the real
execute_share over sqlite:///:memory: without importing the WMS app, touching the
production DB, or issuing HTTP requests.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    'verify_wechat_wecom_rejection',
    ROOT / 'scripts' / 'verify_wechat_wecom_rejection.py',
)
_guard = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_guard)


def test_wecom_explicit_rejection_is_retryable_and_transport_is_not():
    results = _guard.run_checks()
    assert all(results.values()), {k: v for k, v in results.items() if not v}

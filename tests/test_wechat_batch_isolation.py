"""BUG-2026-11-11-001: one broken share image must not abort the whole batch.

Delegates to scripts/verify_wechat_batch_isolation.py, which extracts the real
run_wechat_share_for_today with AST and runs it in a synthetic namespace: no
WMS app import, no database connection, no HTTP, no subprocess.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    'verify_wechat_batch_isolation',
    ROOT / 'scripts' / 'verify_wechat_batch_isolation.py',
)
_guard = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_guard)


def test_single_failed_order_does_not_abort_remaining_orders():
    results = _guard.run_checks()
    assert all(results.values()), {k: v for k, v in results.items() if not v}

"""BUG-2026-11-11-002 regression: resending a log whose config is gone must fail closed.

No WMS app import, no database, no HTTP. The verifier extracts the real route
function with the AST and executes it in a synthetic namespace.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    'verify_wechat_resend_config_guard',
    ROOT / 'scripts' / 'verify_wechat_resend_config_guard.py',
)
_guard = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_guard)


def test_resend_never_invents_or_borrows_a_share_config():
    results = _guard.run_checks(ROOT / 'app' / 'routes' / 'wechat_share.py')
    assert all(results.values()), [name for name, ok in results.items() if not ok]

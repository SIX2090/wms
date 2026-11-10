"""Loopback-only health probe target; no WMS app import, no DB, no HTTP."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    'verify_wechat_helper_health_guard',
    ROOT / 'scripts' / 'verify_wechat_helper_health_guard.py',
)
_guard = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_guard)


def test_helper_health_url_stays_on_loopback():
    results = _guard.run_checks(ROOT / 'app' / 'app.py')
    assert all(results.values()), results

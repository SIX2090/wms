"""BUG-2026-11-11-003 regression: WMS_WECHAT_HELPER_URL must actually win.

No WMS app import, no database, no HTTP. The verifier extracts the real
helper/send/save functions with the AST and executes them in a synthetic
namespace.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    'verify_wechat_helper_env_override',
    ROOT / 'scripts' / 'verify_wechat_helper_env_override.py',
)
_guard = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_guard)

APP_SOURCE = ROOT / 'app' / 'app.py'
ROUTE_SOURCE = ROOT / 'app' / 'routes' / 'wechat_share.py'
_RESULTS = None


def _all_results():
    global _RESULTS
    if _RESULTS is None:
        _RESULTS = _guard.run_checks(APP_SOURCE, ROUTE_SOURCE)
    return _RESULTS


def test_helper_url_env_override_regression_lock():
    results = _all_results()
    assert all(results.values()), [name for name, ok in results.items() if not ok]


def test_regression_lock_covers_the_core_guards():
    results = _all_results()
    required = {
        '_wechat_share_send_image_env_is_first_operand',
        '_wechat_share_helper_health_url_env_is_first_operand',
        'inventory_truth_matches_current_source_anchor',
        'env_override_wins_over_persisted_default',
        'no_env_falls_back_to_config',
        'external_env_rejected',
        'health_env_override_wins',
        'save_route_has_no_hardcoded_default',
        'save_blank_stores_empty_string',
        'save_rejects_external_url',
    }
    assert required <= set(results), sorted(required - set(results))
    assert len(results) >= 50


def test_static_contract_is_independently_green():
    static = _guard._static_checks(APP_SOURCE, ROUTE_SOURCE)
    assert all(static.values()), [name for name, ok in static.items() if not ok]

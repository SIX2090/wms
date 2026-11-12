"""CI-side pytest wrapper for the 2026-11-11 WeChat bugfix QA regression lock.

Each test function is named after the product function/behaviour it covers and
asserts the corresponding group of checks from
scripts/verify_wechat_bugfix_qa_20261111.py. That verifier AST-extracts the
REAL functions into synthetic namespaces; it never imports the WMS application,
opens a product database, or issues an HTTP request.

Also runnable directly as an offline script (no pytest needed):
    py -3.11 -B -X utf8 tests/test_wechat_bugfix_qa_20261111.py
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    'qa_wechat_bugfix_20261111',
    ROOT / 'scripts' / 'verify_wechat_bugfix_qa_20261111.py')
_guard = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_guard)

_RESULTS: dict[str, bool] | None = None


def _results() -> dict[str, bool]:
    global _RESULTS
    if _RESULTS is None:
        _RESULTS = _guard.run_checks()
    return _RESULTS


def _group(prefix: str) -> None:
    results = _results()
    group = {k: v for k, v in results.items() if k.startswith(prefix)}
    assert group, f'no QA checks registered for {prefix}'
    assert all(group.values()), [k for k, v in group.items() if not v]


def test_paste_image_and_optionally_send() -> None:
    _group('fix1_')


def test_open_contact() -> None:
    _group('fix2_')


def test__wechat_helper_authorized() -> None:
    _group('fix3_')


def test__wechat_share_get_helper_health() -> None:
    _group('fix4_')


def test__wechat_share_cleanup_old_images_daily() -> None:
    _group('fix5_')


def test_wechat_share_html_helper_url_input() -> None:
    _group('fix6_')


def test_abandoned_qt_window_class_check() -> None:
    _group('fix7_')


def test_wechat_exception_message_desensitization() -> None:
    _group('fix8_')


def test_all_qa_regression_checks_green() -> None:
    results = _results()
    assert len(results) >= 42, f'QA check set unexpectedly small: {len(results)}'
    assert all(results.values()), [k for k, v in results.items() if not v]


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items())
             if k.startswith('test_') and callable(v)]
    failures = []
    for fn in tests:
        try:
            fn()
            print('  PASS  ' + fn.__name__)
        except Exception as exc:
            print('  FAIL  ' + fn.__name__ + ': ' + str(exc))
            failures.append(fn.__name__)
    print(f'\n  {len(tests) - len(failures)}/{len(tests)} QA wrapper tests passed')
    sys.exit(1 if failures else 0)

"""BUG-2026-10-25-011: real search lifecycle, prompt fallback and request stack."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ['normal-success-original-url-and-headers',
 'normal-empty-result',
 'normal-limit80-total81-preserved',
 'normal-literal-text-escaping',
 'normal-current-http500-failure',
 'normal-current-business-failure',
 'normal-current-json-failure',
 'normal-current-network-failure',
 'normal-session-error-global-handler-preserved',
 'normal-current-error-then-user-retry',
 'normal-row-server-url-preserved',
 'actual-api-getRaw-and-base-stack-control',
 'independent-navigation-keeps-first-last-contract',
 'normal-out-of-order-success',
 'normal-old-network-failure-must-not-clear-new-results',
 'normal-input-debounce-invalidates-immediately',
 'normal-input-clears-selectable-old-row',
 'normal-same-keyword-new-generation',
 'normal-clear-input-invalidates-old-search',
 'normal-hide-cancels-debounce',
 'normal-hide-ignores-pending-success',
 'normal-hide-ignores-pending-failure',
 'normal-detached-dom-rejects-old-response',
 'normal-reopen-does-not-mutate-old-dom',
 'fallback-current-success-opens-first-original-url',
 'fallback-cancel-without-previous-request',
 'fallback-current-empty-keeps-warning',
 'fallback-current-http500-failure',
 'fallback-current-business-failure',
 'fallback-current-network-failure',
 'fallback-two-queries-old-success',
 'fallback-same-query-old-success',
 'fallback-second-cancel-invalidates-success',
 'fallback-second-cancel-invalidates-failure',
 'fallback-old-failure-after-current-success',
 'fallback-old-empty-after-current-success',
 'fallback-to-normal-invalidates-old-navigation',
 'normal-to-fallback-invalidates-old-render',
 'normal-to-fallback-cancel-invalidates-old-render',
 'fallback-cancel-then-current-fallback-works',
 'fallback-old-success-before-current-response',
 'fallback-old-failure-before-current-response',
 'fallback-current-failure-then-old-success',
 'fallback-current-empty-then-old-success',
 'fallback-second-cancel-invalidates-business-failure',
 'fallback-new-module-invalidates-old-module',
 'fallback-to-normal-old-error-is-local-silent',
 'fallback-to-normal-old-empty-is-local-silent',
 'normal-to-fallback-old-error-does-not-render',
 'normal-to-fallback-cancel-old-error-does-not-render',
 'fallback-to-normal-hide-still-invalidates-old-navigation',
 'fallback-two-cancellations-no-request',
 'fallback-cancel-then-normal-works']


@pytest.mark.parametrize('scenario', SCENARIOS)
def test_document_search_lifecycle_runtime(scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    result = subprocess.run(
        [node, '--max-old-space-size=96',
         str(ROOT / 'tests/frontend_document_search_runtime.cjs'), str(ROOT), scenario],
        capture_output=True, text=True, encoding='utf-8', timeout=25,
    )
    assert result.returncode == 0, result.stdout + result.stderr

"""Production no longer needs permission to compile strings as JavaScript."""
import re
from pathlib import Path

import app as app_module
from config import ProductionConfig

ROOT = Path(__file__).resolve().parents[1]


def assert_script_policy(policy):
    script = next(part.strip() for part in policy.split(';') if part.strip().startswith('script-src '))
    assert "'unsafe-eval'" not in script
    assert "'self'" in script
    assert "'unsafe-inline'" in script  # Existing inline scripts/events still depend on this.
    assert "object-src 'none'" in policy
    assert "base-uri 'self'" in policy
    assert "frame-ancestors 'self'" in policy


def test_production_policy_denies_string_codegen():
    assert_script_policy(ProductionConfig.SECURITY_HEADERS['Content-Security-Policy'])


def test_actual_response_uses_policy_without_eval(monkeypatch):
    monkeypatch.setitem(app_module.app.config, 'SECURITY_HEADERS', dict(ProductionConfig.SECURITY_HEADERS))
    response = app_module.app.test_client().get('/login')
    assert response.status_code == 200
    assert_script_policy(response.headers['Content-Security-Policy'])


def test_browser_sources_have_no_string_codegen_dependency():
    # Include locally hosted vendor bundles, not only the A5 business-JS scope.
    paths = list((ROOT / 'app/static').rglob('*.js')) + list((ROOT / 'app/templates').rglob('*.html'))
    patterns = [r'\beval\s*\(', r'\bFunction\s*\(', r'\bset(?:Timeout|Interval)\s*\(\s*[\"\']']
    offenders = []
    for path in paths:
        source = path.read_text(encoding='utf-8')
        if any(re.search(pattern, source) for pattern in patterns):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, offenders

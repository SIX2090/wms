"""Traceability must remain unverified until a material-scoped query is available."""
from pathlib import Path
import subprocess
import sys

import pytest

from app.ai.documents.material_governance_enhanced import (
    approve_alias,
    create_alias_request,
    validate_one_material_multiple_codes_traceable,
)


@pytest.mark.parametrize('query_state', ['empty', 'aliases', 'error'])
def test_validate_one_material_multiple_codes_traceable_reports_unverified(query_state):
    alias = approve_alias(
        alias=create_alias_request(
            alias_key='SYN-ALIAS', material_id=42, material_code='SYN-42',
            created_by='synthetic', now='2026-11-16T08:00:00',
        ),
        approved_by='synthetic', now='2026-11-16T08:01:00',
    )
    calls = []

    def query_aliases(alias_key):
        calls.append(alias_key)
        if query_state == 'error':
            raise RuntimeError('synthetic query failure')
        return [alias] if query_state == 'aliases' else []

    verified, reason, aliases = validate_one_material_multiple_codes_traceable(
        material_id=42, query_aliases=query_aliases,
    )

    assert verified is False, 'Without a material-scoped query, traceability is unverified'
    assert '未验证' in reason
    assert aliases == []
    assert calls == [], 'The alias-key callback must not be used as a material-ID query'


def test_material_governance_verifier_discloses_unverified_traceability(tmp_path):
    script = Path(__file__).resolve().parents[1] / 'scripts/verify_ai_material_governance_enhanced.py'
    result = subprocess.run(
        [sys.executable, '-I', '-B', '-X', 'utf8', str(script)],
        cwd=tmp_path, capture_output=True, text=True, encoding='utf-8', timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '一物多码追溯仍未验证' in result.stdout

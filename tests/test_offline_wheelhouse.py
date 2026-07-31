from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def test_offline_wheelhouse_verifier_is_network_isolated():
    verifier = (ROOT_DIR / "scripts" / "verify_offline_wheelhouse.py").read_text(encoding="utf-8")
    for option in ('"--dry-run"', '"--ignore-installed"', '"--no-index"', '"--find-links"'):
        assert option in verifier
    assert 'app" / "requirements.txt"' in verifier

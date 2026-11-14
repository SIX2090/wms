"""BUG-2026-09-04-003: keep the stable signing invariant for the approved parallel App.

2026-11-14: formal pinned mobile signing replaces the absent legacy debug secret.
Missing credentials must fail before assemble; no ephemeral signing is permitted.
"""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github/workflows/android-build.yml"


def test_restore_step_exists_before_build():
    src = WF.read_text(encoding="utf-8")
    restore = src.index("Restore fixed mobile signing (BUG-2026-09-04-003)")
    assert restore < src.index("Build Release APK (R8 瘦身)")


def test_secret_name_and_decode_target():
    src = WF.read_text(encoding="utf-8")
    assert "secrets.WMS_MOBILE_SIGNING_BUNDLE" in src
    assert "python scripts/prepare_android_signing.py" in src
    assert 'WMS_ALLOW_DEBUG_SIGNED_RELEASE: "1"' not in src


def test_missing_secret_refuses_unstable_update_candidate():
    src = (ROOT / "scripts/prepare_android_signing.py").read_text(encoding="utf-8")
    assert "missing or oversized WMS_MOBILE_SIGNING_BUNDLE" in src
    assert "raise SystemExit" in src
    assert "refusing an ephemeral release signer" in src
    assert "-genkey" not in src
    assert "certificate mismatch" in src


def test_workflow_yaml_parses():
    data = yaml.safe_load(WF.read_text(encoding="utf-8"))
    names = [s.get("name", "") for s in data["jobs"]["build"]["steps"]]
    assert "Restore fixed mobile signing (BUG-2026-09-04-003)" in names

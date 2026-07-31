from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def test_stability_gate_covers_every_mandatory_command():
    gate = (ROOT_DIR / "scripts" / "verify_stability_gate.py").read_text(encoding="utf-8")
    for command in (
        "scripts/lint_wms_rules.py",
        "scripts/lint_no_raw_post_fetch.py",
        "scripts/verify_wms_bugs.py",
        "scripts/verify_in_order_state_machine.py",
        "scripts/verify_offline_wheelhouse.py",
        '"tests/"',
    ):
        assert command in gate


def test_stability_baseline_tracks_all_ten_critical_chains():
    baseline = (ROOT_DIR / "WMS_STABILITY_BASELINE.md").read_text(encoding="utf-8")
    assert "Task: AI-STAB-F01" in baseline
    assert baseline.count("\n1.") == 1
    assert baseline.count("\n10.") == 1

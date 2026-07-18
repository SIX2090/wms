from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"

SMOKE_SCRIPTS = (
    "verify_source_encoding.py",
    "verify_ai_platform_boundaries.py",
    "verify_ai_platform_foundations.py",
    "verify_ai_tool_registry.py",
    "verify_ai_tool_schemas.py",
    "verify_ai_streaming.py",
    "verify_ai_document_evaluation.py",
)

CORE_SCRIPTS = SMOKE_SCRIPTS + (
    'verify_ai_high_risk_boundaries.py',
    'verify_ai_business_permissions.py',
    "verify_ai_permission_matrix.py",
    "verify_ai_security.py",
    "verify_ai_handlers.py",
    "verify_ai_orchestrator.py",
    "verify_ai_history.py",
    "verify_ai_idempotency.py",
    "verify_ai_draft_idempotency.py",
    "verify_ai_audit_models.py",
    "verify_ai_audit_routes.py",
    "verify_ai_tools_endpoint.py",
    "verify_ai_warehouse_assistant_endpoint.py",
    "verify_ai_chat_stream_endpoint.py",
    "verify_ai_draft_check_endpoint.py",
    "verify_ai_document_jobs.py",
    "verify_ai_agents.py",
    "verify_ai_stage4_knowledge.py",
    "verify_ai_stage5_ops.py",
    "verify_ai_stage6_prelaunch.py",
    "verify_ai_stage7_replenishment.py",
    "verify_ai_tool_compliance.py",
    "verify_ai_ledger_consistency.py",
    "verify_ai_golden_samples.py",
    "verify_ai_image_preprocessing.py",
    "verify_ai_provider_evaluation.py",
    "verify_ai_delivery_matcher.py",
    "verify_ai_delivery_matcher_calibration.py",
    "verify_ai_material_governance.py",
    "verify_ai_material_governance_enhanced.py",
    "verify_ai_document_confirmation.py",
    "verify_ai_document_confirmation_status.py",
    "verify_ai_field_feedback.py",
    "verify_ai_warehouse_workbench.py",
    "verify_ai_purchase_followup_workbench.py",
    "verify_ai_knowledge_lifecycle.py",
    "verify_ai_budget_control.py",
    "verify_ai_data_retention.py",
    "verify_ai_business_quality.py",
    "verify_ai_business_quality_dashboard.py",
    "verify_ai_warehouse_workbench_page.py",
    "verify_ai_purchase_workbench_page.py",
    "verify_ai_browser_e2e.py",
    "verify_ai_launch_acceptance.py",
    "verify_ai_rollout_control.py",
    "verify_ai_acceptance_evidence.py",
    "verify_ai_sales_draft_validation.py",
    "verify_ai_release_handover.py",
)

FULL_EXTRA_SCRIPTS = (
    "verify_gray_release.py",
    "verify_integration_e2e.py",
    "verify_wms_bugs.py",
)


@dataclass(frozen=True)
class ScriptResult:
    name: str
    returncode: int
    duration_seconds: float


def _all_ai_scripts() -> tuple[str, ...]:
    names = sorted(
        path.name
        for path in SCRIPTS_DIR.glob("verify_ai_*.py")
        if path.name != Path(__file__).name
    )
    ordered = list(CORE_SCRIPTS)
    ordered.extend(name for name in names if name not in ordered)
    ordered.extend(name for name in FULL_EXTRA_SCRIPTS if name not in ordered)
    return tuple(ordered)


def scripts_for_level(level: str) -> tuple[str, ...]:
    if level == "smoke":
        return SMOKE_SCRIPTS
    if level == "core":
        return CORE_SCRIPTS
    if level == "full":
        return _all_ai_scripts()
    raise ValueError(f"Unknown verification level: {level}")


def _verification_environment(database_path: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.setdefault("FLASK_ENV", "testing")
    environment.setdefault("WMS_SKIP_STARTUP_DB_UPGRADE", "1")
    environment.setdefault("SECRET_KEY", "verify-ai-all-secret")
    environment.setdefault("PYTHONUTF8", "1")
    environment.setdefault("PYTHONIOENCODING", "utf-8")
    environment["WMS_DATABASE_URI"] = f"sqlite:///{database_path.as_posix()}"
    app_dir = str(ROOT / "app")
    existing_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (app_dir, existing_pythonpath) if part
    )
    return environment


def run_script(name: str) -> ScriptResult:
    path = SCRIPTS_DIR / name
    if not path.is_file():
        print(f"FAIL {name}: script does not exist", flush=True)
        return ScriptResult(name=name, returncode=2, duration_seconds=0.0)

    print(f"\n=== Running {name} ===", flush=True)
    started_at = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="wms-ai-verify-") as temp_dir:
        database_path = Path(temp_dir) / "inventory-test.db"
        completed = subprocess.run(
            [sys.executable, str(path)],
            cwd=ROOT,
            env=_verification_environment(database_path),
            check=False,
        )
    duration = time.perf_counter() - started_at
    status = "PASS" if completed.returncode == 0 else "FAIL"
    print(f"=== {status} {name} ({duration:.2f}s) ===", flush=True)
    return ScriptResult(name, completed.returncode, duration)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the WMS AI verification suite.")
    parser.add_argument(
        "--level",
        choices=("smoke", "core", "full"),
        default="core",
        help="Verification depth. Default: core.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first failed script.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List scripts for the selected level without running them.",
    )
    args = parser.parse_args()

    selected_scripts = scripts_for_level(args.level)
    if args.list:
        print(f"WMS AI verification level: {args.level}")
        for name in selected_scripts:
            print(name)
        return 0

    print(
        f"WMS AI verification: level={args.level}, scripts={len(selected_scripts)}, "
        f"python={sys.version.split()[0]}"
    )
    results: list[ScriptResult] = []
    for name in selected_scripts:
        result = run_script(name)
        results.append(result)
        if result.returncode != 0 and args.fail_fast:
            break

    failures = [result for result in results if result.returncode != 0]
    total_duration = sum(result.duration_seconds for result in results)
    print("\n=== WMS AI Verification Summary ===")
    for result in results:
        status = "PASS" if result.returncode == 0 else f"FAIL({result.returncode})"
        print(f"{status:10} {result.duration_seconds:8.2f}s  {result.name}")
    print(
        f"TOTAL scripts={len(results)} passed={len(results) - len(failures)} "
        f"failed={len(failures)} duration={total_duration:.2f}s"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

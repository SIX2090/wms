from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    "verify_ai_material_category_coding.py",
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
    "verify_ai_acceptance_page.py",
    "verify_startup_auto_update.py",
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


# 脚本专属环境变量（CI-PERF-2026-09-24）。
#
# 背景：本脚本原先被 .github/workflows/verify.yml 逐个 step 调用，其中
# **verify_ai_ledger_consistency.py 是带 `AI_LEDGER_ENFORCE=strict` 跑的**。
# 改成本脚本统一调度后，若不带这个变量，它会退回默认的 `gradual`（宽松模式）
# —— 那是**校验强度被削弱**，违反 AGENTS.md §六 A12 与 R8 的精神（只准加强）。
# 故在此把原 workflow 的专属环境变量显式固化，保证语义逐字节等价。
SCRIPT_ENV_OVERRIDES: dict[str, dict[str, str]] = {
    "verify_ai_ledger_consistency.py": {"AI_LEDGER_ENFORCE": "strict"},
}


def _verification_environment(
    database_path: Path, script_name: str = ""
) -> dict[str, str]:
    environment = os.environ.copy()
    environment.setdefault("FLASK_ENV", "testing")
    environment.setdefault("WMS_SKIP_STARTUP_DB_UPGRADE", "1")
    environment.setdefault("SECRET_KEY", "verify-ai-all-secret")
    environment.setdefault("PYTHONUTF8", "1")
    environment.setdefault("PYTHONIOENCODING", "utf-8")
    environment["WMS_DATABASE_URI"] = f"sqlite:///{database_path.as_posix()}"
    # 专属变量必须**强制覆盖**（而非 setdefault）：原 workflow 是直接写在
    # run: 前缀上的，等价于强制赋值，宽松的默认值不得把它盖掉。
    environment.update(SCRIPT_ENV_OVERRIDES.get(script_name, {}))
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

    started_at = time.perf_counter()
    # 每个脚本一个独立临时目录 + 独立 SQLite 库——并发后这一点**必须**保持，
    # 否则同一时刻两个脚本会写同一个库文件，产生偶发假失败。
    with tempfile.TemporaryDirectory(prefix="wms-ai-verify-") as temp_dir:
        database_path = Path(temp_dir) / "inventory-test.db"
        completed = subprocess.run(
            [sys.executable, str(path)],
            cwd=ROOT,
            env=_verification_environment(database_path, name),
            capture_output=True,
            text=True,
            check=False,
        )
    duration = time.perf_counter() - started_at
    status = "PASS" if completed.returncode == 0 else "FAIL"
    # 并发下 stdout 交错会变乱，改为把每个脚本的输出整体回收后在主进程里成块打印，
    # 保证日志仍按脚本边界可读（串行时的可读性不因并发而丢失）。
    body = (completed.stdout or "") + (completed.stderr or "")
    print(f"\n=== {status} {name} ({duration:.2f}s) ===\n{body}", flush=True)
    return ScriptResult(name, completed.returncode, duration)


def _resolve_workers() -> int:
    """并发度：环境变量 VERIFY_AI_WORKERS 优先，否则 min(4, cpu)。

    为什么不默认开更高：每个脚本都要完整 `import app`（构造 Flask app）+ 建内存库，
    是重内存 + 重 IO 任务而非纯 CPU 密集，并发过高会在 4 核 runner 上引发内存/
    磁盘争抢，反而更慢。与 scripts/run_verify_parallel.py 的并发度选择理由一致。
    """
    override = os.environ.get("VERIFY_AI_WORKERS", "").strip()
    if override.isdigit() and int(override) > 0:
        return int(override)
    return min(4, os.cpu_count() or 2)


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
    parser.add_argument(
        "--jobs",
        type=int,
        default=0,
        help="并发进程数。0（默认）时取 VERIFY_AI_WORKERS 或 min(4, cpu)。"
             "设 1 可退回完全串行（与历史行为逐字节等价）。",
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

    # CI-PERF-2026-09-24：把「一个跑完再跑下一个」的串行等待换成进程池并发。
    # **隔离模型一字未改**：仍是每个脚本一个独立 python 进程（subprocess）、
    # 独立临时目录与独立 SQLite 库，不共享内存、不共享库文件。
    # --fail-fast 语义在并发下按「已完成结果」近似：先跑完的先判，但不会取消
    # 已经在飞的任务（取消会引入不确定的中间态，宁可多跑完几个也不制造竞态）。
    if args.jobs > 0:
        workers = args.jobs
    else:
        workers = _resolve_workers()

    results: list[ScriptResult] = []
    if args.fail_fast or workers <= 1:
        for name in selected_scripts:
            result = run_script(name)
            results.append(result)
            if result.returncode != 0 and args.fail_fast:
                selected_scripts = selected_scripts[: len(results)]
                break
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(run_script, name) for name in selected_scripts]
            for future in as_completed(futures):
                results.append(future.result())

    failures = [result for result in results if result.returncode != 0]
    # sum = 各脚本耗时之和（串行时代价），真实墙钟时间由 CI step 计时体现。
    sum_duration = sum(result.duration_seconds for result in results)
    # 汇总表按脚本名排序，避免并发完成顺序让输出每次都不一样（可复现性）
    by_name = {result.name: result for result in results}
    ordered = [by_name[name] for name in selected_scripts if name in by_name]
    print("\n=== WMS AI Verification Summary ===")
    for result in ordered:
        status = "PASS" if result.returncode == 0 else f"FAIL({result.returncode})"
        print(f"{status:10} {result.duration_seconds:8.2f}s  {result.name}")
    print(
        f"TOTAL scripts={len(results)} passed={len(results) - len(failures)} "
        f"failed={len(failures)} sum={sum_duration:.2f}s workers={workers}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

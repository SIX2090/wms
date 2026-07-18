"""AI-R18-F01: executable production readiness and evidence gate.

The gate is intentionally conservative: synthetic samples can prove code
behavior, but they cannot satisfy a production go decision.
"""
# AI_TASK: AI-R18-F01
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ROLES = {"admin", "warehouse", "purchase"}
REQUIRED_REAL_SOURCES = {"delivery_note_photo", "wechat_text", "wechat_screenshot"}
ABSOLUTE_METRICS = (
    "unauthorized_success",
    "duplicate_drafts",
    "automatic_high_risk_actions",
    "low_confidence_unconfirmed_drafts",
)


def _git(*args: str) -> tuple[int, str]:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
    )
    return result.returncode, result.stdout.strip()


def validate_repository() -> list[str]:
    issues: list[str] = []
    code, branch = _git("branch", "--show-current")
    if code != 0 or branch != "main":
        issues.append(f"Git 当前分支必须是 main，实际为 {branch or '不可用'}")
    code, status = _git("status", "--porcelain")
    if code != 0:
        issues.append("无法读取 Git 工作区状态")
    elif status:
        issues.append("Git 工作区存在未提交改动")
    code, remote = _git("remote", "get-url", "origin")
    if code != 0 or not remote.rstrip("/").endswith("SIX2090/wms.git"):
        issues.append("origin 必须指向 https://github.com/SIX2090/wms.git")
    return issues


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def validate_evidence(package: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if package.get("environment") != "production":
        issues.append("证据包 environment 必须为 production")
    if package.get("synthetic_sample_count", 0):
        issues.append("证据包不能把合成样本计入真实生产验收")

    real_samples = package.get("real_samples")
    if not isinstance(real_samples, list) or len(real_samples) < 20:
        issues.append("真实脱敏样本至少需要 20 份")
    else:
        ids = [item.get("sample_id") for item in real_samples if isinstance(item, dict)]
        if len(ids) != len(set(ids)) or any(not value for value in ids):
            issues.append("真实样本 sample_id 必须非空且唯一")
        if any(item.get("desensitized") is not True for item in real_samples if isinstance(item, dict)):
            issues.append("所有真实样本必须明确标记 desensitized=true")
        sources = {item.get("source") for item in real_samples if isinstance(item, dict)}
        missing_sources = REQUIRED_REAL_SOURCES - sources
        if missing_sources:
            issues.append(f"真实样本缺少来源类别: {', '.join(sorted(missing_sources))}")

    snapshots = package.get("daily_snapshots")
    if not isinstance(snapshots, list) or len(snapshots) != 7:
        issues.append("必须提供连续 7 天 daily_snapshots")
    else:
        dates = [_parse_date(item.get("snapshot_date")) for item in snapshots if isinstance(item, dict)]
        if len(dates) != 7 or any(value is None for value in dates):
            issues.append("daily_snapshots 的日期必须全部有效")
        elif dates != sorted(dates) or any(dates[index] != dates[0] + timedelta(days=index) for index in range(7)):
            issues.append("daily_snapshots 日期必须连续且按时间升序")
        for item in snapshots:
            counts = item.get("absolute_counts", {}) if isinstance(item, dict) else {}
            if any(counts.get(metric, 0) != 0 for metric in ABSOLUTE_METRICS):
                issues.append("四项上线违规指标必须每天全部为 0")
            roles = set(item.get("rollout_roles", [])) if isinstance(item, dict) else set()
            if not REQUIRED_ROLES.issubset(roles):
                issues.append("每日灰度证据必须覆盖 admin、warehouse、purchase")
                break

    decision = package.get("go_no_go", {})
    if not isinstance(decision, dict) or decision.get("decision") != "go":
        issues.append("必须有管理员签字的 go 决策")
    elif not decision.get("signed_by") or not decision.get("decided_at"):
        issues.append("go 决策必须包含 signed_by 和 decided_at")
    return sorted(set(issues))


def validate_environment() -> list[str]:
    issues: list[str] = []
    if os.environ.get("FLASK_ENV", "production") == "production" and not os.environ.get("SECRET_KEY"):
        issues.append("生产环境必须显式设置 SECRET_KEY")
    if os.environ.get("WMS_LLM_ENABLED", "true").lower() in {"1", "true", "yes", "on"} and not os.environ.get("WMS_LLM_API_KEY"):
        issues.append("启用 LLM 时必须设置 WMS_LLM_API_KEY")
    return issues


def run_self_test() -> int:
    sample = [{"sample_id": f"REAL-{index:03d}", "source": source, "desensitized": True} for index, source in enumerate(("delivery_note_photo", "wechat_text", "wechat_screenshot") * 7, 1)][:20]
    start = date(2026, 7, 1)
    package = {
        "environment": "production",
        "synthetic_sample_count": 0,
        "real_samples": sample,
        "daily_snapshots": [{"snapshot_date": (start + timedelta(days=i)).isoformat(), "absolute_counts": {metric: 0 for metric in ABSOLUTE_METRICS}, "rollout_roles": sorted(REQUIRED_ROLES)} for i in range(7)],
        "go_no_go": {"decision": "go", "signed_by": "admin", "decided_at": "2026-07-08T10:00:00"},
    }
    assert not validate_evidence(package)
    package["real_samples"][0]["desensitized"] = False
    assert validate_evidence(package)
    print("PASS AI-R18-F01 production readiness self-test")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the conservative WMS production readiness gate.")
    parser.add_argument("--evidence", type=Path, help="Production evidence JSON package")
    parser.add_argument("--self-test", action="store_true", help="Run deterministic gate tests")
    args = parser.parse_args()
    if args.self_test:
        return run_self_test()
    issues = validate_repository() + validate_environment()
    if not args.evidence:
        issues.append("未提供生产 evidence JSON，默认 NO-GO")
    else:
        try:
            package = json.loads(args.evidence.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            issues.append(f"无法读取 evidence JSON: {exc}")
        else:
            issues.extend(validate_evidence(package))
    if issues:
        print("NO-GO AI-R18-F01 production readiness gate")
        for issue in sorted(set(issues)):
            print(f"- {issue}")
        return 1
    print("GO AI-R18-F01 production readiness gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8", errors="ignore")


def line_no(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def scan_commit_success(source: str) -> list[str]:
    findings: list[str] = []
    lines = source.splitlines()
    for index, line in enumerate(lines):
        if "db.session.rollback()" not in line:
            continue
        window = "\n".join(lines[index + 1 : index + 9])
        if "skipped.append" in window:
            continue
        first_return = re.search(r"return\s+(.+)", window)
        if first_return and re.search(r"['\"]status['\"]\s*:\s*['\"]success", first_return.group(1)):
            findings.append(f"app/app.py:{index + 1}: rollback 后首个 return 仍是 success")
    return findings


def scan_csrf_exempt(source: str) -> list[str]:
    findings: list[str] = []
    allowed_markers = ("@api_required", "_wechat_helper_authorized", "native_api_login")
    for match in re.finditer(r"@csrf\.exempt(?P<block>.*?)(?=^@app\.route|\Z)", source, re.S | re.M):
        block = match.group("block")
        if not any(marker in block for marker in allowed_markers):
            findings.append(f"app/app.py:{line_no(source, match.start())}: csrf.exempt 需要人工确认授权方式")
    return findings


def scan_password_hash(source: str) -> list[str]:
    findings: list[str] = []
    for match in re.finditer(r"generate_password_hash\((?P<arg>[^)]*)\)", source):
        window = source[max(0, match.start() - 800) : match.start()]
        arg = match.group("arg").strip()
        if arg in {"admin_password", "bootstrap_password"}:
            continue
        if "ensure_bootstrap_admin_user" in window:
            continue
        if arg in {"password", "new_password"} and "validate_password_strength" not in window:
            findings.append(f"app/app.py:{line_no(source, match.start())}: 密码写入附近未看到强度校验")
    return findings


def scan_raw_safe_templates() -> list[str]:
    findings: list[str] = []
    for path in (ROOT / "app" / "templates").rglob("*.html"):
        if "_disabled_unused" in path.parts:
            continue
        if path.name == "base.html":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r"\|\s*safe", text):
            window = text[max(0, match.start() - 120) : match.start() + 80]
            if "sanitize" not in window and "safe_html" not in window and "template" not in window:
                findings.append(f"{path.relative_to(ROOT)}:{line_no(text, match.start())}: 使用 |safe，需确认来源已净化")
    return findings


def scan_fetch_without_method_csrf() -> list[str]:
    findings: list[str] = []
    for path in (ROOT / "app" / "templates").rglob("*.html"):
        if "_disabled_unused" in path.parts:
            continue
        if path.name == "base.html":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "{% extends \"base.html\" %}" in text or "{% extends 'base.html' %}" in text:
            continue
        for match in re.finditer(r"fetch\([^)]*method\s*:\s*['\"]POST['\"]", text, re.S):
            window = text[max(0, match.start() - 300) : match.end() + 300]
            if "csrf" not in window.lower() and "X-CSRFToken" not in window:
                findings.append(f"{path.relative_to(ROOT)}:{line_no(text, match.start())}: 独立页面 POST fetch 未显式携带 CSRF")
    return findings


def main() -> int:
    app_py = read_text("app/app.py")
    findings: list[tuple[str, list[str]]] = [
        ("commit_success_candidate", scan_commit_success(app_py)),
        ("csrf_exempt_review", scan_csrf_exempt(app_py)),
        ("password_hash_review", scan_password_hash(app_py)),
        ("template_safe_review", scan_raw_safe_templates()),
        ("post_fetch_review", scan_fetch_without_method_csrf()),
    ]

    total = 0
    for name, items in findings:
        if not items:
            print(f"OK {name}: 未发现新增候选")
            continue
        total += len(items)
        print(f"REVIEW {name}: {len(items)} 个候选")
        for item in items[:30]:
            print(f"  - {item}")
        if len(items) > 30:
            print(f"  - ... 还有 {len(items) - 30} 个，先抽样人工判真")

    if total:
        print("\n说明：本脚本只输出候选风险，不等于真实 BUG。修复前必须结合 WMS_BUG_BASELINE.md 判真。")
    else:
        print("\n未发现新增高风险候选。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

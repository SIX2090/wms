#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_ci_green.py
=================

WMS 「CI 全绿门禁」检查器（AGENTS.md §三 硬性规则，2026-09-18 新增）。

规则
----
开始任何任务前，必须确认以下三个工作流在 ``main`` 上**最近一次运行**全部为绿色：

    Android APK Build      .github/workflows/android-build.yml
    WMS AI Verification    .github/workflows/verify.yml
    WMS CI                 .github/workflows/ci.yml

任一非绿 → **不得开工**，必须先修绿红色工作流。

用法
----
    python3 scripts/check_ci_green.py            # 人读输出；全绿 rc=0，非绿 rc=1
    python3 scripts/check_ci_green.py --json     # 机器读输出（供定时任务/流水线消费）
    python3 scripts/check_ci_green.py --quiet    # 只在非绿时输出（适合 cron）

退出码
------
    0  全绿（放行）
    1  存在非绿工作流 / 查不到运行记录（阻断）
    2  检查本身失败（无 token、网络异常）——**也算阻断**，未确认即不放行

Token
-----
按以下顺序取，任一可用即可：

    1. ``$GH_TOKEN`` / ``$GITHUB_TOKEN`` 环境变量
    2. ``/root/.wms_gh_token`` 文件
    3. 无 token 时退化为**匿名请求**（公开仓库可用，但有 60 次/小时限流）

设计要点
--------
* **零依赖**：仅用 Python 3 标准库，与本仓库其他 ``scripts/`` 一致，
  不引入 requests 之类新依赖（受限网络环境下装包是额外风险）。
* **不缓存**：每次现查 GitHub API。缓存会让"昨天绿、今天红"被掩盖，
  而本规则的**全部意义**就是"检查当下状态"。
* **宁可阻断**：网络异常/token 失效一律 rc≠0。本门禁的失效模式必须是
  "误报阻断"而不是"漏报放行"——后者会让人在红色基线上开工。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = "SIX2090/wms"
BRANCH = "main"
API = "https://api.github.com"

# 门禁覆盖的三个工作流（与 AGENTS.md §三 表格逐字对应）。
# 顺序即报告顺序，按"最能反映真实编译"到"最泛的校验"排列。
REQUIRED_WORKFLOWS = [
    ("Android APK Build", ".github/workflows/android-build.yml"),
    ("WMS AI Verification", ".github/workflows/verify.yml"),
    ("WMS CI", ".github/workflows/ci.yml"),
]

GREEN = {"success"}
# 视为"尚未跑完"的状态：不能放行，但也不是失败——要让调用方知道是"还没结果"。
PENDING = {"queued", "in_progress", "requested", "waiting", "pending"}
FAILED = {"failure", "timed_out", "cancelled", "action_required", "startup_failure", "stale"}


def log(msg: str) -> None:
    print(msg, flush=True)


def resolve_token() -> str | None:
    for var in ("GH_TOKEN", "GITHUB_TOKEN"):
        tok = (os.environ.get(var) or "").strip()
        if tok:
            return tok
    for path in ("/root/.wms_gh_token", os.path.expanduser("~/.wms_gh_token")):
        try:
            with open(path, encoding="utf-8") as fh:
                tok = fh.read().strip()
            if tok:
                return tok
        except OSError:
            continue
    return None


def gh_get(path: str, token: str | None) -> dict:
    req = urllib.request.Request(API + path)
    req.add_header("Accept", "application/vnd.github+json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    # 匿名请求也要带 User-Agent，否则 GitHub 直接 403
    req.add_header("User-Agent", "wms-ci-green-check")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def latest_run(workflow_file: str, token: str | None) -> dict | None:
    """取某工作流在 main 上的最近一次运行；查不到返回 None。

    ⚠️ **踩过的坑（2026-09-18 实测）**：GitHub 的 workflow-runs 端点
    ``/actions/workflows/{id}/runs`` 里的 ``{id}`` 只接受
    **workflow 文件名**（如 ``ci.yml``）或**数字 workflow ID**，
    **不接受**相对路径（``.github/workflows/ci.yml``）——传路径会一律 404。
    而 ``/actions/workflows`` 列表接口返回的恰恰是 ``path`` 字段（带目录），
    很容易照着抄进 URL 然后 404。这里统一剥掉目录，只用文件名。
    """
    # 只取文件名，避免把 .github/workflows/ 前缀拼进 URL 造成 404。
    # urlencode 兜底：文件名里若有空格等字符也能正确编码。
    wf = urllib.parse.quote(os.path.basename(workflow_file))
    # 注意：必须带 branch 过滤。不带会把其他分支（如 PR 的临时分支）的运行算进来，
    # 得出"绿"的错误结论——本门禁只关心 main 的基线状态。
    path = (
        f"/repos/{REPO}/actions/workflows/{wf}/runs"
        f"?branch={BRANCH}&per_page=1"
    )
    data = gh_get(path, token)
    runs = data.get("workflow_runs") or []
    return runs[0] if runs else None


def classify(run: dict | None) -> tuple[str, str]:
    """把一次运行归类为 green / pending / failed / missing。"""
    if run is None:
        return "missing", "无运行记录"
    if run.get("status") != "completed":
        return "pending", run.get("status") or "unknown"
    conclusion = (run.get("conclusion") or "unknown").lower()
    if conclusion in GREEN:
        return "green", conclusion
    if conclusion in FAILED:
        return "failed", conclusion
    return "pending", conclusion


def main() -> int:
    ap = argparse.ArgumentParser(description="WMS CI 全绿门禁检查")
    ap.add_argument("--json", action="store_true", help="输出 JSON（供定时任务消费）")
    ap.add_argument("--quiet", action="store_true", help="仅在非绿时输出")
    args = ap.parse_args()

    token = resolve_token()
    results = []
    api_error = None

    for name, wf in REQUIRED_WORKFLOWS:
        try:
            run = latest_run(wf, token)
            state, detail = classify(run)
        except urllib.error.HTTPError as exc:
            # 404 = 工作流文件不存在或被重命名（门禁配置失效，必须让人知道）
            state, detail, run = "failed", f"HTTP {exc.code}", None
            api_error = f"{name}: HTTP {exc.code} {exc.reason}"
        except Exception as exc:  # noqa: BLE001 —— 网络类异常一律阻断
            state, detail, run = "failed", f"{type(exc).__name__}: {exc}", None
            api_error = f"{name}: {type(exc).__name__}: {exc}"

        results.append({
            "workflow": name,
            "file": wf,
            "state": state,
            "detail": detail,
            "conclusion": (run or {}).get("conclusion"),
            "status": (run or {}).get("status"),
            "run_number": (run or {}).get("run_number"),
            "head_sha": ((run or {}).get("head_sha") or "")[:12],
            "created_at": (run or {}).get("created_at"),
            "html_url": (run or {}).get("html_url"),
        })

    blocked = [r for r in results if r["state"] != "green"]
    ok = not blocked

    if args.json:
        log(json.dumps({
            "ok": ok,
            "repo": REPO,
            "branch": BRANCH,
            "token_used": bool(token),
            "api_error": api_error,
            "results": results,
        }, ensure_ascii=False, indent=2))
        return 0 if ok else 1

    if ok and args.quiet:
        return 0

    icon = {"green": "✅", "failed": "❌", "pending": "⏳", "missing": "❓"}
    log("")
    log("=" * 66)
    log("  WMS CI 全绿门禁检查（AGENTS.md §三）")
    log(f"  仓库 {REPO}  分支 {BRANCH}  token={'已提供' if token else '匿名(有限流)'}")
    log("=" * 66)
    for r in results:
        line = f"  {icon.get(r['state'], '?')} {r['workflow']:<22} {r['state']:<8} {r['detail']}"
        if r["run_number"]:
            line += f"  #{r['run_number']} @{r['head_sha']} ({r['created_at']})"
        log(line)
        if r["state"] != "green" and r["html_url"]:
            log(f"     → {r['html_url']}")
    log("=" * 66)

    if ok:
        log("  ✅ 三个工作流全绿，允许开工。")
        log("")
        return 0

    log("  🚫 门禁阻断：以下工作流非绿，**禁止开始新任务**，请先修绿：")
    for r in blocked:
        log(f"     - {r['workflow']}（{r['state']}: {r['detail']}）")
        if r["html_url"]:
            log(f"       {r['html_url']}")
    if api_error:
        log(f"  ⚠️  检查过程出现 API 异常：{api_error}")
        log("     无法确认即不放行（本门禁宁可误报阻断，不可漏报放行）。")
    log("")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)

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

最新失败/运行中/未核实均阻断写入和发布；只读检查与准备可继续。
WMS CI/AI 必须对应目标SHA；旧Android绿色仅在祖先及输入路径无改证明后复用。

用法
----
    python3 scripts/check_ci_green.py            # 人读输出；全绿 rc=0，非绿 rc=1
    python3 scripts/check_ci_green.py --json     # 机器读输出（供定时任务/流水线消费）
    python3 scripts/check_ci_green.py --target-sha <40位远端基线SHA>
    python3 scripts/check_ci_green.py --quiet    # 只在非绿时输出（适合 cron）

退出码
------
    0  全绿（放行）
    1  存在非绿工作流 / 查不到运行记录（阻断）
    2  参数非法或用户中断——也算阻断；查询失败以 rc=1 和未核实状态报告

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
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = "SIX2090/wms"
BRANCH = "main"
API = "https://api.github.com"
ROOT = Path(__file__).resolve().parents[1]
ANDROID_PATHS = ("app/android-native-wms", ".github/workflows/android-build.yml")

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


# BUG-2026-10-17-006：中文 Windows 控制台（cp936/GBK）无法编码 ✅/❌/🚫 等 emoji，
# `print` 直接抛 UnicodeEncodeError，使 AGENTS.md §三 推荐的门禁命令在默认 Windows
# 控制台**完全不可用**（复现：`python scripts/check_ci_green.py` →
# `UnicodeEncodeError: 'gbk' codec can't encode character '\u2705'`）。
# 修法：按输出流编码能力自动降级为 ASCII 标记；同时把 stdout 的 errors 设为
# replace 兜底，任何意外字符（如 API 返回的 emoji 文案）都不会让门禁崩掉。
UNICODE_ICONS = {"green": "✅", "failed": "❌", "pending": "⏳", "missing": "❓"}
ASCII_ICONS = {"green": "[OK]", "failed": "[FAIL]", "pending": "[WAIT]", "missing": "[NONE]"}
UNICODE_MARKS = {"ok": "✅", "blocked": "🚫", "warn": "⚠️"}
ASCII_MARKS = {"ok": "[OK]", "blocked": "[BLOCKED]", "warn": "[WARN]"}


def log(msg: str) -> None:
    print(msg, flush=True)


def stdout_encoding() -> str:
    """当前 stdout 的编码名；拿不到时按 utf-8 处理。"""
    return getattr(sys.stdout, "encoding", None) or "utf-8"


def can_encode(text: str, encoding: str | None = None) -> bool:
    """输出流编码能否表示 text。不确定（LookupError）时返回 False，走 ASCII 降级。"""
    try:
        text.encode(encoding or stdout_encoding())
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def icons() -> dict[str, str]:
    """状态图标：编码支持 emoji 用 emoji，否则退化为 ASCII 标记。"""
    if all(can_encode(v) for v in UNICODE_ICONS.values()):
        return UNICODE_ICONS
    return ASCII_ICONS


def marks() -> dict[str, str]:
    """结论标记（放行/阻断/告警）同上，随输出流编码能力降级。"""
    if all(can_encode(v) for v in UNICODE_MARKS.values()):
        return UNICODE_MARKS
    return ASCII_MARKS


def configure_stdout() -> None:
    """把 stdout 的错误策略降级为 replace：极端字符也不崩（cp936 下 emoji 变 '?'）。

    必须在任何输出之前调用；不可重配置的流（如测试替身）静默跳过。
    """
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if not callable(reconfigure):
        return
    try:
        reconfigure(errors="replace")
    except (ValueError, OSError):
        pass


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


def full_sha(value: str) -> str:
    """Accept only complete commit IDs, never refs, abbreviated IDs or options."""
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", value):
        raise ValueError("目标必须是完整的40位Git SHA")
    if value == "0" * 40:
        raise ValueError("目标不能是全零SHA（远端main基线不存在）")
    return value.lower()


def resolve_target_sha(token: str | None) -> str:
    """Read the current remote main on every default invocation; no local cache."""
    branch = gh_get(f"/repos/{REPO}/branches/{BRANCH}", token)
    return full_sha((branch.get("commit") or {}).get("sha"))


def android_reuse_check(source_sha: str, target_sha: str) -> tuple[bool, str]:
    """Prove ancestry and unchanged Android inputs using complete local objects.

    This is read-only: missing/shallow history is not fetched or assumed equal.
    Disable replace refs so local commit replacement cannot forge the proof.
    """
    try:
        source_sha, target_sha = full_sha(source_sha), full_sha(target_sha)
        def git(*args):
            return subprocess.run(["git", "--no-replace-objects", *args], cwd=ROOT,
                                  capture_output=True, text=True, timeout=15,
                                  env={**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_OPTIONAL_LOCKS": "0"})
        for sha in (source_sha, target_sha):
            if git("cat-file", "-e", sha + "^{commit}").returncode != 0:
                return False, "未核实：Android复用证明缺少本地提交对象，请先取得完整历史"
        if git("merge-base", "--is-ancestor", source_sha, target_sha).returncode != 0:
            return False, "未核实：Android运行提交不是目标提交的已证实祖先"
        changed = git("diff", "--no-ext-diff", "--no-textconv", "--quiet", source_sha, target_sha, "--", *ANDROID_PATHS)
        if changed.returncode == 1:
            return False, "未核实：目标的Android源码或构建工作流已变化，需该目标的新构建"
        if changed.returncode != 0:
            return False, "未核实：无法比较Android源码及构建工作流"
        return True, "success；旧Android运行是目标祖先，Android源码及构建工作流未变"
    except Exception as exc:
        return False, f"未核实：Android复用证明不可用（{type(exc).__name__}）"


def verify_target(run: dict | None, workflow: str, target_sha: str | None) -> tuple[str, str]:
    """Never replace a newer failed/pending run with an older green record."""
    state, detail = classify(run)
    if state != "green":
        return state, detail
    if target_sha is None:
        return "missing", "未核实：无法取得当前远端main目标SHA"
    try:
        run_sha = full_sha(run.get("head_sha"))
    except ValueError:
        return "missing", "未核实：工作流运行缺少完整head_sha"
    if run.get("head_branch") != BRANCH:
        return "missing", "未核实：工作流运行不是已证实的main记录"
    if run_sha == target_sha:
        return "green", detail
    if workflow == ".github/workflows/android-build.yml":
        ok, proof = android_reuse_check(run_sha, target_sha)
        return ("green" if ok else "missing"), proof
    return "missing", f"未核实：最新运行SHA {run_sha[:12]} 与目标 {target_sha[:12]} 不一致"


def classify(run: dict | None) -> tuple[str, str]:
    """把一次运行归类为 green / pending / failed / missing。"""
    if run is None:
        return "missing", "无运行记录"
    if run.get("status") != "completed":
        status = run.get("status")
        if status in PENDING:
            return "pending", status
        return "missing", "未核实：未知运行状态"
    conclusion = (run.get("conclusion") or "unknown").lower()
    if conclusion in GREEN:
        return "green", conclusion
    if conclusion in FAILED:
        return "failed", conclusion
    return "missing", f"未核实：结论为{conclusion}"


def main() -> int:
    ap = argparse.ArgumentParser(description="WMS CI 全绿门禁检查")
    ap.add_argument("--json", action="store_true", help="输出 JSON（供定时任务消费）")
    ap.add_argument("--quiet", action="store_true", help="仅在非绿时输出")
    ap.add_argument("--target-sha", metavar="SHA", help="校验完整40位目标SHA；pre-push传远端待更新基线，不是本地待推HEAD")
    args = ap.parse_args()
    if args.target_sha:
        try:
            args.target_sha = full_sha(args.target_sha)
        except ValueError as exc:
            ap.error(str(exc))

    # BUG-2026-10-17-006：先固定输出流的容错策略，再做任何编码能力探测与输出。
    configure_stdout()
    icon = icons()
    mark = marks()

    token = resolve_token()
    results = []
    api_error = None
    target_sha = args.target_sha
    target_source = "explicit" if target_sha else "remote_main_api"
    if not target_sha:
        try:
            target_sha = resolve_target_sha(token)
        except Exception as exc:
            # Query failure is unknown, never evidence that CI itself failed.
            api_error = f"目标未核实: {type(exc).__name__}: {exc}"

    for name, wf in REQUIRED_WORKFLOWS:
        try:
            run = latest_run(wf, token)
            state, detail = verify_target(run, wf, target_sha)
        except urllib.error.HTTPError as exc:
            # API错误表示本次未核实；不能把403限流/404配置错误当CI实际失败
            state, detail, run = "missing", f"未核实：HTTP {exc.code}", None
            api_error = f"{name}: HTTP {exc.code} {exc.reason}"
        except Exception as exc:  # noqa: BLE001 —— 网络类异常一律阻断
            state, detail, run = "missing", f"未核实：{type(exc).__name__}: {exc}", None
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
            "head_sha_full": (run or {}).get("head_sha"),
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
            "target_sha": target_sha,
            "target_source": target_source,
            "token_used": bool(token),
            "api_error": api_error,
            "results": results,
        }, ensure_ascii=False, indent=2))
        return 0 if ok else 1

    if ok and args.quiet:
        return 0

    log("")
    log("=" * 66)
    log("  WMS CI 全绿门禁检查（AGENTS.md §三）")
    log(f"  仓库 {REPO}  分支 {BRANCH}  token={'已提供' if token else '匿名(有限流)'}")
    log(f"  校验目标 {target_sha or '未核实'}  来源={target_source}")
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
        log(f"  {mark['ok']} 目标SHA的三个工作流验证通过，允许开工和写入/发布。")
        log("")
        return 0

    log(f"  {mark['blocked']} 门禁阻断：目标尚未确认全绿，禁止代码写入、提交、推送或发布；允许只读检查与准备：")
    for r in blocked:
        log(f"     - {r['workflow']}（{r['state']}: {r['detail']}）")
        if r["html_url"]:
            log(f"       {r['html_url']}")
    if any(r["state"] == "failed" for r in blocked):
        log("     最新工作流实际失败，请先修绿；不得用历史绿色结果替代。")
    if any(r["state"] == "pending" for r in blocked):
        log("     工作流尚未完成，请等待结果；运行中不代表失败。")
    if api_error:
        log(f"  {mark['warn']}  检查过程出现 API 异常：{api_error}")
        log("     查询失败只表示未核实，不表示工作流已失败。")
        log("     可用已连接GitHub工具/Actions核对同一目标SHA的最新运行链接、SHA、状态；")
        log("     Android旧SHA还须祖先及路径无改证明。全部核实并记录替代证据后，")
        log("     仅本次查询故障的push可临时WMS_SKIP_CI_GATE=1；未核实不得跳过。")
    log("")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)

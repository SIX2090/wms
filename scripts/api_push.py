#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API 通道推送（AGENTS.md §8.1）：把本地 commits 逐个重放到远端 main。

每个本地提交 ⇒ 一次 Git Data API 四步重放（blob→tree→commit→ref），
保持「1 原子动作 = 1 commit」的粒度。

CI-ENV-2026-09-11 加固：
  1. 推送前校验：待推 sha 必须是本地 HEAD 祖先且存在，防止推陈旧/孤儿提交；
  2. 推送后校验：自动跑 verify_remote_sync.py 做全量 tree 对比，
     任何漏推立即暴露（事故背景见该脚本 docstring）。

用法：
    GH_TOKEN=xxx python3 scripts/api_push.py <local_sha> [<local_sha> ...]
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = os.environ["GH_TOKEN"]
REPO = os.environ.get("WMS_REPO", "SIX2090/wms")
API = "https://api.github.com"


# CI-ENV-2026-09-12：沙箱/CI 到 api.github.com 的 TLS 握手会被中间设备掐断，
# 且只掐 Python 侧——同机同 token，curl 走 --resolve 指定 IP 稳定 200，
# urllib/requests 则 SSLZeroReturnError 全军覆没（含改 /etc/hosts 指向同一 IP，
# 说明卡的不是 DNS 而是握手特征）。故请求层优先用 curl + 多 IP 轮换；
# 环境没有 curl 时才退回 urllib（带退避重试）。
CURL_IPS = ["140.82.112.6", "20.205.243.168", "140.82.112.5", "140.82.113.5"]


def _req_curl(method, path, data):
    base = [
        "curl", "-s", "--max-time", "90",
        "-H", "Authorization: Bearer " + TOKEN,
        "-H", "Accept: application/vnd.github+json",
        "-X", method,
    ]
    if data is not None:
        base += ["-H", "Content-Type: application/json", "--data-binary", "@-"]
    for ip in CURL_IPS:
        proc = subprocess.run(
            base + ["--resolve", f"api.github.com:443:{ip}",
                    "-w", "\n%{http_code}", API + path],
            input=data or b"", capture_output=True)
        raw = proc.stdout.decode("utf-8", "replace")
        if "\n" not in raw:
            print(f"   ⚠ curl 经 {ip} 连接失败（code {proc.returncode}），换下一个 IP")
            continue
        body, _, code = raw.rpartition("\n")
        code = code.strip()
        if code == "0":
            print(f"   ⚠ curl 经 {ip} 连接失败（http 0），换下一个 IP")
            continue
        if not code.startswith("2"):
            raise SystemExit(f"✗ GitHub API {method} {path} -> HTTP {code}\n{body[:800]}")
        return json.loads(body) if body.strip() else {}
    return None  # 全部 IP 都不通


def req(method, path, payload=None, _retries=4):
    """GitHub API 请求：curl（多 IP 轮换）优先，无 curl 时退避重试的 urllib。"""
    data = json.dumps(payload).encode() if payload is not None else None
    if shutil.which("curl"):
        got = _req_curl(method, path, data)
        if got is not None:
            return got
        raise SystemExit(f"✗ GitHub API 请求失败：{method} {path} —— "
                         f"已试遍候选 IP {CURL_IPS}，均被连接层掐断")

    r = urllib.request.Request(API + path, data=data, method=method)
    r.add_header("Authorization", "Bearer " + TOKEN)
    r.add_header("Accept", "application/vnd.github+json")
    if data:
        r.add_header("Content-Type", "application/json")
    last_err = None
    for attempt in range(1, _retries + 1):
        try:
            with urllib.request.urlopen(r, timeout=90) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, ssl.SSLError, ConnectionError, TimeoutError) as e:
            last_err = e
            if attempt == _retries:
                break
            wait = 2 * attempt
            print(f"   ⚠ 连接异常（第 {attempt}/{_retries} 次）：{e}；{wait}s 后重试")
            time.sleep(wait)
    raise SystemExit(f"✗ GitHub API 请求失败（已重试 {_retries} 次）：{method} {path} -> {last_err}")


def git(*args):
    return subprocess.run(["git", "-C", REPO_ROOT, *args],
                          capture_output=True, text=True, check=True).stdout


def precheck(local_shas):
    """待推 sha 必须都存在于本地且是本地 HEAD 的祖先（含 HEAD 自身）。"""
    head = git("rev-parse", "HEAD").strip()
    for sha in local_shas:
        try:
            is_ancestor = subprocess.run(
                ["git", "-C", REPO_ROOT, "merge-base", "--is-ancestor", sha, head],
                capture_output=True).returncode == 0
        except subprocess.CalledProcessError:
            is_ancestor = False
        if not is_ancestor:
            raise SystemExit(
                f"✗ 前置校验失败：{sha} 不是本地 HEAD ({head[:10]}) 的祖先——"
                f"可能是笔误或工作区有未提交改动，拒绝推送")
    print(f"前置校验 OK：{len(local_shas)} 个提交均为本地 HEAD 祖先")


def main():
    local_shas = sys.argv[1:]
    if not local_shas:
        raise SystemExit("用法: api_push.py <local_sha> [...]")

    precheck(local_shas)

    remote_head = req("GET", f"/repos/{REPO}/commits/main")["sha"]
    print(f"远端 HEAD: {remote_head}")

    parent = remote_head
    for sha in local_shas:
        msg = git("log", "-1", "--format=%B", sha).rstrip("\n")
        files = git("diff", "--name-only", f"{sha}^", sha).split("\n")
        files = [f for f in files if f]
        print(f"\n▶ 重放 {sha[:7]}（{len(files)} 文件）")

        entries = []
        for path in files:
            content = subprocess.run(
                ["git", "-C", REPO_ROOT, "show", f"{sha}:{path}"],
                capture_output=True, check=True).stdout
            blob = req("POST", f"/repos/{REPO}/git/blobs", {
                "content": base64.b64encode(content).decode(),
                "encoding": "base64",
            })
            # CI-ENV-2026-09-12-B：mode 必须取自本地 git 的真实文件模式。
            # 此前硬编码 100644，导致被推送的 100755 文件（.githooks/pre-commit、
            # app/android-native-wms/gradlew 等）在远端丢失可执行位——
            # core.hooksPath .githooks 的钩子在 Linux/Mac 上会静默不执行，
            # gradlew 也跑不起来。内容与 blob sha 都没错，
            # 错的只是这一个 mode 字段，所以 blob 级同步校验发现不了。
            mode = git("ls-tree", sha, "--", path).split()[0]
            entries.append({"path": path, "mode": mode,
                            "type": "blob", "sha": blob["sha"]})
            print(f"   ① blob {path}  [{mode}]")

        base_tree = req("GET", f"/repos/{REPO}/git/commits/{parent}")["tree"]["sha"]
        tree = req("POST", f"/repos/{REPO}/git/trees",
                   {"base_tree": base_tree, "tree": entries})
        print(f"   ② tree   {tree['sha'][:10]}")

        commit = req("POST", f"/repos/{REPO}/git/commits",
                     {"message": msg, "tree": tree["sha"], "parents": [parent]})
        print(f"   ③ commit {commit['sha'][:10]}")

        ref = req("PATCH", f"/repos/{REPO}/git/refs/heads/main",
                  {"sha": commit["sha"], "force": False})
        print(f"   ④ main -> {ref['object']['sha'][:10]}")
        parent = commit["sha"]

    print(f"\n✓ 推送完成，远端 HEAD = {parent}")

    # 推送后防呆：全量 tree 对比，漏推零容忍
    print("\n[推送后校验] verify_remote_sync ...")
    rc = subprocess.run(
        [sys.executable,
         os.path.join(REPO_ROOT, "scripts", "verify_remote_sync.py")]).returncode
    if rc != 0:
        raise SystemExit("✗ 推送后同步校验失败，请立即处理（不要假设推完了）")


if __name__ == "__main__":
    main()

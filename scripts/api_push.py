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


def req(method, path, payload=None, _retries=4):
    """带重试的 GitHub API 请求。

    CI-ENV-2026-09-12：沙箱/CI 到 api.github.com 的 TLS 握手会偶发被中间设备
    RST（表现为 SSLZeroReturnError / URLError，curl 同环境重试即可成功），
    单次失败就把整批推送打断太亏，故对「连接层异常」做有限次退避重试；
    HTTP 层错误（4xx/5xx 的 HTTPError）不重试——那是真失败，重来也没用。
    """
    data = json.dumps(payload).encode() if payload is not None else None
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
            entries.append({"path": path, "mode": "100644",
                            "type": "blob", "sha": blob["sha"]})
            print(f"   ① blob {path}")

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

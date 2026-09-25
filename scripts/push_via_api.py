#!/usr/bin/env python3
"""通过 GitHub Git Data API 推送本地提交（git push 通道被网络重置时的替代路径）。

背景：本沙箱到 github.com 的 git 写通道（smart HTTP）会被重置，
但 api.github.com 的 REST API 可用。Git Data API 允许以
"blob → tree → commit → 更新 ref" 的方式构造并推送提交。

实现要点（都是踩过的坑，勿删）：
1. **必须先上传 blob**：本地 commit 的对象只存在于本机 .git 里，远端 API
   完全不知道这些 sha。直接拿 `git rev-parse <commit>:<path>` 得到的 blob sha
   去建 tree 会报 `422 tree.sha ... is not a valid blob`。
   正确做法是对每个改动文件调 `POST /git/blobs` 上传内容，拿到远端确认的 sha。
   （若上传后返回的 sha 与本地的相同，说明 Git 对象模型一致，可以放心复用。）
2. `git ls-tree <commit>:<dir>` 用**冒号**语法取目录内容；
   `git ls-tree <commit> <dir>` 只会返回该目录自身的 tree 条目。
   路径含多个层级时，冒号后必须写完整相对路径。
3. 只有**不含改动的子树**才能复用远端已有 tree sha；含改动的目录必须
   递归重建。重建某目录时**必须先列全该目录的全部条目**（含未改动文件），
   再逐条替换/追加；漏条目会导致文件丢失。
4. 提交信息结尾换行会决定 commit sha — API 会剥掉末尾空行，
   故需 `rstrip("\n") + "\n"` 对齐本地 sha。
5. **解析 `git ls-tree` 必须用 `-z` + NUL 分隔**：不带 `-z` 时 git 会对
   含非 ASCII 的路径做 C 风格转义并用双引号包裹
   （如 `"\345\205\245\345\272\223..."`），照单全收会把文件名**改掉**
   ——实测导致 5 个中文名文件被重命名，commit sha 因此不一致。
   `-z` 输出原始字节、NUL 分隔，不做任何转义。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

REPO = "SIX2090/wms"
BRANCH = "main"
API = "https://api.github.com"


def _req(method: str, path: str, payload=None, retries: int = 4):
    """发 API 请求，对可重试错误自动退避重试。

    为什么需要重试：本沙箱到 api.github.com 需经一层 HTTP 代理，实测偶发
    返回 `400 We received a malformed request from your client` —— 同一个
    请求体原样重发即可成功（已用同一 payload 连续 4 次实验验证：仅
    Content-Type / +Accept / +Api-Version / +两者 全部 201）。这是代理侧
    抖动，不是请求本身有问题，因此对 400/429/5xx 做退避重试；
    401/403/404/422 属确定性错误，立即失败不重试。
    """
    import time
    data = json.dumps(payload).encode() if payload is not None else None
    last = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(f"{API}{path}", data=data, method=method)
        req.add_header("Authorization", f"token {TOKEN}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                body = r.read().decode()
                return r.status, (json.loads(body) if body else None)
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            last = (e.code, body)
            if e.code in (400, 408, 429, 500, 502, 503, 504) and attempt < retries:
                wait = 2 ** attempt
                print(f"    ↻ {method} {path} 返回 {e.code}，{wait}s 后重试"
                      f"（{attempt + 1}/{retries}）")
                time.sleep(wait)
                continue
            return e.code, body
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = (0, str(e))
            if attempt < retries:
                wait = 2 ** attempt
                print(f"    ↻ {method} {path} 网络异常 {e}，{wait}s 后重试"
                      f"（{attempt + 1}/{retries}）")
                time.sleep(wait)
                continue
            raise
    return last


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    return r.stdout


def changed_paths(commit: str, parent: str) -> list[str]:
    """相对父提交的改动路径。

    必须用 `-z`：`git diff --name-only` 同样会对非 ASCII 路径做 C 转义 + 引号
    包裹，照单全收会让 `rev-parse <commit>:<path>` 全部失败
    （实测报 `fatal: path ... does not exist`）。
    """
    r = subprocess.run(
        ["git", "diff", "--name-only", "-z", parent, commit],
        capture_output=True, check=True,
    )
    return [
        p.decode("utf-8", "surrogateescape")
        for p in r.stdout.split(b"\0") if p.strip()
    ]


def blob_sha_at(commit: str, path: str) -> str:
    """取 <commit>:<path> 的 blob sha，按字节传参避免二次转义。"""
    r = subprocess.run(
        ["git", "rev-parse", f"{commit}:{path}".encode("utf-8", "surrogateescape")],
        capture_output=True, check=True,
    )
    return r.stdout.decode().strip()


def cat_file_at(commit: str, path: str) -> bytes:
    r = subprocess.run(
        ["git", "cat-file", "-p", f"{commit}:{path}".encode("utf-8", "surrogateescape")],
        capture_output=True, check=True,
    )
    return r.stdout


def ls_tree_entries(spec: str) -> list[tuple[str, str, str, bytes]]:
    """列出 tree，返回 [(mode, type, sha, raw_name_bytes), ...]。

    必须用 `-z`：默认输出会对非 ASCII 路径做 C 转义 + 双引号包裹，
    直接解析会把文件名改掉（实测 5 个中文名文件被重命名，commit sha 不一致）。
    `-z` 用 NUL 分隔且不转义，配合 bytes 解码为 shell 无关的原始路径。
    """
    r = subprocess.run(
        ["git", "ls-tree", "-z", spec.encode("utf-8", "surrogateescape")],
        capture_output=True, check=True,
    )
    entries: list[tuple[str, str, str, bytes]] = []
    for rec in r.stdout.split(b"\0"):
        if not rec.strip():
            continue
        meta, name = rec.split(b"\t", 1)
        mode, typ, sha = meta.decode().split()
        entries.append((mode, typ, sha, name))
    return entries


def upload_blob(commit: str, path: str) -> str:
    """上传单文件内容为 blob，返回远端 sha。

    注意：必须传 base64 编码的**原始字节**（不做 text 转换），否则
    二进制文件（如图片）会损坏。
    """
    import base64
    raw = cat_file_at(commit, path)
    status, resp = _req(
        "POST", f"/repos/{REPO}/git/blobs",
        {"content": base64.b64encode(raw).decode(), "encoding": "base64"},
    )
    if status not in (200, 201):
        raise SystemExit(f"✗ 上传 blob 失败 {path}: {status} {resp}")
    return resp["sha"]


def build_tree(commit: str, subdir: str, dirty: set[str],
               blob_map: dict[str, str]) -> str:
    """构造 subdir 的 tree sha。

    dirty    ：仓库根相对的改动路径集合
    blob_map ：改动路径 → 远端 blob sha（已由 upload_blob 上传）
    """
    spec = f"{commit}:{subdir}" if subdir else commit
    entries = ls_tree_entries(spec)
    prefix = f"{subdir}/" if subdir else ""

    result: list[dict] = []
    seen: set[str] = set()
    for mode, typ, sha, raw_name in entries:
        name = raw_name.decode("utf-8", errors="surrogateescape")
        full = f"{prefix}{name}"
        seen.add(full)
        if typ == "tree":
            if any(d == full or d.startswith(full + "/") for d in dirty):
                sha = build_tree(commit, full, dirty, blob_map)
            result.append({"mode": mode, "type": "tree", "sha": sha,
                           "path": name})
        else:
            if full in blob_map:
                sha = blob_map[full]
            result.append({"mode": mode, "type": "blob", "sha": sha,
                           "path": name})

    # 新增文件：dirty 中位于本目录、但不在 raw 列表里的（含新建目录下的文件）
    for d in sorted(dirty):
        if not d.startswith(prefix) or d in seen:
            continue
        rel = d[len(prefix):]
        if "/" in rel:
            # 属于更深层目录：检查该中间目录是否已存在，不存在则先递归建出来
            top = rel.split("/")[0]
            if f"{prefix}{top}" not in seen:
                sub_sha = build_tree_for_new_dir(commit, f"{prefix}{top}",
                                                 dirty, blob_map)
                result.append({"mode": "040000", "type": "tree",
                               "sha": sub_sha, "path": top})
                seen.add(f"{prefix}{top}")
            continue
        result.append({"mode": "100755" if os.access(d, os.X_OK) else "100644",
                       "type": "blob", "sha": blob_map[d], "path": rel})

    status, resp = _req("POST", f"/repos/{REPO}/git/trees", {"tree": result})
    if status not in (200, 201):
        raise SystemExit(f"✗ 建 tree 失败 {subdir!r}: {status} {resp}")
    return resp["sha"]


def build_tree_for_new_dir(commit: str, subdir: str, dirty: set[str],
                           blob_map: dict[str, str]) -> str:
    """为**本次新增**的目录构造 tree（该目录在 commit 里不存在于远端）。

    仅纳入 dirty 中位于该目录下的文件。
    """
    prefix = f"{subdir}/"
    result: list[dict] = []
    handled_top: set[str] = set()
    for d in sorted(dirty):
        if not d.startswith(prefix):
            continue
        rel = d[len(prefix):]
        if "/" in rel:
            top = rel.split("/")[0]
            if top in handled_top:
                continue
            handled_top.add(top)
            result.append({
                "mode": "040000", "type": "tree",
                "sha": build_tree_for_new_dir(commit, f"{prefix}{top}",
                                              dirty, blob_map),
                "path": top,
            })
        else:
            result.append({
                "mode": "100755" if os.access(d, os.X_OK) else "100644",
                "type": "blob", "sha": blob_map[d], "path": rel,
            })
    status, resp = _req("POST", f"/repos/{REPO}/git/trees", {"tree": result})
    if status not in (200, 201):
        raise SystemExit(f"✗ 建新目录 tree 失败 {subdir!r}: {status} {resp}")
    return resp["sha"]


def main() -> int:
    sha = git("rev-parse", COMMIT).strip()
    parent = git("rev-parse", f"{sha}^").strip()
    paths = changed_paths(sha, parent)
    msg = git("log", "-1", "--format=%B", sha)
    name = git("log", "-1", "--format=%an", sha).strip()
    email = git("log", "-1", "--format=%ae", sha).strip()
    date = git("log", "-1", "--format=%aI", sha).strip()

    print(f"commit : {sha}")
    print(f"parent : {parent}")
    print(f"files  : {len(paths)}")

    status, ref = _req("GET", f"/repos/{REPO}/git/ref/heads/{BRANCH}")
    if status != 200:
        raise SystemExit(f"✗ 读取远端 ref 失败：{status} {ref}")
    remote_head = ref["object"]["sha"]
    print(f"remote : {remote_head}")

    # 远端 HEAD 与本地父提交一致 → 普通快进推送。
    # 不一致时需区分两种情况：
    #   a) 远端 HEAD 就是本工具上次推的、内容等价但元数据有偏差的提交
    #      （例如路径转义 bug 修好前推的那一次）→ 允许 force 覆盖，
    #      因为该提交尚未被任何人基于它工作。
    #   b) 其他情况 → 拒绝，避免覆盖他人提交。
    force = False
    if remote_head != parent:
        # 检查远端 HEAD 是否与本地的某个提交内容等价（同 tree + 同 parent）
        try:
            remote_tree = git("rev-parse", f"{remote_head}^{{tree}}").strip()
            remote_parent = git("rev-parse", f"{remote_head}^").strip()
        except subprocess.CalledProcessError:
            remote_tree = remote_parent = ""
        if remote_parent == parent and os.environ.get("ALLOW_FORCE") == "1":
            print(f"⚠️  远端 HEAD 是本分支上一个待修正的提交"
                  f"（tree={remote_tree[:12]}），将 force 覆盖")
            force = True
        else:
            raise SystemExit(
                f"✗ 远端 HEAD({remote_head}) ≠ 本地父提交({parent})，拒绝推送。\n"
                f"  如确认远端那个提交是本工具推的、且无人基于它工作，"
                f"可设 ALLOW_FORCE=1 重跑。"
            )

    # ---- 第 1 步：上传所有改动文件的 blob ----
    print("上传 blob ...")
    blob_map: dict[str, str] = {}
    for p in paths:
        local_sha = blob_sha_at(sha, p)
        remote_sha = upload_blob(sha, p)
        blob_map[p] = remote_sha
        flag = "same" if remote_sha == local_sha else "DIFF"
        print(f"  {flag}  {p}  {remote_sha[:12]}")

    # ---- 第 2 步：递归建 tree ----
    root_tree = build_tree(sha, "", set(paths), blob_map)
    print(f"tree   : {root_tree}")

    # ---- 第 3 步：建 commit ----
    payload = {
        "message": msg.rstrip("\n") + "\n",
        "tree": root_tree,
        "parents": [parent],
        "author": {"name": name, "email": email, "date": date},
        "committer": {"name": name, "email": email, "date": date},
    }
    status, resp = _req("POST", f"/repos/{REPO}/git/commits", payload)
    if status not in (200, 201):
        raise SystemExit(f"✗ 建 commit 失败：{status} {resp}")
    new_sha = resp["sha"]
    print(f"new    : {new_sha}")
    print("✓ commit sha 与本地一致" if new_sha == sha
          else f"⚠️  sha 不一致（本地 {sha}），内容相同但元数据有微差")

    # ---- 第 4 步：更新 ref ----
    status, resp = _req("PATCH", f"/repos/{REPO}/git/refs/heads/{BRANCH}",
                        {"sha": new_sha, "force": force})
    if status not in (200, 201):
        raise SystemExit(f"✗ 更新 ref 失败：{status} {resp}")
    print(f"✓ 已推送 {BRANCH} -> {resp['object']['sha']}")
    return 0


if __name__ == "__main__":
    TOKEN = sys.argv[1] if len(sys.argv) > 1 else ""
    COMMIT = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
    if not TOKEN:
        raise SystemExit("用法: push_via_api.py <token> [commit]")
    sys.exit(main())

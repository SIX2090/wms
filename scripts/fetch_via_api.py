#!/usr/bin/env python3
"""fetch_via_api.py — 沙箱 git fetch 被网络封锁时，用 GitHub Git Data API 同步远程提交到本地。

用法: fetch_via_api.py <token> <远程sha或main>
行为: 从目标 sha 沿父链递归写入 commit/tree/blob 对象到本地 .git，
      遇到本地已有对象即停；最后 update-ref refs/remotes/origin/main。
      每个写入的对象都校验 sha 一致性（不等即报错退出，防断链）。
"""
import base64
import json
import subprocess
import sys
import urllib.request

REPO = "SIX2090/wms"


def api(path, token):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}{path}",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "fetch-via-api",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read()
    return json.loads(raw.decode("utf-8", "replace"), strict=False)


def git(*args, data=None):
    return subprocess.run(["git"] + list(args), input=data,
                          capture_output=True, check=True)


def have(sha):
    return subprocess.run(["git", "cat-file", "-e", sha],
                          capture_output=True).returncode == 0


def ts(iso):
    from datetime import datetime
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    off = dt.strftime("%z") or "+0000"
    return f"{int(dt.timestamp())} {off}"


def epoch(iso):
    from datetime import datetime
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


# API 返回的 author/committer date 已规范化为 UTC ISO，但原始 commit 对象里的
# 时区偏移字符串（如 +0800）参与 sha 计算。按候选时区爆破，sha 匹配即停。
# 中国项目优先 +0800；GitHub API/Web 提交通常是 +0000。
_TZ_CANDIDATES = ["+0800", "+0000", "-0700", "-0800", "+0900", "+0530",
                  "+0100", "+0200", "-0500", "-0400", "+1000", "+0700"]


def _hash_commit(tree_sha, parents, author, committer, message, tz, add_nl):
    hdr = [f"tree {tree_sha}"]
    hdr += [f"parent {p}" for p in parents]
    hdr.append(f"author {author['name']} <{author['email']}> {epoch(author['date'])} {tz}")
    hdr.append(f"committer {committer['name']} <{committer['email']}> {epoch(committer['date'])} {tz}")
    msg = message + ("\n" if add_nl and not message.endswith("\n") else "")
    body = ("\n".join(hdr) + "\n\n" + msg).encode()
    return subprocess.run(["git", "hash-object", "-t", "commit", "--stdin"],
                          input=body, capture_output=True).stdout.decode().strip(), body


def write_blob(sha, token, stats):
    if have(sha):
        return
    d = api(f"/git/blobs/{sha}", token)
    content = base64.b64decode(d["content"])
    out = git("hash-object", "-w", "-t", "blob", "--stdin", data=content)
    got = out.stdout.decode().strip()
    if got != sha:
        print(f"FATAL blob sha {got} != {sha}", file=sys.stderr)
        sys.exit(3)
    stats["blob"] += 1


def write_tree(sha, token, stats):
    if have(sha):
        return
    d = api(f"/git/trees/{sha}", token)
    lines = []
    for e in d["tree"]:
        if e["type"] == "tree":
            write_tree(e["sha"], token, stats)
        elif e["type"] == "blob":
            write_blob(e["sha"], token, stats)
        else:
            continue  # submodule (commit 类型) 忽略
        lines.append(f"{e['mode']} {e['type']} {e['sha']}\t{e['path']}")
    payload = ("\n".join(lines) + ("\n" if lines else "")).encode()
    out = git("mktree", data=payload)
    got = out.stdout.decode().strip()
    if got != sha:
        print(f"FATAL tree sha {got} != {sha}", file=sys.stderr)
        sys.exit(3)
    stats["tree"] += 1


def write_commit(sha, token, stats, depth=0):
    if have(sha):
        return False
    d = api(f"/git/commits/{sha}", token)
    for p in d["parents"]:
        write_commit(p["sha"], token, stats, depth + 1)
    write_tree(d["tree"]["sha"], token, stats)
    parents = [p["sha"] for p in d["parents"]]
    body = None
    for tz in _TZ_CANDIDATES:
        for add_nl in (True, False):
            got, body = _hash_commit(d["tree"]["sha"], parents,
                                     d["author"], d["committer"],
                                     d["message"], tz, add_nl)
            if got == sha:
                break
        if got == sha:
            break
    else:
        print(f"FATAL commit {sha[:8]} 无法重构（时区/换行爆破未命中，"
              f"可能含 gpgsig/encoding 头）", file=sys.stderr)
        sys.exit(3)
    git("hash-object", "-w", "-t", "commit", "--stdin", data=body)
    stats["commit"] += 1
    msg = d["message"].split("\n")[0][:60]
    print(f"  写入 {'  ' * depth}{sha[:8]} {msg}")
    return True


def main():
    token, target = sys.argv[1], sys.argv[2]
    if not target.startswith("main"):
        sha = target
    else:
        ref = api("/git/ref/heads/main", token)
        sha = ref["object"]["sha"]
    print(f"目标: {sha[:8]}  本地 origin/main: "
          f"{subprocess.run(['git','rev-parse','--short','origin/main'], capture_output=True, text=True).stdout.strip()}")
    stats = {"commit": 0, "tree": 0, "blob": 0}
    write_commit(sha, token, stats)
    git("update-ref", "refs/remotes/origin/main", sha)
    print(f"完成: +{stats['commit']} commit +{stats['tree']} tree +{stats['blob']} blob")
    print(f"origin/main -> {sha[:8]}")


if __name__ == "__main__":
    main()

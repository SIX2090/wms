"""Native update metadata and promotion. Standard library only; never imports WMS.

Candidates are immutable APK releases. Only the privileged, main-only promotion
workflow creates android-mobile-stable-v<code>-<sha> releases after all required runs pass.
There is no mutable latest pointer and no write to the repository's main branch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlencode, unquote
from urllib.request import HTTPRedirectHandler, Request, build_opener

_REPO = "SIX2090/wms"
_API = f"https://api.github.com/repos/{_REPO}"
_PREFIX = "android-mobile-stable-v"
_CERTIFICATE = "2f50f0d7552be34d83316ee5d1e88b328a5914b1a08c552f5d0d0f2dd5619e4c"
_WORKFLOWS = ("android-build.yml", "ci.yml", "verify.yml")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("GitHub API redirect rejected; credentials must stay on API origin")


def _api(path, *, method="GET", data=None):
    # GitHub compare uses SHA...main; reject dot path segments, not substrings.
    if not path.startswith("/") or path.startswith("//") or "://" in path or "\\" in path or \
            any(part in (".", "..") for part in unquote(path.split("?", 1)[0]).split("/")):
        raise ValueError("invalid API path")
    token = os.environ.get("GH_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "WMS-update-promotion"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None if data is None else json.dumps(data).encode("utf-8")
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(_API + path, data=body, headers=headers, method=method)
    with build_opener(_NoRedirect()).open(request, timeout=30) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError("API response too large")
        return json.loads(raw)


def _candidate_tag(run_number, attempt):
    return f"android-apk-{run_number}-attempt-{attempt}"


def _validate_metadata(meta, sha, run_number, attempt=1):
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or meta.get("commitSha") != sha:
        raise ValueError("candidate SHA mismatch")
    if meta.get("packageName") != "com.factory.wms.mobile":
        raise ValueError("candidate package mismatch")
    if type(meta.get("versionCode")) is not int or not 1 <= meta["versionCode"] <= 2_100_000_000:
        raise ValueError("invalid versionCode")
    if not isinstance(meta.get("versionName"), str) or not 1 <= len(meta["versionName"]) <= 80:
        raise ValueError("invalid versionName")
    if type(meta.get("minSdk")) is not int or not 26 <= meta["minSdk"] <= 100:
        raise ValueError("invalid minimum SDK")
    if type(meta.get("size")) is not int or not 1 <= meta["size"] <= 150 * 1024 * 1024:
        raise ValueError("invalid APK size")
    for key in ("sha256", "certificateSha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", meta.get(key, "")):
            raise ValueError(f"invalid {key}")
    if meta["certificateSha256"] != _CERTIFICATE:
        raise ValueError("candidate signing identity does not match pinned mobile certificate")
    expected = f"https://github.com/{_REPO}/releases/download/{_candidate_tag(run_number, attempt)}/wms-mobile-scan.apk"
    if meta.get("url") != expected:
        raise ValueError("candidate URL mismatch")
    if not isinstance(meta.get("notes"), str) or len(meta["notes"]) > 2000:
        raise ValueError("invalid notes")


def _candidate(apk, aapt, apksigner, sha, run_number, attempt=1):
    badging = subprocess.run([aapt, "dump", "badging", str(apk)], check=True,
                             capture_output=True, text=True, encoding="utf-8").stdout
    signature = subprocess.run([apksigner, "verify", "--print-certs", str(apk)], check=True,
                               capture_output=True, text=True, encoding="utf-8").stdout
    package = re.search(r"package: name='([^']+)' versionCode='([0-9]+)' versionName='([^']+)'", badging)
    minimum = re.search(r"sdkVersion:'([0-9]+)'", badging)
    certs = re.findall(r"Signer #[0-9]+ certificate SHA-256 digest: ([0-9a-fA-F]+)", signature)
    if not package or not minimum or len(certs) != 1:
        raise ValueError("APK package/signing evidence missing")
    with apk.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    meta = dict(packageName=package[1], versionCode=int(package[2]), versionName=package[3],
                minSdk=int(minimum[1]), url=f"https://github.com/{_REPO}/releases/download/"
                f"{_candidate_tag(run_number, attempt)}/wms-mobile-scan.apk", size=apk.stat().st_size,
                sha256=digest,
                certificateSha256=certs[0].lower(), commitSha=sha,
                notes="WMS 手机端更新；仅在三个必需工作流全部验收成功后进入稳定通道。")
    _validate_metadata(meta, sha, run_number, attempt)
    return meta


def _green_runs(sha, api):
    result = {}
    for workflow in _WORKFLOWS:
        query = urlencode(dict(branch="main", head_sha=sha, per_page=100))
        response = api(f"/actions/workflows/{workflow}/runs?{query}")
        runs = [r for r in response["workflow_runs"] if r.get("head_sha") == sha
                and r.get("head_branch") == "main"
                and r.get("event") in ("push", "schedule", "workflow_dispatch")
                and r.get("head_repository", {}).get("full_name") == _REPO]
        if not runs:
            return None
        latest = max(runs, key=lambda r: (r["run_number"], r.get("run_attempt", 1)))
        if latest.get("status") != "completed" or latest.get("conclusion") != "success":
            return None
        if latest.get("path") != f".github/workflows/{workflow}":
            raise ValueError("unexpected workflow source")
        result[workflow] = latest
    return result


def _promote(sha, api=_api):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("full SHA required")
    runs = _green_runs(sha, api)
    if runs is None:
        return "not_ready"
    # Reject detached or fork-only commits even when a forged event names main.
    comparison = api(f"/compare/{sha}...main")
    if comparison.get("status") not in ("ahead", "identical"):
        raise ValueError("target is not an ancestor of main")
    number = runs["android-build.yml"]["run_number"]
    attempt = runs["android-build.yml"].get("run_attempt", 1)
    candidate = api("/releases/tags/" + _candidate_tag(number, attempt))
    if candidate.get("draft") or candidate.get("target_commitish") != sha:
        raise ValueError("APK candidate provenance mismatch")
    meta = json.loads(candidate["body"])
    _validate_metadata(meta, sha, number, attempt)
    assets = [a for a in candidate["assets"] if a["name"] == "wms-mobile-scan.apk"]
    if len(assets) != 1 or assets[0].get("state") != "uploaded" or \
            assets[0].get("size") != meta["size"] or \
            assets[0].get("digest") != "sha256:" + meta["sha256"] or \
            assets[0].get("browser_download_url") != meta["url"]:
        raise ValueError("APK asset digest/identity mismatch")
    refs = api(f"/git/matching-refs/tags/{_PREFIX}")
    previous = []
    for ref in refs:
        match = re.fullmatch(r"refs/tags/android-mobile-stable-v([1-9][0-9]*)-([0-9a-f]{40})", ref["ref"])
        if match:
            # A tag without a published stable release is not an accepted predecessor.
            release = api("/releases/tags/" + ref["ref"].removeprefix("refs/tags/"))
            if not release.get("draft") and not release.get("prerelease"):
                previous.append((int(match[1]), release))
    if previous:
        code, stable = max(previous, key=lambda item: item[0])
        if code >= meta["versionCode"]:
            return "already_stable_or_older"
        if json.loads(stable["body"])["certificateSha256"] != meta["certificateSha256"]:
            raise ValueError("signing identity changed; automatic promotion rejected")
    # Re-read immediately before publication; do not promote against a prior green attempt.
    latest = _green_runs(sha, api)
    if latest is None or any(latest[w]["id"] != runs[w]["id"] or
                             latest[w].get("run_attempt", 1) != runs[w].get("run_attempt", 1)
                             for w in _WORKFLOWS):
        return "not_ready"
    meta["verificationRuns"] = {w: dict(id=r["id"], attempt=r.get("run_attempt", 1))
                                for w, r in latest.items()}
    tag = f"{_PREFIX}{meta['versionCode']}-{sha}"
    api("/releases", method="POST", data=dict(tag_name=tag, target_commitish=sha,
        name=f"Android 稳定版 {meta['versionName']}", body=json.dumps(meta, ensure_ascii=False),
        draft=False, prerelease=False, make_latest="false"))
    return "promoted"


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    candidate = sub.add_parser("candidate")
    for option in ("apk", "aapt", "apksigner", "sha", "run-number", "output"):
        candidate.add_argument("--" + option, required=True)
    candidate.add_argument("--run-attempt", type=int, default=1)
    promote = sub.add_parser("promote")
    promote.add_argument("--sha", required=True)
    args = parser.parse_args()
    if args.command == "candidate":
        meta = _candidate(Path(args.apk), args.aapt, args.apksigner, args.sha, args.run_number, args.run_attempt)
        Path(args.output).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    else:
        print(_promote(args.sha))


if __name__ == "__main__":
    _main()

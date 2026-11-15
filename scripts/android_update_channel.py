"""Publish public update files from immutable, exact-green stable records only.

Runs in the serialized channel job, never on phones. No WMS import or database.
The mutable discovery file names an immutable record; it is not an APK authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from android_update_release import (
    _NoRedirect, _PREFIX, _REPO, _WORKFLOWS, _api, _green_runs, _validate_metadata,
)

_CHANNEL = "android-mobile-stable-channel"


def _upload_asset(release_id, name, content):
    if type(release_id) is not int or release_id <= 0 or not re.fullmatch(r"[a-zA-Z0-9.-]+", name):
        raise ValueError("invalid release asset destination")
    url = f"https://uploads.github.com/repos/{_REPO}/releases/{release_id}/assets?" + urlencode(dict(name=name))
    request = Request(url, data=content, method="POST", headers={
        "Authorization": "Bearer " + os.environ["GH_TOKEN"],
        "User-Agent": "WMS-update-channel", "Content-Type": "application/json",
        "Accept": "application/vnd.github+json",
    })
    with build_opener(_NoRedirect()).open(request, timeout=30) as response:
        raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("asset response too large")
        return json.loads(raw)


def _asset_matches(asset, content):
    return asset.get("state") == "uploaded" and asset.get("size") == len(content) and \
        asset.get("digest") == "sha256:" + hashlib.sha256(content).hexdigest()


def _ensure_asset(release, name, content, upload):
    existing = [asset for asset in release.get("assets", []) if asset["name"] == name]
    if len(existing) > 1:
        raise ValueError("duplicate update asset")
    asset = existing[0] if existing else upload(release["id"], name, content)
    if not _asset_matches(asset, content):
        raise ValueError("update asset digest mismatch")
    return asset


def _publish_channel(api=_api, upload=_upload_asset):
    refs = api(f"/git/matching-refs/tags/{_PREFIX}")
    stable = []
    for ref in refs:
        tag = ref["ref"].removeprefix("refs/tags/")
        match = re.fullmatch(r"android-mobile-stable-v([1-9][0-9]*)-([0-9a-f]{40})", tag)
        if not match:
            continue
        release = api("/releases/tags/" + tag)
        if not release.get("draft") and not release.get("prerelease"):
            stable.append((int(match[1]), match[2], tag, release))
    if not stable:
        return "no_stable_record"
    code, sha, tag, release = max(stable, key=lambda entry: entry[0])
    meta = json.loads(release["body"])
    candidate = re.fullmatch(
        rf"https://github.com/{_REPO}/releases/download/android-apk-([0-9]+)-attempt-([0-9]+)/wms-mobile-scan.apk",
        meta.get("url", ""))
    if not candidate:
        raise ValueError("invalid stable candidate URL")
    _validate_metadata(meta, sha, int(candidate[1]), int(candidate[2]))
    if meta["versionCode"] != code or release.get("target_commitish") != sha:
        raise ValueError("stable record identity mismatch")
    runs = _green_runs(sha, api)
    recorded = meta.get("verificationRuns")
    if runs is None or recorded != {w: dict(id=runs[w]["id"], attempt=runs[w].get("run_attempt", 1))
                                   for w in _WORKFLOWS}:
        return "not_ready"
    comparison = api(f"/compare/{sha}...main")
    if comparison.get("status") not in ("ahead", "identical"):
        raise ValueError("stable target is not on main")
    record = json.dumps(meta, ensure_ascii=False, sort_keys=True).encode("utf-8")
    _ensure_asset(release, "update.json", record, upload)
    pointer = json.dumps(dict(tag=tag), sort_keys=True).encode("utf-8")
    try:
        channel = api("/releases/tags/" + _CHANNEL)
    except HTTPError as error:
        if error.code != 404:
            raise
        channel = api("/releases", method="POST", data=dict(tag_name=_CHANNEL,
            target_commitish=sha, name="WMS stable update discovery", body="Public discovery only; immutable stable records remain authoritative.",
            draft=False, prerelease=False, make_latest="false"))
    if channel.get("draft") or channel.get("prerelease"):
        raise ValueError("update channel is not public stable")
    assets = channel.get("assets", [])
    current = next((a for a in assets if a["name"] == "update.json"), None)
    if current and current.get("label"):
        published = re.fullmatch(r"android-mobile-stable-v([1-9][0-9]*)-([0-9a-f]{40})", current["label"])
        if not published:
            raise ValueError("invalid current channel identity")
        if int(published[1]) > code:
            return "already_newer"
    if current and _asset_matches(current, pointer):
        return "already_published"
    staged = _ensure_asset(channel, f"next-{code}-{sha}.json", pointer, upload)
    # A rerun may have begun during upload. Do not move discovery against old green evidence.
    if _green_runs(sha, api) != runs:
        return "not_ready"
    backup = next((a for a in assets if a["name"] == "previous-update.json"), None)
    if backup:
        api(f"/releases/assets/{backup['id']}", method="DELETE")
    if current:
        api(f"/releases/assets/{current['id']}", method="PATCH", data=dict(name="previous-update.json"))
    try:
        api(f"/releases/assets/{staged['id']}", method="PATCH", data=dict(name="update.json", label=tag))
    except Exception:
        if current:
            api(f"/releases/assets/{current['id']}", method="PATCH", data=dict(name="update.json"))
        raise
    return "published"


if __name__ == "__main__":
    print(_publish_channel())

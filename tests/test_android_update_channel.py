"""Public update-channel behavior using synthetic HTTP/assets, no WMS runtime."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from urllib.error import HTTPError
from urllib.parse import urlsplit, parse_qs
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(_ROOT / "scripts")] + sys.path):
    _SPEC = importlib.util.spec_from_file_location("android_update_channel", _ROOT / "scripts/android_update_channel.py")
    _MODULE = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(_MODULE)


class _ChannelApi:
    def __init__(self):
        self.sha = "a" * 40
        self.tag = "android-mobile-stable-v51-" + self.sha
        self.runs = {w: dict(id=i + 10, run_number=900, run_attempt=1,
            head_sha=self.sha, head_branch="main", event="push", status="completed", conclusion="success",
            head_repository=dict(full_name="SIX2090/wms"), path=".github/workflows/" + w)
            for i, w in enumerate(_MODULE._WORKFLOWS)}
        self.meta = dict(packageName="com.factory.wms.mobile", versionCode=51, versionName="test51", minSdk=26,
            url="https://github.com/SIX2090/wms/releases/download/android-apk-900-attempt-1/wms-mobile-scan.apk",
            size=1000, sha256="b" * 64, certificateSha256="2f50f0d7552be34d83316ee5d1e88b328a5914b1a08c552f5d0d0f2dd5619e4c",
            commitSha=self.sha, notes="synthetic", verificationRuns={w:dict(id=r["id"], attempt=1) for w,r in self.runs.items()})
        self.stable = dict(id=1, target_commitish=self.sha, draft=False, prerelease=False, assets=[])
        self.channel = dict(id=2, draft=False, prerelease=False, assets=[])
        self.content = {}
        self.calls = []
        self.uploads = []
        self.fail_upload = False
        self.fail_rename = False
        self.corrupt_upload = False
        self.during_upload = None

    def upload(self, release_id, name, content):
        if self.fail_upload:
            raise OSError("synthetic upload unavailable")
        asset = dict(id=100 + len(self.uploads), name=name, size=len(content), state="uploaded",
                     digest="sha256:" + hashlib.sha256(content).hexdigest())
        if self.corrupt_upload:
            asset["digest"] = "sha256:" + "f" * 64
        self.uploads.append((release_id, name))
        self.content[asset["id"]] = content
        (self.stable if release_id == 1 else self.channel)["assets"].append(asset)
        if self.during_upload:
            self.during_upload()
        return copy.deepcopy(asset)

    def __call__(self, path, *, method="GET", data=None):
        self.calls.append((path, method))
        if path.startswith("/git/matching-refs/"):
            return [dict(ref="refs/tags/" + self.tag)]
        if path == "/releases/tags/" + self.tag:
            return copy.deepcopy(dict(self.stable, body=json.dumps(self.meta)))
        if path == "/releases/tags/" + _MODULE._CHANNEL:
            if self.channel is None:
                raise HTTPError("https://api.github.com/synthetic", 404, "missing", {}, None)
            return copy.deepcopy(self.channel)
        if path == "/releases" and method == "POST":
            if data["target_commitish"] != "main":
                raise HTTPError("https://api.github.com/synthetic", 403,
                                "workflow permission required for an older non-default target", {}, None)
            self.channel = dict(id=2, assets=[], **data)
            return copy.deepcopy(self.channel)
        if path.startswith("/compare/"):
            return dict(status="identical")
        if path.startswith("/actions/workflows/"):
            run = self.runs[path.split("/")[3]]
            return dict(workflow_runs=[copy.deepcopy(run)])
        if path.startswith("/releases/assets/"):
            asset = next(a for a in self.channel["assets"] if a["id"] == int(path.split("/")[-1]))
            if method == "DELETE":
                self.channel["assets"].remove(asset)
                return None
            if self.fail_rename and asset["name"].startswith("next-"):
                raise OSError("synthetic rename failure")
            asset.update(data)
            return copy.deepcopy(asset)
        raise AssertionError((path, method))


class TestAndroidUpdateChannel(unittest.TestCase):
    def test_real_create_channel_after_404_does_not_require_old_workflow_tag_permission(self):
        api = _ChannelApi(); api.channel = None
        class Transport:
            def open(self, request, timeout):
                url = urlsplit(request.full_url)
                if url.netloc == "uploads.github.com":
                    result = api.upload(int(url.path.split("/")[-2]), parse_qs(url.query)["name"][0], request.data)
                else:
                    path = url.path.removeprefix("/repos/SIX2090/wms")
                    if url.query: path += "?" + url.query
                    result = api(path, method=request.get_method(), data=json.loads(request.data) if request.data else None)
                return io.BytesIO(json.dumps(result).encode())
        with patch.dict("os.environ", {"GH_TOKEN":"synthetic-only"}), \
                patch.object(_MODULE, "build_opener", return_value=Transport()), \
                patch.object(sys.modules[_MODULE._api.__module__], "build_opener", return_value=Transport()):
            self.assertEqual("published", _MODULE._publish_channel())
        self.assertEqual("main", api.channel["target_commitish"])
        self.assertEqual(api.sha, api.stable["target_commitish"])

    def test_full_publication_uses_real_api_guards_upload_and_empty_delete_transport(self):
        api = _ChannelApi()
        api.upload(2, "update.json", b"old pointer")
        api.upload(2, "previous-update.json", b"older pointer")
        class Transport:
            def open(self, request, timeout):
                url = urlsplit(request.full_url)
                if url.netloc == "uploads.github.com":
                    asset = api.upload(int(url.path.split("/")[-2]), parse_qs(url.query)["name"][0], request.data)
                    return io.BytesIO(json.dumps(asset).encode())
                if url.netloc != "api.github.com":
                    raise AssertionError("credentials left fixed GitHub origins")
                path = url.path.removeprefix("/repos/SIX2090/wms")
                if url.query: path += "?" + url.query
                result = api(path, method=request.get_method(), data=json.loads(request.data) if request.data else None)
                return io.BytesIO(b"" if result is None else json.dumps(result).encode())
        transport = Transport()
        with patch.dict("os.environ", {"GH_TOKEN":"synthetic-only"}), \
                patch.object(_MODULE, "build_opener", return_value=transport), \
                patch.object(sys.modules[_MODULE._api.__module__], "build_opener", return_value=transport):
            self.assertEqual("published", _MODULE._publish_channel())
        pointer = next(a for a in api.channel["assets"] if a["name"] == "update.json")
        self.assertEqual(dict(tag=api.tag), json.loads(api.content[pointer["id"]]))
        self.assertIn(("/releases/assets/101", "DELETE"), api.calls)

    def test_publish_channel_keeps_immutable_record_and_public_pointer_bound(self):
        api = _ChannelApi()
        self.assertEqual("published", _MODULE._publish_channel(api, api.upload))
        record = next(a for a in api.stable["assets"] if a["name"] == "update.json")
        pointer = next(a for a in api.channel["assets"] if a["name"] == "update.json")
        self.assertEqual(api.meta, json.loads(api.content[record["id"]]))
        self.assertEqual(dict(tag=api.tag), json.loads(api.content[pointer["id"]]))
        self.assertEqual("already_published", _MODULE._publish_channel(api, api.upload))
        self.assertEqual(2, len(api.uploads))

    def test_publish_channel_creates_only_public_non_latest_discovery_release(self):
        api = _ChannelApi(); api.channel = None
        self.assertEqual("published", _MODULE._publish_channel(api, api.upload))
        self.assertFalse(api.channel["draft"])
        self.assertFalse(api.channel["prerelease"])
        self.assertEqual("false", api.channel["make_latest"])
        self.assertEqual("main", api.channel["target_commitish"])
        self.assertEqual(api.sha, api.stable["target_commitish"])

    def test_non_green_or_unrecorded_runs_never_publish(self):
        for workflow in _MODULE._WORKFLOWS:
            for mode in ("failed", "running", "foreign", "wrong_record"):
                with self.subTest(workflow=workflow, mode=mode):
                    api = _ChannelApi()
                    if mode == "failed": api.runs[workflow]["conclusion"] = "failure"
                    if mode == "running": api.runs[workflow]["status"] = "in_progress"
                    if mode == "foreign": api.runs[workflow]["head_repository"]["full_name"] = "someone/fork"
                    if mode == "wrong_record": api.meta["verificationRuns"][workflow]["id"] = 999
                    self.assertEqual("not_ready", _MODULE._publish_channel(api, api.upload))
                    self.assertEqual([], api.uploads)

    def test_source_tag_package_signature_and_commit_cannot_be_forged(self):
        for field, value in (("versionCode", 52), ("packageName", "other.app"),
                ("commitSha", "f"*40), ("certificateSha256", "e"*64),
                ("url", "https://evil.invalid/unsafe.apk")):
            with self.subTest(field=field):
                api = _ChannelApi(); api.meta[field] = value
                with self.assertRaises(ValueError): _MODULE._publish_channel(api, api.upload)
                self.assertEqual([], api.uploads)

    def test_recheck_during_upload_retains_current_pointer(self):
        api = _ChannelApi()
        _MODULE._publish_channel(api, api.upload)
        current = copy.deepcopy(api.channel["assets"])
        # Force discovery refresh, retaining the existing installable immutable record.
        api.channel["assets"][0]["digest"] = "sha256:" + "0"*64
        api.during_upload = lambda: api.runs["ci.yml"].update(status="in_progress", run_attempt=2)
        self.assertEqual("not_ready", _MODULE._publish_channel(api, api.upload))
        self.assertEqual(current[0]["id"], next(a for a in api.channel["assets"] if a["name"] == "update.json")["id"])

    def test_rename_failure_restores_previous_public_pointer(self):
        api = _ChannelApi()
        old = api.upload(2, "update.json", b'{"tag":"previous"}')
        api.fail_rename = True
        with self.assertRaisesRegex(OSError, "rename failure"):
            _MODULE._publish_channel(api, api.upload)
        current = next(a for a in api.channel["assets"] if a["name"] == "update.json")
        self.assertEqual(old["id"], current["id"])
        self.assertEqual(b'{"tag":"previous"}', api.content[current["id"]])

    def test_failed_or_corrupt_upload_does_not_remove_current_pointer(self):
        for mode in ("unavailable", "corrupt"):
            api = _ChannelApi(); old = api.upload(2, "update.json", b"old")
            api.fail_upload = mode == "unavailable"; api.corrupt_upload = mode == "corrupt"
            with self.assertRaises((OSError, ValueError)):
                _MODULE._publish_channel(api, api.upload)
            self.assertEqual(old["id"], next(a for a in api.channel["assets"] if a["name"] == "update.json")["id"])
            self.assertFalse(any(method == "DELETE" for _, method in api.calls))

    def test_queued_older_target_cannot_move_discovery_backwards(self):
        api = _ChannelApi()
        current = api.upload(2, "update.json", b"newer")
        api.channel["assets"][0]["label"] = "android-mobile-stable-v60-" + "e"*40
        self.assertEqual("already_newer", _MODULE._publish_channel(api, api.upload))
        self.assertEqual(current["id"], api.channel["assets"][0]["id"])
        self.assertFalse(any(method in ("PATCH", "DELETE") for _, method in api.calls))

    def test_all_stable_records_are_considered_and_highest_version_wins(self):
        api = _ChannelApi()
        old_tag = "android-mobile-stable-v50-" + "d"*40
        def reordered(path, **kwargs):
            if path.startswith("/git/matching-refs/"):
                return [dict(ref="refs/tags/"+old_tag), dict(ref="refs/tags/"+api.tag)]
            if path == "/releases/tags/"+old_tag:
                return dict(draft=False, prerelease=False, body="older unused body")
            return api(path, **kwargs)
        self.assertEqual("published", _MODULE._publish_channel(reordered, api.upload))
        self.assertEqual(api.tag, api.channel["assets"][0]["label"])

    def test_query_forbidden_is_never_treated_as_success(self):
        api = _ChannelApi()
        def forbidden(*args, **kwargs):
            raise HTTPError("https://api.github.com/synthetic", 403, "forbidden", {}, None)
        with self.assertRaises(HTTPError): _MODULE._publish_channel(forbidden, api.upload)
        self.assertEqual([], api.uploads)

    def test_upload_asset_pins_origin_and_refuses_redirects(self):
        module = _MODULE
        class Transport:
            def open(self, request, timeout):
                self_outer.assertTrue(request.full_url.startswith("https://uploads.github.com/repos/SIX2090/wms/releases/2/assets?"))
                self_outer.assertEqual("Bearer synthetic-only", request.headers["Authorization"])
                self_outer.assertEqual(b"{}", request.data)
                return io.BytesIO(b'{"id":100}')
        self_outer = self
        with patch.dict("os.environ", {"GH_TOKEN":"synthetic-only"}), patch.object(module, "build_opener", return_value=Transport()) as opener:
            self.assertEqual(dict(id=100), module._upload_asset(2, "update.json", b"{}"))
            self.assertIsInstance(opener.call_args.args[0], module._NoRedirect)
        with self.assertRaises(ValueError): module._upload_asset(2, "../bad", b"{}")

    def test_asset_matches_and_ensure_asset_reject_changed_immutable_content(self):
        api = _ChannelApi()
        _MODULE._ensure_asset(api.stable, "update.json", b"first", api.upload)
        with self.assertRaises(ValueError):
            _MODULE._ensure_asset(api.stable, "update.json", b"changed", api.upload)
        self.assertEqual(1, len(api.uploads))


if __name__ == "__main__":
    unittest.main()

"""Pure release-protocol tests: no WMS import, database, socket or credentials."""
import copy
import importlib.util
import json
import io
from pathlib import Path
import unittest
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("android_update_release", _ROOT / "scripts/android_update_release.py")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


class _ReleaseApi:
    def __init__(self):
        self.sha = "a" * 40
        self.meta = dict(packageName="com.factory.wms.mobile", versionCode=40, versionName="3.9.16",
            minSdk=26, size=1000, sha256="b" * 64, certificateSha256=_MODULE._CERTIFICATE,
            commitSha=self.sha, notes="synthetic update",
            url="https://github.com/SIX2090/wms/releases/download/android-apk-900-attempt-1/wms-mobile-scan.apk")
        self.runs = {name: dict(id=i, run_number=900, run_attempt=1, head_sha=self.sha,
            head_branch="main", event="push", head_repository=dict(full_name="SIX2090/wms"),
            status="completed", conclusion="success", path=f".github/workflows/{name}")
            for i, name in enumerate(_MODULE._WORKFLOWS)}
        self.candidate = dict(draft=False, target_commitish=self.sha, body=json.dumps(self.meta), assets=[
            dict(name="wms-mobile-scan.apk", state="uploaded", size=1000,
                 digest="sha256:" + "b" * 64, browser_download_url=self.meta["url"])])
        self.previous = None
        self.posts = []
        self.calls = []
        self.before_second_gate = None

    def __call__(self, path, *, method="GET", data=None):
        self.calls.append(path)
        if method == "POST":
            self.posts.append(data)
            return dict(id=123)
        if path.startswith("/actions/workflows/"):
            name = path.split("/")[3]
            if name == "android-build.yml" and self.calls.count(path) == 2 and self.before_second_gate:
                self.before_second_gate()
            run = self.runs[name]
            return dict(workflow_runs=[] if run is None else [copy.deepcopy(run)])
        if path.startswith("/compare/"):
            return dict(status="ahead")
        if path == "/releases/tags/" + _MODULE._candidate_tag(900, self.runs["android-build.yml"].get("run_attempt", 1)):
            self.candidate["body"] = json.dumps(self.meta)
            return self.candidate
        if path.startswith("/git/matching-refs/"):
            return [] if self.previous is None else [dict(ref="refs/tags/" + self.previous[0])]
        if self.previous and path == "/releases/tags/" + self.previous[0]:
            return self.previous[1]
        raise AssertionError(path)

    def stable(self, code, cert=_MODULE._CERTIFICATE):
        meta = dict(self.meta, versionCode=code, certificateSha256=cert)
        self.previous = (f"android-mobile-stable-v{code}-{'d' * 40}",
                         dict(draft=False, prerelease=False, body=json.dumps(meta)))


class TestAndroidUpdateRelease(unittest.TestCase):
    def test_real_api_transport_accepts_compare_and_promotes_without_mocking_path_guard(self):
        api = _ReleaseApi()
        class Transport:
            def open(self, request, timeout):
                self_url = request.full_url
                if not self_url.startswith(_MODULE._API + "/"):
                    raise AssertionError("credentials escaped GitHub repository API")
                body = None if request.data is None else json.loads(request.data)
                result = api(self_url.removeprefix(_MODULE._API),
                             method=request.get_method(), data=body)
                return io.BytesIO(json.dumps(result).encode())
        with patch.object(_MODULE, "build_opener", return_value=Transport()):
            self.assertEqual("promoted", _MODULE._promote(api.sha, _MODULE._api))
        self.assertIn(f"/compare/{api.sha}...main", api.calls)
        self.assertEqual(1, len(api.posts))

    def test_real_api_transport_still_rejects_traversal_and_foreign_origins(self):
        for path in ("../main", "/../main", "/a/./b", "/a/%2e%2e/b",
                     "//evil.invalid/repo", "https://evil.invalid/repo", "/a\\..\\b"):
            with self.subTest(path=path), patch.object(_MODULE, "build_opener") as opener:
                with self.assertRaisesRegex(ValueError, "invalid API path"):
                    _MODULE._api(path)
                opener.assert_not_called()

    def test_green_exact_sha_publishes_immutable_stable_record(self):
        api = _ReleaseApi()
        self.assertEqual("promoted", _MODULE._promote(api.sha, api))
        self.assertEqual(1, len(api.posts))
        posted = api.posts[0]
        self.assertEqual("android-mobile-stable-v40-" + api.sha, posted["tag_name"])
        self.assertEqual(api.sha, posted["target_commitish"])
        self.assertEqual("false", posted["make_latest"])
        self.assertEqual(api.meta["url"], json.loads(posted["body"])["url"])
        self.assertEqual(3, len(json.loads(posted["body"])["verificationRuns"]))

    def test_every_non_green_state_retains_current_stable(self):
        for workflow in _MODULE._WORKFLOWS:
            for status, conclusion in (("in_progress", None), ("queued", None),
                    ("completed", "failure"), ("completed", "cancelled"),
                    ("completed", "skipped"), ("completed", None)):
                with self.subTest(workflow=workflow, status=status, conclusion=conclusion):
                    api = _ReleaseApi()
                    api.runs[workflow].update(status=status, conclusion=conclusion)
                    self.assertEqual("not_ready", _MODULE._promote(api.sha, api))
                    self.assertEqual([], api.posts)

    def test_missing_foreign_and_pr_runs_are_not_green(self):
        for mode in ("missing", "foreign", "pull_request", "branch", "sha"):
            api = _ReleaseApi()
            run = api.runs["ci.yml"]
            if mode == "missing": api.runs["ci.yml"] = None
            elif mode == "foreign": run["head_repository"] = dict(full_name="someone/fork")
            elif mode == "pull_request": run["event"] = "pull_request"
            elif mode == "branch": run["head_branch"] = "other"
            else: run["head_sha"] = "f" * 40
            with self.subTest(mode=mode):
                self.assertEqual("not_ready", _MODULE._promote(api.sha, api))
                self.assertFalse(api.posts)

    def test_latest_run_and_attempt_win_over_old_green(self):
        api = _ReleaseApi()
        base_call = api.__call__
        def with_old_green(path, **kwargs):
            result = base_call(path, **kwargs)
            if path.startswith("/actions/workflows/ci.yml/"):
                failed = dict(result["workflow_runs"][0], run_number=901, conclusion="failure")
                result["workflow_runs"].append(failed)
            return result
        self.assertEqual("not_ready", _MODULE._promote(api.sha, with_old_green))
        self.assertFalse(api.posts)

    def test_rerun_started_during_promotion_does_not_publish(self):
        api = _ReleaseApi()
        api.before_second_gate = lambda: api.runs["ci.yml"].update(status="in_progress", run_attempt=2)
        self.assertEqual("not_ready", _MODULE._promote(api.sha, api))
        self.assertFalse(api.posts)

    def test_successful_rerun_uses_new_attempt_asset_not_immutable_old_release(self):
        api = _ReleaseApi()
        api.runs["android-build.yml"]["run_attempt"] = 2
        api.meta["url"] = api.meta["url"].replace("attempt-1/", "attempt-2/")
        api.candidate["assets"][0]["browser_download_url"] = api.meta["url"]
        self.assertEqual("promoted", _MODULE._promote(api.sha, api))
        self.assertIn("/releases/tags/android-apk-900-attempt-2", api.calls)
        self.assertNotIn("/releases/tags/android-apk-900-attempt-1", api.calls)

    def test_api_error_is_not_success_and_does_not_publish(self):
        api = _ReleaseApi()
        def failing(path, **kwargs):
            if "/ci.yml/" in path: raise OSError("synthetic API unavailable")
            return api(path, **kwargs)
        with self.assertRaises(OSError): _MODULE._promote(api.sha, failing)
        self.assertFalse(api.posts)

    def test_older_or_equal_candidate_cannot_move_stable_backwards(self):
        for code in (40, 41, 100):
            api = _ReleaseApi()
            api.stable(code)
            self.assertEqual("already_stable_or_older", _MODULE._promote(api.sha, api))
            self.assertFalse(api.posts)

    def test_signing_identity_change_requires_manual_resolution(self):
        api = _ReleaseApi()
        api.stable(39, "d" * 64)
        with self.assertRaisesRegex(ValueError, "signing identity"):
            _MODULE._promote(api.sha, api)
        self.assertFalse(api.posts)

    def test_candidate_mismatch_does_not_publish(self):
        for field, value in (("packageName", "other.app"), ("packageName", "com.factory.wms"), ("versionCode", 0),
                ("versionCode", True), ("size", 0), ("size", 151 * 1024 * 1024),
                ("sha256", "invalid"), ("certificateSha256", "invalid"), ("certificateSha256", "e" * 64),
                ("commitSha", "f" * 40), ("url", "https://evil.invalid/app.apk")):
            api = _ReleaseApi()
            api.meta[field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError): _MODULE._promote(api.sha, api)
                self.assertFalse(api.posts)

    def test_missing_or_changed_asset_does_not_publish(self):
        for field, value in (("size", 999), ("digest", "sha256:" + "f" * 64),
                ("state", "new"), ("browser_download_url", "https://evil.invalid/app.apk")):
            api = _ReleaseApi()
            api.candidate["assets"][0][field] = value
            with self.subTest(field=field):
                with self.assertRaises(ValueError): _MODULE._promote(api.sha, api)
                self.assertFalse(api.posts)


if __name__ == "__main__":
    unittest.main()

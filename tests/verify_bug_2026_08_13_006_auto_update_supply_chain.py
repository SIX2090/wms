# -*- coding: utf-8 -*-
"""
BUG-2026-08-13-006 回归测试：自动更新供应链加固。
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

import auto_update  # noqa: E402

SHA_A = "a" * 40
SHA_B = "b" * 40
SHORT_A = SHA_A[:12]


class _FakeGit:
    def __init__(self, responses):
        self._responses = responses
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        key = " ".join(args)
        for needle, resp in self._responses.items():
            if needle in key:
                return resp
        return 0, "", ""


class TestVerifyPin(unittest.TestCase):
    def _set_pin(self, pin):
        return patch.object(auto_update, "GIT_PIN", pin)

    def test_empty_pin_allows(self):
        """T1：GIT_PIN 为空放行。"""
        with self._set_pin(""):
            ok, detail = auto_update.verify_pin(SHA_A)
        self.assertTrue(ok)
        self.assertEqual(detail, "")

    def test_full_sha_match_allows(self):
        """T2：完整 SHA 匹配放行。"""
        with self._set_pin(SHA_A):
            ok, _ = auto_update.verify_pin(SHA_A)
        self.assertTrue(ok)

    def test_short_sha_prefix_allows(self):
        """T3：短 SHA 前缀匹配放行。"""
        with self._set_pin(SHORT_A):
            ok, _ = auto_update.verify_pin(SHA_A)
        self.assertTrue(ok)

    def test_sha_mismatch_rejects(self):
        """T4：SHA 不匹配拒绝。"""
        with self._set_pin(SHA_A):
            ok, detail = auto_update.verify_pin(SHA_B)
        self.assertFalse(ok)
        self.assertIn("安全拒绝", detail)

    def test_tag_resolves_and_matches_allows(self):
        """T5：tag rev-parse 成功且匹配放行。"""
        fake = _FakeGit({"rev-parse v1.0.0": (0, SHA_A, "")})
        with self._set_pin("v1.0.0"), patch.object(auto_update, "run_git", side_effect=fake):
            ok, _ = auto_update.verify_pin(SHA_A)
        self.assertTrue(ok)
        self.assertTrue(any("rev-parse" in " ".join(c) and "v1.0.0" in " ".join(c)
                            for c in fake.calls))

    def test_unknown_tag_rejects(self):
        """T6：不存在的 tag 拒绝。"""
        fake = _FakeGit({"rev-parse ghost": (128, "", "unknown revision")})
        with self._set_pin("ghost"), patch.object(auto_update, "run_git", side_effect=fake):
            ok, detail = auto_update.verify_pin(SHA_A)
        self.assertFalse(ok)
        self.assertIn("无法解析", detail)


class TestResolveSha(unittest.TestCase):
    def test_success(self):
        fake = _FakeGit({"rev-parse origin/main": (0, SHA_A, "")})
        with patch.object(auto_update, "run_git", side_effect=fake):
            self.assertEqual(auto_update.resolve_sha("origin/main"), SHA_A)

    def test_failure_none(self):
        fake = _FakeGit({"rev-parse": (128, "", "err")})
        with patch.object(auto_update, "run_git", side_effect=fake):
            self.assertIsNone(auto_update.resolve_sha("origin/main"))


class TestPipRequireHashes(unittest.TestCase):
    def test_flag_on(self):
        """T7：PIP_REQUIRE_HASHES=True -> pip install 命令含 --require-hashes。"""
        cmds = []
        def fake_run(cmd, **kw):
            cmds.append(cmd)
            m = MagicMock()
            m.returncode = 0
            m.stdout = "pkg==1.0\n"
            m.stderr = ""
            return m
        with patch.object(auto_update, "PIP_REQUIRE_HASHES", True), \
             patch("auto_update.subprocess.run", side_effect=fake_run), \
             patch.object(auto_update, "log"):
            auto_update.pip_install(sys.executable)
        install_cmds = [c for c in cmds if "install" in c]
        self.assertTrue(install_cmds)
        self.assertIn("--require-hashes", install_cmds[0])

    def test_flag_off(self):
        """默认 PIP_REQUIRE_HASHES=False -> 不含 --require-hashes。"""
        cmds = []
        def fake_run(cmd, **kw):
            cmds.append(cmd)
            m = MagicMock()
            m.returncode = 0
            m.stdout = ""
            m.stderr = ""
            return m
        with patch.object(auto_update, "PIP_REQUIRE_HASHES", False), \
             patch("auto_update.subprocess.run", side_effect=fake_run), \
             patch.object(auto_update, "log"):
            auto_update.pip_install(sys.executable)
        install_cmds = [c for c in cmds if "install" in c]
        self.assertTrue(install_cmds)
        for c in install_cmds:
            self.assertNotIn("--require-hashes", c)


class TestSourceHardening(unittest.TestCase):
    def test_main_integrations(self):
        """T8：源码静态——main() 接入 verify_pin / resolve_sha / log_pulled_commits。"""
        import inspect
        main_src = inspect.getsource(auto_update.main)
        self.assertIn("verify_pin", main_src)
        self.assertIn("resolve_sha", main_src)
        self.assertIn("log_pulled_commits", main_src)
        self.assertIn("pre_sha", main_src)
        self.assertIn("post_sha", main_src)

    def test_env_vars(self):
        """T9：模块读取 WMS_GIT_PIN 与 WMS_PIP_REQUIRE_HASHES。"""
        import inspect
        src = inspect.getsource(auto_update)
        self.assertIn("WMS_GIT_PIN", src)
        self.assertIn("WMS_PIP_REQUIRE_HASHES", src)
        self.assertIn("--require-hashes", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)

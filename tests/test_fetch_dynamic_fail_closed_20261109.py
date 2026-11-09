"""Synthetic JS cases showing scanner escapes; no WMS runtime is imported."""
from pathlib import Path
import runpy
import socket
import sqlite3
import subprocess
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCANNER = runpy.run_path(str(ROOT / 'scripts/lint_no_raw_post_fetch.py'))
SYNTHETIC = Path('synthetic-project')
JS = SYNTHETIC / 'app/static/js/pages/entry.js'


def refuse(*_args, **_kwargs):
    raise AssertionError('database, network and child processes are forbidden')


class FetchDynamicFailClosed(unittest.TestCase):
    def setUp(self):
        for guard in (patch.object(sqlite3, 'connect', refuse),
                      patch.object(sqlite3.dbapi2, 'connect', refuse),
                      patch.object(socket.socket, 'connect', refuse),
                      patch.object(socket.socket, 'connect_ex', refuse),
                      patch.object(socket, 'getaddrinfo', refuse),
                      patch.object(subprocess, 'Popen', refuse)):
            guard.start()
            self.addCleanup(guard.stop)

    def assert_blocked(self, source):
        try:
            violations = SCANNER['scan_file'](JS, SYNTHETIC, text=source)
        except RuntimeError:
            return  # Unknown syntax may fail closed instead of producing a match.
        self.assertTrue(violations, 'unprovably safe fetch must not pass the scanner')

    def test_identifier_named_get_can_hold_post(self):
        self.assert_blocked('const GET="POST"; fetch("/synthetic", {method:GET});')

    def test_computed_property_can_be_method(self):
        self.assert_blocked('const key="method"; fetch("/synthetic", {[key]:"POST"});')

    def test_request_argument_can_carry_post(self):
        self.assert_blocked('fetch(new Request("/synthetic", {method:"POST"}));')

    def test_alias_can_invoke_fetch(self):
        self.assert_blocked('const send=fetch; send("/synthetic", {method:"POST"});')

    def test_reflect_apply_can_invoke_fetch(self):
        self.assert_blocked('Reflect.apply(fetch,null,["/synthetic",{method:"POST"}]);')

    def test_global_this_fetch_post(self):
        self.assert_blocked('globalThis.fetch("/synthetic",{method:"POST"});')

    def test_member_assignment_alias(self):
        self.assert_blocked('let send; send=globalThis.fetch; send("/synthetic",{method:"POST"});')

    def test_destructuring_alias(self):
        self.assert_blocked('const {fetch:send}=globalThis; send("/synthetic",{method:"POST"});')

    def test_bound_member_alias(self):
        self.assert_blocked('const send=window.fetch.bind(window); send("/synthetic",{method:"POST"});')

    def test_optional_chain_fetch(self):
        self.assert_blocked('globalThis?.["fetch"]?.("/synthetic",{method:"POST"});')

    def test_computed_fetch_name(self):
        self.assert_blocked('globalThis["fe"+"tch"]("/synthetic",{method:"POST"});')

    def test_template_interpolation_alias(self):
        self.assert_blocked('const text=`${globalThis.fetch}`;')

    def test_conditional_expression_alias(self):
        self.assert_blocked('const send=flag?globalThis.fetch:other; send("/synthetic",{method:"POST"});')

    def test_computed_destructuring_alias(self):
        self.assert_blocked('const {["fe"+"tch"]:send}=globalThis; send("/synthetic",{method:"POST"});')

    def test_reflective_property_alias(self):
        self.assert_blocked('const send=Reflect.get(globalThis,"fetch"); send("/synthetic",{method:"POST"});')

    def test_aliased_global_and_dynamic_property(self):
        self.assert_blocked('const root=globalThis; const key="fe"+"tch"; const send=root[key]; send("/synthetic",{method:"POST"});')

    def test_nonstrict_iife_this_can_be_global(self):
        self.assert_blocked('(function(g){const root=this;const send=root["fe"+"tch"];send("/synthetic",{method:"POST"});})(window);')

    def test_iife_argument_alias_and_computed_member(self):
        self.assert_blocked('(function(g){(function(z){z["fe"+"tch"]("/synthetic",{method:"POST"});})(g);})(window);')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(FetchDynamicFailClosed)
    if suite.countTestCases() != 18:
        raise SystemExit('synthetic test list must be explicitly nonempty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())

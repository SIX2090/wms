"""Scope, unknown-syntax and Unicode regression; no app, network or DB imports."""
from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCAN = runpy.run_path(str(ROOT / 'scripts/lint_no_raw_post_fetch.py'))
PATH = ROOT / 'app/static/js/pages/synthetic.js'


class ScopeBoundaries(unittest.TestCase):
    def scan(self, source):
        return SCAN['scan_file'](PATH, ROOT, text=source)

    def test_local_global_named_variables_do_not_leak_between_functions(self):
        source = '''const root=window;
        function local(){const root={}; const key='data'; return root[key];}
        function other(){const self={}; const key='data'; return self[key];}'''
        self.assertEqual(self.scan(source), [])

    def test_local_fetch_function_is_distinct_from_browser_fetch(self):
        self.assertEqual(self.scan('function f(fetch){fetch("/x",{method:"POST"});}'), [])

    def test_nested_wrapper_cannot_hide_another_function(self):
        self.assertTrue(self.scan('function csrfFetch(){function bad(){return fetch("/x",{method:"POST"});}}'))

    def test_unicode_source_keeps_original_line_and_snippet(self):
        source = 'const 文本="😀https://x.invalid";\nfetch(makeUrl(),{method:"POST"});'
        found = self.scan(source)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][0], 2)
        self.assertEqual(found[0][1], source.splitlines()[1])

    def test_oversize_and_unknown_js_do_not_pass(self):
        for source in (' ' * (1024 * 1024 + 1), 'fetch(???'):
            with self.subTest(length=len(source)), self.assertRaises(RuntimeError):
                self.scan(source)

    def test_unknown_template_is_reported_for_existing_warn_strict_policy(self):
        found = SCAN['scan_template_file'](ROOT / 'app/templates/synthetic.html', ROOT,
            text='<script>const x={{ unknown }};</script>')
        self.assertEqual(len(found), 1)
        self.assertIn('无法解析', found[0][1])

    def test_root_whitelist_does_not_apply_to_nested_names(self):
        source = 'fetch("/x",{method:"POST"});'
        self.assertEqual(SCAN['scan_file'](ROOT / 'app/static/js/api.js', ROOT, text=source), [])
        self.assertTrue(SCAN['scan_file'](ROOT / 'app/static/js/pages/api.js', ROOT, text=source))
        script = '<script>' + source + '</script>'
        self.assertEqual(SCAN['scan_template_file'](ROOT / 'app/templates/base.html', ROOT, text=script), [])
        self.assertTrue(SCAN['scan_template_file'](ROOT / 'app/templates/pages/base.html', ROOT, text=script))
        wrapper = 'function csrfFetch(url){return fetch(url,{method:"POST"});}'
        self.assertTrue(self.scan(wrapper), 'a business function name must not grant the unified-layer exemption')
        self.assertEqual(SCAN['scan_file'](ROOT / 'app/static/js/api.js', ROOT, text=wrapper), [])
        self.assertTrue(SCAN['scan_template_file'](ROOT / 'app/templates/pages/base.html', ROOT,
                                                text='<script>' + wrapper + '</script>'))

    def test_request_copy_and_argument_spread_are_not_assumed_get(self):
        for source in ('fetch(new Request(existingRequest));', 'fetch(...arguments);',
                       'fetch(new Request("/x", {method:"POST"}), {});',
                       'const request=new Request("/x", {method:"POST"}); fetch(request, {});',
                       'fetch(new window.Request("/x", {method:"POST"}));',
                       'const R=Request; fetch(new R("/x", {method:"POST"}));',
                       'const {Request:R}=window; fetch(new R("/x", {method:"POST"}));',
                       'const R=Reflect.get(window,"Request"); fetch(new R("/x", {method:"POST"}));'):
            with self.subTest(source=source):
                self.assertTrue(self.scan(source))
        self.assertEqual(self.scan('fetch(new Request("/x", {method:"GET"}));'), [])


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ScopeBoundaries)
    if suite.countTestCases() != 8:
        raise SystemExit('test manifest incomplete')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())

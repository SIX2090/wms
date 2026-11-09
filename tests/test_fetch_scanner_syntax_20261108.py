"""Offline scanner regression with synthetic JavaScript only."""
from pathlib import Path
import inspect
import runpy
import socket
import sqlite3
import subprocess
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCANNER = runpy.run_path(str(ROOT / 'scripts/lint_no_raw_post_fetch.py'))
SYNTHETIC_ROOT = Path('synthetic-project')
JS = SYNTHETIC_ROOT / 'app/static/js/pages/entry.js'
TEMPLATE = SYNTHETIC_ROOT / 'app/templates/entry.html'


def refuse(*_args, **_kwargs):
    raise AssertionError('network, database and subprocess are forbidden')


class FetchSyntax(unittest.TestCase):
    def setUp(self):
        for guard in (patch.object(socket.socket, 'connect', refuse),
                      patch.object(socket.socket, 'connect_ex', refuse),
                      patch.object(socket, 'getaddrinfo', refuse),
                      patch.object(sqlite3, 'connect', refuse),
                      patch.object(subprocess, 'Popen', refuse)):
            guard.start()
            self.addCleanup(guard.stop)

    def js(self, text):
        function = SCANNER['scan_file']
        if 'text' in inspect.signature(function).parameters:
            return function(JS, SYNTHETIC_ROOT, text=text)
        with patch.object(Path, 'read_text', return_value=text):
            return function(JS, SYNTHETIC_ROOT)

    def template(self, text):
        function = SCANNER['scan_template_file']
        if 'text' in inspect.signature(function).parameters:
            return function(TEMPLATE, SYNTHETIC_ROOT, text=text)
        with patch.object(Path, 'read_text', return_value=text):
            return function(TEMPLATE, SYNTHETIC_ROOT)

    def test_absolute_urls_are_not_comments(self):
        for source in ("fetch('https://example.invalid/api', {method: 'POST'});",
                       'fetch("http://example.invalid/a/*literal*/", {method: "DELETE"});'):
            with self.subTest(source=source):
                self.assertEqual(len(self.js(source)), 1)

    def test_nested_url_and_payload_calls_are_checked(self):
        for source in ("fetch(makeUrl(), {method: 'POST'});",
                       "fetch(makeUrl(inner(1)), {method: 'PUT', body: JSON.stringify({a: 1})});"):
            with self.subTest(source=source):
                self.assertEqual(len(self.js(source)), 1)

    def test_templates_use_same_detection(self):
        self.assertEqual(len(self.template("<script>fetch(makeUrl(), {method:'PATCH'});</script>")), 1)
        self.assertEqual(len(self.template("<script>fetch('https://example.invalid', {method:'POST'});</script>")), 1)

    def test_comments_strings_and_get_are_not_violations(self):
        for source in ("// fetch('/fake', {method:'POST'});",
                       "/* fetch('/fake', {method:'POST'}); */",
                       'const text = "fetch(\'/fake\', {method: \'POST\'})";',
                       "fetch(makeUrl(), {method:'GET'});",
                       "WMS.api.post('/fake', {});"):
            with self.subTest(source=source):
                self.assertEqual(self.js(source), [])

    def test_comments_preserve_line_number_and_nested_calls(self):
        source = "// first line\nfetch(/* comment */ makeUrl(), /* next */ {method: 'POST'});"
        found = self.js(source)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][0], 2)

    def test_templates_regex_and_quoted_method_keys(self):
        for source in ("fetch(`https://example.invalid/${id}`, {method: 'POST'});",
                       "const x = `result ${fetch('/fake', {method: 'POST'})}`;",
                       r"fetch(/\)/.source, {method: 'POST'});",
                       "fetch('/fake', {'method': 'POST'});",
                       "fetch('/fake', {['method']: `POST`});"):
            with self.subTest(source=source):
                self.assertEqual(len(self.js(source)), 1)

    def test_existing_wrapper_and_literal_method_text_remain_safe(self):
        wrapper = "function csrfFetch(url) { return fetch(url, {method:'POST'}); }"
        self.assertTrue(self.js(wrapper))
        self.assertEqual(SCANNER['scan_file'](SYNTHETIC_ROOT / 'app/static/js/api.js',
                                            SYNTHETIC_ROOT, text=wrapper), [])
        for source in ("const text = \"method:'POST'\"; fetch('/fake', {method:'GET'});",
                       "const template = `fetch('/fake', {method:'POST'})`;"):
            with self.subTest(source=source):
                self.assertEqual(self.js(source), [])

    def test_postfix_division_does_not_hide_later_fetch(self):
        for left in ('count++', 'count--', "'4'", '`4`'):
            with self.subTest(left=left):
                source = f"let value = {left} / divisor; fetch('/fake', {{method:'POST'}});"
                self.assertEqual(len(self.js(source)), 1)

    def test_regex_after_control_condition_is_not_executable_code(self):
        for statement in ('if (ok)', 'while (ok)', 'for (let i=0;i<1;i++)',
                          'if (ok) ok(); else', 'do', 'async function f(){ await'):
            with self.subTest(statement=statement):
                suffix = ' }' if statement.startswith('async ') else ' while(false);' if statement == 'do' else ''
                self.assertEqual(self.js(f"{statement} /fetch(method:'POST')/.test(s);{suffix}"), [])

    def test_headers_and_payload_method_are_not_fetch_method(self):
        for source in ("fetch(makeUrl(), {method:'GET',headers:{method:'POST'}});",
                       "fetch(makeUrl(), {method:'GET',body:JSON.stringify({method:'POST'})});"):
            with self.subTest(source=source):
                self.assertEqual(self.js(source), [])

    def test_static_parentheses_and_optional_call(self):
        for source in ("fetch('/fake',{method:('POST')});",
                       "fetch?.('/fake',{method:'POST'});",
                       "(fetch)('/fake',{method:'POST'});",
                       "fetch('/fake',{[`method`]:'POST'});"):
            with self.subTest(source=source):
                self.assertEqual(len(self.js(source)), 1)

    def test_regex_after_control_block_and_division_after_object(self):
        self.assertEqual(self.js("if(ok) {} /fetch(method:'POST')/.test(s);"), [])
        self.assertEqual(len(self.js("let n = ({n: 1}).n / divisor; fetch('/x', {method:'POST'});")), 1)
        self.assertEqual(self.js("class C {} /fetch('x',{method:'POST'})/.test(s);"), [])
        self.assertEqual(len(self.js("let f = function() {} / n; fetch('/x',{method:'POST'});")), 1)
        for keyword in ("function*()", "function* named()", "async function* named()"):
            with self.subTest(keyword=keyword):
                self.assertEqual(len(self.js(f"let f = {keyword} {{}} / n; fetch('/x',{{method:'POST'}});")), 1)
        for keyword in ("class extends (foo())", "class extends foo()", "class extends (foo)",
                        "class Named extends (foo())", "class extends (x ? foo : bar)"):
            with self.subTest(keyword=keyword):
                self.assertEqual(len(self.js(f"let f = {keyword} {{}} / n; fetch('/x',{{method:'POST'}});")), 1)
        self.assertEqual(self.js("async function f(){for await (const x of xs) /fetch('x',{method:'POST'})/.test(s);}"), [])

    def test_wrapper_is_not_created_by_comments_or_strings(self):
        for source in ("// function csrfFetch() {\nfetch('/x', {method:'POST'});",
                       "const x = \"function csrfFetch() {\"; fetch('/x', {method:'POST'});"):
            with self.subTest(source=source):
                self.assertEqual(len(self.js(source)), 1)

    def test_wrapper_definitions_with_literals_and_nested_braces(self):
        for source in ("function csrfFetch(url) { const u = 'https://test.invalid'; return fetch(url, {method:'POST'}); }",
                       "const csrfFetch = (url) => { return fetch(url, {method:'POST'}); };",
                       "window.csrfFetch = function(url) { return fetch(url, {method:'POST'}); };"):
            with self.subTest(source=source):
                self.assertTrue(self.js(source))
                self.assertEqual(SCANNER['scan_file'](SYNTHETIC_ROOT / 'app/static/js/api.js',
                                                    SYNTHETIC_ROOT, text=source), [])

    def test_template_interpolation_does_not_split_outer_call_arguments(self):
        source = "fetch(`http://test.invalid/${(a, b)}`, {method:'POST'});"
        self.assertEqual(len(self.js(source)), 1)
        self.assertEqual(len(self.js("const s = `${(a, fetch('/x', {method:'POST'}))}`;")), 1)

    def test_method_in_spread_and_prototype_object_is_detected(self):
        for source in ("fetch('/x', {...{method:'POST'}});",
                       "fetch('/x', {__proto__:{method:'POST'}});",
                       "fetch('/x', Object.assign({method:'POST'}, config));"):
            with self.subTest(source=source):
                self.assertEqual(len(self.js(source)), 1)

    def test_delimiter_characters_in_strings_do_not_break_pairing(self):
        for source in ("fetch(')', {method:'POST'})", "fetch(',', {method:'POST'})",
                       "fetch(makeUrl(')'), {method:'POST'})",
                       "fetch('/x',{method:'POST',body:JSON.stringify({foo:'}'})})"):
            with self.subTest(source=source):
                self.assertEqual(len(self.js(source)), 1)

    def test_static_escape_sequences_and_multiple_parentheses(self):
        for source in (r"fetch('/x',{method:'\x50OST'})", r"fetch('/x',{'\u006dethod':'POST'})",
                       "((fetch))('/x',{method:'POST'})"):
            with self.subTest(source=source):
                self.assertEqual(len(self.js(source)), 1)


if __name__ == '__main__':
    unittest.main()

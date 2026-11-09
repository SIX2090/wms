"""Copied real Jinja template rendered from synthetic data with no WMS import."""
import ast
import builtins
from collections import defaultdict
from pathlib import Path
import platform
import socket
import sqlite3
import subprocess
import sys
import sysconfig
import types
import unittest

CANDIDATE = Path(__file__).resolve().parents[1]


def main():
    def deny(*_a, **_kw): raise AssertionError('network, DB or child process forbidden')
    socket.socket.connect = socket.socket.connect_ex = deny
    socket.getaddrinfo = socket.create_connection = deny
    sqlite3.connect = sqlite3.dbapi2.connect = deny
    class DeniedPopen:
        def __init__(self, *_a, **_kw): deny()
    subprocess.Popen = DeniedPopen
    platform.machine = lambda: 'synthetic'
    orig = builtins.__import__
    def guarded(name, *args, **kwargs):
        level = args[2] if len(args) > 2 else kwargs.get('level', 0)
        if level == 0 and (name == 'app' or name.startswith('app.')): deny()
        return orig(name, *args, **kwargs)
    builtins.__import__ = guarded
    sys.path.append(sysconfig.get_paths()['purelib'])
    from jinja2 import Environment, DictLoader, select_autoescape
    html = (CANDIDATE / 'app/templates/wechat_share.html').read_text(encoding='utf-8-sig')
    source = ast.parse((CANDIDATE / 'app/services/wechat_poll_claim.py').read_text(encoding='utf-8-sig'))
    nodes = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'visible_message']
    if len(nodes) != 1: raise AssertionError('visible-message function missing')
    scope = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), '<candidate-ui>', 'exec'), scope)
    env = Environment(loader=DictLoader({'candidate.html': html, '_runtime_pause_notice.html': '', 'base.html':
        '{% block title %}{% endblock %}{% block extra_css %}{% endblock %}{% block content %}{% endblock %}{% block extra_js %}{% endblock %}'}),
        autoescape=select_autoescape(['html']))
    env.globals.update(url_for=lambda *_a, **_kw: '/synthetic', csrf_token=lambda: 'synthetic')

    class CandidateUI(unittest.TestCase):
        def test_visible_message(self):
            marker = 'a' * 64
            row = types.SimpleNamespace(id=1, status='sending', message='合成诊断\n[claim-sha256:' + marker + ']',
                order_no='SYNTHETIC', created_at=None, receiver_name='', receiver_wechat_id='',
                trigger_type='manual', image_path='', image_size=0, module_key='in_order')
            output = env.get_template('candidate.html').render(
                share_config=defaultdict(str), master_enabled=False, logs=[row], today_orders=[], today_count=0,
                helper_configured=False, helper_health=defaultdict(str), wecom_webhook='', latest_log=row,
                log_counts={'pending':1,'legacy_pending':1,'failed':0,'uncertain':1,'sent_today':0},
                log_filters={'status':'','limit':10}, log_total_count=1, status_label=lambda x:x,
                trigger_label=lambda x:x, message_summary=lambda x:x,
                visible_message=scope['visible_message'], format_file_size=lambda _x:'0', runtime_external_paused=False)
            self.assertIn('历史待人工核对', output)
            self.assertIn('待助手领取', output)
            self.assertIn('合成诊断', output)
            self.assertNotIn('claim-sha256', output)
            self.assertNotIn(marker, output)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CandidateUI)
    if suite.countTestCases() != 1: raise SystemExit('synthetic test list incomplete')
    return not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()


if __name__ == '__main__': raise SystemExit(main())


def test_wechat_candidate_ui_20261109_runs_against_actual_source(tmp_path):
    import os
    import runpy
    guard = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/verify_db_guard.py'))
    guard['require_owned_test_profile']()
    output = tmp_path / 'actual-source-output.txt'
    errors = tmp_path / 'actual-source-errors.txt'
    empty = tmp_path / 'empty-stdin.txt'
    empty.write_bytes(b'')
    import subprocess as child_process
    with empty.open('rb') as inp, output.open('wb') as out, errors.open('wb') as err:
        child = child_process.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(Path(__file__).resolve())],
            stdin=inp, stdout=out, stderr=err, env=dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8'), timeout=90)
    combined = output.read_text(encoding='utf-8') + errors.read_text(encoding='utf-8')
    assert child.returncode == 0, combined
    assert 'OK' in combined and 'Ran 0 tests' not in combined, combined

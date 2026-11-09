"""Prototype-only range checks; no conclusion about real WMS entry points."""
import ast
from decimal import Decimal, ROUND_HALF_UP, localcontext
import math
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def deny(*_args, **_kwargs):
    raise AssertionError('database and network forbidden')


class UnsafeMoneyRangeTests(unittest.TestCase):
    def test_backend_prototype_rejects_out_of_range(self):
        tree = ast.parse((ROOT / 'tests/money_candidate_20261109.py').read_text(encoding='utf-8-sig'))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'round_money_product')
        env = {'Decimal': Decimal, 'ROUND_HALF_UP': ROUND_HALF_UP, 'localcontext': localcontext, 'math': math}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), '<money>', 'exec'), env)
        with patch.object(socket.socket, 'connect', deny), patch.object(socket, 'getaddrinfo', deny), \
             patch.object(sqlite3, 'connect', deny):
            for qty, price in [('1e1000000', '1'), ('1e308', '2'), ('9007199254740993', '0.01')]:
                with self.subTest(qty=qty, price=price), self.assertRaises((ValueError, OverflowError)):
                    env['round_money_product'](qty, price)

    def test_frontend_prototype_rejects_out_of_range(self):
        node = shutil.which('node')
        self.assertIsNotNone(node)
        script = r"""const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const sandbox={window:{},BigInt:undefined};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),sandbox,{timeout:1000});
for(const pair of [['1e1000000','1'],['1e308','2'],['9007199254740993','0.01']])
  assert.throws(()=>sandbox.window.WMSMoney.product(...pair),undefined,pair.join(' * '));"""
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
        with patch.object(socket.socket, 'connect', deny), patch.object(socket, 'getaddrinfo', deny), \
             patch.object(sqlite3, 'connect', deny):
            result = subprocess.run([node, '-e', script, str(ROOT / 'tests/money_candidate_20261109.js')],
                                    env=env, capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(UnsafeMoneyRangeTests)
    if suite.countTestCases() != 2:
        raise SystemExit('synthetic test list is incomplete or empty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())

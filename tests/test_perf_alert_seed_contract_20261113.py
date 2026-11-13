"""Run actual seed/feature functions on a no-I/O model, not a WMS runtime."""
import ast
from contextlib import nullcontext
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def deny(*args, **kwargs):
    raise AssertionError('database, network and children forbidden in the seed model')


def function(path, name):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8-sig'))
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)


class AlertSeedSourceContract(unittest.TestCase):
    def check_seed(self, material_count):
        settings = {}
        guard_calls = []

        class Query:
            def filter_by(self, **kwargs):
                return self

            def first(self):
                return None

            def count(self):
                return material_count

        class Row:
            query = Query()

            def __init__(self, **values):
                self.id = 1
                self.__dict__.update(values)

        app_module = ModuleType('app')
        for name in ('Material', 'MaterialCategory', 'StockTransaction', 'Supplier', 'Unit', 'User', 'Warehouse'):
            setattr(app_module, name, type(name, (Row,), {}))
        app_module.set_system_setting = lambda key, value: settings.__setitem__(key, value)
        runtime = ModuleType('perf_runtime')
        runtime.require_runtime = lambda: guard_calls.append(True)
        session = SimpleNamespace(execute=lambda statement: [], add=lambda row: None,
                                  add_all=lambda rows: None, flush=lambda: None, commit=lambda: None)
        db = SimpleNamespace(engine=SimpleNamespace(url='sqlite:///:memory:'), session=session, text=lambda sql: sql)
        app = SimpleNamespace(app_context=nullcontext, config={})
        env = dict(os=os, SEED_MATERIALS=300, app=app,
                   get_system_setting=lambda key, default='': settings.get(key, default))
        nodes = [function('scripts/perf_baseline.py', '_seed_database'),
                 function('app/app.py', 'inventory_alert_enabled')]
        with patch.dict(sys.modules, {'app': app_module, 'perf_runtime': runtime}), \
                patch.dict(os.environ, clear=False), patch.object(sqlite3, 'connect', deny), \
                patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'bind', deny), \
                patch.object(socket, 'getaddrinfo', deny), patch.object(subprocess, 'Popen', deny):
            exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                         '<actual-perf-seed-and-alert-guard>', 'exec'), env)
            self.assertFalse(env['inventory_alert_enabled']())
            env['_seed_database'](app, db)
            self.assertTrue(guard_calls, 'The actual runtime guard call must remain before seeding')
            self.assertTrue(env['inventory_alert_enabled'](),
                            'Actual /alert guard would redirect instead of measuring the alert page')
            self.assertEqual(settings, {'inventory_alert_enabled': '1'})

    def test_fresh_synthetic_seed_enables_actual_alert_guard(self):
        self.check_seed(0)

    def test_already_seeded_memory_still_enables_actual_alert_guard(self):
        self.check_seed(300)


if __name__ == '__main__':
    unittest.main()

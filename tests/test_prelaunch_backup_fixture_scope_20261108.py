"""Check the legacy prelaunch fixture without importing WMS or touching backup files."""
import ast
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'tests' / 'test_browser_audit_20261027.py'


class FakePath:
    def __truediv__(self, _):
        return self

    def write_bytes(self, data):
        assert data == b'fixture'

    def __str__(self):
        return 'synthetic-fixture-path'


class FakeMonkeyPatch:
    def setattr(self, obj, name, value):
        setattr(obj, name, value)

    def setitem(self, obj, name, value):
        obj[name] = value


class FixtureScopeTest(TestCase):
    def test_prelaunch_fixture_excludes_existing_backup_sources(self):
        tree = ast.parse(TARGET.read_text(encoding='utf-8'))
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'test_prelaunch_instance_db')
        function.decorator_list = []
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        catalog = ModuleType('backup_catalog')
        catalog.get_backup_sources = lambda _manual: {'existing_backup_source': object()}
        app = SimpleNamespace(config={}, test_request_context=nullcontext)

        def fake_prelaunch():
            self.assertEqual(catalog.get_backup_sources('synthetic'), {},
                             'fixture must not enumerate existing backup sources')
            return {'checks': [{'code': 'DB-ACCESS', 'status': 'pass'}]}

        scope = {'wms': SimpleNamespace(app=app, _ai_prelaunch_checks=fake_prelaunch)}
        exec(compile(module, '<synthetic prelaunch fixture>', 'exec'), scope)
        with patch.dict('sys.modules', {'backup_catalog': catalog}):
            scope['test_prelaunch_instance_db'](None, FakePath(), FakeMonkeyPatch())


if __name__ == '__main__':
    main()

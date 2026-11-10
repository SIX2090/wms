"""Isolated source-level audit ordering regression; no WMS or database import."""
import ast
import ipaddress
from pathlib import Path
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]


def extract_function(path, name):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    function.decorator_list = []
    function.body = [n for n in function.body if not (isinstance(n, ast.ImportFrom) and n.module == 'app')]
    return function


class SyntheticSession:
    def __init__(self, fail_business):
        self.pending = []
        self.committed = []
        self.transactions = []
        self.fail_business = fail_business

    def add(self, value):
        self.pending.append(('audit', value))

    def delete(self, value):
        self.pending.append(('delete', value))

    def commit(self):
        if self.fail_business and any(kind == 'delete' for kind, _ in self.pending):
            raise RuntimeError('synthetic business commit failure')
        self.transactions.append([kind for kind, _ in self.pending])
        self.committed.extend(self.pending)
        self.pending.clear()

    def rollback(self):
        self.pending.clear()


class Lookup:
    def __init__(self, value):
        self.value = value

    def get_or_404(self, _id):
        return self.value


def setup(fail_business):
    session = SyntheticSession(fail_business)
    order = types.SimpleNamespace(status='pending')
    item = types.SimpleNamespace(in_order_id=1, material=types.SimpleNamespace(name='synthetic'),
                                 source_purchase_order_item=None)
    namespace = {
        'db': types.SimpleNamespace(session=session),
        'current_user': types.SimpleNamespace(is_authenticated=True, id=1),
        'request': types.SimpleNamespace(remote_addr='synthetic', headers={}),
        'ipaddress': ipaddress,
        'current_app': types.SimpleNamespace(config={'TRUSTED_PROXIES': []}),
        'OperationLog': lambda **values: values,
        'InOrder': types.SimpleNamespace(query=Lookup(order)),
        'InOrderItem': types.SimpleNamespace(query=Lookup(item)),
        'app': types.SimpleNamespace(logger=types.SimpleNamespace(error=lambda *args: None)),
        'api_error': lambda message: ('error', message),
        'jsonify': lambda value: value,
        'recalculate_order_total': lambda _order: None,
        'round_to_2_decimals': lambda value: value,
        'update_purchase_order_status': lambda _order: None,
    }
    # log_operation 内部调用 get_request_ip()；不提供实现时 NameError 会被
    # 其 try/except 吞掉，结果「删除成功但审计永不落库」——本用例正是在守这一点，
    # 因此必须提取真实实现，而不是塞一个恒真替身。
    functions = [extract_function('app/app.py', 'get_request_ip'),
                 extract_function('app/app.py', 'log_operation'),
                 extract_function('app/routes/in_order.py', 'delete_in_order_item')]
    module = ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[]))
    exec(compile(module, '<synthetic source extraction>', 'exec'), namespace)
    return session, namespace['delete_in_order_item']


class InboundAuditOrder(unittest.TestCase):
    def test_failed_delete_has_no_success_audit(self):
        session, delete_item = setup(True)
        response = delete_item(1, 2)
        self.assertEqual(response[1], 500)
        self.assertEqual(session.committed, [])
        self.assertEqual(session.pending, [])

    def test_successful_delete_then_best_effort_audit(self):
        session, delete_item = setup(False)
        response = delete_item(1, 2)
        self.assertEqual(response['status'], 'success')
        self.assertEqual([kind for kind, _ in session.committed], ['delete', 'audit'])


if __name__ == '__main__':
    unittest.main()

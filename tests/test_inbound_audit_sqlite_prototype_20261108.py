"""Run with -I -S -B: synthetic SQLite only, no WMS imports or network."""
import os
import subprocess
import sys

def main():
    import ast
    import builtins
    from decimal import Decimal, ROUND_HALF_UP
    import ipaddress
    import math
    from pathlib import Path
    import platform
    import socket
    import sqlite3
    import subprocess
    import sys
    import sysconfig
    import types
    import unittest


    def deny(*_args, **_kwargs):
        raise AssertionError('network, file databases, WMS and subprocesses are forbidden')


    class DeniedPopen:
        def __init__(self, *_args, **_kwargs):
            deny()


    original_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        if name == 'app' or name.startswith('app.'):
            deny()
        return original_import(name, *args, **kwargs)


    # Only the literal :memory: call in the creator below is allowed.
    memory_connect = sqlite3.connect
    sqlite3.connect = deny
    sqlite3.dbapi2.connect = deny
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    socket.getaddrinfo = deny
    subprocess.Popen = DeniedPopen
    platform.machine = lambda: 'synthetic'
    builtins.__import__ = guarded_import
    sys.path.append(sysconfig.get_paths()['purelib'])  # Do not process site .pth files.

    from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, create_engine, func, select, text
    from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


    ROOT = Path(__file__).resolve().parents[1]


    class Base(DeclarativeBase):
        pass


    class Order(Base):
        __tablename__ = 'orders'
        id: Mapped[int] = mapped_column(primary_key=True)
        status: Mapped[str] = mapped_column(String, nullable=False)
        total_amount: Mapped[int] = mapped_column(Integer, nullable=False)
        items = relationship('Item')


    class PurchaseOrder(Base):
        __tablename__ = 'purchase_order'
        id: Mapped[int] = mapped_column(primary_key=True)
        status: Mapped[str] = mapped_column(String, nullable=False)
        total_amount: Mapped[int] = mapped_column(Integer, nullable=False)
        items = relationship('Source')


    class Source(Base):
        __tablename__ = 'source'
        id: Mapped[int] = mapped_column(primary_key=True)
        received_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
        purchase_order_id: Mapped[int] = mapped_column(ForeignKey('purchase_order.id'))
        quantity: Mapped[int] = mapped_column(Integer, nullable=False)
        price: Mapped[int] = mapped_column(Integer, nullable=False)
        amount: Mapped[int] = mapped_column(Integer, nullable=False)
        purchase_order = relationship(PurchaseOrder, overlaps='items')


    class Item(Base):
        __tablename__ = 'item'
        id: Mapped[int] = mapped_column(primary_key=True)
        in_order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'))
        source_purchase_order_item_id: Mapped[int] = mapped_column(ForeignKey('source.id'))
        quantity: Mapped[int] = mapped_column(Integer, nullable=False)
        amount: Mapped[int] = mapped_column(Integer, nullable=False)
        source_purchase_order_item = relationship(Source)
        @property
        def material(self):
            return types.SimpleNamespace(name='synthetic')


    class Log(Base):
        __tablename__ = 'log'
        __table_args__ = (CheckConstraint("operation_type != 'reject'"),)
        id: Mapped[int] = mapped_column(primary_key=True)
        user_id: Mapped[int] = mapped_column(Integer)
        operation_type: Mapped[str] = mapped_column(String)
        operation_content: Mapped[str] = mapped_column(String)
        target_type: Mapped[str] = mapped_column(String)
        target_id: Mapped[int] = mapped_column(Integer)
        ip_address: Mapped[str] = mapped_column(String)


    class SessionProxy:
        def __init__(self, inner, fail_business):
            self.inner = inner
            self.fail_business = fail_business
        def __getattr__(self, key):
            return getattr(self.inner, key)
        def commit(self):
            if self.fail_business and not any(isinstance(obj, Log) for obj in self.inner.new):
                self.inner.flush()  # exercise an actual rollback of SQL writes
                raise RuntimeError('synthetic business commit failure')
            self.inner.commit()


    class Lookup:
        def __init__(self, session, model):
            self.session, self.model = session, model
        def get_or_404(self, identifier):
            value = self.session.get(self.model, identifier)
            if value is None:
                raise AssertionError('synthetic row missing')
            return value


    def extracted(path, name):
        tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
        function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
        function.decorator_list = []
        function.body = [n for n in function.body if not (isinstance(n, ast.ImportFrom) and n.module == 'app')]
        return function


    class InboundSQLiteRegression(unittest.TestCase):
        def setUp(self):
            self.engine = create_engine('sqlite://', creator=lambda: memory_connect(':memory:'))
            Base.metadata.create_all(self.engine)
            self.session = Session(self.engine)
            self.session.add_all([Order(id=1, status='pending', total_amount=17),
                                  Order(id=2, status='completed', total_amount=4),
                                  PurchaseOrder(id=1, status='completed', total_amount=0),
                                  # amount 必须给真实历史金额：现状实现只补 None（缺失）的行，
                                  # 不会重定价已存在的金额——显式 0 会被当成「确实 0 元」保留。
                                  Source(id=1, purchase_order_id=1, received_quantity=7, quantity=10, price=2, amount=20),
                                  Item(id=1, in_order_id=1, source_purchase_order_item_id=1, quantity=3, amount=12),
                                  Item(id=2, in_order_id=1, source_purchase_order_item_id=1, quantity=1, amount=5),
                                  Item(id=3, in_order_id=2, source_purchase_order_item_id=1, quantity=2, amount=4)])
            self.session.commit()
            databases = self.session.execute(text('PRAGMA database_list')).all()
            self.assertTrue(databases)
            self.assertTrue(all(row[1] in ('main', 'temp') and row[2] == '' for row in databases))

        def tearDown(self):
            self.session.close()
            self.engine.dispose()

        def invoke(self, *, fail_business=False, fail_audit=False, alias=False, item_id=1):
            def log_factory(**values):
                if fail_audit:
                    values['operation_type'] = 'reject'
                return Log(**values)
            Order.query = Lookup(self.session, Order)
            Item.query = Lookup(self.session, Item)
            ns = {
                'db': types.SimpleNamespace(session=SessionProxy(self.session, fail_business)),
                'current_user': types.SimpleNamespace(is_authenticated=True, id=1),
                'request': types.SimpleNamespace(remote_addr='synthetic', headers={}),
                'ipaddress': ipaddress,
                'current_app': types.SimpleNamespace(config={'TRUSTED_PROXIES': []}),
                'OperationLog': log_factory,
                'InOrder': Order,
                'InOrderItem': Item,
                'func': func, 'STOCK_COMPARE_EPSILON': 0.000001,
                'app': types.SimpleNamespace(logger=types.SimpleNamespace(error=lambda *args: None)),
                'api_error': lambda message: ('error', message),
                'jsonify': lambda value: value,
                'Decimal': Decimal, 'ROUND_HALF_UP': ROUND_HALF_UP, 'math': math,
            }
            funcs = [extracted('app/app.py', 'get_request_ip'),
                     extracted('app/utils.py', 'round_to_2_decimals'),
                     extracted('app/app.py', 'log_operation'),
                     extracted('app/app.py', 'update_purchase_order_status'),
                     extracted('app/utils.py', 'recalculate_order_total'),
                     extracted('app/routes/in_order.py', 'delete_in_order_item'),
                     extracted('app/routes/in_order.py', 'in_order_item_delete_alias')]
            module = ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[]))
            exec(compile(module, '<source AST>', 'exec'), ns)
            return ns['in_order_item_delete_alias' if alias else 'delete_in_order_item'](1, item_id)

        def state(self):
            self.session.expire_all()
            return (self.session.get(Source, 1).received_quantity,
                    len(self.session.scalars(select(Item)).all()),
                    len(self.session.scalars(select(Log)).all()),
                    self.session.get(Order, 1).total_amount,
                    self.session.get(PurchaseOrder, 1).status,
                    self.session.get(PurchaseOrder, 1).total_amount)

        def test_business_commit_failure_has_no_success_log(self):
            self.assertEqual(self.invoke(fail_business=True)[1], 500)
            self.assertEqual(self.state(), (7, 3, 0, 17, 'completed', 0))

        def test_success_updates_source_deletes_item_and_logs(self):
            self.assertEqual(self.invoke()['status'], 'success')
            self.assertEqual(self.state(), (4, 2, 1, 5, 'partial', 20))

        def test_log_failure_does_not_undo_business(self):
            self.assertEqual(self.invoke(fail_audit=True)['status'], 'success')
            self.assertEqual(self.state(), (4, 2, 0, 5, 'partial', 20))

        def test_alias_has_same_business_and_logging_behavior(self):
            self.assertEqual(self.invoke(alias=True)['status'], 'success')
            self.assertEqual(self.state(), (4, 2, 1, 5, 'partial', 20))

        def test_source_quantity_uses_actual_rounding(self):
            self.session.get(Source, 1).received_quantity = 7.25
            self.session.get(Item, 1).quantity = 3.20
            self.session.commit()
            self.assertEqual(self.invoke()['status'], 'success')
            self.assertEqual(self.state()[0], 4.05)

        def test_foreign_item_is_rejected_without_writes(self):
            self.assertEqual(self.invoke(item_id=3)[0], 'error')
            self.assertEqual(self.state(), (7, 3, 0, 17, 'completed', 0))

        def test_completed_order_is_rejected_without_writes(self):
            self.session.get(Order, 1).status = 'completed'
            self.session.commit()
            self.assertEqual(self.invoke()[0], 'error')
            self.assertEqual(self.state(), (7, 3, 0, 17, 'completed', 0))


    suite = unittest.defaultTestLoader.loadTestsFromTestCase(InboundSQLiteRegression)
    if suite.countTestCases() != 7:
        raise RuntimeError('合成入库测试清单不完整或为空')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())


def test_inbound_audit_sqlite_in_isolated_process():
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', __file__],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert result.returncode == 0, result.stderr


if __name__ == '__main__':
    main()

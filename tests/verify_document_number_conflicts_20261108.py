"""Synthetic numbering regressions; execute with python -I -S -B -X utf8.

This runs extracted source with synthetic models and a new SQLite memory DB.
It does not import WMS, open any database file, or use network/services.
"""
import os
import subprocess
import sys


def main():
    import ast
    import builtins
    import copy
    import datetime
    from functools import wraps
    import hashlib
    import json
    from pathlib import Path
    import platform
    import re
    import socket
    import sqlite3
    import sysconfig
    import threading
    import types
    import unittest

    def deny(*_args, **_kwargs):
        raise AssertionError('真实应用、文件数据库、网络及子进程均禁止')

    class DeniedPopen:
        def __init__(self, *_args, **_kwargs):
            deny()

    real_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        level = args[3] if len(args) > 3 else kwargs.get('level', 0)
        if level == 0 and (name == 'app' or name.startswith('app.')):
            return deny()
        return real_import(name, *args, **kwargs)

    memory_connect = sqlite3.connect
    sqlite3.connect = sqlite3.dbapi2.connect = deny
    socket.socket.connect = socket.socket.connect_ex = deny
    socket.create_connection = socket.getaddrinfo = deny
    subprocess.Popen = DeniedPopen
    platform.machine = lambda: 'synthetic'
    builtins.__import__ = guarded_import
    sys.path.append(sysconfig.get_paths()['purelib'])
    from sqlalchemy import Date, Integer, String, UniqueConstraint, cast, create_engine, event, func, select, text
    from sqlalchemy.exc import IntegrityError, OperationalError
    from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

    root = Path(__file__).resolve().parents[1]
    core = ast.parse((root / 'app/app.py').read_text(encoding='utf-8-sig'))
    route = ast.parse((root / 'app/routes/in_order.py').read_text(encoding='utf-8-sig'))
    web_service = ast.parse((root / 'app/services/web_document_idempotency.py').read_text(encoding='utf-8-sig'))

    def find(tree, name):
        nodes = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
        if len(nodes) != 1:
            raise AssertionError('源码函数不存在或不唯一：' + name)
        nodes[0].decorator_list = []
        return nodes[0]

    class Base(DeclarativeBase):
        pass

    class InOrder(Base):
        __tablename__ = 'synthetic_in_order'
        id: Mapped[int] = mapped_column(primary_key=True)
        order_no: Mapped[str] = mapped_column(String, unique=True)
        date: Mapped[datetime.date] = mapped_column(Date)
        business_type: Mapped[str] = mapped_column(String)
        operator_id: Mapped[int] = mapped_column(Integer)
        status: Mapped[str] = mapped_column(String, default='pending')

    class OutOrder(Base):
        __tablename__ = 'synthetic_out_order'
        id: Mapped[int] = mapped_column(primary_key=True)
        order_no: Mapped[str] = mapped_column(String, unique=True)

    class SalesOrder(Base):
        __tablename__ = 'synthetic_sales_order'
        id: Mapped[int] = mapped_column(primary_key=True)
        order_no: Mapped[str] = mapped_column(String, unique=True)

    class MobileApiRequest(Base):
        __tablename__ = 'synthetic_mobile_request'
        __table_args__ = (UniqueConstraint('user_id', 'endpoint', 'request_key'),)
        id: Mapped[int] = mapped_column(primary_key=True)
        user_id: Mapped[int] = mapped_column(Integer)
        endpoint: Mapped[str] = mapped_column(String)
        request_key: Mapped[str] = mapped_column(String)
        status_code: Mapped[int] = mapped_column(Integer)
        response_json: Mapped[str] = mapped_column(String)

    class FixedDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 8, tzinfo=tz)

    # Extract the actual create/edit branch, preserving its 409 and flush.
    add = find(route, 'add_in_order')
    candidates = [node for node in ast.walk(add) if isinstance(node, ast.If)
                  and isinstance(node.test, ast.Name) and node.test.id == 'order_id'
                  and any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                          and n.func.attr == 'get' for n in ast.walk(node))]
    if len(candidates) != 1:
        raise AssertionError('入库单创建分支不唯一，需重新审查')
    branch = candidates[0]
    wrapper = ast.parse('''def save_synthetic(order_id, order_no, business_type):
    pass
    return {'status': 'success', 'id': order.id, 'order_no': order.order_no}
''').body[0]
    wrapper.body[0] = branch

    class NumberingRegression(unittest.TestCase):
        def setUp(self):
            self.engine = create_engine('sqlite://', creator=lambda: memory_connect(':memory:'))
            Base.metadata.create_all(self.engine)
            self.session = Session(self.engine)
            self.assertTrue(all(row[1] in ('main', 'temp') and row[2] == ''
                                for row in self.session.execute(text('PRAGMA database_list'))))
            InOrder.query = self.session.query(InOrder)
            OutOrder.query = self.session.query(OutOrder)
            SalesOrder.query = self.session.query(SalesOrder)
            MobileApiRequest.query = self.session.query(MobileApiRequest)
            self.env = {
                'InOrder': InOrder, 'OutOrder': OutOrder, 'SalesOrder': SalesOrder,
                'MobileApiRequest': MobileApiRequest, 'json': json, 'wraps': wraps,
                'db': types.SimpleNamespace(session=self.session, cast=cast, Integer=Integer, func=func),
                'datetime': FixedDatetime, 'date': datetime.date, 're': re,
                '_order_no_generation_lock': threading.Lock(),
                'current_user': types.SimpleNamespace(id=1),
                'api_error': lambda message, code=None: {'status': 'error', 'msg': message, 'code': code},
                'app': types.SimpleNamespace(logger=types.SimpleNamespace(exception=lambda *_: None)),
                'request': types.SimpleNamespace(headers={'X-Idempotency-Key': 'synthetic-request'},
                                                 get_json=lambda **_kwargs: {}),
                'jsonify': lambda payload: payload,
            }
            helpers = [node for node in core.body if isinstance(node, ast.FunctionDef)
                       and node.name == '_numbering_existing_max']
            module = ast.fix_missing_locations(ast.Module(body=[*helpers,
                find(core, 'generate_order_no'), find(core, '_generate_order_no_locked'),
                find(core, 'generate_sales_order_no'), find(core, 'mobile_api_idempotent'), wrapper], type_ignores=[]))
            exec(compile(module, '<synthetic-numbering-source>', 'exec'), self.env)

        def tearDown(self):
            self.session.close()
            self.engine.dispose()

        def create(self, order_no=''):
            result = self.env['save_synthetic'](None, order_no, '采购入库')
            if result['status'] == 'success':
                self.session.commit()
            return result

        def test_distinct_creates_do_not_conflict_on_same_preview(self):
            # 两个独立旧客户端可能持有同一个预览；新建时应由服务端分配正式号。
            preview_a = preview_b = 'IN26110001'
            first = self.create(preview_a)
            second = self.create(preview_b)
            self.assertEqual(first['status'], 'success')
            self.assertEqual(second['status'], 'success', '不同创建请求不应因为预览号冲突而失败')
            self.assertNotEqual(first['id'], second['id'])
            self.assertNotEqual(first['order_no'], second['order_no'])

        def test_allocated_deleted_number_is_not_reused(self):
            first = self.create()
            second = self.create()
            self.assertNotEqual(first['order_no'], second['order_no'])
            self.session.delete(self.session.get(InOrder, second['id']))
            self.session.commit()
            third = self.create()
            self.assertNotEqual(third['order_no'], second['order_no'], '已分配后删除的编号不得复用')

        def test_sales_sequence_exceeding_four_digits(self):
            self.session.add_all([SalesOrder(order_no='SO26119999'), SalesOrder(order_no='SO261110000')])
            self.session.commit()
            self.assertEqual(self.env['generate_sales_order_no'](), 'SO261110001')

        def test_outbound_nonmonotonic_ids_do_not_reissue_existing_number(self):
            self.session.add_all([OutOrder(order_no='OU26110005'), OutOrder(order_no='OU26110077'),
                                  OutOrder(order_no='OU26110004')])
            self.session.commit()
            number = self.env['generate_order_no']('OUT')
            assigned = set(self.session.scalars(select(OutOrder.order_no)))
            self.assertNotIn(number, assigned, '不能按最后插入 ID 回退到已分配号码')

        def test_sequential_unprovided_numbers_are_distinct_control(self):
            first = self.create()
            second = self.create()
            self.assertEqual(first['status'], 'success')
            self.assertEqual(second['status'], 'success')
            self.assertNotEqual(first['order_no'], second['order_no'])

        def test_mobile_receipt_failure_then_retry_does_not_duplicate_business(self):
            session = self.session
            class ReceiptCommitFailsOnce:
                def __init__(self):
                    self.fail = True
                def __getattr__(self, name):
                    return getattr(session, name)
                def commit(self):
                    if self.fail and any(isinstance(item, MobileApiRequest) for item in session.new):
                        self.fail = False
                        raise RuntimeError('synthetic receipt commit failure')
                    return session.commit()

            class Response:
                status_code = 200
                def __init__(self, payload):
                    self.payload = payload
                def get_json(self, **_kwargs):
                    return self.payload

            self.env['db'].session = ReceiptCommitFailsOnce()
            def business(_user):
                return Response(self.create())

            decorated = self.env['mobile_api_idempotent']('inbound')(business)
            user = types.SimpleNamespace(id=1)
            first = decorated(user)
            self.assertEqual(first.status_code, 200)
            second = decorated(user)  # 模拟首个响应丢失后以相同 requestId 重试。
            self.assertEqual(second.status_code, 200)
            self.assertEqual(len(list(session.scalars(select(InOrder.id)))), 1,
                             '幂等回执失败后重试不应重复提交业务单据')

        def test_mobile_reused_key_with_changed_payload_must_not_succeed(self):
            class Response:
                status_code = 200
                def __init__(self, payload):
                    self.payload = payload
                def get_json(self, **_kwargs):
                    return self.payload

            request = types.SimpleNamespace(headers={'X-Idempotency-Key': 'same-key'}, body={'items': [1]})
            request.get_json = lambda **_kwargs: request.body
            self.env['request'] = request
            decorated = self.env['mobile_api_idempotent']('inbound')(
                lambda _user: Response(self.create()))
            self.assertEqual(decorated(types.SimpleNamespace(id=1)).status_code, 200)
            request.body = {'items': [2]}
            _payload, status = decorated(types.SimpleNamespace(id=1))
            self.assertEqual(status, 409, '同请求号更换业务内容必须提示冲突')
            self.assertEqual(len(list(self.session.scalars(select(InOrder.id)))), 1)

        def test_existing_web_atomic_receipt_replays_and_rejects_changed_payload(self):
            class SyntheticContext:
                def pop(self, name, default=None):
                    return self.__dict__.pop(name, default)
            request = types.SimpleNamespace(headers={'X-Idempotency-Key': 'synthetic-web-key'},
                                            is_json=True, path='/in_order/add', body={'items': [1]})
            request.get_json = lambda **_kwargs: request.body
            self.env.update({
                'request': request, 'g': SyntheticContext(), 'hashlib': hashlib,
                'IntegrityError': IntegrityError, 'OperationalError': OperationalError,
                'current_user': types.SimpleNamespace(id=1, is_authenticated=True),
                'jsonify': lambda payload=None, **kwargs: payload if payload is not None else kwargs,
            })
            module = ast.fix_missing_locations(ast.Module(body=[
                find(web_service, '_document_idempotent'), find(web_service, 'stage_document_response')],
                type_ignores=[]))
            exec(compile(module, '<synthetic-web-idempotency-source>', 'exec'), self.env)

            def business():
                result = self.env['save_synthetic'](None, '', '采购入库')
                self.env['stage_document_response'](result)
                self.session.commit()
                return result

            decorated = self.env['_document_idempotent'](business, mobile=False)
            first = decorated()
            self.assertEqual(first['status'], 'success')
            replay, status = decorated()
            self.assertEqual(status, 200)
            self.assertEqual(replay, first)
            request.body = {'items': [2]}
            conflict, status = decorated()
            self.assertEqual(status, 409)
            self.assertEqual(conflict['status'], 'error')
            self.assertEqual(len(list(self.session.scalars(select(InOrder.id)))), 1)

        def test_web_receipt_write_failure_rolls_back_document_and_retry_succeeds(self):
            class SyntheticContext:
                def pop(self, name, default=None):
                    return self.__dict__.pop(name, default)
            request = types.SimpleNamespace(headers={'X-Idempotency-Key': 'receipt-failure'},
                                            is_json=True, path='/in_order/add', body={'items': [1]})
            request.get_json = lambda **_kwargs: request.body
            self.env.update({
                'request': request, 'g': SyntheticContext(), 'hashlib': hashlib,
                'IntegrityError': IntegrityError, 'OperationalError': OperationalError,
                'current_user': types.SimpleNamespace(id=1, is_authenticated=True),
                'jsonify': lambda payload=None, **kwargs: payload if payload is not None else kwargs,
            })
            module = ast.fix_missing_locations(ast.Module(body=[
                find(web_service, '_document_idempotent'), find(web_service, 'stage_document_response')],
                type_ignores=[]))
            exec(compile(module, '<synthetic-web-idempotency-source>', 'exec'), self.env)

            def business():
                result = self.env['save_synthetic'](None, '', '采购入库')
                self.env['stage_document_response'](result)
                self.session.commit()
                return result

            failed = [False]
            def inject_receipt_failure(_conn, _cursor, statement, _parameters, _context, _many):
                if not failed[0] and statement.lstrip().upper().startswith('UPDATE SYNTHETIC_MOBILE_REQUEST'):
                    failed[0] = True
                    raise RuntimeError('synthetic receipt finalization failed')
            event.listen(self.engine, 'before_cursor_execute', inject_receipt_failure)
            decorated = self.env['_document_idempotent'](business, mobile=False)
            try:
                with self.assertRaisesRegex(RuntimeError, 'synthetic receipt finalization failed'):
                    decorated()
                self.assertTrue(failed[0])
                self.assertEqual(len(list(self.session.scalars(select(InOrder.id)))), 0)
                self.assertEqual(len(list(self.session.scalars(select(MobileApiRequest.id)))), 0)
                first = decorated()
                replay, status = decorated()
                self.assertEqual(status, 200)
                self.assertEqual(replay, first)
                self.assertEqual(len(list(self.session.scalars(select(InOrder.id)))), 1)
            finally:
                event.remove(self.engine, 'before_cursor_execute', inject_receipt_failure)

        def test_synthetic_purchase_receipt_allocator_candidate(self):
            # This deliberately transforms only a copied AST. It is a design
            # experiment, not the real WMS route or a production migration.
            self.session.execute(text('CREATE TABLE synthetic_counter '
                                      '(prefix TEXT PRIMARY KEY, value INTEGER NOT NULL)'))
            self.session.execute(text('CREATE TABLE synthetic_subcontract_receive '
                                      '(receive_no TEXT NOT NULL)'))
            self.session.add(InOrder(order_no='IN26119999', date=datetime.date(2026, 11, 8),
                                     business_type='采购入库', operator_id=1))
            self.session.commit()

            def allocate(prefix):
                base = prefix + '2611'
                inserted = self.session.execute(text(
                    'INSERT OR IGNORE INTO synthetic_counter(prefix, value) VALUES(:prefix, 0)'),
                    {'prefix': base}).rowcount
                if inserted:
                    rows = list(self.session.scalars(select(InOrder.order_no).where(InOrder.order_no.like(base + '%'))))
                    if prefix == 'SR':
                        rows.extend(self.session.scalars(text(
                            'SELECT receive_no FROM synthetic_subcontract_receive WHERE receive_no LIKE :pattern'),
                            {'pattern': base + '%'}))
                    numbers = [int(number[len(base):]) for number in rows
                               if number.startswith(base) and number[len(base):].isdecimal()]
                    self.session.execute(text('UPDATE synthetic_counter SET value=:value WHERE prefix=:prefix'),
                                         {'value': max(numbers, default=0), 'prefix': base})
                self.session.execute(text('UPDATE synthetic_counter SET value=value+1 WHERE prefix=:prefix'),
                                     {'prefix': base})
                current = self.session.execute(text('SELECT value FROM synthetic_counter WHERE prefix=:prefix'),
                                               {'prefix': base}).scalar_one()
                return f'{base}{current:04d}'

            candidate = copy.deepcopy(wrapper)
            candidate.body[0].orelse = ast.parse('''
prefix = {'采购入库': 'IN', '产品入库': 'PI', '其他入库': 'OI', '销售退货入库': 'SR'}[business_type]
order_no = allocate(prefix)
order = InOrder(order_no=order_no, date=date.today(), business_type=business_type, operator_id=current_user.id)
db.session.add(order)
db.session.flush()
''').body
            self.env['allocate'] = allocate
            exec(compile(ast.fix_missing_locations(ast.Module(body=[candidate], type_ignores=[])),
                         '<synthetic-candidate-route>', 'exec'), self.env)
            save = self.env['save_synthetic']
            first = save(None, 'IN26110001', '采购入库')
            self.assertEqual(first['order_no'], 'IN261110000')
            self.session.commit()
            second = save(None, 'IN26110001', '采购入库')
            self.assertEqual(second['order_no'], 'IN261110001')
            self.session.commit()
            edited = save(first['id'], 'unexpected-preview', '采购入库')
            self.assertEqual(edited['order_no'], first['order_no'])
            self.session.commit()
            self.session.delete(self.session.get(InOrder, second['id']))
            self.session.commit()
            failed = save(None, '', '采购入库')
            self.assertEqual(failed['order_no'], 'IN261110002')
            self.session.rollback()
            retry = save(None, '', '采购入库')
            self.assertEqual(retry['order_no'], 'IN261110002')
            self.session.commit()

            # SR shares a prefix with subcontract receives, so historical seed
            # must consider both sources, not just the inbound table.
            self.session.execute(text('INSERT INTO synthetic_subcontract_receive VALUES (:number)'),
                                 {'number': 'SR26110099'})
            sales_return = save(None, '', '销售退货入库')
            self.assertEqual(sales_return['order_no'], 'SR26110100')
            self.session.rollback()

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NumberingRegression)
    if suite.countTestCases() != 10:
        raise RuntimeError('合成单号回归清单不完整或为空')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


def test_document_numbering_in_isolated_process():
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', __file__],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert result.returncode == 0, result.stderr


if __name__ == '__main__':
    main()

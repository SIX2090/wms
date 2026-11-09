"""Extracted native inbound/outbound route experiment; never imports WMS.

Uses a new in-memory SQLite DB, synthetic ORM models and Flask requests. Only
the AST copies are adapted; this is not a product fix or all-seven validation.
"""
import os
import subprocess
import sys


def main():
    import ast
    import builtins
    import copy
    import datetime
    import hashlib
    import json
    import logging
    from functools import wraps
    from pathlib import Path
    import platform
    import secrets
    import socket
    import sqlite3
    import sysconfig
    import threading
    import types
    import unittest
    from concurrent.futures import ThreadPoolExecutor

    def deny(*_args, **_kwargs):
        raise AssertionError('application import, file DB, network and subprocess forbidden')
    actual_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        level = args[3] if len(args) > 3 else kwargs.get('level', 0)
        if level == 0 and (name == 'app' or name.startswith('app.')):
            deny()
        return actual_import(name, *args, **kwargs)
    builtins.__import__ = guarded_import
    connect_memory = sqlite3.connect
    sqlite3.connect = sqlite3.dbapi2.connect = deny
    socket.socket.connect = socket.socket.connect_ex = deny
    socket.create_connection = socket.getaddrinfo = deny
    class DeniedPopen:
        def __init__(self, *_args, **_kwargs):
            deny()
    subprocess.Popen = DeniedPopen
    platform.machine = lambda: 'synthetic'
    sys.path.append(sysconfig.get_paths()['purelib'])
    from flask import Flask, g, has_request_context, jsonify, request
    from pydantic import BaseModel, Field
    from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, create_engine, event, text
    from sqlalchemy.exc import IntegrityError, OperationalError
    from sqlalchemy.orm import declarative_base, relationship, scoped_session, sessionmaker

    Base = declarative_base()
    class Flexible:
        def __init__(self, **values):
            for name, value in values.items():
                setattr(self, name, value)
    class InOrder(Flexible, Base):
        __tablename__ = 'synthetic_inbound'
        id = Column(Integer, primary_key=True)
        order_no = Column(String, unique=True)
    class OutOrder(Flexible, Base):
        __tablename__ = 'synthetic_outbound'
        id = Column(Integer, primary_key=True)
        order_no = Column(String, unique=True)
    class InItem(Flexible, Base):
        __tablename__ = 'synthetic_in_item'
        id = Column(Integer, primary_key=True)
        in_order_id = Column(Integer)
    class OutItem(Flexible, Base):
        __tablename__ = 'synthetic_out_item'
        id = Column(Integer, primary_key=True)
        out_order_id = Column(Integer)
        amount = Column(Float)
    class Material(Base):
        __tablename__ = 'synthetic_material'
        id = Column(Integer, primary_key=True)
        code = Column(String, unique=True)
        name = Column(String)
        stock = Column(Float)
        price = Column(Float)
        spec = ''
        unit = None
        category = None
    class StockLedger(Base):
        __tablename__ = 'synthetic_stock_ledger'
        id = Column(Integer, primary_key=True)
        delta = Column(Float)
    class PrintJob(Base):
        __tablename__ = 'synthetic_print_job'
        id = Column(Integer, primary_key=True)
        kind = Column(String)
        target_id = Column(Integer)
    class AdjustmentDraft(Base):
        __tablename__ = 'synthetic_adjustment_draft'
        id = Column(Integer, primary_key=True)
    class AIConversation(Base):
        __tablename__ = 'synthetic_ai_conversation'
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer)
        title = Column(String)
        touches = Column(Integer, default=0)
        def touch_activity(self):
            self.touches = (self.touches or 0) + 1
    class AIMessage(Flexible, Base):
        __tablename__ = 'synthetic_ai_message'
        id = Column(Integer, primary_key=True)
        conversation_id = Column(Integer)
        role = Column(String)
        content = Column(String)
    class OpeningStock(Base):
        __tablename__ = 'synthetic_opening'
        id = Column(Integer, primary_key=True)
        material_id = Column(Integer)
        warehouse_id = Column(Integer)
        warehouse = Column(String)
        date = Column(Date)
        quantity = Column(Float)
        price = Column(Float)
        amount = Column(Float)
        remark = Column(String)
        operator_id = Column(Integer)
        doc_id = Column(Integer)
    class Warehouse(Base):
        __tablename__ = 'synthetic_warehouse'
        id = Column(Integer, primary_key=True)
        code = Column(String)
        name = Column(String)
        status = Column(String)
    class OpeningDoc(Base):
        __tablename__ = 'synthetic_opening_doc'
        id = Column(Integer, primary_key=True)
        number = Column(String, unique=True)
    class InventoryCheck(Base):
        __tablename__ = 'synthetic_check'
        id = Column(Integer, primary_key=True)
        check_no = Column(String)
        warehouse = Column(String)
        status = Column(String)
        scanned = Column(Integer, default=0)
        items = None
    class InventoryCheckScan(Flexible, Base):
        __tablename__ = 'synthetic_check_scan'
        id = Column(Integer, primary_key=True)
        check_no = Column(String, unique=True)
    class InventoryCheckScanItem(Flexible, Base):
        __tablename__ = 'synthetic_check_scan_item'
        id = Column(Integer, primary_key=True)
        check_scan_id = Column(Integer)
    class Receipt(Base):
        __tablename__ = 'synthetic_receipt'
        __table_args__ = (UniqueConstraint('user_id', 'endpoint', 'request_key'),)
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer)
        endpoint = Column(String)
        request_key = Column(String)
        status_code = Column(Integer)
        response_json = Column(String)
    class SyntheticUser(Base):
        __tablename__ = 'synthetic_user'
        id = Column(Integer, primary_key=True)
        role = Column(String)
        is_active = Column(Integer)
    class ApiToken(Base):
        __tablename__ = 'synthetic_api_token'
        id = Column(Integer, primary_key=True)
        token = Column(String, unique=True)
        user_id = Column(Integer, ForeignKey('synthetic_user.id'))
        revoked = Column(Integer, default=False)
        expires_at = Column(DateTime)
        last_used_at = Column(DateTime)
        user = relationship(SyntheticUser)

    nonce = secrets.token_hex(16)
    memory_uri = 'file:wms_native_' + nonce + '?mode=memory&cache=shared'
    def open_memory():
        if len(nonce) != 32 or any(c not in '0123456789abcdef' for c in nonce):
            raise AssertionError('invalid private memory DB identity')
        conn = connect_memory(memory_uri, uri=True, timeout=0.2, check_same_thread=False)
        rows = conn.execute('PRAGMA database_list').fetchall()
        if not rows or any(name not in ('main', 'temp') or path != '' for _, name, path in rows):
            conn.close()
            raise AssertionError('database is not private memory')
        return conn
    engine = create_engine('sqlite://', creator=open_memory)
    session = scoped_session(sessionmaker(bind=engine))
    Base.query = session.query_property()
    Base.metadata.create_all(engine)
    session.add(Material(code='M', name='合成物料', stock=10, price=2))
    session.commit()
    assert all(not row[2] for row in session.execute(text('PRAGMA database_list')))
    app = Flask('synthetic_native')
    user = types.SimpleNamespace(id=1, role='warehouse', is_authenticated=True)
    warehouse = types.SimpleNamespace(name='合成仓')
    OutOrder.items = property(lambda order: session.query(OutItem).filter_by(out_order_id=order.id).all())
    voice_calls = []
    voice_hook = [None]
    assistant_hook = [None]
    intent_hook = [None]
    def voice_parse(text):
        voice_calls.append(bool(getattr(g, 'web_document_receipt', None)))
        if voice_hook[0] is not None:
            voice_hook[0]()
        return {'raw': text, 'normalized': text, 'keyword': '合成物料', 'spec_hint': '', 'quantity': 2, 'unit': '个'}
    def voice_match(_keyword, _spec, _warehouse):
        material = Material.query.one()
        return {'status': 'success', 'material': material, 'root': '合成物料',
                'matches': [{'material': material, 'score': 100, 'strategy': 'synthetic'}],
                'strategies_tried': ['synthetic']}

    def parse_lines(payload):
        material = Material.query.filter_by(code='M').first()
        lines = payload.get('lines') or []
        if not lines:
            return None, '明细不能为空'
        return [(material, float(row['quantity']), row) for row in lines], None
    def apply_delta(material, delta, **_kwargs):
        if material.stock + delta < 0:
            return False, '库存不足'
        material.stock += delta
        session.add(StockLedger(delta=delta))
        return True, ''
    def enqueue_print(kind, target_id, _warehouse, **_kwargs):
        session.add(PrintJob(kind=kind, target_id=target_id))
    def candidate_number(prefix):
        model = InOrder if prefix == 'IN' else InventoryCheckScan if prefix == 'CS' else OutOrder
        return prefix + str(session.query(model).count() + 1).zfill(4)
    def api_success(data=None, message='操作成功'):
        return jsonify({'status': 'success', 'success': True, 'msg': message,
                        'message': message, 'data': data or {}})
    def api_error(message, status_code=400):
        return jsonify({'status': 'error', 'success': False, 'msg': message, 'message': message}), status_code
    def opening_revision(opening, _actor):
        return f'{opening.id}:{opening.quantity}'
    def update_opening(opening, material, quantity, price, amount, remark, *args, **kwargs):
        if opening is None:
            wh = args[0]
            opening = OpeningStock(material_id=material.id, warehouse_id=wh.id, warehouse=wh.name,
                                   date=args[1], quantity=0, price=0, amount=0, doc_id=kwargs.get('doc_id'))
            session.add(opening)
        delta = quantity - opening.quantity
        opening.quantity, opening.price, opening.amount, opening.remark = quantity, price, amount, remark
        material.stock += delta
        session.add(StockLedger(delta=delta))
        return opening, delta
    class OpeningLineEditInput:
        @staticmethod
        def model_validate(_payload):
            return None
    def opening_compat(_date, _generator):
        doc = OpeningDoc.query.filter_by(number='QSLEGACY').first()
        if doc is None:
            doc = OpeningDoc(number='QSLEGACY')
            session.add(doc)
            session.flush()
        return doc
    def adjustment_draft(_message):
        row = AdjustmentDraft()
        session.add(row)
        session.commit()
        return {'order_no': 'ADJ-SYNTHETIC', 'items': [], 'url': '/synthetic',
                'adjustment_type': '盘盈'}, None
    def synthetic_intent(_message):
        if intent_hook[0] is not None:
            intent_hook[0]()
        return {'intent': 'create_adjustment_draft', 'params': {}}

    env = {'request': request, 'g': g, 'jsonify': jsonify, 'json': json, 'hashlib': hashlib, 'wraps': wraps,
           'IntegrityError': IntegrityError, 'OperationalError': OperationalError,
           'db': types.SimpleNamespace(session=session, engine=engine), 'MobileApiRequest': Receipt,
           'current_user': user, 'app': app, 'InOrder': InOrder, 'OutOrder': OutOrder,
           'InOrderItem': InItem, 'OutOrderItem': OutItem, 'Contract': object, 'Supplier': object,
           'Department': object, 'api_json_success': api_success, 'api_json_error': api_error,
           'generate_order_no': candidate_number, 'parse_api_lines': parse_lines,
           'parse_float_value': lambda value, default=0: float(value if value is not None else default),
           'round_to_2_decimals': lambda value: round(float(value), 2),
           'location_management_enabled': lambda: False, 'location_required_on_save': lambda: False,
           'purchase_in_order_requires_order': lambda: False, 'allow_negative_stock': lambda: False,
           'resolve_request_warehouse': lambda _payload: (warehouse, ''),
           'resolve_item_contract': lambda _order: (None, None, None),
           '_decode_evidence': lambda _payload: ([], ''), '_save_evidence': lambda *_args: None,
           '_native_document_location': lambda _lines: ('', ''),
           '_native_outbound_stock_error': lambda lines, _warehouse:
               '库存不足' if any(m.stock < qty for m, qty, _line in lines) else '',
           'apply_stock_delta': apply_delta, 'enqueue_auto_print_job': enqueue_print,
           'InventoryCheck': InventoryCheck, 'InventoryCheckScan': InventoryCheckScan,
           'InventoryCheckScanItem': InventoryCheckScanItem, 'Material': Material,
           'AIConversation': AIConversation, 'AIMessage': AIMessage,
           'has_request_context': has_request_context, 'get_default_warehouse': lambda: warehouse,
           'ApiToken': ApiToken, 'datetime': datetime.datetime, 'timedelta': datetime.timedelta,
           'TOKEN_HASH_PREFIX': 'sha256:',
           'LAST_USED_FLUSH_SECONDS': 300, 'RENEW_THRESHOLD_SECONDS': 86400, 'TOKEN_TTL_DAYS': 7,
           'validate_inventory_warehouse': lambda _value: (warehouse, ''), 'selectinload': lambda _value: None,
           'get_warehouse_stock_quantities': lambda _warehouse: {Material.query.one().id: Material.query.one().stock},
           '_find_active_check_batch': lambda *_args: None,
           '_create_adjustment_drafts_from_check_scan': lambda *_args: None,
           '_apply_scan_to_batch': lambda batch, *_args, **_kwargs: setattr(batch, 'scanned', batch.scanned + 1),
           'OpeningStock': OpeningStock, 'OpeningLineEditInput': OpeningLineEditInput,
           'Warehouse': Warehouse, '_opening_stock_compat_doc': opening_compat,
           '_parse_opening_stock_date': lambda _value: datetime.date.today(),
           '_find_material_by_name_spec': lambda *_args: None, '_resolve_material_unit': lambda *_args: None,
           '_generate_auto_material_code': lambda: 'SYNTHETIC-AUTO',
           'AI_CAPABILITY_BUSINESS_ENDPOINTS': {}, '_ai_feature_enabled': lambda *_args: True,
           '_ai_global_enabled': lambda: True, '_ai_permission_denied_text': lambda *_args: '无权限',
           '_ai_rollout_mode': lambda: 'enabled',
           'evaluate_rollout_access': lambda **_kwargs: types.SimpleNamespace(allowed=True),
           'get_ai_tool_spec': lambda *_args: types.SimpleNamespace(risk_level='draft'),
           'is_ai_capability_allowed_for_role': lambda *_args, **_kwargs: True,
           '_mobile_capability_allowed': lambda *_args, **_kwargs: True,
           '_VOICE_MATERIAL_KEYS': ('material', 'material_code', 'material_name', 'keyword', 'spec', 'quantity', 'qty'),
           '_VOICE_FILTER_KEYS': ('material', 'material_code', 'material_name', 'keyword', 'spec', 'quantity', 'qty',
                                  'order_no', 'date', 'start_date', 'end_date', 'q'),
           '_ai_call_llm_intent': synthetic_intent,
           '_ai_guess_keyword': lambda _message: '', '_ai_supplier_profile_response': lambda *_args: None,
           '_ai_create_adjustment_draft': adjustment_draft,
           '_ai_json_response': lambda message, *_args: jsonify({'reply': message, 'cards': []}),
           '_slim_mobile_cards': lambda cards: cards,
           '_parse_voice_out_text_llm': voice_parse, '_parse_voice_out_text': voice_parse,
           '_match_voice_material': voice_match,
           'normalize_stock_quantity': lambda value: float(value), '_apply_opening_stock_balance': update_opening,
           'opening_line_revision': opening_revision,
           'opening_line_revision_matches': lambda opening, actor, revision: revision == opening_revision(opening, actor)}
    root = Path(__file__).resolve().parents[1]
    routes = ast.parse((root / 'app/routes/native_api.py').read_text(encoding='utf-8-sig'))
    services = ast.parse((root / 'app/services/web_document_idempotency.py').read_text(encoding='utf-8-sig'))
    def find(tree, name):
        nodes = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
        if len(nodes) != 1:
            raise AssertionError('missing or duplicate source function ' + name)
        nodes[0].decorator_list = []
        return nodes[0]
    class RemoveImports(ast.NodeTransformer):
        def visit_ImportFrom(self, node):
            if node.module in ('app', 'document_evidence', 'services.warehouse_stock_service', 'routes.print_queue',
                               'request_input', 'services.document_edit_guard', 'ai.ops.rollout_control',
                               'ai.tools.registry', 'ai.policies', 'flask_login'):
                return ast.copy_location(ast.Pass(), node)
            return node
    class StageBeforeCommit(ast.NodeTransformer):
        def visit_Try(self, node):
            self.generic_visit(node)
            for index in range(len(node.body) - 1):
                a, b = node.body[index:index + 2]
                if (isinstance(a, ast.Expr) and isinstance(a.value, ast.Call)
                        and ast.unparse(a.value.func) == 'db.session.commit'
                        and index + 3 < len(node.body)
                        and isinstance(b, ast.Assign) and isinstance(node.body[index + 2], ast.If)
                        and isinstance(node.body[index + 3], ast.Return)
                        and isinstance(node.body[index + 3].value, ast.Call)
                        and ast.unparse(node.body[index + 3].value.func) == 'api_json_success'):
                    response = node.body[index + 3].value
                    replacement = ast.parse('_response = None\nstage_document_response(_response.get_json())\n'
                                            'db.session.commit()\nreturn _response').body
                    replacement[0].value = response
                    node.body[index:index + 4] = [b, node.body[index + 2], *replacement]
                    return node
                if (isinstance(a, ast.Expr) and isinstance(a.value, ast.Call)
                        and ast.unparse(a.value.func) == 'db.session.commit'
                        and index + 3 < len(node.body)
                        and isinstance(b, ast.Assign) and isinstance(node.body[index + 2], ast.Assign)
                        and isinstance(node.body[index + 3], ast.Return)
                        and isinstance(node.body[index + 3].value, ast.Call)
                        and ast.unparse(node.body[index + 3].value.func) == 'api_json_success'):
                    response = node.body[index + 3].value
                    replacement = ast.parse('_response = None\nstage_document_response(_response.get_json())\n'
                                            'db.session.commit()\nreturn _response').body
                    replacement[0].value = response
                    node.body[index:index + 4] = [b, node.body[index + 2], *replacement]
                    return node
                if (isinstance(a, ast.Expr) and isinstance(a.value, ast.Call)
                        and ast.unparse(a.value.func) == 'db.session.commit'
                        and isinstance(b, ast.Return) and isinstance(b.value, ast.Call)
                        and ast.unparse(b.value.func) == 'api_json_success'):
                    replacement = ast.parse('_response = None\nstage_document_response(_response.get_json())\n'
                                            'db.session.commit()\nreturn _response').body
                    replacement[0].value = b.value
                    node.body[index:index + 2] = replacement
                    return node
            return node
    def route(name, fix_lock):
        node = RemoveImports().visit(copy.deepcopy(find(routes, name)))
        node = StageBeforeCommit().visit(node)
        if name == 'native_api_outbound' and fix_lock:
            found = [n for n in ast.walk(node) if isinstance(n, ast.If)
                     and ast.unparse(n.test) == "db.engine.dialect.name == 'sqlite'"
                     and len(n.body) == 2 and ast.unparse(n.body[0]) == 'db.session.rollback()']
            if len(found) != 1:
                raise AssertionError('outbound SQLite lock branch changed')
            old = found[0].body
            wrapper = ast.parse("if not getattr(g, 'web_document_receipt', None):\n    pass").body[0]
            wrapper.body = old
            found[0].body = [wrapper]
        if name == 'native_api_opening_stock_update' and fix_lock:
            rollback = [n for n in node.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                        and ast.unparse(n.value.func) == 'db.session.rollback']
            lock = [n for n in ast.walk(node) if isinstance(n, ast.If)
                    and ast.unparse(n.test) == "db.engine.dialect.name == 'sqlite'"]
            if len(rollback) != 1 or len(lock) != 1:
                raise AssertionError('opening SQLite lock path changed')
            wrapper = ast.parse("if not getattr(g, 'web_document_receipt', None):\n    pass").body[0]
            wrapper.body = [rollback[0]]
            node.body[node.body.index(rollback[0])] = wrapper
            lock[0].test = ast.parse("db.engine.dialect.name == 'sqlite' and not getattr(g, 'web_document_receipt', None)",
                                     mode='eval').body
        if name == 'native_api_voice_out_draft':
            preview = [n for n in node.body if isinstance(n, ast.If) and ast.unparse(n.test) == 'req.dry_run']
            if len(preview) != 1 or len(preview[0].body) != 1 or not isinstance(preview[0].body[0], ast.Return):
                raise AssertionError('voice preview branch changed')
            original_response = preview[0].body[0].value
            new_body = ast.parse('''
_response = None
if getattr(g, 'web_document_receipt', None):
    stage_document_response(_response.get_json())
    db.session.commit()
return _response
''').body
            new_body[0].value = original_response
            preview[0].body = new_body
            marker = ast.parse('''
_replay = claim_deferred_native_receipt()
if _replay is not None:
    return _replay
''').body
            position = node.body.index(preview[0])
            node.body[position:position] = marker
        return node

    unsafe = route('native_api_outbound', False)
    unsafe.name = 'unsafe_outbound'
    raw_old_inbound = RemoveImports().visit(copy.deepcopy(find(routes, 'native_api_inbound')))
    raw_old_inbound.name = 'raw_old_inbound'
    app_source = ast.parse((root / 'app/app.py').read_text(encoding='utf-8-sig'))
    ai_audit_source = ast.parse((root / 'app/ai/audit.py').read_text(encoding='utf-8-sig'))
    nodes = [find(services, '_document_idempotent'), find(services, 'stage_document_response'),
             find(app_source, '_acquire_order_write_lock'), find(app_source, 'mobile_api_idempotent'),
             find(app_source, 'hash_access_token'), find(app_source, 'get_bearer_user'),
             find(app_source, 'api_role_required'), find(app_source, '_ai_execute_intent'),
             find(ai_audit_source, 'create_conversation'), find(ai_audit_source, 'create_message'),
             find(routes, '_voice_param_present'),
             route('native_api_inbound', True),
             route('native_api_outbound', True), route('native_api_stocktake', True),
             route('native_api_opening_stock_update', True), route('native_api_opening_stock_submit', True),
             route('native_api_inbound_draft', True), route('native_api_voice_out_draft', True),
             route('native_api_voice_intent', True), route('native_api_assistant_chat', True), unsafe, raw_old_inbound]
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                 '<synthetic-native-candidate>', 'exec'), env)
    ai_schemas = []
    for name in ('VoiceIntentRequest', 'AssistantChatRequest'):
        found = [node for node in ast.walk(routes) if isinstance(node, ast.ClassDef) and node.name == name]
        if len(found) != 1:
            raise AssertionError('missing or duplicate original AI request schema ' + name)
        ai_schemas.append(copy.deepcopy(found[0]))
    schema_env = {'BaseModel': BaseModel, 'Field': Field}
    exec(compile(ast.fix_missing_locations(ast.Module(body=ai_schemas, type_ignores=[])),
                 '<synthetic-ai-request-schemas>', 'exec'), schema_env)
    def fingerprint(payload):
        payload = {key: value for key, value in payload.items() if key != 'request_id'}
        return hashlib.sha256(json.dumps({'payload': payload, 'path': request.path}, sort_keys=True,
                                         ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    def replay(existing, expected):
        if not 200 <= existing.status_code < 300:
            return api_error('保存请求记录未完成，请人工确认', 503)
        try:
            saved = json.loads(existing.response_json)
        except (TypeError, ValueError):
            return jsonify({'status': 'error', 'success': False, 'msg': '历史响应无法读取'}), existing.status_code
        metadata = Receipt.query.filter_by(user_id=existing.user_id,
                                           endpoint='nmeta:' + existing.endpoint,
                                           request_key=existing.request_key).first()
        if metadata:
            if metadata.status_code != 200:
                return api_error('保存请求校验记录未完成，请人工确认', 503)
            try:
                stored = json.loads(metadata.response_json)
                known_fingerprint = stored['fingerprint']
            except (TypeError, ValueError, KeyError):
                return api_error('保存请求记录无法核对，请人工确认', 503)
            if (not isinstance(known_fingerprint, str) or len(known_fingerprint) != 64
                    or any(char not in '0123456789abcdef' for char in known_fingerprint)):
                return api_error('保存请求记录无法核对，请人工确认', 503)
            if known_fingerprint != expected:
                return api_error('本次请求已保存其他内容，请核对后重试', 409)
            return jsonify(saved), existing.status_code
        # An old receipt and a new receipt whose metadata was deleted are
        # indistinguishable. Require human review rather than guess the payload.
        return api_error('历史请求缺少完整校验记录，请人工核对原单据', 409)
    def claim_native_receipt(user_id, endpoint, key, expected):
        session.rollback()
        receipt = Receipt(user_id=user_id, endpoint=endpoint, request_key=key,
                          status_code=0, response_json='')
        meta = Receipt(user_id=user_id, endpoint='nmeta:' + endpoint, request_key=key,
                       status_code=0, response_json='')
        try:
            session.add_all([receipt, meta])
            session.flush()
        except IntegrityError:
            session.rollback()
            try:
                existing = Receipt.query.filter_by(user_id=user_id, endpoint=endpoint, request_key=key).first()
            except OperationalError:
                session.rollback()
                return api_error('保存暂时繁忙', 503)
            return replay(existing, expected) if existing else api_error('保存请求未能确认', 503)
        except OperationalError:
            session.rollback()
            return api_error('保存暂时繁忙', 503)
        g.web_document_receipt = (receipt, meta, expected)
        return None
    def stage_native_response(payload):
        pending = getattr(g, 'web_document_receipt', None)
        if pending is None:
            return
        receipt, meta, expected = pending
        receipt.status_code = 200
        receipt.response_json = json.dumps(payload, ensure_ascii=False)
        meta.status_code = 200
        meta.response_json = json.dumps({'fingerprint': expected}, ensure_ascii=False)
    env['stage_document_response'] = stage_native_response
    def claim_deferred_native_receipt():
        pending = getattr(g, 'native_pending', None)
        return claim_native_receipt(*pending) if pending else None
    env['claim_deferred_native_receipt'] = claim_deferred_native_receipt
    def native_atomic(endpoint, view, *, defer=False):
        @wraps(view)
        def wrapped(user, *args, **kwargs):
            payload = request.get_json(silent=True) or {}
            if not isinstance(payload, dict):
                return api_error('请求数据必须为JSON对象', 400)
            key = request.headers.get('X-Idempotency-Key') or payload.get('request_id') or ''
            if not isinstance(key, str):
                return api_error('幂等请求号必须为字符串', 400)
            key = key.strip()
            if not key:
                return view(user, *args, **kwargs)
            if len(key) > 120:
                return api_error('幂等请求号不能超过120个字符', 400)
            expected = fingerprint(payload)
            user_id = user.id
            try:
                existing = Receipt.query.filter_by(user_id=user_id, endpoint=endpoint, request_key=key).first()
            except OperationalError:
                session.rollback()
                return api_error('保存暂时繁忙', 503)
            if existing:
                return replay(existing, expected)
            session.rollback()  # preflight was read-only; release before external voice parsing
            if defer:
                g.native_pending = (user_id, endpoint, key, expected)
            else:
                prior = claim_native_receipt(user_id, endpoint, key, expected)
                if prior is not None:
                    return prior
            try:
                return view(user, *args, **kwargs)
            finally:
                session.rollback()
                g.pop('web_document_receipt', None)
                g.pop('native_pending', None)
        return wrapped
    def native_ai_guard(endpoint, view):
        """Synthetic safety candidate; unresolved execution stays manual-only."""
        def filter_replay(result, user):
            if endpoint == 'voice_intent' and isinstance(result, tuple) and result[1] == 200:
                body = result[0].get_json(silent=True) or {}
                data = body.get('data') if isinstance(body, dict) else None
                if (isinstance(data, dict) and data.get('action') == 'voice_out_draft'
                        and not env['_mobile_capability_allowed'](user, 'voice_out_draft', drafts=True)):
                    return api_success({'action': 'reply', 'intent': data.get('intent'),
                                        'speak': '领料草稿当前未开放，请到出库页手工开单',
                                        'cards': []}, '领料草稿未开放')
            return result
        @wraps(view)
        def wrapped(user, *args, **kwargs):
            payload = request.get_json(silent=True) or {}
            if not isinstance(payload, dict):
                return api_error('请求数据必须为JSON对象', 400)
            key = request.headers.get('X-Idempotency-Key') or payload.get('request_id') or ''
            if not isinstance(key, str):
                return api_error('幂等请求号必须为字符串', 400)
            key = key.strip()
            if not key:
                return api_error('缺少请求编号，请更新客户端并重试', 400)
            if len(key) > 120:
                return api_error('幂等请求号不能超过120个字符', 400)
            # Mirror the original view's validation and read-only permission
            # checks before replay or any durable processing claim.
            try:
                schema = schema_env['VoiceIntentRequest' if endpoint == 'voice_intent' else 'AssistantChatRequest']
                parsed = schema.model_validate(payload)
            except Exception:
                return api_error('请求参数不合法' if endpoint == 'voice_intent'
                                 else '消息内容不能为空且不超过 2000 字', 400)
            if endpoint == 'assistant_chat' and not parsed.text.strip() and not parsed.image and not (parsed.file and parsed.file_name):
                return api_error('消息内容不能为空', 400)
            if endpoint == 'assistant_chat' and parsed.image and len(parsed.image) > 5 * 1024 * 1024:
                return api_error('图片太大（超过 5MB），请压缩后重试', 400)
            if not env['_ai_global_enabled']():
                if endpoint == 'voice_intent':
                    return api_success({'action': 'fallback_local', 'reason': 'ai_disabled'}, 'AI 功能未启用')
                return api_success({'action': 'reply', 'reply': 'AI 功能当前已由管理员关闭，请联系管理员在系统设置中开启。'},
                                   'AI 未启用')
            if not env['_mobile_capability_allowed'](user, 'knowledge_base'):
                if endpoint == 'voice_intent':
                    return api_success({'action': 'fallback_local', 'reason': 'permission_denied'}, '当前账号不能使用语音助手')
                return api_error('当前账号没有权限使用 AI 助手', 403)
            user_id = user.id
            expected = fingerprint(payload)
            try:
                existing = Receipt.query.filter_by(user_id=user_id, endpoint=endpoint, request_key=key).first()
                if existing:
                    return filter_replay(replay(existing, expected), user)
                session.rollback()
                prior = claim_native_receipt(user_id, endpoint, key, expected)
                if prior is not None:
                    return filter_replay(prior, user)
                session.commit()  # durable processing claim; releases writer lock before LLM
                g.pop('web_document_receipt', None)  # never imply a write lock after commit
            except Exception:
                session.rollback()
                g.pop('web_document_receipt', None)
                return api_error('请求状态无法确认，请人工核对', 503)
            try:
                response = view(user, *args, **kwargs)
                response_obj = response[0] if isinstance(response, tuple) else response
                code = response[1] if isinstance(response, tuple) and len(response) > 1 else response_obj.status_code
                if not 200 <= code < 300:
                    session.rollback()
                    return response  # processing remains; retry requires human review
                payload = response_obj.get_json(silent=True) or {}
                receipt = Receipt.query.filter_by(user_id=user_id, endpoint=endpoint, request_key=key).one()
                meta = Receipt.query.filter_by(user_id=user_id, endpoint='nmeta:' + endpoint, request_key=key).one()
                receipt.status_code, receipt.response_json = code, json.dumps(payload, ensure_ascii=False)
                meta.status_code, meta.response_json = 200, json.dumps({'fingerprint': expected})
                session.commit()
                return response
            except Exception:
                session.rollback()
                return api_error('处理结果未确认，请人工核对后再操作', 503)
            finally:
                session.rollback()
        return wrapped
    for route_name, function_name, native_endpoint in (
            ('/in', 'native_api_inbound', 'inbound'), ('/out', 'native_api_outbound', 'outbound'),
            ('/stocktake', 'native_api_stocktake', 'stocktake'),
            ('/opening', 'native_api_opening_stock_submit', 'opening_stock'),
            ('/in-draft', 'native_api_inbound_draft', 'inbound_draft'),
            ('/voice', 'native_api_voice_out_draft', 'voice_out_draft'), ('/unsafe-out', 'unsafe_outbound', 'unsafe')):
        fn = native_atomic(native_endpoint, env[function_name], defer=native_endpoint == 'voice_out_draft')
        app.add_url_rule(route_name, endpoint=function_name,
                         view_func=lambda f=fn: f(user), methods=['POST'])
    opening_view = native_atomic('opening_stock_edit', env['native_api_opening_stock_update'])
    app.add_url_rule('/opening/<int:line_id>', endpoint='opening_update',
                     view_func=lambda line_id: opening_view(user, line_id), methods=['POST'])
    old_native_reader = env['mobile_api_idempotent']('inbound')(
        lambda _user: api_error('不应执行旧业务', 500))
    app.add_url_rule('/old-in', endpoint='old_native_reader',
                     view_func=lambda: old_native_reader(user), methods=['POST'])
    authenticated_inbound = env['api_role_required']('warehouse')(
        native_atomic('inbound', env['native_api_inbound']))
    app.add_url_rule('/auth-in', endpoint='auth_inbound', view_func=authenticated_inbound, methods=['POST'])
    old_preflight_entered = threading.Event()
    old_preflight_release = threading.Event()
    def old_business(_user):
        old_preflight_entered.set()
        if not old_preflight_release.wait(timeout=5):
            raise TimeoutError('synthetic old writer timeout')
        return env['raw_old_inbound'](_user)
    old_writer = env['mobile_api_idempotent']('inbound')(old_business)
    app.add_url_rule('/old-concurrent-in', endpoint='old_concurrent_in',
                     view_func=lambda: old_writer(user), methods=['POST'])
    app.add_url_rule('/voice-intent', endpoint='voice_intent_direct',
                     view_func=lambda: env['native_api_voice_intent'](user), methods=['POST'])
    env['login_user'] = lambda _user: None
    def synthetic_assistant(_payload):
        if assistant_hook[0] is not None:
            assistant_hook[0]()
        conversation = env['create_conversation'](user.id, '合成对话')
        g.ai_bound_conversation_id = conversation.id
        env['create_message'](conversation.id, 'user', '合成输入')
        env['create_message'](conversation.id, 'assistant', '合成回复')
        return jsonify({'reply': '合成回复', 'cards': [], 'actions': []})
    env['_ai_handle_warehouse_assistant_request'] = synthetic_assistant
    intent_atomic = native_atomic('voice_intent', env['native_api_voice_intent'])
    assistant_atomic = native_atomic('assistant_chat', env['native_api_assistant_chat'])
    app.add_url_rule('/voice-intent-atomic', endpoint='voice_intent_atomic',
                     view_func=lambda: intent_atomic(user), methods=['POST'])
    app.add_url_rule('/assistant-atomic', endpoint='assistant_atomic',
                     view_func=lambda: assistant_atomic(user), methods=['POST'])
    safe_intent = native_ai_guard('voice_intent', env['native_api_voice_intent'])
    safe_assistant = native_ai_guard('assistant_chat', env['native_api_assistant_chat'])
    app.add_url_rule('/voice-intent-safe', endpoint='voice_intent_safe',
                     view_func=lambda: safe_intent(user), methods=['POST'])
    app.add_url_rule('/assistant-safe', endpoint='assistant_safe',
                     view_func=lambda: safe_assistant(user), methods=['POST'])
    @app.teardown_request
    def cleanup(_error):
        session.rollback()

    class NativeCandidate(unittest.TestCase):
        def setUp(self):
            session.remove()
            voice_calls.clear()
            voice_hook[0] = None
            assistant_hook[0] = None
            intent_hook[0] = None
            old_preflight_entered.clear()
            old_preflight_release.clear()
            for model in (InItem, OutItem, InOrder, OutOrder, StockLedger, PrintJob, Receipt,
                          InventoryCheckScanItem, InventoryCheckScan, InventoryCheck, OpeningStock,
                          OpeningDoc, Warehouse, ApiToken, SyntheticUser, AdjustmentDraft, AIMessage, AIConversation):
                session.query(model).delete()
            material = Material.query.one()
            material.stock = 10
            session.add(InventoryCheck(id=1, check_no='CK-1', warehouse='合成仓', status='pending', scanned=0))
            session.add(Warehouse(id=1, code='WH', name='合成仓', status='active'))
            session.add(SyntheticUser(id=1, role='warehouse', is_active=True))
            session.add(ApiToken(token=env['hash_access_token']('synthetic-token'), user_id=1,
                                 revoked=False, expires_at=datetime.datetime.now() + datetime.timedelta(hours=1),
                                 last_used_at=None))
            session.add_all([OpeningStock(id=index, material_id=material.id, warehouse_id=1, warehouse='合成仓',
                                          date=datetime.date.today(), quantity=4, price=2, amount=8)
                             for index in (1, 2)])
            session.commit()
            self.client = app.test_client()
            self.body = {'lines': [{'code': 'M', 'quantity': 2}]}
        def request(self, endpoint, key, body=None):
            return self.client.post(endpoint, json=body or self.body, headers={'X-Idempotency-Key': key})
        def test_inbound_response_loss_replays_once(self):
            a = self.request('/in', 'same')
            b = self.request('/in', 'same')
            self.assertEqual((a.status_code, b.status_code), (200, 200))
            self.assertEqual(a.json, b.json)
            self.assertEqual(Material.query.one().stock, 12)
            self.assertEqual((session.query(InOrder).count(), session.query(StockLedger).count()), (1, 1))
            self.assertEqual(session.query(PrintJob).count(), 1)
        def test_outbound_response_loss_replays_once_and_checks_stock(self):
            a = self.request('/out', 'same')
            b = self.request('/out', 'same')
            self.assertEqual((a.status_code, b.status_code), (200, 200))
            self.assertEqual(a.json, b.json)
            self.assertEqual(Material.query.one().stock, 8)
            self.assertEqual((session.query(OutOrder).count(), session.query(StockLedger).count()), (1, 1))
            self.assertEqual(session.query(PrintJob).count(), 1)
            error = self.request('/out', 'insufficient', {'lines': [{'code': 'M', 'quantity': 20}]})
            self.assertEqual(error.status_code, 400)
            self.assertEqual(Material.query.one().stock, 8)

        def test_outbound_original_lock_rolls_back_claim_and_duplicates(self):
            a = self.request('/unsafe-out', 'same')
            b = self.request('/unsafe-out', 'same')
            self.assertEqual((a.status_code, b.status_code), (200, 200))
            self.assertEqual(Material.query.one().stock, 6)
            self.assertEqual((session.query(OutOrder).count(), session.query(StockLedger).count()), (2, 2))
            self.assertEqual(session.query(Receipt).count(), 0)

        def test_outbound_without_key_keeps_original_lock_path(self):
            result = self.client.post('/out', json=self.body)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(Material.query.one().stock, 8)
            self.assertEqual(session.query(Receipt).count(), 0)

        def test_stocktake_replay_preserves_batch_and_single_scan(self):
            payload = {'check_id': 1, 'warehouse': '合成仓', 'lines': [{'code': 'M', 'actual_stock': 8}]}
            a = self.request('/stocktake', 'same', payload)
            b = self.request('/stocktake', 'same', payload)
            self.assertEqual((a.status_code, b.status_code), (200, 200), (a.json, b.json))
            self.assertEqual(a.json, b.json)
            self.assertEqual(session.query(InventoryCheck).one().scanned, 1)
            self.assertEqual(session.query(InventoryCheckScan).count(), 1)
            self.assertEqual(session.query(InventoryCheckScanItem).count(), 1)

        def test_opening_edit_replay_is_bound_to_resource_path(self):
            payload = {'quantity': 7, 'revision': '1:4.0'}
            a = self.request('/opening/1', 'same', payload)
            b = self.request('/opening/1', 'same', payload)
            self.assertEqual((a.status_code, b.status_code), (200, 200), (a.json, b.json))
            self.assertEqual(a.json, b.json)
            self.assertEqual(session.get(OpeningStock, 1).quantity, 7)
            self.assertEqual(Material.query.one().stock, 13)
            self.assertEqual(session.query(StockLedger).count(), 1)
            conflict = self.request('/opening/2', 'same', payload)
            self.assertEqual(conflict.status_code, 409)
            self.assertEqual(session.get(OpeningStock, 2).quantity, 4)

        def test_opening_stale_revision_releases_claim(self):
            result = self.request('/opening/1', 'stale', {'quantity': 7, 'revision': 'old'})
            self.assertEqual(result.status_code, 409)
            self.assertEqual(session.get(OpeningStock, 1).quantity, 4)
            self.assertEqual(session.query(Receipt).count(), 0)
            self.assertEqual(Material.query.one().stock, 10)

        def test_opening_submit_replays_without_reapplying_delta(self):
            payload = {'warehouse_code': 'WH', 'lines': [{'code': 'M', 'quantity': 7, 'price': 2}]}
            a = self.request('/opening', 'same', payload)
            b = self.request('/opening', 'same', payload)
            self.assertEqual((a.status_code, b.status_code), (200, 200), (a.json, b.json))
            self.assertEqual(a.json, b.json)
            self.assertEqual(Material.query.one().stock, 13)
            self.assertEqual(session.query(StockLedger).count(), 1)
            self.assertEqual(session.query(OpeningDoc).count(), 1)

        def test_inbound_draft_replays_without_stock_change(self):
            payload = {'warehouse_code': 'WH', 'lines': [{'material_code': 'M', 'quantity': 2, 'price': 2}]}
            a = self.request('/in-draft', 'same', payload)
            b = self.request('/in-draft', 'same', payload)
            self.assertEqual((a.status_code, b.status_code), (200, 200), (a.json, b.json))
            self.assertEqual(a.json, b.json)
            self.assertEqual(session.query(InOrder).count(), 1)
            self.assertEqual(session.query(InItem).count(), 1)
            self.assertEqual(Material.query.one().stock, 10)
            self.assertEqual(session.query(StockLedger).count(), 0)

        def test_voice_draft_replays_without_stock_change(self):
            payload = {'text': '合成物料', 'warehouse_code': 'WH', 'dry_run': False,
                       'material_code': 'M', 'quantity': 2}
            a = self.request('/voice', 'same', payload)
            b = self.request('/voice', 'same', payload)
            self.assertEqual((a.status_code, b.status_code), (200, 200), (a.json, b.json))
            self.assertEqual(a.json, b.json)
            self.assertEqual(session.query(OutOrder).count(), 1)
            self.assertEqual(session.query(OutItem).count(), 1)
            self.assertEqual(Material.query.one().stock, 10)
            self.assertEqual(session.query(StockLedger).count(), 0)
            self.assertEqual(voice_calls, [False], '解析期间不得持有回执写占位')

        def test_voice_preview_same_key_does_not_reexecute_or_drop_receipt(self):
            payload = {'text': '合成物料', 'warehouse_code': 'WH', 'dry_run': True}
            a = self.request('/voice', 'same', payload)
            b = self.request('/voice', 'same', payload)
            self.assertEqual((a.status_code, b.status_code), (200, 200), (a.json, b.json))
            self.assertEqual(a.json, b.json)
            self.assertEqual(len(voice_calls), 1, '相同请求不应再次执行解析')
            self.assertEqual(session.query(Receipt).count(), 2)
            self.assertEqual(voice_calls, [False], '解析期间不得持有回执写占位')

        def test_voice_parsing_does_not_hold_sqlite_writer_lock(self):
            entered = threading.Event()
            release = threading.Event()
            def pause_voice():
                entered.set()
                if not release.wait(timeout=3):
                    raise TimeoutError('synthetic voice wait')
            voice_hook[0] = pause_voice
            payload = {'text': '合成物料', 'warehouse_code': 'WH', 'dry_run': True}
            def send():
                try:
                    return app.test_client().post('/voice', json=payload,
                                                  headers={'X-Idempotency-Key': 'voice-lock'})
                finally:
                    session.remove()
            with ThreadPoolExecutor(max_workers=1) as pool:
                task = pool.submit(send)
                self.assertTrue(entered.wait(timeout=3))
                peer = open_memory()
                try:
                    peer.execute('BEGIN IMMEDIATE')
                    peer.rollback()
                finally:
                    peer.close()
                    release.set()
                result = task.result(timeout=5)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(voice_calls, [False])

        def test_simultaneous_same_and_distinct_request_keys(self):
            for same in (True, False):
                with self.subTest(same=same):
                    self.setUp()
                    barrier = threading.Barrier(2)
                    def send(index):
                        key = 'same' if same else f'unique-{index}'
                        try:
                            client = app.test_client()
                            barrier.wait(timeout=3)
                            result = client.post('/in', json=self.body, headers={'X-Idempotency-Key': key})
                            return key, result.status_code, result.get_json()
                        finally:
                            session.remove()
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        results = list(pool.map(send, range(2)))
                    final = []
                    for key, status, payload in results:
                        self.assertIn(status, (200, 503), (status, payload))
                        if status == 503:
                            retried = self.request('/in', key)
                            status, payload = retried.status_code, retried.get_json()
                        self.assertEqual(status, 200, payload)
                        final.append(payload)
                    self.assertEqual(session.query(InOrder).count(), 1 if same else 2)
                    self.assertEqual(session.query(StockLedger).count(), 1 if same else 2)
                    self.assertEqual(Material.query.one().stock, 12 if same else 14)
                    if same:
                        self.assertEqual(final[0], final[1])
                    else:
                        self.assertNotEqual(final[0]['data']['id'], final[1]['data']['id'])

        def test_old_and_new_worker_same_key_cannot_duplicate(self):
            def old_send():
                try:
                    return app.test_client().post('/old-concurrent-in', json=self.body,
                                                  headers={'X-Idempotency-Key': 'mixed'})
                finally:
                    session.remove()
            with ThreadPoolExecutor(max_workers=1) as pool:
                old = pool.submit(old_send)
                self.assertTrue(old_preflight_entered.wait(timeout=3))
                try:
                    current = self.request('/in', 'mixed')
                    self.assertEqual(current.status_code, 200, current.json)
                finally:
                    old_preflight_release.set()
                old_result = old.result(timeout=5)
            self.assertEqual(old_result.status_code, 200)
            self.assertEqual(session.query(InOrder).count(), 1, '旧新进程同 key 不得分别提交')
            self.assertEqual(session.query(StockLedger).count(), 1)
            self.assertEqual(Material.query.one().stock, 12)

        def test_all_seven_legacy_receipts_replay_original_response(self):
            entries = [('/in', 'inbound'), ('/out', 'outbound'), ('/stocktake', 'stocktake'),
                       ('/opening/1', 'opening_stock_edit'), ('/opening', 'opening_stock'),
                       ('/in-draft', 'inbound_draft'), ('/voice', 'voice_out_draft')]
            for index, (path, endpoint) in enumerate(entries):
                with self.subTest(endpoint=endpoint):
                    key = f'old-{index}'
                    legacy = {'status': 'success', 'success': True, 'msg': '历史成功',
                              'message': '历史成功', 'data': {'id': 100 + index}}
                    session.add(Receipt(user_id=1, endpoint=endpoint, request_key=key, status_code=200,
                                        response_json=json.dumps(legacy, ensure_ascii=False)))
                    session.commit()
                    result = self.request(path, key, {'different': '历史回执没有指纹'})
                    self.assertEqual(result.status_code, 200)
                    self.assertEqual(result.json, legacy)
            self.assertEqual(session.query(StockLedger).count(), 0)
            self.assertEqual(session.query(InOrder).count(), 0)
            self.assertEqual(session.query(OutOrder).count(), 0)
            self.assertEqual(Material.query.one().stock, 10)

        def test_all_seven_legacy_receipts_require_manual_review(self):
            entries = [('/in', 'inbound'), ('/out', 'outbound'), ('/stocktake', 'stocktake'),
                       ('/opening/1', 'opening_stock_edit'), ('/opening', 'opening_stock'),
                       ('/in-draft', 'inbound_draft'), ('/voice', 'voice_out_draft')]
            for index, (path, endpoint) in enumerate(entries):
                with self.subTest(endpoint=endpoint):
                    key = f'old-{index}'
                    legacy = {'status': 'success', 'success': True, 'data': {'id': 100 + index}}
                    session.add(Receipt(user_id=1, endpoint=endpoint, request_key=key, status_code=200,
                                        response_json=json.dumps(legacy, ensure_ascii=False)))
                    session.commit()
                    result = self.request(path, key, {'different': '历史回执没有指纹'})
                    self.assertEqual(result.status_code, 409)
                    self.assertIn('人工核对', result.json['msg'])
            self.assertEqual(session.query(InOrder).count(), 0)
            self.assertEqual(session.query(OutOrder).count(), 0)
            self.assertEqual(session.query(StockLedger).count(), 0)

        def test_old_native_reader_replays_new_receipt_after_code_rollback(self):
            first = self.request('/in', 'rollback-replay')
            self.assertEqual(first.status_code, 200)
            old = self.request('/old-in', 'rollback-replay')
            self.assertEqual(old.status_code, 200)
            self.assertEqual(old.json, first.json, '旧版回退后必须读取原成功响应')
            self.assertEqual(session.query(InOrder).count(), 1)
            self.assertEqual(Material.query.one().stock, 12)

        def test_missing_fingerprint_metadata_must_not_replay_changed_payload(self):
            self.assertEqual(self.request('/in', 'lost-meta').status_code, 200)
            meta = Receipt.query.filter_by(user_id=1, endpoint='nmeta:inbound', request_key='lost-meta').one()
            session.delete(meta)
            session.commit()
            changed = self.request('/in', 'lost-meta', {'lines': [{'code': 'M', 'quantity': 3}]})
            self.assertIn(changed.status_code, (409, 503), '元数据不完整不得视为可安全重放的旧回执')
            self.assertEqual(session.query(InOrder).count(), 1)
            self.assertEqual(Material.query.one().stock, 12)

        def test_missing_main_receipt_does_not_execute_business_again(self):
            self.assertEqual(self.request('/in', 'lost-main').status_code, 200)
            primary = Receipt.query.filter_by(user_id=1, endpoint='inbound', request_key='lost-main').one()
            session.delete(primary)
            session.commit()
            retry = self.request('/in', 'lost-main')
            self.assertEqual(retry.status_code, 503)
            self.assertEqual(session.query(InOrder).count(), 1)
            self.assertEqual(Material.query.one().stock, 12)

        def test_incomplete_or_corrupt_metadata_fails_closed(self):
            self.assertEqual(self.request('/in', 'corrupt').status_code, 200)
            meta = Receipt.query.filter_by(user_id=1, endpoint='nmeta:inbound', request_key='corrupt').one()
            meta.status_code = 0
            session.commit()
            self.assertEqual(self.request('/in', 'corrupt').status_code, 503)
            meta.status_code = 200
            meta.response_json = '{"fingerprint":"bad"}'
            session.commit()
            self.assertEqual(self.request('/in', 'corrupt').status_code, 503)
            self.assertEqual(session.query(InOrder).count(), 1)
            self.assertEqual(Material.query.one().stock, 12)

        def test_native_endpoint_metadata_names_and_maximum_request_key(self):
            endpoints = ('inbound', 'outbound', 'stocktake', 'opening_stock_edit', 'opening_stock',
                         'inbound_draft', 'voice_out_draft', 'voice_intent', 'assistant_chat')
            names = ['nmeta:' + value for value in endpoints]
            self.assertTrue(all(len(value) <= 40 for value in names))
            self.assertTrue(set(names).isdisjoint(endpoints))
            self.assertTrue(all(not value.startswith(('web:', 'mobile:')) for value in names))
            key = 'k' * 120
            first = self.request('/in', key)
            second = self.request('/in', key)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.json, second.json)
            self.assertEqual(Receipt.query.filter_by(request_key=key).count(), 2)

        def test_request_key_is_scoped_to_authenticated_user(self):
            first = self.request('/in', 'same-key')
            self.assertEqual(first.status_code, 200)
            user.id = 2
            try:
                second = self.request('/in', 'same-key')
                self.assertEqual(second.status_code, 200)
                self.assertNotEqual(first.json['data']['id'], second.json['data']['id'])
            finally:
                user.id = 1
            self.assertEqual(session.query(InOrder).count(), 2)
            self.assertEqual(Material.query.one().stock, 14)

        def test_overlong_key_fails_before_business_write(self):
            result = self.request('/in', 'k' * 121)
            self.assertEqual(result.status_code, 400)
            self.assertEqual(session.query(InOrder).count(), 0)
            self.assertEqual(session.query(Receipt).count(), 0)
            self.assertEqual(Material.query.one().stock, 10)

        def test_real_bearer_auth_renews_token_before_business_commit(self):
            commits = []
            def record(_connection):
                commits.append(1)
            event.listen(engine, 'commit', record)
            try:
                result = self.client.post('/auth-in', json=self.body,
                    headers={'Authorization': 'Bearer synthetic-token', 'X-Idempotency-Key': 'auth'})
            finally:
                event.remove(engine, 'commit', record)
            self.assertEqual(result.status_code, 200, result.json)
            self.assertEqual(len(commits), 2, 'token 续期与业务分别提交')
            token = ApiToken.query.one()
            self.assertIsNotNone(token.last_used_at)
            self.assertGreater(token.expires_at, datetime.datetime.now() + datetime.timedelta(days=6))
            self.assertEqual(session.query(InOrder).count(), 1)

        def test_real_bearer_commit_failure_does_not_fake_business_success(self):
            attempts = []
            def reject_first(_connection):
                attempts.append(1)
                if len(attempts) == 1:
                    raise RuntimeError('synthetic token commit failure')
            event.listen(engine, 'commit', reject_first)
            try:
                result = self.client.post('/auth-in', json=self.body,
                    headers={'Authorization': 'Bearer synthetic-token', 'X-Idempotency-Key': 'auth-fail'})
            finally:
                event.remove(engine, 'commit', reject_first)
            self.assertEqual(result.status_code, 200, result.json)
            self.assertEqual(len(attempts), 2)
            self.assertIsNone(ApiToken.query.one().last_used_at)
            self.assertEqual(session.query(InOrder).count(), 1)
            self.assertEqual(Material.query.one().stock, 12)

        def test_real_bearer_role_denial_precedes_receipt_and_business(self):
            account = session.get(SyntheticUser, 1)
            account.role = 'guest'
            session.commit()
            result = self.client.post('/auth-in', json=self.body,
                headers={'Authorization': 'Bearer synthetic-token', 'X-Idempotency-Key': 'denied'})
            self.assertEqual(result.status_code, 403)
            self.assertEqual(session.query(Receipt).count(), 0)
            self.assertEqual(session.query(InOrder).count(), 0)
            self.assertEqual(Material.query.one().stock, 10)

        def test_receipt_finalization_failure_rolls_back_all_seven_endpoints(self):
            cases = [
                ('/in', self.body), ('/out', self.body),
                ('/stocktake', {'check_id': 1, 'warehouse': '合成仓', 'lines': [{'code': 'M', 'actual_stock': 8}]}),
                ('/opening/1', {'quantity': 7, 'revision': '1:4.0'}),
                ('/opening', {'warehouse_code': 'WH', 'lines': [{'code': 'M', 'quantity': 7, 'price': 2}]}),
                ('/in-draft', {'warehouse_code': 'WH', 'lines': [{'material_code': 'M', 'quantity': 2, 'price': 2}]}),
                ('/voice', {'text': '合成物料', 'warehouse_code': 'WH', 'dry_run': False,
                            'material_code': 'M', 'quantity': 2}),
            ]
            for endpoint, payload in cases:
                with self.subTest(endpoint=endpoint):
                    self.setUp()
                    failed = [False]
                    def inject(_conn, _cursor, statement, _params, _context, _many):
                        if not failed[0] and statement.lstrip().upper().startswith('UPDATE SYNTHETIC_RECEIPT'):
                            failed[0] = True
                            raise RuntimeError('synthetic receipt failure')
                    event.listen(engine, 'before_cursor_execute', inject)
                    try:
                        result = self.request(endpoint, 'failure', payload)
                        self.assertGreaterEqual(result.status_code, 400)
                        self.assertTrue(failed[0])
                    finally:
                        event.remove(engine, 'before_cursor_execute', inject)
                    self.assertEqual(Material.query.one().stock, 10)
                    self.assertEqual(session.query(Receipt).count(), 0)
                    self.assertEqual(session.query(InOrder).count(), 0)
                    self.assertEqual(session.query(OutOrder).count(), 0)
                    self.assertEqual(session.query(StockLedger).count(), 0)
                    self.assertEqual(session.query(PrintJob).count(), 0)
                    self.assertEqual(session.query(InventoryCheckScan).count(), 0)
                    self.assertEqual(session.query(OpeningDoc).count(), 0)
                    self.assertEqual(session.get(OpeningStock, 1).quantity, 4)
                    self.assertEqual(session.get(InventoryCheck, 1).scanned, 0)
                    retry = self.request(endpoint, 'failure', payload)
                    self.assertEqual(retry.status_code, 200, retry.json)
                    self.assertEqual(session.query(Receipt).count(), 2)

        def test_business_commit_failure_rolls_back_all_seven_endpoints(self):
            cases = [
                ('/in', self.body), ('/out', self.body),
                ('/stocktake', {'check_id': 1, 'warehouse': '合成仓', 'lines': [{'code': 'M', 'actual_stock': 8}]}),
                ('/opening/1', {'quantity': 7, 'revision': '1:4.0'}),
                ('/opening', {'warehouse_code': 'WH', 'lines': [{'code': 'M', 'quantity': 7, 'price': 2}]}),
                ('/in-draft', {'warehouse_code': 'WH', 'lines': [{'material_code': 'M', 'quantity': 2, 'price': 2}]}),
                ('/voice', {'text': '合成物料', 'warehouse_code': 'WH', 'dry_run': False,
                            'material_code': 'M', 'quantity': 2}),
            ]
            for endpoint, payload in cases:
                with self.subTest(endpoint=endpoint):
                    self.setUp()
                    attempts = []
                    def reject(_connection):
                        attempts.append(1)
                        raise RuntimeError('synthetic commit failure')
                    event.listen(engine, 'commit', reject)
                    try:
                        result = self.request(endpoint, 'commit-failure', payload)
                        self.assertGreaterEqual(result.status_code, 400)
                        self.assertEqual(len(attempts), 1)
                    finally:
                        event.remove(engine, 'commit', reject)
                    self.assertEqual(Material.query.one().stock, 10)
                    for model in (Receipt, InOrder, OutOrder, StockLedger, PrintJob, InventoryCheckScan, OpeningDoc):
                        self.assertEqual(session.query(model).count(), 0, model.__name__)
                    self.assertEqual(session.get(OpeningStock, 1).quantity, 4)
                    self.assertEqual(session.get(InventoryCheck, 1).scanned, 0)
                    retry = self.request(endpoint, 'commit-failure', payload)
                    self.assertEqual(retry.status_code, 200, retry.json)

        def test_metadata_claim_failure_rolls_back_all_seven_endpoints(self):
            cases = [
                ('/in', self.body), ('/out', self.body),
                ('/stocktake', {'check_id': 1, 'warehouse': '合成仓', 'lines': [{'code': 'M', 'actual_stock': 8}]}),
                ('/opening/1', {'quantity': 7, 'revision': '1:4.0'}),
                ('/opening', {'warehouse_code': 'WH', 'lines': [{'code': 'M', 'quantity': 7, 'price': 2}]}),
                ('/in-draft', {'warehouse_code': 'WH', 'lines': [{'material_code': 'M', 'quantity': 2, 'price': 2}]}),
                ('/voice', {'text': '合成物料', 'warehouse_code': 'WH', 'dry_run': False,
                            'material_code': 'M', 'quantity': 2}),
            ]
            for endpoint, payload in cases:
                with self.subTest(endpoint=endpoint):
                    self.setUp()
                    failed = [False]
                    def inject(_conn, _cursor, statement, parameters, _context, _many):
                        if (not failed[0] and statement.lstrip().upper().startswith('INSERT INTO SYNTHETIC_RECEIPT')
                                and 'nmeta:' in repr(parameters)):
                            failed[0] = True
                            raise RuntimeError('synthetic metadata insert failure')
                    event.listen(engine, 'before_cursor_execute', inject)
                    try:
                        result = self.request(endpoint, 'claim-failure', payload)
                        self.assertGreaterEqual(result.status_code, 400)
                        self.assertTrue(failed[0])
                    finally:
                        event.remove(engine, 'before_cursor_execute', inject)
                    self.assertEqual(Material.query.one().stock, 10)
                    for model in (Receipt, InOrder, OutOrder, StockLedger, PrintJob, InventoryCheckScan, OpeningDoc):
                        self.assertEqual(session.query(model).count(), 0, model.__name__)
                    self.assertEqual(session.get(OpeningStock, 1).quantity, 4)
                    self.assertEqual(session.get(InventoryCheck, 1).scanned, 0)
                    retry = self.request(endpoint, 'claim-failure', payload)
                    self.assertEqual(retry.status_code, 200, retry.json)

        def test_validation_failure_releases_key_in_all_seven_endpoints(self):
            cases = [
                ('/in', {'lines': []}, self.body), ('/out', {'lines': []}, self.body),
                ('/stocktake', {'lines': []}, {'check_id': 1, 'warehouse': '合成仓',
                                              'lines': [{'code': 'M', 'actual_stock': 8}]}),
                ('/opening/1', {'quantity': 7, 'revision': 'stale'}, {'quantity': 7, 'revision': '1:4.0'}),
                ('/opening', {'lines': []}, {'warehouse_code': 'WH', 'lines': [{'code': 'M', 'quantity': 7}]}),
                ('/in-draft', {'lines': []}, {'warehouse_code': 'WH',
                                             'lines': [{'material_code': 'M', 'quantity': 2}]}),
                ('/voice', {'text': '', 'dry_run': False}, {'text': '合成物料', 'warehouse_code': 'WH',
                            'dry_run': False, 'material_code': 'M', 'quantity': 2}),
            ]
            for endpoint, invalid, valid in cases:
                with self.subTest(endpoint=endpoint):
                    self.setUp()
                    result = self.request(endpoint, 'validation', invalid)
                    self.assertGreaterEqual(result.status_code, 400)
                    self.assertEqual(session.query(Receipt).count(), 0)
                    self.assertEqual(session.query(StockLedger).count(), 0)
                    retry = self.request(endpoint, 'validation', valid)
                    self.assertEqual(retry.status_code, 200, retry.json)

        def test_voice_parse_interruption_has_no_receipt_or_business_write(self):
            def cancel():
                raise RuntimeError('synthetic voice cancellation')
            voice_hook[0] = cancel
            payload = {'text': '合成物料', 'warehouse_code': 'WH', 'dry_run': False,
                       'material_code': 'M', 'quantity': 2}
            result = self.request('/voice', 'cancelled', payload)
            self.assertEqual(result.status_code, 500)
            self.assertEqual(session.query(Receipt).count(), 0)
            self.assertEqual(session.query(OutOrder).count(), 0)
            self.assertEqual(Material.query.one().stock, 10)
            voice_hook[0] = None
            self.assertEqual(self.request('/voice', 'cancelled', payload).status_code, 200)

        def test_voice_intent_unmapped_dispatch_can_invoke_committing_draft_helper(self):
            # Real intent route + real dispatcher; only LLM and draft helper are
            # synthetic, so this proves reachable control flow, not real draft semantics.
            commits = []
            def record(_connection):
                commits.append(1)
            event.listen(engine, 'commit', record)
            try:
                response = self.client.post('/voice-intent', json={'text': '合成调整单'})
            finally:
                event.remove(engine, 'commit', record)
            self.assertEqual(response.status_code, 200, response.json)
            self.assertEqual(response.json['data']['action'], 'reply')
            self.assertEqual(session.query(AdjustmentDraft).count(), 1)
            self.assertEqual(len(commits), 1)

        def test_voice_intent_inner_commit_must_not_leave_partial_receipt(self):
            payload = {'text': '合成调整单'}
            first = self.request('/voice-intent-atomic', 'same', payload)
            second = self.request('/voice-intent-atomic', 'same', payload)
            self.assertEqual(first.status_code, 200, first.json)
            self.assertEqual(second.status_code, 200, second.json)
            self.assertEqual(first.json, second.json)
            self.assertEqual(session.query(AdjustmentDraft).count(), 1)

        def test_assistant_history_commit_must_not_leave_partial_receipt(self):
            payload = {'text': '合成对话'}
            first = self.request('/assistant-atomic', 'same', payload)
            second = self.request('/assistant-atomic', 'same', payload)
            self.assertEqual(first.status_code, 200, first.json)
            self.assertEqual(second.status_code, 200, second.json)
            self.assertEqual(first.json, second.json)
            self.assertEqual(session.query(AIConversation).count(), 1)

        def test_ai_guard_success_replays_after_independent_business_commits(self):
            cases = [('/voice-intent-safe', {'text': '合成调整单'}, AdjustmentDraft),
                     ('/assistant-safe', {'text': '合成对话'}, AIConversation)]
            for path, payload, model in cases:
                with self.subTest(path=path):
                    self.setUp()
                    first = self.request(path, 'same', payload)
                    second = self.request(path, 'same', payload)
                    self.assertEqual((first.status_code, second.status_code), (200, 200), (first.json, second.json))
                    self.assertEqual(first.json, second.json)
                    self.assertEqual(session.query(model).count(), 1)
                    if model is AIConversation:
                        self.assertEqual(session.query(AIMessage).count(), 2)

        def test_ai_guard_finalization_failure_preserves_business_and_blocks_retry(self):
            cases = [('/voice-intent-safe', {'text': '合成调整单'}, AdjustmentDraft),
                     ('/assistant-safe', {'text': '合成对话'}, AIConversation)]
            for path, payload, model in cases:
                with self.subTest(path=path):
                    self.setUp()
                    fired = [False]
                    def reject(_conn, _cursor, statement, _params, _context, _many):
                        if not fired[0] and statement.lstrip().upper().startswith('UPDATE SYNTHETIC_RECEIPT'):
                            fired[0] = True
                            raise RuntimeError('synthetic finalization failure')
                    event.listen(engine, 'before_cursor_execute', reject)
                    try:
                        first = self.request(path, 'unknown', payload)
                        self.assertEqual(first.status_code, 503)
                        self.assertTrue(fired[0])
                    finally:
                        event.remove(engine, 'before_cursor_execute', reject)
                    self.assertEqual(session.query(model).count(), 1, '已提交的 AI 数据必须保留')
                    if model is AIConversation:
                        self.assertEqual(session.query(AIMessage).count(), 2, '已提交会话消息必须保留')
                    retry = self.request(path, 'unknown', payload)
                    self.assertEqual(retry.status_code, 503)
                    self.assertEqual(session.query(model).count(), 1, '未知结果不得再次执行')
                    if model is AIConversation:
                        self.assertEqual(session.query(AIMessage).count(), 2)

        def test_ai_guard_releases_writer_lock_before_external_call(self):
            cases = [('/voice-intent-safe', {'text': '合成调整单'}, intent_hook),
                     ('/assistant-safe', {'text': '合成对话'}, assistant_hook)]
            for path, payload, hook in cases:
                with self.subTest(path=path):
                    self.setUp()
                    entered, release = threading.Event(), threading.Event()
                    def pause():
                        self.assertIsNone(getattr(g, 'web_document_receipt', None))
                        entered.set()
                        if not release.wait(timeout=3):
                            raise TimeoutError('synthetic external call timeout')
                    hook[0] = pause
                    def send():
                        try:
                            return app.test_client().post(path, json=payload,
                                                          headers={'X-Idempotency-Key': 'ai-lock'})
                        finally:
                            session.remove()
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        task = pool.submit(send)
                        self.assertTrue(entered.wait(timeout=3))
                        peer = open_memory()
                        try:
                            peer.execute('BEGIN IMMEDIATE')
                            peer.rollback()
                        finally:
                            peer.close()
                            release.set()
                        result = task.result(timeout=5)
                    self.assertEqual(result.status_code, 200, result.json)

        def test_ai_guard_same_key_concurrent_runs_once(self):
            cases = [('/voice-intent-safe', {'text': '合成调整单'}, intent_hook, AdjustmentDraft),
                     ('/assistant-safe', {'text': '合成对话'}, assistant_hook, AIConversation)]
            for path, payload, hook, model in cases:
                with self.subTest(path=path):
                    self.setUp()
                    entered, release = threading.Event(), threading.Event()
                    def pause():
                        entered.set()
                        if not release.wait(timeout=3):
                            raise TimeoutError('synthetic AI concurrency timeout')
                    hook[0] = pause
                    def send():
                        try:
                            return app.test_client().post(path, json=payload,
                                                          headers={'X-Idempotency-Key': 'same-ai-key'})
                        finally:
                            session.remove()
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        task = pool.submit(send)
                        self.assertTrue(entered.wait(timeout=3))
                        try:
                            concurrent = self.request(path, 'same-ai-key', payload)
                            self.assertEqual(concurrent.status_code, 503)
                        finally:
                            release.set()
                        first = task.result(timeout=5)
                    self.assertEqual(first.status_code, 200, first.json)
                    replayed = self.request(path, 'same-ai-key', payload)
                    self.assertEqual(replayed.status_code, 200)
                    self.assertEqual(replayed.json, first.json)
                    self.assertEqual(session.query(model).count(), 1)

        def test_distinct_ai_request_can_commit_while_other_waits_for_model(self):
            entered, release = threading.Event(), threading.Event()
            def pause():
                entered.set()
                if not release.wait(timeout=3):
                    raise TimeoutError('synthetic assistant wait')
            assistant_hook[0] = pause
            def send_assistant():
                try:
                    return app.test_client().post('/assistant-safe', json={'text': '合成对话'},
                                                  headers={'X-Idempotency-Key': 'assistant-key'})
                finally:
                    session.remove()
            with ThreadPoolExecutor(max_workers=1) as pool:
                task = pool.submit(send_assistant)
                self.assertTrue(entered.wait(timeout=3))
                try:
                    other = self.request('/voice-intent-safe', 'intent-key', {'text': '合成调整单'})
                    self.assertEqual(other.status_code, 200, other.json)
                    self.assertEqual(session.query(AdjustmentDraft).count(), 1)
                finally:
                    release.set()
                first = task.result(timeout=5)
            self.assertEqual(first.status_code, 200, first.json)
            self.assertEqual(session.query(AIConversation).count(), 1)
            self.assertEqual(session.query(AIMessage).count(), 2)

        def test_ai_replay_rechecks_capability_before_disclosing_old_response(self):
            cases = [('/voice-intent-safe', {'text': '合成调整单'}, 200),
                     ('/assistant-safe', {'text': '合成对话'}, 403)]
            for path, payload, expected_status in cases:
                with self.subTest(path=path):
                    self.setUp()
                    first = self.request(path, 'permission', payload)
                    self.assertEqual(first.status_code, 200)
                    original = env['_mobile_capability_allowed']
                    env['_mobile_capability_allowed'] = lambda *_args, **_kwargs: False
                    try:
                        denied = self.request(path, 'permission', payload)
                        self.assertEqual(denied.status_code, expected_status)
                        self.assertNotEqual(denied.json, first.json)
                        if path.startswith('/voice'):
                            self.assertEqual(denied.json['data']['reason'], 'permission_denied')
                    finally:
                        env['_mobile_capability_allowed'] = original
                    self.assertEqual(self.request(path, 'permission', payload).json, first.json)

        def test_ai_replay_obeys_global_disable(self):
            cases = [('/voice-intent-safe', {'text': '合成调整单'}), ('/assistant-safe', {'text': '合成对话'})]
            for path, payload in cases:
                with self.subTest(path=path):
                    self.setUp()
                    first = self.request(path, 'global', payload)
                    self.assertEqual(first.status_code, 200)
                    original = env['_ai_global_enabled']
                    env['_ai_global_enabled'] = lambda: False
                    try:
                        disabled = self.request(path, 'global', payload)
                        self.assertEqual(disabled.status_code, 200)
                        self.assertNotEqual(disabled.json, first.json)
                    finally:
                        env['_ai_global_enabled'] = original

        def test_voice_intent_replay_rechecks_specific_draft_capability(self):
            prior_intent = env['_ai_call_llm_intent']
            prior_capability = env['_mobile_capability_allowed']
            env['_ai_call_llm_intent'] = lambda _message: {
                'intent': 'create_out_order_draft', 'params': {'material': 'M'}}
            try:
                payload = {'text': '合成领料'}
                first = self.request('/voice-intent-safe', 'cap-specific', payload)
                self.assertEqual(first.status_code, 200, first.json)
                self.assertEqual(first.json['data']['action'], 'voice_out_draft')
                env['_mobile_capability_allowed'] = lambda _user, capability, **_kwargs: capability == 'knowledge_base'
                replayed = self.request('/voice-intent-safe', 'cap-specific', payload)
                self.assertNotEqual(replayed.json['data']['action'], 'voice_out_draft',
                                    '下游语音建单能力撤销后不得重放旧导航')
            finally:
                env['_ai_call_llm_intent'] = prior_intent
                env['_mobile_capability_allowed'] = prior_capability

        def test_ai_validation_failure_does_not_claim_request(self):
            cases = [('/voice-intent-safe', {'text': ''}, {'text': '合成调整单'}),
                     ('/assistant-safe', {'text': ''}, {'text': '合成对话'})]
            for path, invalid, valid in cases:
                with self.subTest(path=path):
                    self.setUp()
                    self.assertEqual(self.request(path, 'validate-ai', invalid).status_code, 400)
                    self.assertEqual(session.query(Receipt).count(), 0)
                    self.assertEqual(self.request(path, 'validate-ai', valid).status_code, 200)

        def test_ai_old_body_request_id_replays(self):
            cases = [('/voice-intent-safe', {'text': '合成调整单', 'request_id': 'body-key'}, AdjustmentDraft),
                     ('/assistant-safe', {'text': '合成对话', 'request_id': 'body-key'}, AIConversation)]
            for path, payload, model in cases:
                with self.subTest(path=path):
                    self.setUp()
                    first = self.client.post(path, json=payload)
                    second = self.client.post(path, json=payload)
                    self.assertEqual((first.status_code, second.status_code), (200, 200))
                    self.assertEqual(first.json, second.json)
                    self.assertEqual(session.query(model).count(), 1)

        def test_ai_no_request_id_requires_upgrade_without_writes(self):
            cases = [('/voice-intent-safe', {'text': '合成调整单'}), ('/assistant-safe', {'text': '合成对话'})]
            for path, payload in cases:
                with self.subTest(path=path):
                    self.setUp()
                    result = self.client.post(path, json=payload)
                    self.assertEqual(result.status_code, 400)
                    self.assertIn('请求编号', result.json['msg'])
                    self.assertEqual(session.query(Receipt).count(), 0)
                    self.assertEqual(session.query(AdjustmentDraft).count(), 0)
                    self.assertEqual(session.query(AIConversation).count(), 0)

        def test_ai_old_no_request_id_behavior_remains_available(self):
            # Kept as a red compatibility constraint: the previous endpoints
            # accepted keyless clients, but those retries cannot be identified.
            cases = [('/voice-intent-safe', {'text': '合成调整单'}), ('/assistant-safe', {'text': '合成对话'})]
            for path, payload in cases:
                with self.subTest(path=path):
                    self.setUp()
                    self.assertEqual(self.client.post(path, json=payload).status_code, 200)

        def test_failure_logs_once_and_print_job_rolls_back(self):
            records = []
            class Collector(logging.Handler):
                def emit(self, record):
                    records.append(record.getMessage())
            collector = Collector()
            app.logger.addHandler(collector)
            fired = [False]
            def inject(_conn, _cursor, statement, _params, _context, _many):
                if not fired[0] and statement.lstrip().upper().startswith('UPDATE SYNTHETIC_RECEIPT'):
                    fired[0] = True
                    raise RuntimeError('synthetic receipt failure')
            event.listen(engine, 'before_cursor_execute', inject)
            try:
                self.assertEqual(self.request('/in', 'logged-failure').status_code, 500)
            finally:
                event.remove(engine, 'before_cursor_execute', inject)
                app.logger.removeHandler(collector)
            self.assertEqual(sum(message == 'Android inbound failed' for message in records), 1)
            self.assertEqual(session.query(PrintJob).count(), 0)
            self.assertEqual(session.query(InOrder).count(), 0)
        def test_same_key_with_changed_payload_conflicts(self):
            self.assertEqual(self.request('/out', 'same').status_code, 200)
            changed = self.request('/out', 'same', {'lines': [{'code': 'M', 'quantity': 3}]})
            self.assertEqual(changed.status_code, 409)
            self.assertEqual(Material.query.one().stock, 8)
        def test_receipt_update_failure_rolls_back_stock_and_order(self):
            failed = [False]
            def inject(_conn, _cursor, statement, _params, _context, _many):
                if not failed[0] and statement.lstrip().upper().startswith('UPDATE SYNTHETIC_RECEIPT'):
                    failed[0] = True
                    raise RuntimeError('synthetic receipt failure')
            event.listen(engine, 'before_cursor_execute', inject)
            try:
                result = self.request('/out', 'failure')
                self.assertEqual(result.status_code, 500)
                self.assertTrue(failed[0])
            finally:
                event.remove(engine, 'before_cursor_execute', inject)
            self.assertEqual(Material.query.one().stock, 10)
            self.assertEqual((session.query(OutOrder).count(), session.query(StockLedger).count(),
                              session.query(Receipt).count()), (0, 0, 0))
            self.assertEqual(session.query(PrintJob).count(), 0)
            self.assertEqual(self.request('/out', 'failure').status_code, 200)
            self.assertEqual(Material.query.one().stock, 8)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NativeCandidate)
    if suite.countTestCases() != 49:
        raise RuntimeError('explicit candidate test list incomplete')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    session.remove()
    engine.dispose()
    raise SystemExit(not result.wasSuccessful())


if __name__ == '__main__':
    main()

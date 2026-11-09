"""Parse JavaScript as data; never evaluate source text."""
import importlib.util
import sys
import time
from pathlib import Path

_parser_path = Path(__file__).resolve().parents[1] / 'vendor' / 'esprima' / '__init__.py'
_parser_name = '_wms_bundled_esprima'
if _parser_name in sys.modules:
    esprima = sys.modules[_parser_name]
    if Path(esprima.__file__).resolve() != _parser_path:
        raise RuntimeError('JavaScript parser was preloaded from an unexpected path')
else:
    _spec = importlib.util.spec_from_file_location(_parser_name, _parser_path)
    esprima = importlib.util.module_from_spec(_spec)
    sys.modules[_parser_name] = esprima
    try:
        _spec.loader.exec_module(esprima)
    except BaseException:
        sys.modules.pop(_parser_name, None)
        raise


def string(node):
    if not isinstance(node, dict):
        return None
    if node.get('type') == 'Literal' and isinstance(node.get('value'), str):
        return node['value']
    if node.get('type') == 'TemplateLiteral' and not node.get('expressions'):
        return node['quasis'][0]['value'].get('cooked')
    if node.get('type') == 'BinaryExpression' and node.get('operator') == '+':
        left, right = string(node.get('left')), string(node.get('right'))
        if left is not None and right is not None:
            return left + right
    return None


def key(node):
    prop = node.get('property', node.get('key', {}))
    if not node.get('computed') and prop.get('type') == 'Identifier':
        return prop['name']
    return string(prop)


def unsafe_options(node):
    if node is None:
        return False
    if node.get('type') != 'ObjectExpression':
        return True
    for prop in node['properties']:
        if prop['type'] == 'SpreadElement':
            if unsafe_options(prop['argument']):
                return True
            continue
        name = key(prop)
        if name is None or prop.get('kind') not in (None, 'init') or prop.get('method'):
            return True
        if name == '__proto__' and unsafe_options(prop.get('value')):
            return True
        if name == 'method' and (string(prop.get('value')) or '').upper() != 'GET':
            return True
    return False


def positions(source):
    if len(source.encode('utf-8')) > 1024 * 1024:
        raise RuntimeError('JavaScript 超过 1 MiB，请拆分后检查')
    deadline = time.monotonic() + 30
    count = 0
    def budget(node, metadata):
        nonlocal count
        count += 1
        if count > 300000 or time.monotonic() > deadline:
            raise RuntimeError('JavaScript 解析超过资源限制')
    try:
        parsed = esprima.parseScript(source, {'range': True, 'positionEncoding': 'scalar'}, delegate=budget)
    except Exception:
        try:
            parsed = esprima.parseModule(source, {'range': True, 'positionEncoding': 'scalar'}, delegate=budget)
        except Exception as exc:
            raise RuntimeError('JavaScript 无法安全解析，请核对语法或拆分文件') from exc
    try:
        tree = esprima.toDict(parsed)
    except (RecursionError, MemoryError) as exc:
        raise RuntimeError('JavaScript 结构超过资源限制') from exc
    nodes, parents = [], {}
    stack = [(tree, None)]
    while stack:
        if time.monotonic() > deadline:
            raise RuntimeError('JavaScript 分析超过时间限制')
        node, parent = stack.pop()
        nodes.append(node)
        parents[id(node)] = parent
        for value in node.values():
            if isinstance(value, dict) and 'type' in value:
                stack.append((value, node))
            elif isinstance(value, list):
                stack.extend((child, node) for child in value if isinstance(child, dict) and 'type' in child)
    scopes = {}
    class Scope:
        def __init__(self, parent=None, function=None):
            self.parent, self.function, self.names = parent, function, set()
        def resolve(self, name):
            current = self
            while current:
                if name in current.names:
                    return (id(current), name)
                current = current.parent
            return ('global', name)
    root_scope = Scope()
    def declared(target):
        if not isinstance(target, dict): return []
        if target.get('type') == 'Identifier': return [target['name']]
        result = []
        for field in ('properties', 'elements'):
            for child in target.get(field, []):
                if child:
                    result.extend(declared(child.get('value', child.get('argument', child))))
        return result
    todo = [(tree, root_scope)]
    while todo:
        node, scope = todo.pop()
        typ = node.get('type')
        if typ in ('FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression'):
            if typ == 'FunctionDeclaration' and node.get('id'):
                scope.names.add(node['id']['name'])
            scope = Scope(scope, node)
            if node.get('id'): scope.names.add(node['id']['name'])
            for param in node.get('params', []): scope.names.update(declared(param))
        elif typ in ('BlockStatement', 'CatchClause'):
            scope = Scope(scope)
            if typ == 'CatchClause': scope.names.update(declared(node.get('param')))
        scopes[id(node)] = scope
        if typ == 'VariableDeclarator':
            owner = parents[id(node)] or {}
            target_scope = scope
            if owner.get('kind') == 'var':
                while target_scope.parent and target_scope.function is None:
                    target_scope = target_scope.parent
            target_scope.names.update(declared(node.get('id')))
        for value in node.values():
            if isinstance(value, dict) and 'type' in value:
                todo.append((value, scope))
            elif isinstance(value, list):
                todo.extend((child, scope) for child in value if isinstance(child, dict) and 'type' in child)
    def binding(node):
        return scopes[id(node)].resolve(node['name'])
    globals_ = {('global', name) for name in ('window', 'globalThis', 'self')}
    fetches = {('global', 'fetch')}
    constructors = {('global', 'Request')}
    requests = set()
    def global_value(node):
        if not isinstance(node, dict):
            return False
        kind = node.get('type')
        if kind == 'ThisExpression':
            scope = scopes[id(node)]
            while scope.parent and scope.function is None: scope = scope.parent
            function = scope.function
            if function is None: return True
            if function.get('type') == 'ArrowFunctionExpression': return False
            owner = parents[id(function)] or {}
            statements = function.get('body', {}).get('body', [])
            strict = any(item.get('directive') == 'use strict' for item in statements)
            return not strict and owner.get('type') == 'CallExpression' and owner.get('callee') is function
        if kind == 'Identifier':
            return binding(node) in globals_
        if kind == 'ConditionalExpression':
            return global_value(node['consequent']) or global_value(node['alternate'])
        return False
    def fetch_value(node):
        if not isinstance(node, dict):
            return False
        kind = node.get('type')
        if kind == 'Identifier':
            return binding(node) in fetches
        if kind == 'MemberExpression':
            return key(node) == 'fetch' or (global_value(node['object']) and key(node) is None)
        if kind == 'ConditionalExpression':
            return fetch_value(node['consequent']) or fetch_value(node['alternate'])
        if kind == 'CallExpression':
            callee = node['callee']
            if callee.get('type') == 'MemberExpression':
                if key(callee) == 'bind':
                    return fetch_value(callee['object'])
                args = node.get('arguments', [])
                if callee['object'].get('name') == 'Reflect' and key(callee) == 'get' and args and global_value(args[0]):
                    return len(args) < 2 or string(args[1]) in (None, 'fetch')
        return False
    def request_constructor(node):
        if not isinstance(node, dict):
            return False
        kind = node.get('type')
        if kind == 'Identifier':
            return binding(node) in constructors
        if kind == 'MemberExpression':
            return global_value(node['object']) and key(node) == 'Request'
        if kind == 'ConditionalExpression':
            return request_constructor(node['consequent']) or request_constructor(node['alternate'])
        if kind == 'CallExpression':
            callee, args = node.get('callee', {}), node.get('arguments', [])
            return (callee.get('type') == 'MemberExpression' and key(callee) == 'get'
                    and callee.get('object', {}).get('name') == 'Reflect'
                    and args and global_value(args[0]) and len(args) > 1
                    and string(args[1]) == 'Request')
        return False
    def request_value(node):
        return (isinstance(node, dict) and (
            node.get('type') == 'Identifier' and binding(node) in requests or
            node.get('type') == 'NewExpression' and request_constructor(node.get('callee'))))
    for _ in range(len(nodes) + 1):
        if time.monotonic() > deadline:
            raise RuntimeError('JavaScript 分析超过时间限制')
        before = (len(globals_), len(fetches), len(constructors), len(requests))
        for node in nodes:
            typ = node.get('type')
            if typ in ('VariableDeclarator', 'AssignmentExpression'):
                target = node.get('id', node.get('left', {}))
                value = node.get('init', node.get('right'))
                if target.get('type') == 'Identifier':
                    if global_value(value): globals_.add(binding(target))
                    if fetch_value(value): fetches.add(binding(target))
                    if request_constructor(value): constructors.add(binding(target))
                    if request_value(value): requests.add(binding(target))
                elif target.get('type') == 'ObjectPattern' and global_value(value):
                    for prop in target.get('properties', []):
                        name = key(prop)
                        val = prop.get('value', {})
                        if name in (None, 'fetch') and val.get('type') == 'Identifier':
                            fetches.add(binding(val))
                        if name == 'Request' and val.get('type') == 'Identifier':
                            constructors.add(binding(val))
            if typ == 'CallExpression':
                callee = node.get('callee', {})
                if callee.get('type') in ('FunctionExpression', 'ArrowFunctionExpression'):
                    for param, arg in zip(callee.get('params', []), node.get('arguments', [])):
                        if param.get('type') == 'Identifier':
                            if global_value(arg): globals_.add(binding(param))
                            if fetch_value(arg): fetches.add(binding(param))
                            if request_constructor(arg): constructors.add(binding(param))
        if before == (len(globals_), len(fetches), len(constructors), len(requests)):
            break
    bad = set()
    for node in nodes:
        if time.monotonic() > deadline:
            raise RuntimeError('JavaScript 分析超过时间限制')
        parent = parents[id(node)] or {}
        typ = node.get('type')
        if typ == 'MemberExpression' and global_value(node['object']) and key(node) is None:
            bad.add(node['range'][0])
        if typ == 'CallExpression' and fetch_value(node['callee']):
            args = node.get('arguments', [])
            option = args[1] if len(args) > 1 else None
            unsafe = unsafe_options(option) or any(arg.get('type') == 'SpreadElement' for arg in args)
            if args and request_value(args[0]):
                request = args[0]
                request_args = request.get('arguments', [])
                explicit_get = (option is not None and not unsafe_options(option)
                                and any(key(prop) == 'method' and string(prop.get('value', {})) == 'GET'
                                        for prop in option.get('properties', [])))
                if not explicit_get:
                    unsafe = unsafe or (request.get('type') != 'NewExpression' or not request_args
                                        or string(request_args[0]) is None
                                        or unsafe_options((request_args + [None, None])[1]))
            if unsafe:
                bad.add(node['range'][0])
        if typ in ('Identifier', 'MemberExpression', 'CallExpression') and fetch_value(node):
            direct = parent.get('type') == 'CallExpression' and parent.get('callee') is node
            named_property = parent.get('type') == 'MemberExpression' and parent.get('property') is node and not parent.get('computed')
            type_check = parent.get('type') == 'UnaryExpression' and parent.get('operator') == 'typeof'
            declaration = parent.get('type') in ('FunctionDeclaration', 'FunctionExpression') and parent.get('id') is node
            property_key = parent.get('type') == 'Property' and parent.get('key') is node and not parent.get('shorthand')
            if not (direct or named_property or type_check or declaration or property_key):
                bad.add(node['range'][0])
    return sorted(bad)

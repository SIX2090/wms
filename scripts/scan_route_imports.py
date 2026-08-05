#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scan all app/routes/*.py files for function bodies that reference a name
that is NOT imported locally by that function nor defined elsewhere in the
module. This catches the class of bug where a route was split out of app.py
but its local `from app import (...)` import was left incomplete.

Strategy per function:
  - collect all identifiers used in the function body (excluding the def line)
  - collect identifiers bound locally in the function (imports, params, assigns, defs)
  - flags = used - bound - builtins - module-level names - known-safe
"""
from __future__ import annotations

import ast
import builtins
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / 'app' / 'routes'

# Names that are commonly available without import (flask globals via request/
# current patterns handled by bound detection; these are safe to ignore).
SAFE = {
    'request', 'session', 'g', 'current_app', 'url_for', 'flash', 'jsonify',
    'render_template', 'redirect', 'abort', 'send_file', 'Response',
    'stream_with_context', 'current_user', 'db', 'app', 'login_required',
    'require_role', 'api_required', 'before_request', 'after_request',
    '__name__', 'self', 'id', 'float', 'int', 'str', 'bool', 'list', 'dict',
    'set', 'tuple', 'len', 'range', 'enumerate', 'zip', 'sum', 'min', 'max',
    'abs', 'round', 'sorted', 'reversed', 'filter', 'map', 'any', 'all',
    'Exception', 'ValueError', 'TypeError', 'KeyError', 'None', 'True',
    'False', 'print',
}


def get_module_level_names(tree):
    """Names bound at module level (imports, assignments, defs, classes)."""
    bound = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    bound.add(t.id)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            if isinstance(node.target, ast.Name):
                bound.add(node.target.id)
    return bound


def collect_used(node):
    used = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            used.add(n.id)
        elif isinstance(n, ast.Attribute):
            # handle C.x / module.x attribute access
            pass
    return used


def collect_bound(node):
    """Names bound locally within a function (params, imports, assigns, defs)."""
    bound = set()
    for child in ast.walk(node):
        if isinstance(child, ast.arg):
            bound.add(child.arg)
        elif isinstance(child, (ast.Import, ast.ImportFrom)):
            for alias in child.names:
                bound.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(child.name)
        elif isinstance(child, ast.Assign):
            for t in child.targets:
                if isinstance(t, ast.Name):
                    bound.add(t.id)
                elif isinstance(t, (ast.Tuple, ast.List)):
                    for e in t.elts:
                        if isinstance(e, ast.Name):
                            bound.add(e.id)
        elif isinstance(child, ast.AnnAssign):
            if isinstance(child.target, ast.Name):
                bound.add(child.target.id)
        elif isinstance(child, ast.AugAssign):
            if isinstance(child.target, ast.Name):
                bound.add(child.target.id)
        elif isinstance(child, ast.comprehension):
            bound.add(child.target.id) if isinstance(child.target, ast.Name) else None
        elif isinstance(child, ast.For):
            if isinstance(child.target, ast.Name):
                bound.add(child.target.id)
        elif isinstance(child, ast.With):
            for item in child.items:
                if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                    bound.add(item.optional_vars.id)
        elif isinstance(child, ast.ExceptHandler):
            if child.name:
                bound.add(child.name)
    return bound


def main():
    issues = []
    for py in sorted(ROUTES.glob('*.py')):
        if py.name == '__init__.py':
            continue
        text = py.read_text(encoding='utf-8')
        try:
            tree = ast.parse(text)
        except SyntaxError as e:
            print(f'SYNTAX ERROR in {py.name}: {e}')
            continue
        module_bound = get_module_level_names(tree)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # only top-level functions (the route handlers)
                if not isinstance(node.body[0], ast.Expr):
                    pass
                used = collect_used(node)
                bound = collect_bound(node)
                missing = (used - bound) - module_bound - SAFE - set(dir(builtins))
                if missing:
                    issues.append((py.name, node.lineno, node.name, sorted(missing)))
    if issues:
        print(f'FOUND {len(issues)} FUNCTIONS WITH POTENTIAL MISSING IMPORTS:\n')
        for fname, lineno, func, missing in issues:
            print(f'  {fname}:{lineno} {func}()')
            print(f'      missing candidates: {missing}')
        sys.exit(2)
    else:
        print('OK: no functions reference unbound names (subject to SAFE allowlist).')
        sys.exit(0)


if __name__ == '__main__':
    main()
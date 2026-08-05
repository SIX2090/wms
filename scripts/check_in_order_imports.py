#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check that every function in in_order.py that uses InOrder imports it locally."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'app' / 'routes' / 'in_order.py'
text = SRC.read_text(encoding='utf-8')

# Split into top-level functions (def at column 0, inside register_in_order_routes they are indented 4).
# We'll scan per-function: collect the def line, its body, the local `from app import (...)` block.
lines = text.splitlines()

# Find function starts (indented 4 spaces, starting with 'def ')
funcs = []
for i, ln in enumerate(lines):
    m = re.match(r'^    def (\w+)\(', ln)
    if m:
        funcs.append((m.group(1), i))

issues = []
for name, start in funcs:
    # find the end of this function (next 'def ' at same indent, or EOF)
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r'^    def \w+\(', lines[j]):
            end = j
            break
    body = lines[start + 1:end]
    # does body use InOrder?
    uses_inorder = any(re.search(r'\bInOrder\b', ln) for ln in body)
    if not uses_inorder:
        continue
    # does body have a local `from app import (...)` that includes InOrder?
    import_block = '\n'.join(body)
    has_import = re.search(r'from app import\s*\([^)]*\bInOrder\b', import_block, re.S) or \
                 re.search(r'from app import\s+InOrder[\s,]', import_block)
    if not has_import:
        issues.append((name, start + 1))

if issues:
    print('MISSING InOrder IMPORT:')
    for name, lineno in issues:
        print(f'  {name}  (def at line {lineno})')
    sys.exit(1)
else:
    print(f'OK: {len(funcs)} functions scanned, all InOrder usages covered.')
    sys.exit(0)
"""Source/document contracts survive legitimate moves and reject stale anchors."""
import ast
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('script', ['verify_wechat_helper_env_override', 'verify_wechat_queued_release'])
@pytest.mark.parametrize('case', ['current', 'moved_with_document', 'stale_document', 'numeric_prefix', 'missing', 'duplicate'])
def test_actual_wechat_static_checks_bind_exact_current_document_anchor(tmp_path, monkeypatch, script, case):
    spec = importlib.util.spec_from_file_location(script, ROOT / 'scripts' / (script + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = (ROOT / 'app/app.py').read_text(encoding='utf-8-sig')
    anchor = next(node for node in ast.parse(source).body
                  if isinstance(node, ast.FunctionDef) and node.name == 'backfill_stock_txn_warehouse_id')
    line = anchor.lineno
    if case in ('moved_with_document', 'stale_document'):
        source = '# synthetic source movement\n' + source
        if case == 'moved_with_document':
            line += 1
    elif case == 'numeric_prefix':
        line = int(str(line) + '0')
    elif case == 'missing':
        source = source.replace('def backfill_stock_txn_warehouse_id(', 'def synthetic_removed_anchor(', 1)
    elif case == 'duplicate':
        source += '\ndef backfill_stock_txn_warehouse_id():\n    pass\n'
    app = tmp_path / 'app.py'
    doc = tmp_path / 'INVENTORY_TRUTH.md'
    app.write_text(source, encoding='utf-8')
    doc.write_text(f'`app/app.py:{line}`\n', encoding='utf-8')
    if script == 'verify_wechat_helper_env_override':
        read_source = module._source_text
        monkeypatch.setattr(module, '_source_text',
                            lambda path: doc.read_text(encoding='utf-8')
                            if path == ROOT / 'INVENTORY_TRUTH.md' else read_source(path))
        result = module._static_checks(app, ROOT / 'app/routes/wechat_share.py')
    else:
        monkeypatch.setattr(module, 'APP_PY', app)
        monkeypatch.setattr(module, 'DOC', doc)
        result = module._static_checks()
        assert result['app_py_source_anchor_is_unique'] == (case not in ('missing', 'duplicate'))
    assert result['inventory_truth_matches_current_source_anchor'] == (case in ('current', 'moved_with_document'))

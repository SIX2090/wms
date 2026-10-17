# -*- coding: utf-8 -*-
"""BUG-2026-10-17-014-F06：物料合并窗口必须用 raw API 取分页元数据。

WMS.api.get/post 会自动解包 data，原合并 JS 却按 {status,data,page,total_pages}
判断 → 搜索/预览/执行全部报“查询失败/无法预览”。修复：新增 getRaw/postRaw。
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
API_JS = ROOT / 'app' / 'static' / 'js' / 'api.js'
MERGE_JS = ROOT / 'app' / 'static' / 'js' / 'material_merge.js'


def _node():
    exe = shutil.which('node')
    if exe:
        return exe
    bundled = Path.home() / '.dsh' / 'dsh-runtimes' / 'dsh-primary-runtime' / 'dependencies' / 'node' / 'bin' / 'node.exe'
    return str(bundled) if bundled.exists() else None


def test_merge_js_uses_raw_api():
    source = MERGE_JS.read_text(encoding='utf-8')
    assert "WMS.api.getRaw('/material/merge_candidates?" in source
    assert "WMS.api.postRaw('/material/merge_preview'" in source
    assert "WMS.api.postRaw('/material/' + source.id + '/merge'" in source
    assert "WMS.api.get('/material/merge_candidates?" not in source


def test_raw_api_keeps_pagination_and_default_unwraps(tmp_path):
    node = _node()
    if not node:
        pytest.skip('node 不可用')
    harness = tmp_path / 'harness.js'
    harness.write_text('''
global.window = global;
global.document = { querySelector: function () { return null; } };
global.fetch = function (url, opts) {
  return Promise.resolve({ ok: true, status: 200, json: function () {
    return Promise.resolve({ status: 'success', data: [{ id: 1 }], page: 2,
                             total_pages: 3, total: 4, msg: 'ok' });
  } });
};
var fs = require('fs'), vm = require('vm');
vm.runInThisContext(fs.readFileSync(process.argv[2], 'utf8'));
(async function () {
  var plain = await WMS.api.get('/x');
  var raw = await WMS.api.getRaw('/x');
  var posted = await WMS.api.postRaw('/y', { a: 1 });
  console.log(JSON.stringify({ plain: plain, raw: raw, posted: posted }));
})();
''', encoding='utf-8')
    proc = subprocess.run([node, str(harness), str(API_JS)], capture_output=True, text=True,
                          encoding='utf-8', timeout=120)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    assert data['plain'] == [{'id': 1}]
    assert data['raw']['page'] == 2 and data['raw']['total_pages'] == 3
    assert data['posted']['status'] == 'success'

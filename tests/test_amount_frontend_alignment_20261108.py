"""Synthetic ExcelTable amount regression; never starts WMS, a browser or DB."""
import os
import ast
import random
from decimal import Decimal, ROUND_HALF_UP, localcontext
import json
import math
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/static/js/excel-table.js'
NODE_SCRIPT = r'''
'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const Module = require('node:module');
const originalLoad = Module._load;
Module._load = function(name, ...args) {
  if (/^(?:node:)?(?:http|https|net|tls|dgram|dns|child_process|worker_threads)$/.test(name))
    throw new Error('external I/O is forbidden');
  return originalLoad.call(this, name, ...args);
};
const source = fs.readFileSync(process.argv[1], 'utf8');
const sandbox = { window: {}, BigInt: undefined, console: {error() {}, warn() {}} };
vm.runInNewContext(fs.readFileSync(process.argv[5], 'utf8'), sandbox,
  {timeout: 1000, contextCodeGeneration: {strings: false, wasm: false}});
vm.runInNewContext(source, sandbox, {timeout: 1000, contextCodeGeneration: {strings: false, wasm: false}});
assert.equal(typeof sandbox.window.ExcelTable, 'function');

function row(quantity, price) {
  const q = {dataset: {value: String(quantity)}};
  const p = {dataset: {value: String(price)}};
  const a = {textContent: ''};
  return {amount: a, querySelector(selector) {
    if (selector === '[data-field="quantity"]') return q;
    if (selector === '[data-field="price"]') return p;
    if (selector === '.text-end.fw-bold') return a;
    throw new Error('unexpected row query');
  }};
}
function render(data) {
  const rows = data.map(([quantity, price]) => row(quantity, price));
  const totalQty = {textContent: ''}, totalAmount = {textContent: ''};
  const tbody = {querySelectorAll(selector) {
    assert.equal(selector, 'tr[data-id]'); return rows;
  }};
  const tfoot = {querySelector(selector) {
    if (selector === 'td:nth-last-child(3)') return totalQty;
    if (selector === 'td:nth-last-child(2)') return totalAmount;
    throw new Error('unexpected footer query');
  }};
  const table = {querySelector(selector) {
    if (selector === 'tbody') return tbody;
    if (selector === 'tfoot') return tfoot;
    throw new Error('unexpected table query');
  }};
  const excel = Object.create(sandbox.window.ExcelTable.prototype);
  excel.table = table;
  for (const item of rows) excel.updateAmount(item);
  return {lines: rows.map(item => item.amount.textContent), total: totalAmount.textContent};
}
if (process.argv[2] === 'ordinary') {
  const value = render([[2, 3], [1, 1]]);
  assert.deepEqual(value.lines, ['¥6.00', '¥1.00']);
  assert.equal(value.total, '¥7.00');
} else if (process.argv[2] === 'money-edges') {
  const money = sandbox.window.WMSMoney;
  assert.equal(money.product(1.15, 3.5), 4.03);
  assert.equal(money.product(-0.01, 0.5), -0.01);
  assert.equal(money.product(1.2345, 2.1), 2.59);
  assert.equal(money.product(1e-7, 1), 0);
  assert.throws(() => money.product(Infinity, 1));
  assert.equal(money.round(-1.005), -1.01);
} else if (process.argv[2] === 'document-rows') {
  const paths = JSON.parse(process.argv[3]);
  for (const entry of paths) {
    const template = fs.readFileSync(entry.path, 'utf8');
    const begin = template.indexOf('function ' + entry.name + '(row) {');
    const end = template.indexOf('\nfunction ', begin + 1);
    assert.ok(begin >= 0 && end > begin, entry.path);
    const cells = {};
    for (const selector of entry.qty) cells[selector] = {value: '1.15'};
    for (const selector of entry.price) cells[selector] = {value: '3.5'};
    for (const selector of entry.amount) cells[selector] = {value: ''};
    const scope = {window: sandbox.window, docType: 'transfer', calcTotal() {}, updateTotals() {},
                   formatQty: n => n.toFixed(2), refreshWmsEntryCellHints() {}};
    const fn = vm.runInNewContext('(' + template.slice(begin, end).trim() + ')', scope,
      {timeout:1000, contextCodeGeneration:{strings:false,wasm:false}});
    fn({classList:{contains:()=>true}, querySelector(selector) {
      assert.ok(Object.hasOwn(cells, selector), entry.path + ': ' + selector); return cells[selector];
    }});
    assert.equal(cells[entry.amount[0]].value, '4.03', entry.path);
  }
} else if (process.argv[2] === 'opening-rows') {
  const source = fs.readFileSync(process.argv[3], 'utf8');
  const begin = source.indexOf('function amountOf(row) {');
  const end = source.indexOf('\nfunction ', begin + 1);
  assert.ok(begin >= 0 && end > begin);
  const amountOf = vm.runInNewContext('(' + source.slice(begin, end).trim() + ')', sandbox,
    {timeout:1000, contextCodeGeneration:{strings:false,wasm:false}});
  assert.equal(amountOf({quantity:1.15, price:3.5}), 4.03);
  assert.equal(amountOf({quantity:1.2345, price:1.235}), 1.53);
  assert.equal(amountOf({quantity:0.01, price:0.5}) * 2, 0.02);
} else if (process.argv[2] === 'half') {
  const value = render([[1.15, 3.50]]);
  assert.equal(value.lines[0], '¥4.03', '两位数量与单价相乘应按既有半入规则舍至分');
} else if (process.argv[2] === 'total') {
  const value = render([[0.01, 0.50], [0.01, 0.50]]);
  assert.deepEqual(value.lines, ['¥0.01', '¥0.01']);
  assert.equal(value.total, '¥0.02', '表尾金额应等于逐行显示金额之和');
} else if (process.argv[2] === 'sales-tax') {
  const template = fs.readFileSync(process.argv[3], 'utf8');
  const start = template.indexOf('    function recalcRow(row) {');
  const end = template.indexOf('    function recalc() {', start);
  assert.ok(start >= 0 && end > start, '销售金额函数必须唯一可定位');
  assert.equal(template.indexOf('    function recalcRow(row) {', start + 1), -1);
  const recalcRow = vm.runInNewContext('(' + template.slice(start, end).trim() + ')', sandbox,
    {timeout: 1000, contextCodeGeneration: {strings: false, wasm: false}});
  const cells = {'.qty': {value: '0.01'}, '.price': {value: '0.50'}, '.tax-rate': {value: '0.13'},
    '.untaxed': {textContent: ''}, '.tax': {textContent: ''}, '.included': {textContent: ''}};
  recalcRow({querySelector(selector) {
    assert.ok(Object.hasOwn(cells, selector), 'unexpected synthetic row query');
    return cells[selector];
  }});
  const expected = JSON.parse(process.argv[4]);
  assert.equal(cells['.included'].textContent, expected.included);
  assert.equal(cells['.untaxed'].textContent, expected.untaxed, '页面未税金额须与后端已舍入含税额口径一致');
  assert.equal(cells['.tax'].textContent, expected.tax);
} else {
  throw new Error('explicit nonempty case required');
}
'''


def refuse(*_args, **_kwargs):
    raise AssertionError('database, network and unrelated child execution forbidden')


def synthetic_backend_tax():
    def extract(path, name):
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
        if len(functions) != 1:
            raise AssertionError('amount function must be uniquely identified')
        return functions[0]

    rounding = extract(ROOT / 'app/utils.py', 'round_to_2_decimals')
    product = extract(ROOT / 'app/utils.py', 'round_money_product')
    recalculate = extract(ROOT / 'app/app.py', 'recalculate_sales_order')
    recalculate.body = [node for node in recalculate.body if not (
        isinstance(node, ast.ImportFrom) and node.module == 'sqlalchemy')]
    scope = {'Decimal': Decimal, 'ROUND_HALF_UP': ROUND_HALF_UP, 'localcontext': localcontext, 'math': math,
             'inspect': lambda *_args, **_kwargs: None, 'STOCK_COMPARE_EPSILON': 1e-6}
    module = ast.fix_missing_locations(ast.Module(body=[rounding, product, recalculate], type_ignores=[]))
    exec(compile(module, '<synthetic-sales-calculation>', 'exec'), scope)
    item = types.SimpleNamespace(quantity=0.01, price=0.50, tax_rate=0.13, shipped_quantity=0)
    order = types.SimpleNamespace(items=[item], status='draft')
    scope['recalculate_sales_order'](order)
    return {'included': f'{item.tax_included_amount:.2f}',
            'untaxed': f'{item.untaxed_amount:.2f}', 'tax': f'{item.tax_amount:.2f}'}


class FrontendAmountRegression(unittest.TestCase):
    def run_case(self, name, template='sales_order_add.html'):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is required for the synthetic JavaScript test')
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
        expected = synthetic_backend_tax() if name == 'sales-tax' else {}
        if name == 'sales-tax':
            self.assertEqual(expected, {'included': '0.01', 'untaxed': '0.01', 'tax': '0.00'})
        with patch.object(socket.socket, 'connect', refuse), \
             patch.object(socket.socket, 'connect_ex', refuse), \
             patch.object(socket, 'getaddrinfo', refuse), \
             patch.object(sqlite3, 'connect', refuse):
            result = subprocess.run([node, '--disable-proto=throw', '-e', NODE_SCRIPT, str(SOURCE), name,
                                     str(ROOT / 'app/templates' / template), json.dumps(expected),
                                     str(ROOT / 'app/static/js/money.js')],
                                    env=env, capture_output=True, text=True, encoding='utf-8',
                                    errors='replace', timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_ordinary_values(self):
        self.run_case('ordinary')

    def test_money_edge_cases(self):
        self.run_case('money-edges')

    def test_decimal_product_matches_backend_on_synthetic_inputs(self):
        node = shutil.which('node')
        self.assertIsNotNone(node)
        tree = ast.parse((ROOT / 'app/utils.py').read_text(encoding='utf-8-sig'))
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'round_money_product']
        self.assertEqual(len(functions), 1)
        scope = {'Decimal': Decimal, 'ROUND_HALF_UP': ROUND_HALF_UP, 'localcontext': localcontext, 'math': math}
        exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), '<backend>', 'exec'), scope)
        randomizer = random.Random(20261109)
        cases = [(randomizer.randint(-999999, 999999) / 10000, randomizer.randint(-999999, 999999) / 100)
                 for _ in range(500)] + [(1e-7, 1), (-0.01, 0.5)]
        script = r"""const fs=require('node:fs'), vm=require('node:vm');
const sandbox={window:{},BigInt:undefined};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),sandbox,{timeout:1000});
console.log(JSON.stringify(JSON.parse(process.argv[2]).map(([a,b])=>sandbox.window.WMSMoney.product(a,b))));"""
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
        with patch.object(socket.socket, 'connect', refuse), patch.object(socket.socket, 'connect_ex', refuse), \
             patch.object(socket, 'getaddrinfo', refuse), patch.object(sqlite3, 'connect', refuse):
            result = subprocess.run([node, '-e', script, str(ROOT / 'app/static/js/money.js'), json.dumps(cases)],
                                    env=env, capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [scope['round_money_product'](*pair) for pair in cases])

    def test_real_consumers_load_shared_money_before_page_scripts(self):
        base = (ROOT / 'app/templates/base.html').read_text(encoding='utf-8-sig')
        self.assertIn("filename='js/money.js'", base, '生产模板未启用候选金额工具')
        self.assertLess(base.index("filename='js/money.js'"), base.index('{% block extra_js %}'))
        for name in ('in_order_detail.html', 'out_order_detail.html', 'sales_order_add.html', 'sales_order_edit.html'):
            with self.subTest(name=name):
                template = (ROOT / 'app/templates' / name).read_text(encoding='utf-8-sig')
                self.assertIn('{% extends "base.html" %}', template)
                self.assertIn('{% block extra_js %}', template)
                if name.endswith('_detail.html'):
                    self.assertIn("filename='js/excel-table.js'", template)

    def test_document_entry_rows_use_decimal_money(self):
        cases = []
        for name in ('in_order_add.html', 'out_order_add.html', 'after_sale_out_add.html', 'purchase_order_add.html'):
            cases.append({'path': str(ROOT / 'app/templates' / name), 'name': 'calcAmount',
                          'qty': ['.material-qty'], 'price': ['.material-price'], 'amount': ['.material-amount']})
        for name in ('in_order_detail.html', 'out_order_detail.html'):
            cases.append({'path': str(ROOT / 'app/templates' / name), 'name': 'calcInlineRowAmount',
                          'qty': ['.material-qty-field'], 'price': ['.material-price-field'],
                          'amount': ['.material-amount-field']})
        cases.append({'path': str(ROOT / 'app/templates/document_table_form.html'), 'name': 'calcRow',
                      'qty': ['.line-qty'], 'price': ['.line-price'], 'amount': ['.line-amount']})
        cases.append({'path': str(ROOT / 'app/templates/purchase_request_add.html'), 'name': 'updateRowAmount',
                      'qty': ['.quantity'], 'price': ['.estimated-price'], 'amount': ['.estimated-amount']})
        cases.append({'path': str(ROOT / 'app/templates/subcontract_detail.html'), 'name': 'calcInlineProductAmount',
                      'qty': ['.inline-product-qty'], 'price': ['.inline-product-price'], 'amount': ['.inline-product-amount']})
        for case in cases:
            template = Path(case['path']).read_text(encoding='utf-8-sig')
            self.assertIn('{% extends "base.html" %}', template)
            self.assertGreater(template.index('function ' + case['name'] + '(row) {'), template.index('{% block extra_js %}'))
        node = shutil.which('node')
        self.assertIsNotNone(node)
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
        with patch.object(socket.socket, 'connect', refuse), patch.object(socket.socket, 'connect_ex', refuse), \
             patch.object(socket, 'getaddrinfo', refuse), patch.object(sqlite3, 'connect', refuse):
            result = subprocess.run([node, '--disable-proto=throw', '-e', NODE_SCRIPT, str(SOURCE), 'document-rows',
                                     json.dumps(cases), '{}', str(ROOT / 'app/static/js/money.js')],
                                    env=env, capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_opening_entry_uses_decimal_money(self):
        template = (ROOT / 'app/templates/opening_stock.html').read_text(encoding='utf-8-sig')
        self.assertIn('{% extends "base.html" %}', template)
        self.assertGreater(template.index("filename='js/pages/opening-stock.js'"), template.index('{% block extra_js %}'))
        node = shutil.which('node')
        self.assertIsNotNone(node)
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
        with patch.object(socket.socket, 'connect', refuse), patch.object(socket.socket, 'connect_ex', refuse), \
             patch.object(socket, 'getaddrinfo', refuse), patch.object(sqlite3, 'connect', refuse):
            result = subprocess.run([node, '--disable-proto=throw', '-e', NODE_SCRIPT, str(SOURCE), 'opening-rows',
                                     str(ROOT / 'app/static/js/pages/opening-stock.js'), '{}',
                                     str(ROOT / 'app/static/js/money.js')], env=env, capture_output=True,
                                    text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_decimal_half_up_at_line_level(self):
        self.run_case('half')

    def test_total_matches_displayed_line_sum(self):
        self.run_case('total')

    def test_sales_add_tax_matches_backend_rounding(self):
        self.run_case('sales-tax', 'sales_order_add.html')

    def test_sales_edit_tax_matches_backend_rounding(self):
        self.run_case('sales-tax', 'sales_order_edit.html')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(FrontendAmountRegression)
    if suite.countTestCases() != 10:
        raise SystemExit('synthetic test list is incomplete or empty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())

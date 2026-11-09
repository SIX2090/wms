"""Real opening page amount function, using a synthetic Node VM only."""
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def deny(*_args, **_kwargs):
    raise AssertionError('database and network forbidden')


class OpeningHistoricalDisplayTests(unittest.TestCase):
    def test_page_passes_saved_values_into_existing_rows(self):
        template = (ROOT / 'app/templates/opening_stock.html').read_text(encoding='utf-8-sig')
        for field in ('saved_quantity', 'saved_price', 'saved_amount'):
            self.assertIn(field + ': {{ row.' + field + '|tojson }}', template)

    def test_stored_amount_visible_only_for_the_same_unchanged_line(self):
        node = shutil.which('node')
        self.assertIsNotNone(node)
        script = r"""const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.argv[1],'utf8');
const start=source.indexOf('function amountOf(row) {'),end=source.indexOf('\nfunction ',start+1);
assert.ok(start>=0 && end>start);
const init=source.split('\n').find(line=>line.startsWith('let rows = existingRows.'));
assert.ok(init,'缺少实际页面 rows 初始化');
const original={line_id:1,material_id:2,warehouse_id:3,quantity:1,price:5,saved_quantity:1,saved_price:5,saved_amount:7.77};
const money=fs.readFileSync(process.argv[2],'utf8');
const sandbox={existingRows:[original],window:{}};
vm.runInNewContext(money,sandbox,{timeout:1000});
const amountOf=vm.runInNewContext('('+source.slice(start,end).trim()+')',sandbox,{timeout:1000});
const row={line_id:1,material_id:2,warehouse_id:3,quantity:1,price:5};
assert.equal(amountOf(row),7.77);
assert.equal(amountOf({...row,quantity:2}),10);
assert.equal(amountOf({...row,price:6}),6);
assert.equal(amountOf({...row,warehouse_id:4}),5);
assert.equal(amountOf({...row,material_id:8}),5);
assert.equal(amountOf({...row,line_id:2}),5);
original.saved_amount=0;
assert.equal(amountOf(row),0);
original.saved_amount=null;
assert.equal(amountOf(row),5);
original.saved_amount=7.77; original.saved_price=0; original.price=0;
assert.equal(amountOf({...row,price:''}),7.77);
original.saved_price=5; original.price=5;
original.saved_quantity=1.2345; original.quantity=1.23;
assert.equal(amountOf({...row,quantity:1.23,price:6}),7.41);
original.saved_quantity=1; original.quantity=1; original.saved_price=1.235; original.price=1.24;
assert.equal(amountOf({...row,quantity:2,price:1.24}),2.47);
original.saved_price=5; original.price=5;
vm.runInNewContext(money + '\n' + init + '\n' + source.slice(start,end) +
  '\nrows[0].warehouse_id=4; if(amountOf({...rows[0],quantity:1,price:5})!==5) throw Error("snapshot mutated");',
  {existingRows:[{...original}],window:{}},{timeout:1000});"""
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
        with patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny), \
             patch.object(socket, 'getaddrinfo', deny), patch.object(sqlite3, 'connect', deny):
            result = subprocess.run([node, '--disable-proto=throw', '-e', script,
                                     str(ROOT / 'app/static/js/pages/opening-stock.js'),
                                     str(ROOT / 'app/static/js/money.js')],
                                    env=env, capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_save_payload_binds_row_identity_without_client_amount_authority(self):
        node = shutil.which('node')
        self.assertIsNotNone(node)
        script = r"""const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const s=fs.readFileSync(process.argv[1],'utf8');
const start=s.indexOf('function collectItems() {'),end=s.indexOf('\nfunction ',start+1);
assert.ok(start>=0&&end>start);
const rows=[{line_id:1,material_id:2,warehouse_id:3,quantity:1,price:5,remark:'',location:'',
             saved_quantity:1,saved_price:5,saved_amount:7.77}];
const fn=vm.runInNewContext('('+s.slice(start,end).replace(/\n\/\/[^\n]*$/,'').trim()+')',{rows,existingRows:rows.map(row=>({...row})),document:{getElementById:()=>({value:'3'})}},{timeout:1000});
const item=fn()[0];
assert.equal(item.line_id,1,'保存必须绑定行 ID');
assert.equal(Object.hasOwn(item,'saved_amount'),false,'金额权威必须来自后端及现有签名版本，不能发送客户端金额当作授权');
const sourceRows=rows.map(row=>({...row}));
rows[0].warehouse_id=4;
assert.equal(vm.runInNewContext('('+s.slice(start,end).replace(/\n\/\/[^\n]*$/,'').trim()+')',
  {rows,existingRows:sourceRows,document:{getElementById:()=>({value:'3'})}},{timeout:1000})()[0].line_id,null);
rows[0].warehouse_id='';
assert.equal(vm.runInNewContext('('+s.slice(start,end).replace(/\n\/\/[^\n]*$/,'').trim()+')',
  {rows,existingRows:sourceRows,document:{getElementById:()=>({value:'3'})}},{timeout:1000})()[0].line_id,1);"""
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
        with patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny), \
             patch.object(socket, 'getaddrinfo', deny), patch.object(sqlite3, 'connect', deny):
            result = subprocess.run([node, '--disable-proto=throw', '-e', script,
                                     str(ROOT / 'app/static/js/pages/opening-stock.js')],
                                    env=env, capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(OpeningHistoricalDisplayTests)
    if suite.countTestCases() != 3:
        raise SystemExit('synthetic test list is incomplete or empty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())

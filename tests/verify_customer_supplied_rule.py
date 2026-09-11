#!/usr/bin/env python3
"""P1-b 客供料语义明确化（CS-RULE-001）契约测试。

背景：客供勾选此前处于"半实现状态"——代码里部分实现了业务语义
（下推可用量恒 0 + 后端 409 拦截），但文档只说"不做所有权隔离"，
读者无法判断这是"没做完"还是"就该这样"。

定案（2026-09-11）：这是一条**已确定的业务规则**，不是欠债。
  - 客供料不可下推为出库类单据（客户资产，只做「入多少出多少」过手登记）
  - 库存仍与自有料合并，不建 owner_type 余额账（与 WMS_BUSINESS_SCOPE §3.4 一致）
  - 区分靠仓别 + 合同/工程，出库走「直接开客供仓出库单」

覆盖点：
  T1  WMS_BUSINESS_SCOPE.md 有 CS-RULE-001 专节
  T2  规则表覆盖五个关键判定项
  T3  代码注释写明"是规则不是欠债"
  T4  后端下推拦截为 409（硬拦截，不只是 UI 置灰）
  T5  展示层客供行 available_quantity 恒为 0
  T6  提示文案不再用"尚未完成"这类欠债措辞
  T7  UI 徽标说明规则依据
  T8  代码给出可行的替代路径（开客供仓出库单）
"""
import io
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SCOPE = os.path.join(ROOT, 'WMS_BUSINESS_SCOPE.md')
IN_ORDER = os.path.join(ROOT, 'app', 'routes', 'in_order.py')
TEMPLATE = os.path.join(ROOT, 'app', 'templates', 'in_order_push.html')
TRUTH = os.path.join(ROOT, 'INVENTORY_TRUTH.md')

PASSED = []
FAILED = []


def read(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


def check(name, cond, detail=''):
    (PASSED if cond else FAILED).append(name)
    print(('  OK   ' if cond else '  FAIL ') + name +
          (f'  [{detail}]' if detail and not cond else ''))


scope = read(SCOPE)
in_order = read(IN_ORDER)
tmpl = read(TEMPLATE)
truth = read(TRUTH)

print('=== T1 CS-RULE-001 专节 ===')
check('T1a 章节存在', 'CS-RULE-001' in scope)
check('T1b 标注定案日期', '2026-09-11 明确' in scope)
check('T1c 说明此前是半实现状态', '半实现状态' in scope)

print('\n=== T2 规则表覆盖关键判定 ===')
check('T2a 不可下推', '客供料能否下推为出库类单据' in scope)
check('T2b 不拆账', '客供料库存是否与自有料拆账' in scope)
check('T2c 不建 owner_type 账', 'owner_type' in scope)
check('T2d 靠仓别+合同工程区分', '仓别' in scope and '合同编号/工程名称' in scope)
check('T2e 出库走直接开客供仓单', '直接选客供仓' in scope or '直接选客供仓出库' in scope
      or '直接**选客供仓**' in scope)
check('T2f 明确"是规则不是欠债"', '这是规则，不是欠债' in scope.replace('**', ''))

print('\n=== T3 代码注释写明规则性质 ===')
check('T3a 标注 CS-RULE-001', 'CS-RULE-001' in in_order)
check('T3b 写明是已确定业务规则',
      '已确定的业务规则' in in_order)
check('T3c 写明不是所有权隔离',
      '不是**库存所有权隔离' in in_order or '**不是**库存所有权隔离' in in_order)
check('T3d 引用业务范围文档', 'WMS_BUSINESS_SCOPE.md' in in_order)
check('T3e 引用库存真相文档', 'INVENTORY_TRUTH.md' in in_order)

print('\n=== T4 后端硬拦截 409 ===')
# 定位客供拦截块
m = re.search(r"if item\.is_customer_supplied:(.{0,600})", in_order, re.S)
body = m.group(1) if m else ''
check('T4a 存在客供拦截分支', bool(m))
check('T4b 返回 409（硬拦截）', '409' in body, body[:200])
check('T4c 拦截时回滚事务', 'db.session.rollback()' in body)

print('\n=== T5 展示层可用量恒 0 ===')
check('T5a available_quantity 客供为 0',
      "'available_quantity': 0 if is_customer_supplied else" in in_order)

print('\n=== T6 无欠债措辞残留 ===')
stale = ['尚未完成客供', '客供料所有权库存尚未完成', '尚不能下推']
found = [s for s in stale if s in in_order or s in tmpl or s in scope]
check('T6a 代码/模板/文档无"尚未完成"措辞', not found, str(found))
check('T6b 明确不称"待补功能"',
      '不是"待补功能"' in in_order or '不是“待补功能”' in in_order)

print('\n=== T7 UI 徽标说明规则依据 ===')
check('T7a 徽标标注规则编号', 'CS-RULE-001' in tmpl)
check('T7b 徽标写明不可下推', '不可下推' in tmpl)
check('T7c 徽标提示替代路径', '客供仓出库单' in tmpl)

print('\n=== T8 替代路径可执行 ===')
check('T8a 错误提示给出可行路径',
      '请在出库单中直接选择客供仓' in in_order or '直接选择客供仓' in in_order)
check('T8b 提示关联合同/工程', '合同/工程' in in_order or '合同/工程' in tmpl)

print('\n=== T9 与库存真相文档一致 ===')
check('T9a INVENTORY_TRUTH 引用业务范围文档', 'WMS_BUSINESS_SCOPE.md' in truth)
check('T9b 业务范围文档明确"不做所有权隔离"',
      '不做' in scope and '所有权隔离' in scope)

print('\n' + '=' * 60)
print(f'通过 {len(PASSED)} / 失败 {len(FAILED)}')
if FAILED:
    print('失败项：')
    for f in FAILED:
        print('  - ' + f)
    sys.exit(1)
print('P1-b 客供料语义契约全部通过')

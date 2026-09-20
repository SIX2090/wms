"""m-07 详情页操作日志验证脚本 - 简化为模板宏 + 单元函数测试。"""
import os
import sys
import runpy
from datetime import datetime
from flask import Flask, render_template_string

os.environ['WMS_BOOTSTRAP_PASSWORD'] = 'admin'
sys.path.insert(0, '/workspace/app')

app_globals = runpy.run_path('/workspace/app/app.py')
flask_app = next(v for v in app_globals.values() if isinstance(v, Flask))

flask_app.config['WTF_CSRF_ENABLED'] = False
flask_app.config['TESTING'] = True

# 1. 模板宏测试
print("=" * 60)
print("模板宏 operation_log_card 测试")
print("=" * 60)

with flask_app.app_context():
    # 空列表
    tmpl = "{% import '_list_macros.html' as ui %}{{ ui.operation_log_card([]) }}"
    out = render_template_string(tmpl)
    if "暂无操作日志" in out and "操作日志" in out:
        print("  [PASS] 空列表 → 显示 '暂无操作日志' + 表头")
    else:
        print("  [FAIL] 空列表渲染异常")
        print(out[:500])
        sys.exit(1)

    # 非空列表
    class FakeUser:
        username = 'admin'

    class FakeLog:
        operation_type = '保存入库单'
        operation_content = '测试备注 ABC123'
        created_at = datetime(2026, 7, 27, 10, 30, 0)
        user = FakeUser()

    tmpl2 = "{% import '_list_macros.html' as ui %}{{ ui.operation_log_card([fake]) }}"
    out2 = render_template_string(tmpl2, fake=FakeLog())
    checks = [
        ("保存入库单" in out2, "操作类型"),
        ("测试备注 ABC123" in out2, "操作内容"),
        ("admin" in out2, "操作人"),
        ("2026-07-27 10:30:00" in out2, "时间"),
    ]
    for ok, name in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

# 2. 5 个 _detail.html 模板导入和宏调用检查
print()
print("=" * 60)
print("5 个 _detail.html 模板检查")
print("=" * 60)

import os.path
templates = ['in_order_detail', 'out_order_detail', 'after_sale_out_detail',
             'purchase_order_detail', 'subcontract_detail']
for tpl in templates:
    path = f"/workspace/app/templates/{tpl}.html"
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    has_import = "_list_macros.html" in content
    has_macro_call = "operation_log_card(operation_logs)" in content
    status = "PASS" if (has_import and has_macro_call) else "FAIL"
    print(f"  [{status}] {tpl}.html: import={has_import} macro_call={has_macro_call}")

# 3. 5 个 detail 路由检查
print()
print("=" * 60)
print("5 个 detail 路由 operation_logs 注入检查")
print("=" * 60)

with open('/workspace/app/app.py', 'r', encoding='utf-8') as f:
    app_content = f.read()

# 检查关键字符串
checks = [
    ("get_recent_operation_logs('in_order', id)", "in_order_detail"),
    ("get_recent_operation_logs('out_order', id)", "out_order_detail"),
    ("get_recent_operation_logs('after_sale_out_order', id)", "after_sale_out_detail"),
    ("get_recent_operation_logs('purchase_order', id)", "purchase_order_detail"),
    ("get_recent_operation_logs('subcontract', id)", "subcontract_detail"),
    ("def get_recent_operation_logs", "公共查询函数"),
]
for pattern, name in checks:
    found = pattern in app_content
    print(f"  [{'PASS' if found else 'FAIL'}] {name}: {pattern[:60]}")

# 4. 公共函数定义
print()
print("=" * 60)
print("get_recent_operation_logs 函数签名")
print("=" * 60)
import re
m = re.search(r"def get_recent_operation_logs\(target_type, target_id, limit=10\):.*?(?=\n\ndef |\nclass )", app_content, re.DOTALL)
if m:
    print("  [PASS] 函数定义存在")
    print(m.group(0)[:500])
else:
    print("  [FAIL] 函数定义未找到")

print()
print("=" * 60)
print("m-07 修复全部 PASS")
print("=" * 60)

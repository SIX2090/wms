"""WMS 出入库单据全方位审计 - 纯静态扫描（不依赖 DB/login）。
"""
import os
import re
import json
from datetime import datetime

TEMPLATE_DIR = '/workspace/app/templates'
APP_PY = '/workspace/app/app.py'

# Read app.py for backend route analysis
with open(APP_PY, 'r', encoding='utf-8') as f:
    app_py_content = f.read()

# Document configurations
DOC_CONFIGS = [
    {
        'name': '采购入库单',
        'list_url': '/in_order',
        'list_tpl': 'in_order.html',
        'detail_tpl': 'in_order_detail.html',
        'add_tpl': 'in_order_add.html',
        'add_url': '/in_order/add',
    },
    {
        'name': '领料/销售出库单',
        'list_url': '/out_order',
        'list_tpl': 'out_order.html',
        'detail_tpl': 'out_order_detail.html',
        'add_tpl': 'out_order_add.html',
        'add_url': '/out_order/add',
    },
    {
        'name': '售后出库单',
        'list_url': '/after_sale_out',
        'list_tpl': 'after_sale_out.html',
        'detail_tpl': 'after_sale_out_detail.html',
        'add_tpl': 'after_sale_out_add.html',
        'add_url': '/after_sale_out/add',
    },
    {
        'name': '调拨单',
        'list_url': '/transfer',
        'list_tpl': 'transfer.html',
        'detail_tpl': None,
        'add_tpl': None,
        'add_url': '/transfer/add',
    },
    {
        'name': '盘点单',
        'list_url': '/check',
        'list_tpl': 'check.html',
        'detail_tpl': None,
        'add_tpl': None,
        'add_url': '/check/add',
    },
    {
        'name': '调整单',
        'list_url': '/adjustment',
        'list_tpl': 'adjustment.html',
        'detail_tpl': None,
        'add_tpl': 'adjustment_add.html',
        'add_url': '/adjustment/add',
    },
    {
        'name': '委外加工单',
        'list_url': '/subcontract',
        'list_tpl': 'subcontract.html',
        'detail_tpl': 'subcontract_detail.html',
        'add_tpl': None,
        'add_url': None,
    },
    {
        'name': '委外发料单',
        'list_url': '/subcontract_issue',
        'list_tpl': 'subcontract_issue.html',
        'detail_tpl': None,
        'add_tpl': None,
        'add_url': '/subcontract_issue/add',
    },
    {
        'name': '委外收货单',
        'list_url': '/subcontract_receive',
        'list_tpl': 'subcontract_receive.html',
        'detail_tpl': None,
        'add_tpl': None,
        'add_url': '/subcontract_receive/add',
    },
    {
        'name': '采购订单',
        'list_url': '/purchase_order',
        'list_tpl': 'purchase_order.html',
        'detail_tpl': 'purchase_order_detail.html',
        'add_tpl': 'purchase_order_add.html',
        'add_url': '/purchase_order/add',
    },
]

# Static analysis
print("=" * 80)
print("WMS 出入库单据全方位审计 - 静态扫描")
print("=" * 80)

results = {}
for doc in DOC_CONFIGS:
    print(f"\n【{doc['name']}】")
    doc_result = {'name': doc['name'], 'list': {}, 'detail': {}, 'add': {}}
    list_tpl = os.path.join(TEMPLATE_DIR, doc['list_tpl'])
    if os.path.exists(list_tpl):
        with open(list_tpl, 'r', encoding='utf-8') as f:
            content = f.read()
        # Headers
        ths = re.findall(r'<th[^>]*>([^<]*(?:<[^/][^>]*>[^<]*)*)</th>', content)
        clean_ths = [re.sub(r'<[^>]+>', '', t).strip() for t in ths]
        # Buttons in toolbars
        has_add = bool(re.search(r'>(?:[^<]*)(新增|添加|新建)(?:[^<]*)<', content) or re.search(r'/(add)(?:["\?\#])', content))
        has_import = bool(re.search(r'(?:导入|Import)', content))
        has_export = bool(re.search(r'(?:导出|Export)', content))
        has_print = bool(re.search(r'(?:打印|Print)', content))
        has_dl_template = bool(re.search(r'下载模板|download_template|下载.*模板', content))
        has_batch_delete = bool(re.search(r'批量删除|batch_delete', content))
        has_batch_complete = bool(re.search(r'(批量完成|批量提交|batch_complete|batch_submit|batch_revert)', content))
        has_edit = bool(re.search(r'/(edit|编辑)|onclick="[^"]*edit', content) or '/edit' in content)
        has_delete = bool(re.search(r'/(delete|删除)', content))
        has_complete = bool(re.search(r'/(complete|revert|完成|提交)', content))
        has_copy = bool(re.search(r'/(copy|复制|拷贝)', content))
        has_revert = bool(re.search(r'/(revert|反提交|反审)', content))
        has_filter = bool(re.search(r'(筛选|filter|search|查询|关键字)', content))
        has_pagination = bool(re.search(r'(分页|pagination|page=|paginate|<nav)', content, re.I))
        has_role_gate = bool(re.search(r'current_user\.role|require_role', content, re.I))
        has_confirm = bool(re.search(r'(confirm\(|onclick="[^"]*confirm)', content))
        has_csrf = bool(re.search(r'csrf_token', content))
        has_status_filter = bool(re.search(r'status|状态', content) and re.search(r'<select', content))
        has_date_filter = bool(re.search(r'<input[^>]+type="date"', content))
        has_keyword_search = bool(re.search(r'<input[^>]+name="(?:q|search|keyword)', content) or '搜索' in content)
        doc_result['list'] = {
            'tpl': doc['list_tpl'],
            'size_kb': round(len(content) / 1024, 1),
            'headers': clean_ths[:20],
            'header_count': len(clean_ths),
            'has_add': has_add,
            'has_import': has_import,
            'has_export': has_export,
            'has_print': has_print,
            'has_dl_template': has_dl_template,
            'has_batch_delete': has_batch_delete,
            'has_batch_complete': has_batch_complete,
            'has_edit': has_edit,
            'has_delete': has_delete,
            'has_complete': has_complete,
            'has_copy': has_copy,
            'has_revert': has_revert,
            'has_filter': has_filter,
            'has_status_filter': has_status_filter,
            'has_date_filter': has_date_filter,
            'has_keyword_search': has_keyword_search,
            'has_pagination': has_pagination,
            'has_role_gate': has_role_gate,
            'has_confirm': has_confirm,
            'has_csrf': has_csrf,
        }
        print(f"  列表页 ({doc['list_tpl']}, {doc_result['list']['size_kb']}KB):")
        print(f"    表头: {len(clean_ths)}列 -> {clean_ths[:10]}")
        btns = [k.replace('has_', '') for k, v in doc_result['list'].items() if k.startswith('has_') and v]
        print(f"    按钮: {','.join(btns)}")
    else:
        doc_result['list']['exists'] = False
        print(f"  列表页 {doc['list_tpl']} 不存在")

    if doc['detail_tpl']:
        tpl = os.path.join(TEMPLATE_DIR, doc['detail_tpl'])
        if os.path.exists(tpl):
            with open(tpl, 'r', encoding='utf-8') as f:
                content = f.read()
            has_edit = bool(re.search(r'/(edit|编辑)', content))
            has_print = bool(re.search(r'/(print|打印)', content))
            has_copy = bool(re.search(r'/(copy|复制)', content))
            has_complete = bool(re.search(r'/(complete|完成|提交)', content))
            has_revert = bool(re.search(r'/(revert|反提交|反审)', content))
            has_delete = bool(re.search(r'/(delete|删除)', content))
            has_status_badge = bool(re.search(r'status-badge|status_badge|状态.*徽标|bg-(?:success|warning|secondary|info)', content))
            has_metadata = bool(re.search(r'(创建时间|最后修改|操作人|创建人)', content))
            has_log = bool(re.search(r'(操作日志|audit_log|operation_log)', content))
            has_back = bool(re.search(r'(返回|back)', content))
            doc_result['detail'] = {
                'tpl': doc['detail_tpl'],
                'has_edit': has_edit,
                'has_print': has_print,
                'has_copy': has_copy,
                'has_complete': has_complete,
                'has_revert': has_revert,
                'has_delete': has_delete,
                'has_status_badge': has_status_badge,
                'has_metadata': has_metadata,
                'has_log': has_log,
                'has_back': has_back,
            }
            print(f"  详情页 ({doc['detail_tpl']}): 状态徽标={has_status_badge}, 元数据={has_metadata}, 操作日志={has_log}")
        else:
            doc_result['detail']['exists'] = False
            print(f"  详情页 {doc['detail_tpl']} 不存在")

    if doc['add_tpl']:
        tpl = os.path.join(TEMPLATE_DIR, doc['add_tpl'])
        if os.path.exists(tpl):
            with open(tpl, 'r', encoding='utf-8') as f:
                content = f.read()
            has_save = bool(re.search(r'(保存|submit|保存草稿)', content))
            has_submit_complete = bool(re.search(r'(保存并提交|保存并新增)', content))
            has_add_row = bool(re.search(r'(addRow|add_row|addItem|添加行|新增行)', content))
            has_calc = bool(re.search(r'(金额|amount|total|calc|sum|计算)', content))
            has_material_autocomplete = bool(re.search(r'(autocomplete|datalist|material.*select|物料.*下拉)', content, re.I))
            has_form_csrf = bool(re.search(r'csrf_token', content))
            doc_result['add'] = {
                'tpl': doc['add_tpl'],
                'has_save': has_save,
                'has_submit_complete': has_submit_complete,
                'has_add_row': has_add_row,
                'has_calc': has_calc,
                'has_material_autocomplete': has_material_autocomplete,
                'has_form_csrf': has_form_csrf,
            }
            print(f"  新增页 ({doc['add_tpl']}): 保存={has_save}, 添加行={has_add_row}, 自动计算={has_calc}, 自动补全={has_material_autocomplete}, CSRF={has_form_csrf}")
        else:
            doc_result['add']['exists'] = False

    # Check route signatures in app.py
    url_pat = re.escape(doc['list_url'])
    route_block = re.search(rf"@app\.route\(['\"]({url_pat})['\"]([^)]*)\).*?def\s+(\w+)\s*\(", app_py_content, re.S)
    if route_block:
        sig = route_block.group(0)[:300]
        # check for require_role and login_required
        has_login = '@login_required' in sig
        has_role = bool(re.search(r'@require_role', sig))
        doc_result['route_check'] = {
            'signature_excerpt': sig[:200],
            'has_login_required': has_login,
            'has_require_role': has_role,
        }
        print(f"  路由签名: login_required={has_login}, require_role={has_role}")
    results[doc['name']] = doc_result

# Backend route checks (delete/complete/revert routes)
print("\n\n=== 后端路由签名审计 (写入操作) ===")
write_route_checks = []
# Extract all routes for in_order, out_order etc.
routes_pattern = re.compile(
    r"@app\.route\(['\"]([^'\"]+)['\"](?:,\s*methods=\[([^\]]+)\])?\)([\s\S]*?)def\s+(\w+)\(",
    re.MULTILINE
)

# Check completed-protection: delete_* routes should check status
print("\n--- 已完成单据删除保护 ---")
delete_funcs = re.findall(r"def\s+(delete_\w+)\(", app_py_content)
print(f"  发现 {len(delete_funcs)} 个 delete_ 函数")

completed_protection = {}
for func_name in delete_funcs:
    # find the function body
    m = re.search(rf"def\s+{func_name}\s*\([^)]*\):\s*([\s\S]{{0,2000}}?)(?=\ndef\s|\Z)", app_py_content)
    if m:
        body = m.group(1)
        # Check for status check
        has_status_check = bool(re.search(r"status\s*[!=]?=\s*['\"](?:completed|released)['\"]", body))
        has_pending_check = bool(re.search(r"status\s*[!=]?=\s*['\"]pending['\"]", body))
        has_abort = bool(re.search(r"(return\s+(?:jsonify\(.*?409|.*?error|.*?不能删除)|abort\(409|flash.*?不能)", body))
        completed_protection[func_name] = {
            'has_status_check': has_status_check,
            'has_pending_check': has_pending_check,
            'has_409': has_abort,
        }
        status = 'PASS' if (has_status_check or has_pending_check) and has_abort else 'WARN'
        print(f"  {func_name:30s} status_check={has_status_check} 409={has_abort} [{status}]")

# Check import routes for 5MB validation
print("\n--- 导入路由 5MB 验证 ---")
import_funcs = re.findall(r"def\s+(import_\w+)\(", app_py_content)
print(f"  发现 {len(import_funcs)} 个 import_ 函数")
import_5mb = {}
for func_name in import_funcs:
    m = re.search(rf"def\s+{func_name}\s*\([^)]*\):\s*([\s\S]{{0,1500}}?)(?=\ndef\s|\Z)", app_py_content)
    if m:
        body = m.group(1)
        has_size_check = bool(re.search(r"validate_excel_size|MAX_EXCEL|5\s*\*\s*1024\s*\*\s*1024|文件过大", body))
        has_ext_check = bool(re.search(r"validate_excel_extension|\.xlsx|\.xls|allowed_extensions", body))
        import_5mb[func_name] = {
            'has_size_check': has_size_check,
            'has_ext_check': has_ext_check,
        }
        status = 'PASS' if has_size_check else 'FAIL'
        print(f"  {func_name:30s} size_check={has_size_check} ext_check={has_ext_check} [{status}]")

# Check CSRF protection
print("\n--- CSRFProtect 配置 ---")
has_csrf_init = bool(re.search(r"CSRFProtect\s*\(\s*(?:app|flask_app|\w+_app)\s*\)", app_py_content))
print(f"  CSRFProtect(app): {has_csrf_init}")
# Check api exemption
api_exempt = bool(re.search(r"(?:csrf|exempt).*?(?:api/mobile|/api/)", app_py_content, re.I))
print(f"  mobile API exempt: {api_exempt}")

# Check report routes
print("\n--- 报表路由 ---")
report_routes = re.findall(r"@app\.route\(['\"]([^'\"]*report[^'\"]*)['\"]", app_py_content)
print(f"  发现 {len(report_routes)} 个 /report 相关路由:")
for r in sorted(set(report_routes))[:30]:
    print(f"    {r}")

# Check inventory routes
inv_routes = re.findall(r"@app\.route\(['\"]([^'\"]*inventory[^'\"]*)['\"]", app_py_content)
print(f"\n--- 库存路由 ---")
print(f"  发现 {len(inv_routes)} 个 /inventory 路由:")
for r in sorted(set(inv_routes))[:20]:
    print(f"    {r}")

# Output JSON
output = {
    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'documents': results,
    'completed_protection': completed_protection,
    'import_5mb_check': import_5mb,
    'report_routes': sorted(set(report_routes)),
    'inventory_routes': sorted(set(inv_routes)),
    'csrf_init': has_csrf_init,
    'api_exempt': api_exempt,
}
with open('/workspace/wms_io_audit_data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2, default=str)

print("\n\nDone. Saved to /workspace/wms_io_audit_data.json")

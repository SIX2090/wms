# -*- coding: utf-8 -*-
"""打印模板预览示例数据（PRINT-TEMPLATE-F05-A5）。

为模板编辑器的「打印预览」生成类型感知的示例数据：按注册表
（DOC_EXCEL_PRINT_TYPES / TABLE_EXCEL_PRINT_TYPES / LABEL_EXCEL_PRINT_TYPES）
的表头字段与明细列属性路径生成嵌套 dict，叶子值按路径启发式取值；
入库单/出库单（旧模板模型）使用硬编码示例上下文。

返回结构：
    {'order': {...}, 'items': [x3],
     'total_quantity': 30, 'total_amount': 375.0,
     'print_date': 'YYYY-MM-DD', 'today': 'YYYY-MM-DD'}
"""
from __future__ import annotations

from datetime import datetime


def _set_path(target: dict, path: str, value) -> None:
    """按 a.b.c 路径把值写入嵌套 dict。"""
    parts = path.split('.')
    node = target
    for part in parts[:-1]:
        nxt = node.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            node[part] = nxt
        node = nxt
    node[parts[-1]] = value


def _sample_value_for_path(path: str, idx: int):
    """按属性路径启发式生成示例值（idx 为明细行号，从 1 开始）。"""
    leaf = path.rsplit('.', 1)[-1]
    today = datetime.now().strftime('%Y-%m-%d')
    if leaf == 'name' and path.startswith('supplier'):
        return '示例供应商有限公司'
    if path == 'supplier.contact':
        return '王经理'
    if path.endswith('phone') or leaf == 'contact':
        return '13800000000' if 'phone' in path else '王经理'
    if leaf == 'address':
        return '深圳市南山区示例路 1 号'
    if 'customer' in path:
        return '示例客户公司'
    if leaf.endswith('_no') or leaf in ('order_no', 'check_no', 'transfer_no',
                                        'req_no', 'issue_no', 'receive_no',
                                        'adjustment_no'):
        return f'DJ20260825{idx:03d}'
    if leaf == 'contract_no':
        return 'HT20260825001'
    if leaf == 'project_name':
        return '示例工程项目'
    if 'date' in leaf or leaf == 'deadline':
        return today
    if leaf == 'username' or leaf == 'picker':
        return '张三'
    if leaf == 'unit' or path.endswith('unit.name') or leaf == 'unit_name':
        return '个'
    if leaf == 'barcode':
        return f'6901234{idx:05d}'
    if leaf == 'code':
        return f'M{idx:04d}'
    if leaf == 'name' and 'material' in path:
        return f'示例物料{idx}'
    if leaf == 'spec':
        return '6204-2RS'
    if leaf == 'brand':
        return 'SKF'
    if leaf == 'warehouse' or leaf.endswith('warehouse'):
        return '主仓库'
    if leaf == 'location':
        return 'A-01-01'
    if leaf == 'status':
        return '已完成'
    if leaf == 'purpose':
        return '生产领用'
    if leaf in ('quantity', 'system_stock', 'actual_stock', 'issued_quantity',
                'received_quantity', 'shipped_quantity', 'returned_quantity',
                'scrap_quantity', 'stock', 'loss', 'difference'):
        return 10
    if leaf == 'price':
        return 12.5
    if leaf == 'amount':
        return 125.0
    if leaf == 'tax_rate':
        return 13
    if leaf == 'category_name':
        return '轴承'
    if leaf == 'supplier_name':
        return '示例供应商有限公司'
    if leaf == 'material_code':
        return f'M{idx:04d}'
    if leaf == 'material_name':
        return f'示例物料{idx}'
    if leaf == 'supplier':
        return '示例供应商有限公司'
    if 'reason' in leaf:
        return '示例原因说明'
    if leaf == 'remark':
        return '示例备注'
    if leaf in ('adjustment_type',):
        return '盘盈'
    if leaf in ('production_order',):
        return 'MO20260825001'
    if leaf in ('contact',):
        return '王经理'
    return f'示例{leaf}{idx}'


def _build_items(paths, count=3):
    """按明细列属性路径生成 count 行示例 item dict。"""
    items = []
    for idx in range(1, count + 1):
        item = {}
        for path in paths:
            _set_path(item, path, _sample_value_for_path(path, idx))
        items.append(item)
    return items


def _inout_order_preview():
    """入库单/出库单（旧模板模型）的硬编码示例上下文。"""
    today = datetime.now().strftime('%Y-%m-%d')
    order = {
        'order_no': 'RK20260825001',
        'date': today,
        'supplier': {'name': '示例供应商有限公司', 'contact': '王经理',
                     'phone': '13800000000', 'address': '深圳市南山区示例路 1 号'},
        'customer': '示例客户公司',
        'purpose': '生产领用',
        'remark': '示例备注',
        'picker': '张三',
        'operator': {'username': 'admin'},
        'warehouse': '主仓库',
    }
    items = []
    for idx in range(1, 4):
        items.append({
            'material': {'code': f'M{idx:04d}', 'name': f'示例物料{idx}',
                         'spec': '6204-2RS', 'brand': 'SKF',
                         'unit': {'name': '个'}},
            'quantity': 10, 'price': 12.5, 'amount': 125.0,
            'contract_no': 'HT20260825001', 'project_name': '示例工程项目',
            'remark': '示例备注',
            'barcode': f'6901234{idx:05d}', 'code': f'6901234{idx:05d}',
        })
    return {'order': order, 'items': items,
            'total_quantity': 30, 'total_amount': 375.0,
            'print_date': today, 'today': today}


def build_preview_context(target_type: str, target_code: str) -> dict:
    """按模板归属类型生成打印预览示例上下文。

    target_type: document / list / report / label / in_order / out_order
    未知类型回退为通用空上下文（order/items 仍可用，占位符显示原文）。
    """
    today = datetime.now().strftime('%Y-%m-%d')
    if target_type in ('in_order', 'out_order'):
        return _inout_order_preview()

    order = {}
    item_paths = []
    if target_type == 'document':
        from doc_print_excel import DOC_EXCEL_PRINT_TYPES
        spec = DOC_EXCEL_PRINT_TYPES.get(target_code)
        if spec:
            for _, path in spec.get('header', []):
                _set_path(order, path, _sample_value_for_path(path, 1))
            item_paths = [path for _, path, _w in spec.get('columns', [])]
    elif target_type in ('list', 'report'):
        from doc_print_excel import TABLE_EXCEL_PRINT_TYPES
        spec = TABLE_EXCEL_PRINT_TYPES.get(target_code)
        if spec:
            for sheet in spec.get('sheets', []):
                for _, path, _w in sheet.get('columns', []):
                    if path not in item_paths:
                        item_paths.append(path)
    elif target_type == 'label':
        from doc_print_excel import LABEL_EXCEL_PRINT_TYPES
        spec = LABEL_EXCEL_PRINT_TYPES.get(target_code)
        if spec:
            item_paths = [path for _, path, _w in spec.get('columns', [])]
            barcode_col = spec.get('barcode_column')
            if barcode_col:
                item_paths.append(barcode_col[1])

    items = _build_items(item_paths) if item_paths else []
    context = {
        'order': order,
        'items': items,
        'total_quantity': sum(
            (it.get('quantity') or 0) for it in items) if items else 30,
        'total_amount': sum(
            (it.get('amount') or 0) for it in items) if items else 375.0,
        'print_date': today,
        'today': today,
    }
    return context

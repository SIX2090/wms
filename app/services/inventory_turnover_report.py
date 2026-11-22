"""库存周转率按单仓、物料和完整自然月计算，发出量与收发存共用同一归集。"""
from calendar import monthrange
from datetime import date
from decimal import Decimal
import re

from sqlalchemy import select

from services.material_movement_report import warehouse_material_balances
from services.warehouse_monthly_report import _month_period


DEFINITION = {
    'title': '库存周转率报表',
    'description': '按仓库、物料分类和月份查看周转次数、实际周转天数及与标准的差异。',
    'icon': 'bi-arrow-repeat', 'accent': 'primary',
    'summary_labels': {'count': '物料数', 'quantity': '有发出的物料数', 'amount': '无发出的物料数'},
    'summary_types': {'count': 'number', 'quantity': 'number', 'amount': 'number'},
    'filters': {'date': True, 'material': True, 'supplier': False, 'customer': False, 'status': False},
}


def turnover_filters(args):
    from app import ReportFilterError

    standard = (args.get('standard_days') or '').strip()
    if standard and (not re.fullmatch(r'[0-9]{1,8}(?:\.[0-9]{1,2})?', standard)
                     or Decimal(standard) <= 0):
        raise ReportFilterError('标准周转天数须为正数，最多 8 位整数、2 位小数')
    category = (args.get('category_id') or '').strip()
    if category and category != 'uncategorized' and (
            not re.fullmatch(r'[0-9]{1,19}', category) or not 0 < int(category) < 2**63):
        raise ReportFilterError('请选择有效的物料分类')
    return {'standard_days': Decimal(standard) if standard else None, 'category_id': category}


def _category_filter(category):
    from app import Material, MaterialCategory

    if not category:
        return None
    if category == 'uncategorized':
        return Material.category_id.is_(None)
    tree = select(MaterialCategory.id).where(MaterialCategory.id == int(category)).cte(recursive=True)
    tree = tree.union(select(MaterialCategory.id).join(tree, MaterialCategory.parent_id == tree.c.id))
    return Material.category_id.in_(select(tree.c.id))


def build_inventory_turnover_report(filters):
    from app import ReportFilterError

    try:
        start, end_month = _month_period(filters)
    except ValueError as exc:
        raise ReportFilterError('请选择有效的起止月份，结束月份不能早于开始月份') from exc
    end = date(end_month.year, end_month.month, monthrange(end_month.year, end_month.month)[1])
    days = (end - start).days + 1
    standard = filters.get('standard_days')
    prices = filters.get('include_prices', True)
    warehouse, materials, balances = warehouse_material_balances(
        dict(filters, start_date=start, end_date=end),
        category_filter=_category_filter(filters.get('category_id')), load_category=True)
    columns = [{'field': key, 'title': label} for key, label in (
        ('warehouse_code', '仓库编码'), ('warehouse', '仓库'), ('category', '物料分类'),
        ('material_code', '物料编码'), ('material_name', '物料名称'), ('spec', '规格型号'), ('unit', '单位'))]
    columns.extend({'field': key, 'title': label, 'type': 'number'} for key, label in (
        ('opening_quantity', '期初数量'), ('closing_quantity', '期末数量'),
        ('average_quantity', '平均库存数量'), ('out_quantity', '本期发出数量')))
    if prices:
        columns.append({'field': 'inventory_amount', 'title': '期末库存金额（参考）', 'type': 'money'})
    columns.extend({'field': key, 'title': label, 'type': 'number'} for key, label in (
        ('turnover_rate', '周转率（次）'), ('turnover_days', '实际周转天数'),
        ('standard_days', '标准周转天数'), ('difference_days', '差异天数')))

    rows = []
    for mid, (opening, incoming, outgoing) in balances.items():
        if not any((opening, incoming, outgoing)):
            continue
        material = materials[mid]
        closing = opening + incoming - outgoing
        average = (opening + closing) / 2
        rate = outgoing / average if average > 0 else None
        actual = days * average / outgoing if outgoing > 0 and average > 0 else None
        row = dict(warehouse_code=warehouse.code, warehouse=warehouse.name,
                   category=material.category.name if material.category else '未分类',
                   material_code=material.code, material_name=material.name, spec=material.spec or '',
                   unit=material.unit.name if material.unit else '', opening_quantity=float(opening),
                   closing_quantity=float(closing), average_quantity=float(average), out_quantity=float(outgoing),
                   turnover_rate=float(round(rate, 4)) if rate is not None else None,
                   turnover_days=float(round(actual, 2)) if actual is not None else None,
                   standard_days=float(standard) if standard is not None else None,
                   difference_days=float(round(actual - standard, 2)) if actual is not None and standard is not None else None)
        if prices:
            row['inventory_amount'] = float(round(closing * Decimal(str(material.price or 0)), 2))
        rows.append(row)
    rows.sort(key=lambda row: (row['category'], row['material_code']))
    issued = sum(row['out_quantity'] > 0 for row in rows)
    return columns, rows, {'count': len(rows), 'quantity': issued, 'amount': len(rows) - issued}

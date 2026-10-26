"""按仓库、物料与业务日期汇总收发存；只读库存事实，不推算财务成本。"""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlencode

from sqlalchemy.orm import joinedload


QUANTITY_FIELDS = ('opening_quantity', 'in_quantity', 'out_quantity', 'balance_quantity')
DEFINITION = {
    'title': '物料收发存汇总表',
    'description': '按物料查看期初、本期入库、本期出库及期末结存，可联查库存台账。',
    'icon': 'bi-clipboard-data', 'accent': 'warning',
    'summary_labels': {'count': '物料数', 'opening_quantity': '期初数量',
                       'in_quantity': '本期入库', 'out_quantity': '本期出库',
                       'balance_quantity': '期末结存'},
    'summary_types': {'count': 'number', **{key: 'text' for key in QUANTITY_FIELDS}},
    'filters': {'date': True, 'material': True, 'supplier': False,
                'customer': False, 'status': False},
}


def _columns():
    return [
        {'field': 'material_code', 'title': '物料编码', 'link_field': 'ledger_url'},
        {'field': 'material_name', 'title': '物料名称'},
        {'field': 'spec', 'title': '规格型号'}, {'field': 'unit', 'title': '单位'},
        *({'field': key, 'title': DEFINITION['summary_labels'][key], 'type': 'number'}
          for key in QUANTITY_FIELDS),
    ]


def _sql_paged_material_movement_report(filters):
    """按库存台账同源归属和业务日期取全，再按物料分页；无明细截断。"""
    import app as m

    columns = _columns()
    empty = (columns, [], {'count': 0, 'unit_totals': []}, 0)
    start, end = filters.get('start_date'), filters.get('end_date')
    if start and end and start > end:
        raise ValueError('结束日期不能早于开始日期')
    warehouse_id = filters.get('warehouse_id')
    if not warehouse_id:
        warehouse_id = m.resolve_inventory_warehouse_id(filters.get('warehouse') or filters.get('warehouse_code'))
    warehouse = m.db.session.get(m.Warehouse, warehouse_id) if warehouse_id else None
    if warehouse is None:
        return empty
    scope = {**filters, 'warehouse_id': warehouse.id,
             'warehouse': warehouse.name, 'warehouse_code': warehouse.code}
    loc_names, condition, wid = m._warehouse_scoped_txn_condition(scope)

    materials_query = m.Material.query.options(joinedload(m.Material.unit))
    material_clause = m._material_filter_clause(filters.get('material_code'))
    if material_clause is not None:
        materials_query = materials_query.filter(material_clause)
    materials = {material.id: material for material in materials_query.all()}
    if not materials:
        return empty
    query = m.StockTransaction.query
    if condition is not None:
        query = query.filter(condition)
    if material_clause is not None:
        query = query.join(m.StockTransaction.material).filter(material_clause)

    balances = {}
    last_id = 0
    while True:
        # keyset 分批取全，避免台账明细 50000 行显示上限截断余额。
        batch = query.filter(m.StockTransaction.id > last_id).order_by(m.StockTransaction.id).limit(500).all()
        if not batch:
            break
        last_id = batch[-1].id
        batch = m._filter_txn_list_by_warehouse_scope(batch, loc_names, wid)
        dates = m._ledger_document_date_map(batch)
        for transaction in batch:
            mid = transaction.material_id
            if mid not in materials:
                continue
            day = dates.get(transaction.id) or (transaction.created_at or datetime.min).date()
            if end and day > end:
                continue
            bucket = balances.setdefault(mid, [Decimal(0), Decimal(0), Decimal(0)])
            quantity = Decimal(str(transaction.quantity or 0))
            if start and day < start:
                bucket[0] += quantity
            elif quantity >= 0:
                bucket[1] += quantity
            else:
                bucket[2] -= quantity

    rows = []
    totals = defaultdict(lambda: {key: Decimal(0) for key in QUANTITY_FIELDS})
    for mid, (opening, incoming, outgoing) in balances.items():
        closing = opening + incoming - outgoing
        if filters.get('hide_zero') and closing == 0:
            continue
        material = materials[mid]
        unit = material.unit.name if material.unit else '未设单位'
        values = dict(zip(QUANTITY_FIELDS, (opening, incoming, outgoing, closing)))
        params = {'warehouse_id': warehouse.id, 'material_code': material.code, 'material_id': material.id}
        if start: params['start_date'] = start.isoformat()
        if end: params['end_date'] = end.isoformat()
        rows.append({'material_code': material.code or '', 'material_name': material.name or '',
                     'spec': material.spec or '', 'unit': unit,
                     **{key: float(value) for key, value in values.items()},
                     'ledger_url': '/report/view/ledger?' + urlencode(params)})
        for key, value in values.items():
            totals[unit][key] += value
    # 同值保持编码顺序，排序、分页、导出都使用这一完整行集。
    rows.sort(key=lambda row: row['material_code'])
    rows = m._sort_rows(rows, filters.get('sort_field'), filters.get('sort_order'))
    total = len(rows)
    summary = {'count': total, 'unit_totals': [
        {'unit': unit, **{key: float(value) for key, value in values.items()}}
        for unit, values in sorted(totals.items())]}
    if filters.get('export') != 'excel':
        page, size = max(int(filters.get('page') or 1), 1), max(int(filters.get('page_size') or 20), 1)
        rows = rows[(page - 1) * size:page * size]
    return columns, rows, summary, total


def _build_material_movement_report(filters):
    columns, rows, summary, _total = _sql_paged_material_movement_report(filters)
    return columns, rows, summary

"""只读仓库月报：按业务月份从库存事实正向累计结存。"""
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import urlencode

from sqlalchemy.orm import joinedload

FIELDS = ('beginning_quantity', 'in_quantity', 'out_quantity', 'ending_quantity')


def _month_period(filters):
    def _parse_month(key, legacy):
        value = filters.get(key)
        if value:
            if len(value) != 7:
                raise ValueError('月份格式应为 YYYY-MM')
            return date.fromisoformat(value + '-01')
        return (filters.get(legacy) or date.today()).replace(day=1)
    start, end = _parse_month('start_month', 'start_date'), _parse_month('end_month', 'end_date')
    if start > end:
        raise ValueError('结束月份不能早于开始月份')
    return start, end


def build_warehouse_monthly_report(filters):
    """分页与输出共用完整月行集；总览期初取首月、期末取末月。"""
    import app as m
    # 说明放在表头；原字段仍保留在行数据中，兼容已有自定义模板。
    columns = [column for column in m._warehouse_monthly_columns()
               if column['field'] not in ('remark', 'transaction_count')]
    start, end = _month_period(filters)
    summary = {'count': 0, 'material_count': 0, 'quantity': 0, 'amount': 0,
               'start_month': start.strftime('%Y-%m'), 'end_month': end.strftime('%Y-%m'),
               'unit_totals': []}
    wid = filters.get('warehouse_id') or m.resolve_inventory_warehouse_id(
        filters.get('warehouse') or filters.get('warehouse_code'))
    warehouse = m.db.session.get(m.Warehouse, wid) if wid else None
    if warehouse is None:
        return columns, [], summary
    scope = dict(filters, warehouse_id=warehouse.id, warehouse=warehouse.name,
                 warehouse_code=warehouse.code)
    names, condition, wid = m._warehouse_scoped_txn_condition(scope)
    query = m.Material.query.options(joinedload(m.Material.unit))
    if filters.get('supplier_id'):
        query = query.filter(m.Material.supplier_id == filters['supplier_id'])
    supplier = m._supplier_filter_clause(filters.get('supplier'))
    if supplier is not None:
        query = query.join(m.Material.supplier).filter(supplier)
    clause = m._material_filter_clause(filters.get('material_code'))
    if clause is not None:
        query = query.filter(clause)
    materials = {item.id: item for item in query.all()}
    if not materials:
        return columns, [], summary
    transactions = m.StockTransaction.query
    if condition is not None:
        transactions = transactions.filter(condition)
    opening = defaultdict(Decimal)
    def _new_bucket():
        return dict(in_quantity=Decimal(0), out_quantity=Decimal(0), in_amount=Decimal(0),
                    out_amount=Decimal(0), transaction_count=0, document_keys=set())
    buckets = defaultdict(_new_bucket)
    last_id = 0
    cutoff = m._month_end(end)
    while True:
        batch = transactions.filter(m.StockTransaction.id > last_id).order_by(m.StockTransaction.id).limit(500).all()
        if not batch:
            break
        last_id = batch[-1].id
        batch = [t for t in m._filter_txn_list_by_warehouse_scope(batch, names, wid) if t.material_id in materials]
        dates = m._ledger_document_date_map(batch)
        prices = m._monthly_txn_price_map(batch)
        for txn in batch:
            day = dates.get(txn.id) or (txn.created_at or datetime.min).date()
            if day > cutoff:
                continue
            qty = Decimal(str(txn.quantity or 0))
            if day < start:
                opening[txn.material_id] += qty
                continue
            bucket = buckets[(txn.material_id, day.replace(day=1))]
            direction = 'in' if qty >= 0 else 'out'
            bucket[direction + '_quantity'] += abs(qty)
            price = prices.get(txn.id, materials[txn.material_id].price or 0)
            bucket[direction + '_amount'] += abs(qty) * Decimal(str(price))
            bucket['transaction_count'] += 1
            bucket['document_keys'].add((txn.reference_type, txn.reference_id) if txn.reference_type and txn.reference_id else ('stock_transaction', txn.id))
    months = list(m._iter_month_starts(start, end))
    totals = defaultdict(lambda: {field: Decimal(0) for field in FIELDS})
    rows, material_count = [], 0
    for mid, material in sorted(materials.items(), key=lambda pair: (pair[1].code or '', pair[0])):
        balance = opening[mid]
        monthly_rows = []
        unit = material.unit.name if material.unit else '未设单位'
        for month in months:
            bucket = buckets.get((mid, month), _new_bucket())
            beginning = balance
            balance += bucket['in_quantity'] - bucket['out_quantity']
            # 显式按完整物料编码核对时允许显示零行；常规浏览不铺开其他仓物料。
            exact_requested = filters.get('material_code') == material.code
            if not any((beginning, bucket['in_quantity'], bucket['out_quantity'], balance)) and not exact_requested:
                continue
            params = dict(warehouse_id=warehouse.id, material_id=mid, material_code=material.code,
                          start_date=month.isoformat(), end_date=m._month_end(month).isoformat())
            row = dict(month=month.strftime('%Y-%m'), material_code=material.code or '',
                       material_name=material.name or '', spec=material.spec or '', unit=unit,
                       beginning_quantity=float(beginning), ending_quantity=float(balance),
                       price=float(material.price or 0),
                       inventory_amount=round(float(balance * Decimal(str(material.price or 0))), 2),
                       document_count=len(bucket['document_keys']), transaction_count=bucket['transaction_count'],
                       remark='出入库金额按来源单据实际单价；无单据价及期末金额按当前单价参考估值，非成本核算',
                       ledger_url='/report/view/ledger?' + urlencode(params))
            row.update({key: float(bucket[key]) for key in ('in_quantity','out_quantity','in_amount','out_amount')})
            monthly_rows.append(row)
        if not monthly_rows or (filters.get('hide_zero') and balance == 0):
            continue
        material_count += 1
        rows.extend(monthly_rows)
        totals[unit]['beginning_quantity'] += opening[mid]
        totals[unit]['ending_quantity'] += balance
        for row in monthly_rows:
            totals[unit]['in_quantity'] += Decimal(str(row['in_quantity']))
            totals[unit]['out_quantity'] += Decimal(str(row['out_quantity']))
    rows.sort(key=lambda row: row['month'], reverse=True)
    summary.update(count=len(rows), material_count=material_count,
                   unit_totals=[dict(unit=unit, **{k:float(v) for k,v in values.items()}) for unit,values in sorted(totals.items())],
                   quantity=float(sum(v['ending_quantity'] for v in totals.values())) if len(totals) <= 1 else None,
                   amount=sum(r['inventory_amount'] for r in rows if r['month']==end.strftime('%Y-%m')))
    return columns, rows, summary

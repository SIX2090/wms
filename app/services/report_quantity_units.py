"""Format report quantities without combining incompatible units."""
from decimal import Decimal


def format_quantities(quantities):
    parts = []
    for unit, value in sorted(quantities.items()):
        amount = format(Decimal(str(round(value, 4))).normalize(), 'f')
        parts.append(f'{amount} {unit}')
    return ' / '.join(parts) or '0'


def order_quantity_units(source, order_key, item, selected_ids, page_ids, columns, field, summary, metric):
    """Label a single-unit column or return unit-specific text for the visible orders."""
    from db import db
    from models.master_data import Material, Unit
    unit = db.func.coalesce(Unit.name, '未设单位')
    source = source.outerjoin(Unit, Unit.id == db.func.coalesce(item.unit_id, Material.unit_id))
    total = db.func.sum(item.quantity)
    groups = dict(source.with_entities(unit, total).filter(order_key.in_(selected_ids)).group_by(unit).all())
    if not groups:
        return None
    summary[metric + '_text'] = format_quantities(groups)
    if len(groups) == 1:
        column = next(column for column in columns if column['field'] == field)
        column['title'] += f'（{next(iter(groups))}）'
        return None
    summary[metric] = None
    groups_by_order = {}
    for order_id, label, quantity in source.with_entities(order_key, unit, total).filter(
            order_key.in_(page_ids)).group_by(order_key, unit).all():
        groups_by_order.setdefault(order_id, {})[label] = quantity
    return {order_id: format_quantities(values) for order_id, values in groups_by_order.items()}

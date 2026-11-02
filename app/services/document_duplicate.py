"""Exact business-content comparison for manual in/out duplicate warnings.

Document IDs, creation times, status and free-text notes are not business keys.
Row order is immaterial; repeated rows retain their multiplicity.
"""
from collections import Counter
from decimal import Decimal, InvalidOperation


_HEADER_FIELDS = (
    'date', 'business_type', 'supplier_id', 'customer_id', 'customer', 'department_id',
    'warehouse', 'location', 'contract_id', 'contract_no', 'project_name',
    'source_purchase_order_id', 'source_sales_order_id', 'source_in_order_id',
    'purpose', 'picker',
)
_LINE_FIELDS = (
    'material_id', 'contract_id', 'contract_no', 'project_name',
    'source_purchase_order_item_id', 'source_sales_order_item_id',
    'source_in_order_item_id', 'batch_no', 'expiry_date', 'is_customer_supplied',
)


def _value(record, field):
    value = getattr(record, field, None)
    return '' if value is None else value.strip() if isinstance(value, str) else value


def _lines(order):
    rows = []
    for item in order.items:
        if not item.material_id:
            return None
        try:
            numbers = tuple(Decimal(str(getattr(item, name)))
                            for name in ('quantity', 'price', 'amount'))
        except (InvalidOperation, ValueError, TypeError, AttributeError):
            return None
        if not all(number.is_finite() for number in numbers):
            return None
        rows.append(tuple(_value(item, name) for name in _LINE_FIELDS) + numbers)
    return Counter(rows) if rows else None


def documents_match_for_duplicate_warning(order, other):
    """Require equal header keys and a complete multiset of equal detail rows."""
    if any(_value(order, name) != _value(other, name) for name in _HEADER_FIELDS):
        return False
    rows = _lines(order)
    return rows is not None and rows == _lines(other)

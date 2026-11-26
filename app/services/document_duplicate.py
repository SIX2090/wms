"""Exact business-content comparison for manual in/out duplicate warnings.

Document IDs, creation times, status and free-text notes are not business keys.
Row order is immaterial; repeated rows retain their multiplicity.
"""
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation


# 重复录入检测回溯窗口（天），覆盖当天及补录的近 7 天历史单据。
DUPLICATE_ORDER_LOOKBACK_DAYS = 7


_HEADER_FIELDS = (
    'date', 'business_type', 'supplier_id', 'customer_id', 'customer', 'department_id',
    'warehouse', 'location', 'contract_id', 'contract_no', 'project_name',
    'source_purchase_order_id', 'source_sales_order_id', 'source_in_order_id',
    'purpose', 'picker',
)
_LINE_FIELDS = (
    'material_id', 'contract_id', 'contract_no', 'project_name',
    'source_purchase_order_item_id', 'source_sales_order_item_id',
    'source_in_order_item_id', 'batch_no', 'expiry_date', 'is_customer_supplied', 'box_no',
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


def is_within_duplicate_check_window(order_date, today=None, lookback_days=DUPLICATE_ORDER_LOOKBACK_DAYS):
    """判断单据业务日期是否落在近 N 天重复检测窗口内（含当天）。"""
    if not order_date:
        return False
    anchor = today or date.today()
    return (anchor - timedelta(days=lookback_days)) <= order_date <= anchor


def format_duplicate_order_warning_msg(order, existing_order, today=None):
    """生成重复录入提醒文案：当天称今天单据，补录历史单据注明同日日期。"""
    anchor = today or date.today()
    date_label = '今天' if order.date == anchor else f'{order.date.isoformat()} 同日'
    return f'本单关键字段及全部 {len(order.items)} 行明细（含数量、单价）与{date_label}单据 {existing_order.order_no} 一致，疑似重复录入，请确认是否继续'


def documents_match_for_duplicate_warning(order, other):
    """Require equal header keys and a complete multiset of equal detail rows."""
    if any(_value(order, name) != _value(other, name) for name in _HEADER_FIELDS):
        return False
    rows = _lines(order)
    return rows is not None and rows == _lines(other)

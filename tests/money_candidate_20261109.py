"""Isolated amount prototype; not imported by production WMS."""
from decimal import Decimal, ROUND_HALF_UP, localcontext
import math


def round_money_product(quantity, price):
    left = Decimal(str(quantity))
    right = Decimal(str(price))
    if not left.is_finite() or not right.is_finite():
        raise ValueError('金额数量或单价不是有限数值')
    for value in (left, right):
        converted = float(value)
        if not math.isfinite(converted) or Decimal(str(converted)) != value:
            raise ValueError('金额数量或单价超出可精确处理范围')
    with localcontext() as context:
        context.prec = max(80, len(left.as_tuple().digits) + len(right.as_tuple().digits) + 4)
        amount = left * right
        if not math.isfinite(float(amount)):
            raise ValueError('金额超出可精确处理范围')
        context.prec = max(context.prec, amount.adjusted() + 4)
        rounded = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        result = float(rounded)
        if not math.isfinite(result) or Decimal(str(result)) != rounded:
            raise ValueError('金额超出可精确处理范围')
        return result

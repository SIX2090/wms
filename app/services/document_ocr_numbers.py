"""Finite OCR quantities at the existing two-decimal business precision.

No new business maximum: values that cannot round/serialize consistently are
rejected before review writes. Unknown text remains for manual correction.
"""
import copy
from decimal import Decimal, DecimalException, ROUND_HALF_UP, localcontext
import json
import math
import re

_NUMBER = re.compile(r'[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?')
_TRANSLATE = str.maketrans('０１２３４５６７８９．，,＊×Xx', '0123456789.,,****')


class InvalidOCRNumber(ValueError):
    """A recognized numeric value cannot be represented safely for confirmation."""


def _recognized_number(value):
    text = str(value or '').translate(_TRANSLATE).strip()
    text = re.sub(r'(?<=\d),(?=\d{3}(?:\D|$))', '', text)
    try:
        literal = Decimal(text)
        if not literal.is_finite():
            raise InvalidOCRNumber('nonfinite')
    except DecimalException:
        pass  # Existing unit-suffixed or unknown OCR text can still be handled.
    match = _NUMBER.search(text)
    if not match:
        return None
    try:
        exact = Decimal(match.group(0))
        rounded = exact.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        number = float(rounded)
        if not math.isfinite(number) or Decimal(str(number)) != rounded:
            raise InvalidOCRNumber('not representable at business precision')
        return 0.0 if rounded == 0 else number
    except (DecimalException, ValueError, OverflowError) as exc:
        raise InvalidOCRNumber('not representable at business precision') from exc


def parse_ocr_number(value, default=0):
    """Shared lenient parser: invalid/unknown is unmatched, never guessed as 1."""
    try:
        number = _recognized_number(value)
        if number is not None:
            return number
    except InvalidOCRNumber:
        pass
    try:
        fallback = float(default)
        return fallback if math.isfinite(fallback) else 0.0
    except (ValueError, TypeError, OverflowError):
        return 0.0


def packaged_ocr_quantity(box_count, pcs_per_box, *, strict=False):
    """Use positive factors; preserve exact product before business rounding."""
    try:
        first, second = _recognized_number(box_count), _recognized_number(pcs_per_box)
        if first is None or second is None or first <= 0 or second <= 0:
            return 0.0
        a, b = Decimal(str(first)), Decimal(str(second))
        with localcontext() as context:
            context.prec = max(28, len(a.as_tuple().digits) + len(b.as_tuple().digits))
            product = a * b
        # Validate with the same precision domain as standalone quantities.
        return _recognized_number(str(product))
    except (InvalidOCRNumber, DecimalException) as exc:
        if strict:
            raise InvalidOCRNumber('packaging product is not representable') from exc
        return 0.0


def normalize_document_quantities(extracted):
    """Return a copy with one quantity representation before any matching/write."""
    if not isinstance(extracted, dict):
        return extracted
    try:
        json.dumps(extracted, allow_nan=False)
    except (ValueError, OverflowError) as exc:
        raise InvalidOCRNumber('nonfinite JSON number') from exc
    normalized = copy.deepcopy(extracted)
    items = normalized.get('items')
    if not isinstance(items, list):
        return normalized  # Existing malformed-shape handling remains separate.
    for item in items:
        if not isinstance(item, dict):
            continue
        for field in ('quantity', 'box_count', 'pcs_per_box'):
            if field not in item or item[field] is None:
                continue
            if isinstance(item[field], bool):
                raise InvalidOCRNumber('boolean is not a quantity')
            number = _recognized_number(item[field])
            if number is not None:
                item[field] = number
        if parse_ocr_number(item.get('quantity'), 0) == 0:
            packaged = packaged_ocr_quantity(item.get('box_count'), item.get('pcs_per_box'), strict=True)
            if packaged > 0:
                item['quantity'] = packaged
    return normalized

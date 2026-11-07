"""Approved, immutable print facts; templates never navigate application objects."""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
import re
from types import MappingProxyType


class PrintFieldError(ValueError):
    """A template requests something outside its public display contract."""


# Published legacy in/out templates and the fixed product-receipt form. Other
# document fields come from their existing explicit print registries below.
_ORDER_LEGACY = frozenset('''id order_no date business_type status warehouse location
    warehouse.name warehouse.code customer customer.name customer.contact customer.phone
    customer.address supplier.name supplier.contact supplier.phone supplier.address
    purpose remark picker operator.username total_amount title contract_no project_name
    supplier_name customer_name operator_name amount_words created_at updated_at'''.split())
_ITEM_LEGACY = frozenset('''material.code material.name material.spec material.brand
    material.unit.name material.category.name unit.name quantity price amount contract_no
    project_name remark box_no batch_no expiry_date code name spec brand unit unit_name
    category_name supplier_name stock barcode qrcode number sequence material_name
    warehouse location date order_no supplier customer reason purchase_order.order_no'''.split())
_NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')
_FORBIDDEN = frozenset('''query metadata registry session password password_hash api_tokens
    token token_hash secret_key commit rollback delete save execute connection'''.split())
_SCALARS = (str, int, float, bool, date, datetime, Decimal)
_DISPLAY_NAMES = {'customer': 'name', 'supplier': 'name', 'warehouse': 'name',
                  'department': 'name', 'unit': 'name'}
_LEGACY_NAMES = {'supplier_name': 'supplier', 'customer_name': 'customer',
                 'operator_name': 'operator.username'}


def _public_path(path):
    return isinstance(path, str) and all(
        _NAME.fullmatch(part) and part not in _FORBIDDEN for part in path.split('.'))


@lru_cache(maxsize=1)
def _registered_fields():
    from doc_print_excel import DOC_EXCEL_PRINT_TYPES, TABLE_EXCEL_PRINT_TYPES, LABEL_EXCEL_PRINT_TYPES
    order, item = set(_ORDER_LEGACY), set(_ITEM_LEGACY)
    for spec in DOC_EXCEL_PRINT_TYPES.values():
        order.update(field for _, field in spec['header'])
        item.update(field for _, field, _ in spec['columns'])
    for spec in TABLE_EXCEL_PRINT_TYPES.values():
        for sheet in spec['sheets']:
            item.update(field for _, field, _ in sheet['columns'])
    for spec in LABEL_EXCEL_PRINT_TYPES.values():
        item.update(field for _, field, _ in spec['columns'])
        item.add(spec['barcode_column'][1])
    return frozenset(order), frozenset(item)


def _field_paths(scope, *, document=None, columns=None):
    if document:
        from doc_print_excel import DOC_EXCEL_PRINT_TYPES
        spec = DOC_EXCEL_PRINT_TYPES[document]
        fields = set(_ORDER_LEGACY if scope == 'order' else _ITEM_LEGACY)
        if scope == 'order':
            fields.update(field for _, field in spec['header'])
        else:
            fields.update(field for _, field, _ in spec['columns'])
    else:
        fields = set(_registered_fields()[scope == 'item'])
    if columns is not None:
        # These are server-declared report columns, never paths from a workbook.
        for field in columns:
            if not _NAME.fullmatch(field) or field in _FORBIDDEN:
                raise PrintFieldError('报表展示字段不正确，请检查列定义')
            fields.add(field)
    if not all(_public_path(field) for field in fields):
        raise PrintFieldError('打印展示字段定义不正确')
    return frozenset(fields)


@dataclass(frozen=True)
class _PrintFields:
    values: object
    fields: frozenset

    def resolve(self, path):
        if path not in self.fields or not _public_path(path):
            raise PrintFieldError('模板包含不支持的占位符字段 {%s}，请使用模板中心列出的展示字段' % path)
        return self.values.get(path)

    def __getattr__(self, name):
        # Existing adapters may read approved fields as attributes. This view
        # contains only frozen scalar facts, with no delegation to source ORM.
        if not _NAME.fullmatch(name) or name in _FORBIDDEN:
            raise AttributeError(name)
        prefix = name + '.'
        children = {path[len(prefix):]: self.values.get(path)
                    for path in self.fields if path.startswith(prefix)}
        if children and any(value is not None for value in children.values()):
            return _PrintFields(MappingProxyType(children), frozenset(children))
        if name in self.fields:
            return self.values.get(name)
        if children:
            return None
        raise AttributeError(name)


def _read_display(source, path):
    value = source
    for part in path.split('.'):
        if value is None:
            return None
        value = value.get(part) if isinstance(value, dict) else getattr(value, part, None)
        if callable(value):
            raise PrintFieldError('打印字段 %s 不支持方法或可调用值' % path)
    if value is None and path in _LEGACY_NAMES:
        return _read_display(source, _LEGACY_NAMES[path])
    if value is not None and type(value) not in _SCALARS and path in _DISPLAY_NAMES:
        value = getattr(value, _DISPLAY_NAMES[path], None)
    if value is not None and type(value) not in _SCALARS:
        raise PrintFieldError('打印字段 %s 不是可展示的标量值' % path)
    return value


def _project(source, fields, overrides=None):
    if isinstance(source, _PrintFields):
        return source
    values = {path: _read_display(source, path) for path in fields}
    for path, value in (overrides or {}).items():
        if path not in fields or (value is not None and type(value) not in _SCALARS):
            raise PrintFieldError('打印展示字段覆盖值不正确')
        values[path] = value
    return _PrintFields(MappingProxyType(values), fields)

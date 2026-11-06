"""Resolve product clipboard masters inside the receipt's existing write transaction."""
import re

from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError

from db import db


class _ProductMaterial(BaseModel):
    model_config = ConfigDict(extra='ignore')
    code: StrictStr = Field(default='', max_length=50)
    name: StrictStr = Field(default='', max_length=100)
    spec: StrictStr = Field(default='', max_length=100)
    unit: StrictStr = Field(default='', max_length=20)


def resolve_product_receipt_materials(items):
    """Reuse exact masters or allocate six-digit codes; never commit separately.

    The caller has already flushed the receipt (or acquired the edit write lock).
    SQLite therefore serializes matching and allocation across both operators.
    Box numbers deliberately remain receipt-line data and never enter the key.
    """
    from app import Material, Unit, _material_dedupe_expr, _material_dedupe_key
    resolved = []
    for index, item in enumerate(items, 1):
        try:
            entry = _ProductMaterial.model_validate(item)
        except ValidationError:
            raise ValueError(f'第 {index} 行物料编码、名称、规格或单位格式/长度不正确') from None
        code, name, spec, unit = (value.strip() for value in
                                  (entry.code, entry.name, entry.spec, entry.unit))
        # Existing code-only clients retain their established selection contract.
        if not name and code and not any(key in item for key in ('name', 'spec', 'unit')):
            resolved.append(dict(item))
            continue
        if not name:
            raise ValueError(f'第 {index} 行请填写物料名称')
        if code:
            material = Material.query.filter_by(code=code).first()
            if material is None:
                raise ValueError(f'第 {index} 行物料编码 {code} 不存在；新增物料请留空编码，由保存时自动编号')
            if (_material_dedupe_key(material.name) != _material_dedupe_key(name) or
                    _material_dedupe_key(material.spec) != _material_dedupe_key(spec)):
                raise ValueError(f'第 {index} 行编码 {code} 的名称或规格与物料档案不一致')
        else:
            matches = Material.query.filter(
                _material_dedupe_expr(Material.name) == _material_dedupe_key(name),
                _material_dedupe_expr(Material.spec) == _material_dedupe_key(spec),
            ).order_by(Material.id).limit(2).all()
            if len(matches) > 1:
                raise ValueError(f'第 {index} 行名称和规格对应多个物料，请填写物料编码以确定档案')
            material = matches[0] if matches else None
        if material is not None:
            if material.status not in (None, '', 'active'):
                raise ValueError(f'第 {index} 行物料 {material.code} 已停用，请核对物料档案')
            if unit and (not material.unit or material.unit.name != unit):
                raise ValueError(f'第 {index} 行单位与物料 {material.code} 的档案不一致')
        else:
            if not unit:
                raise ValueError(f'第 {index} 行新物料请填写单位')
            unit_record = Unit.query.filter_by(name=unit).first()
            if unit_record is None:
                raise ValueError(f'第 {index} 行单位“{unit}”不存在，请先在基础资料中建立单位')
            # String order is numeric order for these fixed-width ASCII codes.
            codes = db.session.query(Material.code).filter(
                Material.code >= '400001', Material.code <= '999999',
                db.func.length(Material.code) == 6).order_by(Material.code.desc())
            last = next((value for (value,) in codes if re.fullmatch(r'[0-9]{6}', value)), '400000')
            number = int(last) + 1
            if number > 999999:
                raise ValueError('六位产品物料编号已用满，请联系管理员处理')
            material = Material(code=str(number), name=name, spec=spec, unit_id=unit_record.id)
            db.session.add(material)
            db.session.flush()
        resolved.append(dict(item, code=material.code))
    return resolved

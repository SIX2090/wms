"""Without a conversion model, line quantities use the material's stock unit."""


def require_stock_unit(material, unit_id=None):
    from app import Unit, db
    try:
        chosen = int(unit_id) if unit_id not in (None, '') else material.unit_id
    except (TypeError, ValueError):
        raise ValueError(f'物料 {material.code} 请选择有效库存单位')
    if chosen != material.unit_id:
        expected = material.unit.name if material.unit else '未配置'
        raise ValueError(f'物料 {material.code} 必须使用库存单位「{expected}」，系统未配置单位换算，请核对用量')
    if chosen and not db.session.get(Unit, chosen):
        raise ValueError(f'物料 {material.code} 的库存单位不存在，请先维护物料资料')
    return chosen

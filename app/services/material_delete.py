"""Selected archive cleanup: preserve every reference and every nonzero stock bucket."""
import math

from sqlalchemy import inspect, or_, select, text

from db import db


def delete_unused_materials(ids):
    """Commit eligible selected archives, isolating individual DELETE failures with savepoints."""
    from app import Material, LocationInventory

    ids = list(dict.fromkeys(ids))
    db.session.rollback()
    if db.engine.dialect.name == 'sqlite':
        # Serialize against new document references and inventory writes before checking eligibility.
        db.session.connection().exec_driver_sql('BEGIN IMMEDIATE')
    query = Material.query.filter(Material.id.in_(ids)).order_by(Material.id)
    if db.engine.dialect.name != 'sqlite':
        query = query.with_for_update()
    materials = {m.id: m for m in query.all()}
    reasons = {}
    if materials:
        # Inspect actual tables first: only historically optional AI tables may be absent.
        existing = set(inspect(db.session.connection()).get_table_names())
        optional = {'ai_material_alias', 'ai_document_item'}
        references = [table for table in db.metadata.sorted_tables
                      if 'material_id' in table.c and table.name != 'location_inventory']
        codes = {m.code: m.id for m in materials.values()}
        for table in references:
            if table.name not in existing:
                if table.name in optional:
                    continue
                raise RuntimeError('Required material reference table is missing: ' + table.name)
            referenced = db.session.execute(select(table.c.material_id).where(
                table.c.material_id.in_(ids)).distinct()).scalars()
            reason = '存在物料图片' if table.name == 'material_image' else '存在业务引用'
            for material_id in referenced:
                # Retain the existing explicit image guidance.
                if reason == '存在物料图片' or material_id not in reasons:
                    reasons[material_id] = reason
        # Legacy BOM headers and purchase-request rows may refer by code without material_id.
        for table in db.metadata.sorted_tables:
            for name in ('material_code', 'product_code'):
                if name not in table.c:
                    continue
                if table.name not in existing:
                    if table.name in optional:
                        continue
                    raise RuntimeError('Required material code reference table is missing: ' + table.name)
                for code in db.session.execute(select(table.c[name]).where(
                        table.c[name].in_(codes)).distinct()).scalars():
                    reasons.setdefault(codes[code], '存在业务引用（物料编码）')
        # Check every warehouse/location separately, including inactive/unknown historical buckets.
        # Summing quantities would incorrectly permit +5 in one warehouse and -5 in another.
        occupied = db.session.execute(select(LocationInventory.material_id).where(
            LocationInventory.material_id.in_(ids),
            or_(LocationInventory.quantity != 0, LocationInventory.quantity.is_(None)),
        ).distinct()).scalars()
        for material_id in occupied:
            reasons.setdefault(material_id, '存在仓库或库位库存')

    items = []
    snapshots = []
    for material_id in ids:
        material = materials.get(material_id)
        item = {'id': material_id, 'code': material.code if material else '',
                'name': material.name if material else '', 'status': 'skipped', 'reason': ''}
        if material is None:
            item['reason'] = '物料不存在或已删除'
        elif (material.image or '').strip():
            item['reason'] = '存在物料图片'
        elif material_id in reasons:
            item['reason'] = reasons[material_id]
        # stock-truth:reason=档案删除的额外异常余额保护；所有仓库/库位逐行余额及任何历史流水引用已独立保护，不用总账代替仓库库存校验或改写库存
        elif not math.isfinite(float(material.stock or 0)) or float(material.stock or 0) != 0:
            item['reason'] = '存在库存总账余额'
        else:
            snapshot = {'id': material.id, 'code': material.code, 'name': material.name,
                        'spec': material.spec or '', 'price': material.price or 0}
            try:
                with db.session.begin_nested():
                    LocationInventory.query.filter_by(material_id=material_id).delete(synchronize_session=False)
                    # Core DELETE avoids loading optional AI ORM backrefs in old databases.
                    db.session.execute(text('DELETE FROM material WHERE id = :material_id'),
                                       {'material_id': material_id})
                    db.session.expunge(material)
                snapshots.append(snapshot)
                item.update(status='deleted', reason='未使用，已删除')
            except Exception:
                # The savepoint restores this item's auxiliary rows without rolling back earlier successes.
                item.update(status='failed', reason='删除失败，已保留，请稍后重试')
        items.append(item)
    db.session.commit()
    return {
        'selected_count': len(ids),
        'deleted_count': sum(item['status'] == 'deleted' for item in items),
        'skipped_count': sum(item['status'] == 'skipped' for item in items),
        'failed_count': sum(item['status'] == 'failed' for item in items),
        'items': items,
    }, snapshots

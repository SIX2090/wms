"""Resolve a legacy no-document write without guessing or changing ownership."""


class _OpeningOwnershipError(ValueError):
    pass


def _begin_legacy_opening_write():
    from app import db
    # SQLite SELECT FOR UPDATE is a no-op. Obtain its write fence before resolving
    # candidates; preserve an existing idempotency claim/transaction if present.
    if db.engine.dialect.name == 'sqlite':
        connection = db.session.connection()
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql('BEGIN IMMEDIATE')


def _resolve_legacy_opening(material, warehouse, raw_date, generate_order_no_fn):
    from app import (db, Material, OpeningStock, OpeningStockDoc,
                     _opening_stock_compat_doc, _parse_opening_stock_date)
    if hasattr(raw_date, 'isoformat'):
        raw_date = raw_date.isoformat()
    if db.engine.dialect.name != 'sqlite':
        Material.query.filter_by(id=material.id).with_for_update().one()
    rows = OpeningStock.query.filter_by(material_id=material.id, warehouse_id=warehouse.id
        ).order_by(OpeningStock.id).with_for_update().limit(2).all()
    if len(rows) > 1:
        raise _OpeningOwnershipError('同物料同仓库存在多行期初，请定位到明确单据后编辑')
    opening = rows[0] if rows else None
    if opening is not None and opening.doc_id is not None:
        doc = OpeningStockDoc.query.filter_by(id=opening.doc_id).with_for_update().first()
        if doc is None:
            raise _OpeningOwnershipError('原期初单据归属无法核实，请定位到明确单据后编辑')
        # Ordinary documents use their authoritative header date. Historic
        # QSLEGACY clients retain their established per-line date editing.
        effective_date = (_parse_opening_stock_date(raw_date) if raw_date and
                          (doc.doc_no or '').startswith('QSLEGACY') else doc.date)
        return opening, doc, effective_date
    doc = _opening_stock_compat_doc(raw_date, generate_order_no_fn)
    return opening, doc, _parse_opening_stock_date(raw_date) if raw_date else doc.date

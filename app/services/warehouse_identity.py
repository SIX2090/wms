"""Warehouse names and codes share one namespace; IDs remain authoritative."""
from sqlalchemy import select


class WarehouseIdentityError(ValueError):
    """An alias cannot safely identify exactly one warehouse."""


def lock_warehouse_namespace(session):
    """Serialize namespace checks with writes, including when the catalog is empty."""
    # SQLite SELECT/FOR UPDATE cannot reserve an empty namespace. This no-op
    # write acquires its existing transaction's writer lock, without committing
    # or rolling back any caller-owned changes.
    session.connection().exec_driver_sql('UPDATE warehouse SET id = id WHERE 0')


def validate_warehouse_namespace(session, warehouses):
    """Check committed and pending aliases while holding the same write transaction."""
    from models.master_data import Warehouse
    lock_warehouse_namespace(session)
    rows = session.connection().execute(select(Warehouse.id, Warehouse.code, Warehouse.name)).all()
    for warehouse in warehouses:
        aliases = {value for value in (warehouse.code, warehouse.name) if value}
        if any(row.id != warehouse.id and aliases.intersection((row.code, row.name)) for row in rows):
            raise WarehouseIdentityError('仓库名称与编码存在跨仓重名，请使用不同的仓库名称和编码')
        if any(other is not warehouse and aliases.intersection((other.code, other.name))
               for other in warehouses):
            raise WarehouseIdentityError('本批仓库名称与编码存在跨仓重名，请核对后重新导入')


def resolve_warehouse_text(value, *, strict=False):
    """Resolve text only when unique, before applying any active-state filter."""
    from models.master_data import Warehouse
    from db import db
    text = str(value or '').strip()
    if not text:
        return None
    matches = Warehouse.query.filter(
        db.or_(Warehouse.name == text, Warehouse.code == text)).limit(2).all()
    if len(matches) > 1:
        if strict:
            raise WarehouseIdentityError('仓库名称与编码存在跨仓重名或歧义，请按明确仓库ID操作并人工核对档案')
        return None
    return matches[0] if matches else None


def warehouse_aliases(warehouse):
    """Legacy text may supplement an ID only when no other master record owns it."""
    from models.master_data import Warehouse
    aliases = list(dict.fromkeys(value.strip() for value in (warehouse.name, warehouse.code) if value))
    if not aliases:
        return []
    from db import db
    rows = db.session.query(Warehouse.id, Warehouse.name, Warehouse.code).filter(
        db.or_(Warehouse.name.in_(aliases), Warehouse.code.in_(aliases))).all()
    return [alias for alias in aliases if not any(
        row.id != warehouse.id and alias in (row.name, row.code) for row in rows)]

"""Shared material-category selection for inventory reports."""
import re

from sqlalchemy import select


def parse_report_category(args):
    from app import ReportFilterError

    category_id = (args.get('category_id') or '').strip()
    if category_id and category_id != 'uncategorized' and (
            not re.fullmatch(r'[0-9]{1,19}', category_id) or not 0 < int(category_id) < 2**63):
        raise ReportFilterError('请选择有效的物料分类')
    return category_id


def report_category_clause(category_id):
    from app import Material, MaterialCategory

    if not category_id:
        return None
    if category_id == 'uncategorized':
        return Material.category_id.is_(None)
    tree = select(MaterialCategory.id).where(MaterialCategory.id == int(category_id)).cte(recursive=True)
    tree = tree.union(select(MaterialCategory.id).join(tree, MaterialCategory.parent_id == tree.c.id))
    return Material.category_id.in_(select(tree.c.id))

"""Explicit additive SQLite schema planning; no Flask startup or business writes."""
from sqlalchemy.dialects.sqlite import dialect
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy import literal, UniqueConstraint
from schema_indexes import compare_model_indexes, read_sqlite_indexes


def plan_schema_upgrade(connection, metadata):
    """Return reviewable DDL; reject changes requiring data/constraint decisions."""
    compiler = dialect()
    quote = compiler.identifier_preparer.quote_identifier
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    index_owners = dict(connection.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index'"))
    statements, blocked = [], []
    for table in metadata.sorted_tables:
        if table.name not in tables:
            statements.append(str(CreateTable(table).compile(dialect=compiler)))
            statements.extend(str(CreateIndex(index).compile(dialect=compiler))
                              for index in sorted(table.indexes, key=lambda i: i.name))
            continue
        columns = {row[1] for row in connection.execute('PRAGMA table_info(' + quote(table.name) + ')')}
        for column in table.columns:
            if column.name in columns:
                continue
            name = table.name + '.' + column.name
            if column.primary_key:
                blocked.append(name + ': 主键需要专门迁移')
                continue
            default = column.server_default
            if default is not None:
                default_sql = str(default.arg.compile(dialect=compiler)) if hasattr(default.arg, 'compile') else str(literal(default.arg).compile(dialect=compiler, compile_kwargs={'literal_binds': True}))
            elif column.default is not None and column.default.is_scalar:
                default_sql = str(literal(column.default.arg, type_=column.type).compile(dialect=compiler, compile_kwargs={'literal_binds': True}))
            else:
                default_sql = None
            if not column.nullable and default_sql is None:
                populated = connection.execute('SELECT 1 FROM ' + quote(table.name) + ' LIMIT 1').fetchone()
                if populated:
                    blocked.append(name + ': 非空列缺少固定默认值，需要人工决定历史值')
                    continue
            ddl = 'ALTER TABLE ' + quote(table.name) + ' ADD COLUMN ' + quote(column.name) + ' ' + column.type.compile(dialect=compiler)
            if not column.nullable:
                ddl += ' NOT NULL'
            if default_sql is not None:
                ddl += ' DEFAULT ' + default_sql
            statements.append(ddl)
        # Add constraints involving new columns and all missing model indexes.
        # A uniqueness conflict aborts the whole transaction; never weaken it.
        for constraint in table.constraints:
            if isinstance(constraint, UniqueConstraint) and any(c.name not in columns for c in constraint.columns):
                names = [c.name for c in constraint.columns]
                index_name = constraint.name or ('ux_upgrade_' + table.name + '_' + '_'.join(names))
                statements.append('CREATE UNIQUE INDEX ' + quote(index_name) + ' ON ' + quote(table.name) + ' (' + ', '.join(quote(n) for n in names) + ')')
        missing_indexes, conflicts = compare_model_indexes(table, read_sqlite_indexes(connection, table.name))
        blocked.extend(conflicts)
        for index in missing_indexes:
            if index.name in index_owners:
                blocked.append(f'索引名冲突: {index.name} 已属于表 {index_owners[index.name]}')
            else:
                statements.append(str(CreateIndex(index).compile(dialect=compiler)))
    return {'statements': statements, 'blocked': blocked}


def apply_schema_upgrade(connection, metadata):
    """Apply one all-or-nothing additive transaction; never seed or rewrite rows."""
    connection.execute('BEGIN IMMEDIATE')
    try:
        plan = plan_schema_upgrade(connection, metadata)
        if plan['blocked']:
            raise ValueError('升级未执行：' + '; '.join(plan['blocked']))
        for statement in plan['statements']:
            connection.execute(statement)
        remaining = plan_schema_upgrade(connection, metadata)
        if remaining['statements'] or remaining['blocked']:
            raise RuntimeError('结构升级校验未通过，已回滚')
        connection.commit()
        return len(plan['statements'])
    except Exception:
        connection.rollback()
        raise

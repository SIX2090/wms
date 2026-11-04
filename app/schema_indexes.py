"""Read-only comparison of declared indexes; never replace existing definitions."""
import re

from sqlalchemy.dialects.sqlite import dialect


def read_sqlite_indexes(connection, table_name):
    """Return inspector-shaped index records from an existing sqlite3 connection."""
    indexes = []
    for name, unique, partial in connection.execute(
        'SELECT name, "unique", partial FROM pragma_index_list(?)', (table_name,)
    ):
        columns = [row[0] for row in connection.execute(
            'SELECT name FROM pragma_index_info(?) ORDER BY seqno', (name,)
        )]
        sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name=?", (name,)
        ).fetchone()[0] or ''
        where = re.search(r'\bWHERE\b(.*)$', sql, re.IGNORECASE | re.DOTALL) if partial else None
        indexes.append({'name': name, 'unique': bool(unique), 'column_names': columns,
                        'dialect_options': {'sqlite_where': where.group(1).strip() if where else None}})
    return indexes


def compare_model_indexes(table, actual_indexes):
    """Return missing Index objects and conflicting names, preserving column order."""
    actual = {index['name']: index for index in actual_indexes}
    missing, conflicts = [], []
    for index in sorted(table.indexes, key=lambda value: value.name):
        found = actual.get(index.name)
        if found is None:
            missing.append(index)
            continue
        expected_where = index.dialect_options['sqlite']['where']
        if expected_where is not None:
            expected_where = expected_where.compile(
                dialect=dialect(), compile_kwargs={'literal_binds': True, 'include_table': False}
            )
        actual_where = found.get('dialect_options', {}).get('sqlite_where')
        expected_filter = ' '.join(str(expected_where).split()) if expected_where is not None else ''
        actual_filter = ' '.join(str(actual_where).split()) if actual_where is not None else ''
        if (found['column_names'] != [getattr(expression, 'name', None) for expression in index.expressions]
                or bool(found['unique']) != bool(index.unique)
                or actual_filter != expected_filter):
            conflicts.append(f'索引定义不一致: {table.name}.{index.name}，请人工核对列顺序、唯一性和条件')
    return missing, conflicts

"""Keep additive schema changes without committing unmarked business writes.

Used only inside the startup migrator's existing exclusive transaction. Rolling
back a nested savepoint retains that outer lock throughout schema replay.
"""
import re


class SchemaOnlyCheckpoint:
    def __init__(self, connection):
        if not connection.in_transaction:
            raise RuntimeError('结构检查点缺少外层事务')
        self.connection = connection
        self.cancelled = False
        self.before = self._catalog()
        connection.execute('SAVEPOINT wms_additive_schema')

    def cancel(self):
        """Preserve the old no-commit behaviour after a caught rebuild failure."""
        self.cancelled = True

    def _catalog(self):
        return {(kind, name): (table, sql) for kind, name, table, sql in
                self.connection.execute(
                    "SELECT type, name, tbl_name, sql FROM main.sqlite_master "
                    "WHERE substr(name,1,7) != 'sqlite_' ORDER BY type, name")}

    def persist_additions(self):
        if self.cancelled:
            return False
        after = self._catalog()
        if any(after.get(key) != value for key, value in self.before.items()):
            raise RuntimeError('未标记迁移修改了已有结构，拒绝额外提交')
        additions = [(kind, name, *value) for (kind, name), value in after.items()
                     if (kind, name) not in self.before]
        if not additions:
            return False
        for kind, name, _table, sql in additions:
            pattern = (r'^CREATE\s+TABLE\s+' if kind == 'table' else
                       r'^CREATE\s+(?:UNIQUE\s+)?INDEX\s+' if kind == 'index' else None)
            if pattern is None or not sql or not re.match(pattern, sql, re.IGNORECASE):
                raise RuntimeError('新增结构不能安全单独持久化')
            if kind == 'table':
                # SQLite identifiers cannot be value parameters. These names
                # come only from SQLite's catalog and are quoted in full.
                identifier = '"' + name.replace('"', '""') + '"'
                query = 'SELECT 1 FROM main.' + identifier + ' LIMIT 1'
                if self.connection.execute(query).fetchone():
                    raise RuntimeError('新增表含业务数据，拒绝仅提交结构')
        self.connection.execute('ROLLBACK TO SAVEPOINT wms_additive_schema')
        for _kind, _name, _table, sql in sorted(
                additions, key=lambda row: (row[0] != 'table', row[1])):
            self.connection.execute(sql)
        if self._catalog() != after:
            raise RuntimeError('新增结构重放结果不一致')
        self.connection.execute('RELEASE SAVEPOINT wms_additive_schema')
        return True

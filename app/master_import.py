"""Shared archive Excel validation; no database writes in this module."""


class MasterImportError(ValueError):
    """A validated, user-facing spreadsheet error."""


def master_import_rows(worksheet, required):
    header = [str(value).strip() if value is not None else '' for value in
              next(worksheet.iter_rows(min_row=1, max_row=1, values_only=True), ())]
    missing = [name for name in required if name not in header]
    if missing:
        raise MasterImportError('Excel表头缺少必要列：' + '、'.join(missing))
    names = [name for name in header if name]
    if len(names) != len(set(names)):
        raise MasterImportError('Excel表头存在重复列，请按模板保留唯一列名')
    indexes = {name: index for index, name in enumerate(header) if name}
    return ({name: str(row[index]).strip() if index < len(row) and row[index] is not None else ''
             for name, index in indexes.items()}
            for row in worksheet.iter_rows(min_row=2, values_only=True))


def normalize_master_status(value):
    status = {'active': 'active', 'inactive': 'inactive',
              '启用': 'active', '停用': 'inactive'}.get((value or '').strip().lower() or 'active')
    if status is None:
        raise MasterImportError('状态无效，请填写启用、停用、active或inactive')
    return status

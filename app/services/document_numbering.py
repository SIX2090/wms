"""Transaction-owned document sequence, stored in the existing settings table."""
import re

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from models.core import SystemSetting


KEY_PREFIX = 'document_sequence:'


def _locked_sequence(connection, base):
    """Acquire a database write lock before reading or initializing the sequence."""
    table = SystemSetting.__table__
    key = KEY_PREFIX + base
    lock = update(table).where(table.c.key == key).values(value=table.c.value)
    if connection.execute(lock).rowcount == 0:
        # A concurrent first writer may have inserted after the empty UPDATE.
        # Keep its transaction and all caller changes intact on that race.
        try:
            with connection.begin_nested():
                connection.execute(table.insert().values(key=key, value='0',
                    remark='单据已用序号；由保存事务维护'))
        except IntegrityError:
            if connection.execute(lock).rowcount != 1:
                raise
    value = connection.execute(select(table.c.value).where(table.c.key == key)).scalar_one()
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+', value):
        raise ValueError('单据编号记录异常，请人工核对；不能重新从 0001 取号')
    return key, int(value)


def reserve_document_number(session, base, existing_maximum):
    """Reserve in the caller transaction; never commit or roll it back here."""
    with session.no_autoflush:
        connection = session.connection()
        key, previous = _locked_sequence(connection, base)
        sequence = max(previous, existing_maximum()) + 1
        number = f'{base}{sequence:04d}'
        if len(number) > 50:
            raise ValueError('单据编号已超出支持长度，请人工核对')
        connection.execute(update(SystemSetting.__table__).where(
            SystemSetting.__table__.c.key == key).values(value=str(sequence)))
    return number


def preview_document_number(session, base, existing_maximum):
    """A page preview reads the sequence without reserving a formal number."""
    with session.no_autoflush:
        value = session.execute(select(SystemSetting.value).where(
            SystemSetting.key == KEY_PREFIX + base)).scalar_one_or_none()
        if value is not None and not re.fullmatch(r'[0-9]+', value):
            raise ValueError('单据编号记录异常，请人工核对')
        sequence = max(int(value or '0'), existing_maximum()) + 1
    return f'{base}{sequence:04d}'


def retain_document_number(connection, number, prefixes):
    """Retain imported/current numbers without changing historical documents."""
    if not isinstance(number, str):
        return
    match = re.fullmatch('(' + '|'.join(sorted(prefixes, key=len, reverse=True))
                         + r')([0-9]{2}(?:0[1-9]|1[0-2]))([0-9]+)', number)
    if match is None:
        return
    base = match[1] + match[2]
    key, previous = _locked_sequence(connection, base)
    sequence = int(match[3])
    if sequence > previous:
        connection.execute(update(SystemSetting.__table__).where(
            SystemSetting.__table__.c.key == key).values(value=str(sequence)))

"""The supplied product receipt form: twenty rows per printed page."""
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace


def amount_in_words(value):
    """Return Chinese RMB words after rounding to cents."""
    amount = Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    digits = '零壹贰叁肆伍陆柒捌玖'
    cents = int(abs(amount) * 100)
    yuan, fraction = divmod(cents, 100)
    groups = []
    while yuan:
        yuan, group = divmod(yuan, 10000)
        groups.append(group)
    text, zero = '', False
    for index in range(len(groups) - 1, -1, -1):
        group = groups[index]
        if not group:
            zero = bool(text)
            continue
        if text and (zero or group < 1000):
            text += '零'
        part, pending = '', False
        for power in range(3, -1, -1):
            number = group // (10 ** power) % 10
            if number:
                if pending:
                    part += '零'
                part += digits[number] + ('', '拾', '佰', '仟')[power]
                pending = False
            elif part:
                pending = True
        text += part + ('', '万', '亿', '兆', '京', '垓', '秭')[index]
        zero = False
    text = (text or '零') + '元'
    jiao, fen = divmod(fraction, 10)
    if not fraction:
        text += '整'
    else:
        if jiao:
            text += digits[jiao] + '角'
        elif cents >= 100:
            text += '零'
        if fen:
            text += digits[fen] + '分'
    return ('负' if amount < 0 else '') + text


def product_receipt_pages(order):
    """Read all saved rows and pad each page without inventing cabinet numbers."""
    items = sorted(order.items, key=lambda item: item.id or 0)
    pages = []
    for offset in range(0, max(len(items), 1), 20):
        chunk = items[offset:offset + 20]
        amount = sum((Decimal(str(item.amount or 0)) for item in chunk), Decimal(0))
        quantity = sum((Decimal(str(item.quantity or 0)) for item in chunk), Decimal(0))
        header = SimpleNamespace(
            customer_name=order.customer.name if order.customer else '',
            contract_no=order.contract_no or '', project_name=order.project_name or '',
            date=order.date.isoformat() if order.date else '',
            operator_name=order.operator.username if order.operator else '',
            total_amount=float(amount), amount_words=amount_in_words(amount),
        )
        rows = []
        for index in range(20):
            item = chunk[index] if index < len(chunk) else None
            material = item.material if item else None
            rows.append(SimpleNamespace(
                number=offset + index + 1, box_no=(item.box_no or '') if item else '',
                name=material.name if material else '', spec=(material.spec or '') if material else '',
                unit=material.unit.name if material and material.unit else '',
                quantity=item.quantity if item else '', price=item.price if item else '',
                amount=item.amount if item else '', remark=(item.remark or '') if item else '',
            ))
        pages.append(SimpleNamespace(header=header, rows=rows, quantity=float(quantity)))
    return pages


def build_product_receipt_excel(order):
    """Fill the approved fixed form, using one complete worksheet per page."""
    from openpyxl import load_workbook
    from openpyxl.worksheet.page import PageMargins
    from print_fill import _Filler
    path = Path(__file__).resolve().parents[1] / 'static' / 'templates' / 'product_receipt.xlsx'
    workbook = load_workbook(path)
    pages = product_receipt_pages(order)
    sheets = [workbook.active]
    for _ in pages[1:]:
        sheets.append(workbook.copy_worksheet(workbook.active))
    for index, (sheet, page) in enumerate(zip(sheets, pages), 1):
        sheet.title = f'产品入库单-{index}'
        # Exactly twenty padded rows keeps the supplied merged footer intact.
        _Filler(page.header, page.rows, page.header.date).fill(sheet)
        for row in sheet.iter_rows(min_row=8, max_row=27):
            for column in (1, 2, 3, 4, 8):
                # Cabinet identifiers and master-data text are literal print content.
                row[column].data_type = 's'
        sheet.print_area = 'A1:I31'
        sheet.page_setup.orientation = 'portrait'
        sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 1
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_margins = PageMargins(left=0.3, right=0.3, top=0.3, bottom=0.3)
        if len(pages) > 1:
            sheet.oddFooter.center.text = f'第 {index} / {len(pages)} 页'
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    output.seek(0)
    return output

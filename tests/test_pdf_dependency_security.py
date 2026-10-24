"""PDF dependency security lock and real attachment parsing compatibility."""
import ast
import logging
import re
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter
from pypdf.errors import LimitReachedError
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parents[1]


def parser():
    tree = ast.parse((ROOT / 'app/app.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_ai_parse_pdf_bytes')
    scope = {'app': SimpleNamespace(logger=logging.getLogger('pdf-attachment-test'))}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'app/app.py', 'exec'), scope)
    return scope['_ai_parse_pdf_bytes']


def test_dependency_pin_includes_all_five_reported_fixes():
    pins = [line.partition('==')[2] for line in (ROOT / 'app/requirements.txt').read_text(encoding='utf-8').splitlines() if line.startswith('pypdf==')]
    assert len(pins) == 1
    assert tuple(map(int, pins[0].split('.'))) >= (6, 21, 1)


def test_dependency_pin_includes_october_24_security_fixes():
    pins = [line.partition('==')[2] for line in (ROOT / 'app/requirements.txt').read_text(encoding='utf-8').splitlines() if line.startswith('pypdf==')]
    assert len(pins) == 1
    assert tuple(map(int, pins[0].split('.'))) >= (6, 21, 2)


def test_repeated_missing_object_does_not_rescan_whole_pdf():
    class CountedPdf(BytesIO):
        full_reads = 0

        def getbuffer(self):
            self.full_reads += 1
            return super().getbuffer()

        def read(self, size=-1):
            if size < 0:
                self.full_reads += 1
            return super().read(size)

    document = CountedPdf()
    writer = PdfWriter()
    writer.add_blank_page(72, 72)
    writer.write(document)
    document.seek(0)
    reader = PdfReader(document)
    document.full_reads = 0
    for _ in range(8):
        assert reader.get_object(9999) is None
    assert document.full_reads == 1


def test_xref_size_exceeding_file_capacity_is_rejected():
    document = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(72, 72)
    writer.write(document)
    data, replacements = re.subn(rb'(xref\s+0\s+)\d+', rb'\g<1>1000', document.getvalue(), count=1)
    assert replacements == 1
    with pytest.raises(LimitReachedError, match='exceeds allowed limit'):
        PdfReader(BytesIO(data))


@pytest.mark.parametrize('image_format', ['JPEG', 'PNG'])
def test_dct_image_uses_only_jpeg_decoder(image_format):
    image_bytes = BytesIO()
    Image.new('RGB', (4, 4), 'red').save(image_bytes, format=image_format)
    stream = DecodedStreamObject()
    stream.set_data(image_bytes.getvalue())
    stream.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Image'),
                   NameObject('/Width'): NumberObject(4), NameObject('/Height'): NumberObject(4),
                   NameObject('/BitsPerComponent'): NumberObject(8), NameObject('/ColorSpace'): NameObject('/DeviceRGB'),
                   NameObject('/Filter'): NameObject('/DCTDecode')})
    writer = PdfWriter()
    page = writer.add_blank_page(72, 72)
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/XObject'): DictionaryObject({NameObject('/Im1'): writer._add_object(stream)})})
    document = BytesIO()
    writer.write(document)
    page = PdfReader(BytesIO(document.getvalue())).pages[0]
    if image_format == 'PNG':
        with pytest.raises(UnidentifiedImageError):
            _ = page.images[0]
    else:
        assert page.images[0].image.size == (4, 4)
        assert page.images[0].image.format == 'JPEG'


def test_attachment_text_from_multiple_pages():
    document = BytesIO()
    canvas = Canvas(document)
    canvas.drawString(10, 40, 'MATERIAL-A 12 PCS')
    canvas.showPage()
    canvas.drawString(10, 40, 'MATERIAL-B 7 PCS')
    canvas.save()
    text = parser()(document.getvalue(), 'fixture.pdf')
    assert 'MATERIAL-A 12 PCS' in text and 'MATERIAL-B 7 PCS' in text
    assert text.index('MATERIAL-A') < text.index('MATERIAL-B')


@pytest.mark.parametrize('data', [b'', b'not a PDF', b'%PDF-1.7\ntruncated'])
def test_invalid_attachment_falls_back_to_empty(data):
    assert parser()(data, 'invalid.pdf') == ''


def test_encrypted_attachment_falls_back_without_throwing():
    writer = PdfWriter()
    writer.add_blank_page(72, 72)
    writer.encrypt('synthetic-test-only')
    document = BytesIO()
    writer.write(document)
    assert parser()(document.getvalue(), 'encrypted.pdf') == ''

"""One material QR identity for printed labels, H5 and Android scanners."""
import base64
import io
import os
from urllib.parse import parse_qs, urlencode, urlsplit

from flask import request


def material_scan_code(value):
    """Accept legacy plain codes and our material-detail URLs without fetching them."""
    value = (value or '').strip()
    try:
        parsed = urlsplit(value)
        if parsed.scheme in ('http', 'https') and parsed.netloc and parsed.path == '/mobile/material':
            values = parse_qs(parsed.query).get('code', [])
            return values[0] if len(values) == 1 else ''
    except ValueError:
        pass
    return value


def material_label_qr(code, base_url=None):
    """Embed the PNG so signed print pages do not need login-only image endpoints."""
    import qrcode
    base = (base_url or os.environ.get('WMS_PUBLIC_URL') or request.url_root).rstrip('/')
    parsed = urlsplit(base)
    if (parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.query or parsed.fragment
            or parsed.username or parsed.password or parsed.path):
        raise ValueError('WMS_PUBLIC_URL 必须是可访问的 HTTP/HTTPS 系统地址')
    target = base + '/mobile/material?' + urlencode({'code': code})
    image = qrcode.make(target, box_size=8, border=4)
    output = io.BytesIO()
    image.save(output, format='PNG')
    return {'qrcode': target, 'qrcode_png': base64.b64encode(output.getvalue()).decode('ascii')}

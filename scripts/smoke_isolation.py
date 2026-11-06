"""Isolation contract for the writable HTTP smoke suite (BUG-2026-11-06-001)."""
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

import requests

IDENTITY_HEADER = 'X-WMS-Isolated-Smoke'


def validate_base_url(value):
    """Reject public hosts, production ports, credentials and non-root URLs."""
    parsed = urlsplit(value)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1'
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ('', '/') or not parsed.port
            or not 10240 <= parsed.port <= 65535):
        raise ValueError('Smoke tests require an owned loopback service on a test port')
    return f'http://127.0.0.1:{parsed.port}'


def read_identity(path):
    """Read the ready file emitted only after the isolated child binds its socket."""
    path = Path(path).resolve(strict=True)
    data = json.loads(path.read_text(encoding='utf-8'))
    root = path.parent
    if (data.get('schema') != 1 or not root.name.startswith('wms-isolated-smoke-')
            or not re.fullmatch(r'[a-f0-9]{64}', data.get('nonce', ''))
            or type(data.get('pid')) is not int or data['pid'] <= 0
            or Path(data.get('database', '')).resolve() != root / 'synthetic.db'):
        raise ValueError('Missing or invalid isolated smoke identity')
    data['base_url'] = validate_base_url(data['base_url'])
    return data


class IsolatedSession(requests.Session):
    """Check every request and redirect before sending; require the child identity."""

    def __init__(self, identity):
        super().__init__()
        self.base_url = validate_base_url(identity['base_url'])
        self.nonce = identity['nonce']
        self.trust_env = False
        self.hooks['response'].append(self.verify_response)

    def verify_response(self, response, **kwargs):
        if response.headers.get(IDENTITY_HEADER) != self.nonce:
            response.close()
            raise ValueError('Service identity mismatch; no smoke action is permitted')
        return response

    def send(self, request, **kwargs):
        parsed = urlsplit(request.url)
        origin = f'{parsed.scheme}://{parsed.netloc}'
        if origin != self.base_url:
            raise ValueError('Refusing a request or redirect outside the isolated service')
        if kwargs.get('timeout') is None:
            kwargs['timeout'] = 15
        return super().send(request, **kwargs)

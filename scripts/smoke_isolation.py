"""Isolation contract for the writable HTTP smoke suite (BUG-2026-11-06-001)."""
import json
import base64
import os
from pathlib import Path
import re
import socket
from urllib.parse import urlsplit

import requests

IDENTITY_HEADER = 'X-WMS-Isolated-Smoke'


class IsolationError(ValueError):
    """A missing or invalid isolation capability must terminate the smoke run."""


def listener_url(listener):
    """Return the held loopback listener's origin, rejecting non-exclusive sockets."""
    try:
        if (not isinstance(listener, socket.socket) or listener.family != socket.AF_INET
                or listener.type & socket.SOCK_STREAM != socket.SOCK_STREAM
                or not listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN)):
            raise IsolationError('An owned listening socket is required')
        if os.name == 'nt':
            if not listener.getsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE):
                raise IsolationError('The test listener must be exclusive')
        elif hasattr(socket, 'SO_REUSEPORT') and listener.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT):
            raise IsolationError('A reusable test port is not permitted')
        host, port = listener.getsockname()
        return validate_base_url(f'http://{host}:{port}')
    except (OSError, TypeError, ValueError) as exc:
        raise IsolationError('Invalid or closed owned test listener') from exc


class OwnedSocketLease:
    """Capability: the caller holds the listener for the lifetime of requests."""

    def __init__(self, listener, identity):
        self.listener = listener
        self.base_url = listener_url(listener)
        self.nonce = identity.get('nonce')
        self.pid = identity.get('pid')
        if (identity.get('base_url') != self.base_url
                or not isinstance(self.nonce, str)
                or not re.fullmatch(r'[a-f0-9]{64}', self.nonce)
                or type(self.pid) is not int or self.pid <= 0):
            raise IsolationError('The listener and child identity do not match')

    def validate(self, identity):
        if (listener_url(self.listener) != self.base_url
                or identity.get('base_url') != self.base_url
                or identity.get('nonce') != self.nonce
                or identity.get('pid') != self.pid):
            raise IsolationError('The owned listener or child identity changed')


def encode_listener_capability(listener, child_pid, nonce, server_pid):
    """Encode the listener for the specific owned child, not for a file receipt."""
    base_url = listener_url(listener)
    if (type(child_pid) is not int or child_pid <= 0
            or type(server_pid) is not int or server_pid <= 0
            or not isinstance(nonce, str) or not re.fullmatch(r'[a-f0-9]{64}', nonce)):
        raise IsolationError('Invalid listener capability parameters')
    payload = {'base_url': base_url, 'nonce': nonce, 'pid': server_pid}
    if os.name == 'nt':
        payload.update(kind='windows-share', share=base64.b64encode(listener.share(child_pid)).decode('ascii'))
    else:
        payload.update(kind='inherited-fd', fd=listener.fileno())
    return json.dumps(payload, separators=(',', ':')).encode('ascii')


def receive_listener_capability(stream):
    """Read a bounded private-pipe capability and validate the held socket."""
    listener = None
    try:
        data = stream.read(32769)
        if not data or len(data) > 32768:
            raise IsolationError('Missing or oversized listener capability')
        payload = json.loads(data.decode('ascii'))
        if not isinstance(payload, dict):
            raise IsolationError('Invalid listener capability')
        if os.name == 'nt' and payload.get('kind') == 'windows-share':
            listener = socket.fromshare(base64.b64decode(payload['share'], validate=True))
        elif os.name != 'nt' and payload.get('kind') == 'inherited-fd':
            fd = payload['fd']
            if type(fd) is not int or fd < 3:
                raise IsolationError('Invalid inherited listener descriptor')
            listener = socket.fromfd(fd, socket.AF_INET, socket.SOCK_STREAM)
            os.close(fd)
        else:
            raise IsolationError('Listener capability platform mismatch')
        lease = OwnedSocketLease(listener, payload)
        return listener, lease
    except (OSError, TypeError, ValueError, KeyError) as exc:
        if listener is not None:
            listener.close()
        raise IsolationError('Invalid owned listener capability') from exc


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
    """Check origins and responses; the parent must also verify child ownership."""

    def __init__(self, identity, lease=None):
        super().__init__()
        if type(lease) is not OwnedSocketLease:
            raise IsolationError('An owned listener capability is required')
        lease.validate(identity)
        self.identity = dict(identity)
        self.lease = lease
        self.base_url = validate_base_url(identity['base_url'])
        self.nonce = identity['nonce']
        # A matching response nonce is required before writes, but does not by
        # itself prove the child or listening socket belongs to the launcher.
        self._identity_verified = False
        self.trust_env = False
        self.hooks['response'].append(self.verify_response)

    def verify_response(self, response, **kwargs):
        if response.headers.get(IDENTITY_HEADER) != self.nonce:
            self._identity_verified = False
            response.close()
            raise IsolationError('Service identity mismatch; no smoke action is permitted')
        self._identity_verified = True
        return response

    def send(self, request, **kwargs):
        # trust_env=False only suppresses inherited settings; requests still
        # honors session and per-request proxies. A proxy would receive the
        # request and credentials before the response nonce can be checked.
        if self.trust_env is not False or self.proxies or kwargs.get('proxies'):
            self._identity_verified = False
            raise IsolationError('Proxies are forbidden for isolated smoke requests')
        try:
            self.lease.validate(self.identity)
        except Exception:
            self._identity_verified = False
            raise
        parsed = urlsplit(request.url)
        origin = f'{parsed.scheme}://{parsed.netloc}'
        if origin != self.base_url:
            self._identity_verified = False
            raise IsolationError('Refusing a request or redirect outside the isolated service')
        if request.method != 'GET' and not self._identity_verified:
            raise IsolationError('Verify the isolated service identity before any write request')
        # requests 的单请求 hooks 会覆盖 session hooks。把强制身份检查放到
        # 所有用户回调之前，并再次检查回调替换或修改后的响应；否则普通
        # GET/重定向可以跳过校验或让后续写请求沿用过期身份。
        if not isinstance(request.hooks, dict):
            self._identity_verified = False
            raise IsolationError('Invalid response hooks for isolated smoke request')
        hooks = request.hooks.get('response', [])
        if not isinstance(hooks, list):
            self._identity_verified = False
            raise IsolationError('Invalid response hooks for isolated smoke request')
        other_hooks = [hook for hook in hooks if hook != self.verify_response]
        request.hooks['response'] = ([self.verify_response, *other_hooks, self.verify_response]
                                     if other_hooks else [self.verify_response])
        if kwargs.get('timeout') is None:
            kwargs['timeout'] = 15
        try:
            return super().send(request, **kwargs)
        except Exception:
            self._identity_verified = False
            raise

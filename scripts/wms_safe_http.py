"""Standard-library HTTP redirects that never forward credentials cross-origin."""
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
import urllib.request


def _origin(url):
    parsed = urlsplit(url)
    if (parsed.scheme.lower() not in ('http', 'https') or not parsed.hostname
            or parsed.username is not None or parsed.password is not None):
        raise ValueError('invalid redirect origin')
    scheme = parsed.scheme.lower()
    port = parsed.port
    if port is None:
        port = 443 if scheme == 'https' else 80
    if not 1 <= port <= 65535:
        raise ValueError('invalid redirect port')
    return scheme, parsed.hostname.lower(), port


class SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep normal urllib semantics for same-origin redirects; reject all others."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            valid = _origin(req.full_url) == _origin(urljoin(req.full_url, newurl))
        except ValueError:
            valid = False
        if not valid:
            raise HTTPError(req.full_url, code, '跨源重定向已拒绝，凭据未转发', headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_same_origin(request, *, timeout):
    """Open with normal TLS and proxy handling and an origin-bound redirect policy."""
    return urllib.request.build_opener(SameOriginRedirectHandler()).open(request, timeout=timeout)

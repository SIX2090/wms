"""Keep sensitive POST redirects on the configured HTTP origin."""
from urllib.parse import urljoin, urlsplit

import requests
from flask import has_request_context, request


class UnsafeRedirect(requests.RequestException):
    """A redirect would send a request outside its original origin."""


def _origin(url):
    parsed = urlsplit(url)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname
            or parsed.username is not None or parsed.password is not None):
        raise ValueError('invalid origin')
    port = parsed.port
    if port == 0:
        raise ValueError('invalid port')
    return (parsed.scheme, parsed.hostname.lower(), port or (443 if parsed.scheme == 'https' else 80))


def post(url, **kwargs):
    """Send using requests while rejecting cross-origin redirects before replay.

    The requests response hook runs for each response before it follows Location.
    Requests remains responsible for normal same-origin redirect semantics.
    """
    if has_request_context() and request.environ.get('wms.ai_unsafe_redirect_blocked'):
        raise UnsafeRedirect('请求重定向超出原始服务，已停止')
    try:
        original = _origin(requests.Request('POST', url).prepare().url)
    except (ValueError, requests.RequestException):
        if has_request_context():
            request.environ['wms.ai_unsafe_redirect_blocked'] = True
        raise UnsafeRedirect('请求地址无效') from None

    def check_redirect(response, *args, **options):
        try:
            location = requests.sessions.Session.get_redirect_target(None, response)
            if location:
                target = urljoin(response.url, location)
                prepared = requests.Request('GET', target).prepare().url
                if _origin(prepared) != original:
                    raise ValueError('different origin')
        except (ValueError, UnicodeError, requests.RequestException):
            if has_request_context():
                request.environ['wms.ai_unsafe_redirect_blocked'] = True
            response.close()
            raise UnsafeRedirect('请求重定向超出原始服务，已停止') from None
        return response

    kwargs['hooks'] = {'response': check_redirect}
    return requests.post(url, **kwargs)

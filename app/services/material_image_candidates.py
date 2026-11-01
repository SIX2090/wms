"""Normalize untrusted search metadata without resolving or fetching URLs."""

import re
from urllib.parse import urlsplit


def candidate_http_url(value):
    if not isinstance(value, str):
        return ''
    value = value.strip()
    if not value or any(char.isspace() or ord(char) < 32 for char in value):
        return ''
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in ('http', 'https') or not parsed.hostname:
            return ''
        parsed.port  # Reject malformed ports without DNS or network access.
    except ValueError:
        return ''
    return value


def normalize_image_candidate(image, thumbnail=None, source=None, title=None,
                              strip_title_html=False):
    image_url = candidate_http_url(image)
    if not image_url:
        return None
    title = title.strip() if isinstance(title, str) else ''
    if strip_title_html:
        title = re.sub(r'<[^>]+>', '', title).strip()
    return {
        'image_url': image_url,
        'thumb_url': candidate_http_url(thumbnail) or image_url,
        'source_url': candidate_http_url(source),
        'title': title[:120],
    }

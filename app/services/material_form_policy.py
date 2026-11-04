"""A script policy for the migrated embedded material-entry page only.

Hashes are reviewed constants, not computed from response HTML. Another CSP
header intersects with the existing policy, so stricter local policies remain.
"""
from flask import request


SHARED_SCRIPT_HASHES = (
    'zgtP3dt2hmvziwrgZAqsiZepR5IAbff3t0o8DF2GA7M=',
    'quHh3qf2gZoeL2+r7K5FpAzJ0tfnJjE71ledX/cYLkw=',
    'bm+mddv2eP9mMvk6dZglCFGss4agvY3dznCgSNXVNKo=',
)


def apply_material_script_policy(response):
    """Allow reviewed shell startup scripts; page code is a same-origin asset."""
    if (request.method == 'GET' and request.endpoint == 'add_material'
            and request.args.get('embedded') == '1'
            and response.status_code == 200 and response.mimetype == 'text/html'):
        hashes = ' '.join("'sha256-" + value + "'" for value in SHARED_SCRIPT_HASHES)
        response.headers.add('Content-Security-Policy',
                             "script-src 'self' " + hashes + "; script-src-attr 'none'")
    return response

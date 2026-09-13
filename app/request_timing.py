from math import isfinite
from time import perf_counter

from flask import g as request_state, request


def init_request_timing(app):
    """Measure Flask response preparation, excluding queueing and body streaming."""
    if app.extensions.get('wms_request_timing'):
        return
    try:
        threshold_ms = float(app.config.get('WMS_SLOW_REQUEST_MS', 500))
        if not isfinite(threshold_ms) or threshold_ms < 0:
            raise ValueError('invalid threshold')
    except (TypeError, ValueError, OverflowError):
        threshold_ms = 500.0
        app.logger.warning('WMS_SLOW_REQUEST_MS 配置无效，使用默认阈值 500ms')
    app.extensions['wms_request_timing'] = True

    @app.before_request
    def _start_request_timer():
        if threshold_ms > 0:
            request_state.wms_request_started_at = perf_counter()

    @app.after_request
    def _log_slow_request(response):
        started_at = getattr(request_state, 'wms_request_started_at', None)
        if started_at is None:
            return response
        elapsed_ms = (perf_counter() - started_at) * 1000
        if elapsed_ms > threshold_ms:
            try:
                app.logger.warning(
                    'slow_request method=%s route=%s endpoint=%s status=%s elapsed_ms=%.1f streamed=%s phase=response_ready',
                    request.method,
                    request.url_rule.rule if request.url_rule else '<unmatched>',
                    request.endpoint or '<unmatched>',
                    response.status_code, elapsed_ms, response.is_streamed,
                )
            except Exception:
                pass
        return response

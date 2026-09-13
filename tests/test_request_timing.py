from unittest.mock import Mock

import pytest
from flask import Flask, Response, abort


def _application(monkeypatch, threshold="500", elapsed=0.6):
    import request_timing

    application = Flask("timing-test")
    application.config.update(TESTING=True, WMS_SLOW_REQUEST_MS=threshold)
    logger = Mock()
    monkeypatch.setattr(application.logger, "warning", logger)
    ticks = iter([10.0, 10.0 + elapsed])
    monkeypatch.setattr(request_timing, "perf_counter", lambda: next(ticks))
    request_timing.init_request_timing(application)
    return application, logger


@pytest.mark.parametrize("status", [200, 400, 500])
def test_slow_request_logs_route_not_sensitive_input(monkeypatch, status):
    application, logger = _application(monkeypatch)
    application.add_url_rule('/probe/<string:secret>', 'probe',
        lambda secret: ('ok', status), methods=['POST'])
    response = application.test_client().post('/probe/private-value?token=query-secret',
        json={"password": "body-secret"}, headers={"Authorization": "Bearer header-secret"})
    assert response.status_code == status
    logger.assert_called_once()
    message = logger.call_args.args[0] % logger.call_args.args[1:]
    assert 'route=/probe/<string:secret>' in message
    assert f'status={status}' in message
    assert 'elapsed_ms=600.0' in message
    for private in ('private-value', 'query-secret', 'body-secret', 'header-secret'):
        assert private not in message


@pytest.mark.parametrize("threshold,elapsed", [(500, 0.1), (500, 0.5), (1000, 0.6), (0, 0.6)])
def test_fast_threshold_boundary_and_disabled_are_silent(monkeypatch, threshold, elapsed):
    application, logger = _application(monkeypatch, threshold, elapsed)
    application.add_url_rule('/probe', 'probe', lambda: 'ok')
    assert application.test_client().get('/probe').status_code == 200
    logger.assert_not_called()


@pytest.mark.parametrize("threshold", ["invalid", "nan", "inf", -1, None])
def test_invalid_threshold_falls_back_to_default(monkeypatch, threshold):
    application, logger = _application(monkeypatch, threshold)
    logger.assert_called_once()
    logger.reset_mock()
    application.add_url_rule('/probe', 'probe', lambda: 'ok')
    assert application.test_client().get('/probe').status_code == 200
    logger.assert_called_once()


def test_early_rejection_and_unmatched_path_are_safe(monkeypatch):
    application, logger = _application(monkeypatch)
    application.before_request(lambda: abort(403))
    assert application.test_client().get('/private-unknown-path').status_code == 403
    message = logger.call_args.args[0] % logger.call_args.args[1:]
    assert 'route=<unmatched>' in message
    assert 'private-unknown-path' not in message


def test_stream_logged_as_response_preparation(monkeypatch):
    application, logger = _application(monkeypatch)
    application.add_url_rule('/stream', 'stream', lambda: Response(iter(['first', 'second'])))
    with application.test_client().get('/stream') as response:
        assert response.get_data(as_text=True) == 'firstsecond'
    message = logger.call_args.args[0] % logger.call_args.args[1:]
    assert 'streamed=True' in message
    assert 'phase=response_ready' in message


def test_logging_failure_does_not_break_response(monkeypatch):
    application, logger = _application(monkeypatch)
    logger.side_effect = OSError('logging unavailable')
    application.add_url_rule('/probe', 'probe', lambda: 'ok')
    assert application.test_client().get('/probe').get_data(as_text=True) == 'ok'


def test_init_request_timing(monkeypatch):
    import app as wms
    import request_timing

    application, logger = _application(monkeypatch)
    request_timing.init_request_timing(application)
    assert len(application.before_request_funcs[None]) == 1
    assert len(application.after_request_funcs[None]) == 1
    assert wms.app.extensions.get('wms_request_timing') is True
    assert wms.app.before_request_funcs[None][0].__module__ == 'request_timing'


def test_unhandled_exception_still_logs_500_without_exception_details(monkeypatch):
    application, logger = _application(monkeypatch)
    application.config.update(TESTING=False, PROPAGATE_EXCEPTIONS=False)

    def fail():
        raise ValueError('private-exception-text')

    application.add_url_rule('/failure', 'failure', fail)
    assert application.test_client().get('/failure').status_code == 500
    logger.assert_called_once()
    message = logger.call_args.args[0] % logger.call_args.args[1:]
    assert 'status=500' in message
    assert 'private-exception-text' not in message


def test_timer_includes_later_response_hooks(monkeypatch):
    import request_timing

    application, logger = _application(monkeypatch)
    clock = [10.0]
    monkeypatch.setattr(request_timing, 'perf_counter', lambda: clock[0])

    def prepare_response(response):
        clock[0] = 10.9
        return response

    application.after_request(prepare_response)
    application.add_url_rule('/probe', 'probe', lambda: 'ok')
    assert application.test_client().get('/probe').status_code == 200
    message = logger.call_args.args[0] % logger.call_args.args[1:]
    assert 'elapsed_ms=900.0' in message

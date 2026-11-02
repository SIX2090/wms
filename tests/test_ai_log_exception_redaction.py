"""Offline log formatting checks: synthetic markers, no app/DB/provider calls."""
import io
import logging
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
from ai.security import SafeLogFilter, sanitize_log_message


@pytest.mark.parametrize('message', [
    'api_key=QA_ONLY_12345678',
    '{"api_key": "QA_ONLY_12345678"}',
    "{'api-key': 'QA_ONLY_12345678'}",
    'Authorization: Bearer QA_ONLY_12345678',
    'Authorization: bearer QA_ONLY_12345678',
])
def test_sensitive_marker_is_redacted_from_messages(message):
    assert 'QA_ONLY_12345678' not in sanitize_log_message(message)


@pytest.mark.parametrize('cached_exception', [False, True])
@pytest.mark.parametrize('handler_count', [1, 2])
def test_safe_filter_redacts_formatted_exception_and_cause(cached_exception, handler_count):
    outputs = [io.StringIO() for _ in range(handler_count)]
    logger = logging.Logger('offline-log-probe', logging.WARNING)
    for output in outputs:
        handler = logging.StreamHandler(output)
        handler.setFormatter(logging.Formatter('%(levelname)s %(message)s'))
        handler.addFilter(SafeLogFilter())
        logger.addHandler(handler)
    try:
        try:
            raise RuntimeError('provider api_key=QA_ONLY_12345678')
        except RuntimeError as cause:
            raise ValueError('authorization Bearer QA_ONLY_CAUSE_12345678') from cause
    except ValueError:
        record = logger.makeRecord(logger.name, logging.ERROR, __file__, 1,
                                   'Provider failed (%s)', ('ValueError',), sys.exc_info())
        if cached_exception:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        logger.handle(record)
    for output in outputs:
        text = output.getvalue()
        assert 'Provider failed (ValueError)' in text
        assert 'ValueError' in text and 'RuntimeError' in text
        assert 'Traceback' in text
        assert 'QA_ONLY_12345678' not in text
        assert 'QA_ONLY_CAUSE_12345678' not in text


def test_safe_filter_preserves_unrelated_diagnostic_message():
    message = 'ConnectionError while processing synthetic order QA-42'
    assert sanitize_log_message(message) == message

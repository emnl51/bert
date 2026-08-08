import logging

from app import log_store


def _reset_buffer():
    log_store.clear_logs()


def test_log_redacts_secrets_and_jooble_key():
    text = log_store.redact_log_text(
        'token=abc123 https://jooble.org/api/super-secret-key authorization: Bearer xyz'
    )
    assert 'abc123' not in text
    assert 'super-secret-key' not in text
    assert 'Bearer xyz' not in text
    assert '***' in text


def test_memory_handler_ignores_log_polling_and_health():
    _reset_buffer()
    handler = log_store.MemoryLogHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))

    record = logging.LogRecord('uvicorn.access', logging.INFO, __file__, 1, 'GET /api/logs HTTP/1.1 200 OK', (), None)
    handler.emit(record)
    record2 = logging.LogRecord('uvicorn.access', logging.INFO, __file__, 2, 'GET /health HTTP/1.1 200 OK', (), None)
    handler.emit(record2)
    assert log_store.log_stats()['stored'] == 0

    record3 = logging.LogRecord('jobtrack.jobspy', logging.WARNING, __file__, 3, 'linkedin timeout after 45s', (), None)
    handler.emit(record3)
    rows = log_store.list_logs(level='WARNING')
    assert len(rows) == 1
    assert rows[0]['logger'] == 'jobtrack.jobspy'
    assert 'timeout' in rows[0]['message']


def test_log_filters_by_level_logger_and_query():
    _reset_buffer()
    handler = log_store.MemoryLogHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    handler.emit(logging.LogRecord('jobtrack.provider', logging.INFO, __file__, 1, 'Arbeitnow fetched 100 jobs', (), None))
    handler.emit(logging.LogRecord('jobtrack.jobspy', logging.WARNING, __file__, 2, 'LinkedIn timeout', (), None))

    assert len(log_store.list_logs(level='WARNING')) == 1
    assert len(log_store.list_logs(logger_name='jobspy')) == 1
    assert len(log_store.list_logs(query='arbeitnow')) == 1

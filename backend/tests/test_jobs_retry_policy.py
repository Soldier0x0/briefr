from jobs.retry_policy import is_retryable_job_error, next_retry_delay_seconds


class DatabaseError(Exception):
    pass


def test_timeout_message_is_retryable():
    assert is_retryable_job_error(DatabaseError("Database command timeout")) is True


def test_auth_error_not_retryable():
    assert is_retryable_job_error(RuntimeError("missing API key")) is False


def test_backoff_sequence():
    assert next_retry_delay_seconds(1) == 180
    assert next_retry_delay_seconds(2) == 240
    assert next_retry_delay_seconds(3) == 300
    assert next_retry_delay_seconds(4) is None

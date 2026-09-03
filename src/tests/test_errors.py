from app.mcp.tools import _error_code


def test_internal_error_is_internal_error():
    from pydantic import ValidationError

    assert _error_code(ValueError("x")) == "INTERNAL_ERROR"


def test_timeout_is_retryable_provider_timeout():
    assert _error_code(TimeoutError()) == "PROVIDER_TIMEOUT"


def test_connection_error_is_retryable_provider_unavailable():
    assert _error_code(ConnectionError()) == "PROVIDER_UNAVAILABLE"

"""
Tests for src/rag/exceptions.py

Covers RAGError (attributes, __str__ format), all subclasses
(EmbeddingError, VectorSearchError, GraphQueryError, DocumentProcessingError,
RAGConnectionError, RAGConfigurationError, RateLimitError,
CircuitBreakerOpenError), RAGErrorCodes constants, and the helper functions
wrap_exception, is_retriable_error, and get_retry_delay.
No network, no Tkinter, no file I/O.
"""

import sys
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rag.exceptions import (
    RAGError,
    EmbeddingError,
    VectorSearchError,
    GraphQueryError,
    DocumentProcessingError,
    RAGConnectionError,
    RAGConfigurationError,
    RateLimitError,
    CircuitBreakerOpenError,
    RAGErrorCodes,
    wrap_exception,
    is_retriable_error,
    get_retry_delay,
)


# ===========================================================================
# RAGError
# ===========================================================================

class TestRAGError:
    def test_is_exception(self):
        assert issubclass(RAGError, Exception)

    def test_message_stored(self):
        err = RAGError("test error")
        assert err.message == "test error"

    def test_default_error_code(self):
        err = RAGError("test")
        assert err.error_code == "RAG_E000"

    def test_custom_error_code(self):
        err = RAGError("test", error_code="RAG_E001")
        assert err.error_code == "RAG_E001"

    def test_details_defaults_empty_dict(self):
        err = RAGError("test")
        assert err.details == {}

    def test_custom_details(self):
        err = RAGError("test", details={"model": "gpt-4"})
        assert err.details["model"] == "gpt-4"

    def test_recoverable_defaults_true(self):
        err = RAGError("test")
        assert err.recoverable is True

    def test_recoverable_can_be_false(self):
        err = RAGError("test", recoverable=False)
        assert err.recoverable is False

    def test_str_contains_error_code(self):
        err = RAGError("test error")
        assert "RAG_E000" in str(err)

    def test_str_contains_message(self):
        err = RAGError("my error message")
        assert "my error message" in str(err)

    def test_str_format_with_no_details(self):
        err = RAGError("msg", error_code="RAG_E001")
        assert str(err) == "[RAG_E001] msg"

    def test_str_format_with_details(self):
        err = RAGError("msg", error_code="RAG_E001", details={"k": "v"})
        s = str(err)
        assert "[RAG_E001]" in s
        assert "msg" in s
        assert "k=v" in s

    def test_can_raise_and_catch(self):
        with pytest.raises(RAGError):
            raise RAGError("test")


# ===========================================================================
# EmbeddingError
# ===========================================================================

class TestEmbeddingError:
    def test_is_rag_error(self):
        assert issubclass(EmbeddingError, RAGError)

    def test_model_stored(self):
        err = EmbeddingError("failed", model="text-embedding-3-small")
        assert err.model == "text-embedding-3-small"

    def test_model_in_details(self):
        err = EmbeddingError("failed", model="text-embedding-3-small")
        assert "model" in err.details

    def test_input_length_stored(self):
        err = EmbeddingError("too long", input_length=9000)
        assert err.input_length == 9000

    def test_input_length_in_details(self):
        err = EmbeddingError("too long", input_length=9000)
        assert "input_length" in err.details

    def test_default_error_code(self):
        err = EmbeddingError("failed")
        assert err.error_code == RAGErrorCodes.EMBEDDING_FAILED

    def test_model_none_not_in_details(self):
        err = EmbeddingError("failed")
        assert "model" not in err.details

    def test_input_length_none_not_in_details(self):
        err = EmbeddingError("failed")
        assert "input_length" not in err.details


# ===========================================================================
# VectorSearchError
# ===========================================================================

class TestVectorSearchError:
    def test_is_rag_error(self):
        assert issubclass(VectorSearchError, RAGError)

    def test_store_type_stored(self):
        err = VectorSearchError("failed", store_type="neon")
        assert err.store_type == "neon"

    def test_store_type_in_details(self):
        err = VectorSearchError("failed", store_type="neon")
        assert "store_type" in err.details

    def test_query_type_stored(self):
        err = VectorSearchError("failed", query_type="similarity")
        assert err.query_type == "similarity"

    def test_query_type_in_details(self):
        err = VectorSearchError("failed", query_type="similarity")
        assert "query_type" in err.details

    def test_default_error_code(self):
        err = VectorSearchError("failed")
        assert err.error_code == RAGErrorCodes.VECTOR_SEARCH_FAILED


# ===========================================================================
# GraphQueryError
# ===========================================================================

class TestGraphQueryError:
    def test_is_rag_error(self):
        assert issubclass(GraphQueryError, RAGError)

    def test_query_stored(self):
        err = GraphQueryError("failed", query="MATCH (n) RETURN n")
        assert err.query == "MATCH (n) RETURN n"

    def test_short_query_not_truncated(self):
        q = "MATCH (n) RETURN n"
        err = GraphQueryError("failed", query=q)
        assert err.details["query"] == q

    def test_long_query_truncated_in_details(self):
        long_query = "A" * 300
        err = GraphQueryError("failed", query=long_query)
        # Details should be truncated at 200 chars + "..."
        assert len(err.details["query"]) < 210
        assert err.details["query"].endswith("...")

    def test_full_query_stored_on_self(self):
        long_query = "A" * 300
        err = GraphQueryError("failed", query=long_query)
        # self.query stores the original
        assert err.query == long_query

    def test_graph_type_defaults_neo4j(self):
        err = GraphQueryError("failed")
        assert err.graph_type == "neo4j"

    def test_graph_type_in_details(self):
        err = GraphQueryError("failed")
        assert "graph_type" in err.details

    def test_default_error_code(self):
        err = GraphQueryError("failed")
        assert err.error_code == RAGErrorCodes.GRAPH_QUERY_FAILED


# ===========================================================================
# DocumentProcessingError
# ===========================================================================

class TestDocumentProcessingError:
    def test_is_rag_error(self):
        assert issubclass(DocumentProcessingError, RAGError)

    def test_document_id_stored(self):
        err = DocumentProcessingError("failed", document_id="doc123")
        assert err.document_id == "doc123"

    def test_document_id_in_details(self):
        err = DocumentProcessingError("failed", document_id="doc123")
        assert "document_id" in err.details

    def test_processing_stage_stored(self):
        err = DocumentProcessingError("failed", processing_stage="chunking")
        assert err.processing_stage == "chunking"

    def test_processing_stage_in_details_as_stage(self):
        err = DocumentProcessingError("failed", processing_stage="chunking")
        assert err.details.get("stage") == "chunking"

    def test_default_error_code(self):
        err = DocumentProcessingError("failed")
        assert err.error_code == RAGErrorCodes.DOCUMENT_PROCESSING_FAILED


# ===========================================================================
# RAGConnectionError
# ===========================================================================

class TestRAGConnectionError:
    def test_is_rag_error(self):
        assert issubclass(RAGConnectionError, RAGError)

    def test_service_stored(self):
        err = RAGConnectionError("failed", service="neon")
        assert err.service == "neon"

    def test_service_in_details(self):
        err = RAGConnectionError("failed", service="neon")
        assert "service" in err.details

    def test_endpoint_sanitized_removes_credentials(self):
        endpoint = "user:password@db.example.com/mydb"
        err = RAGConnectionError("failed", endpoint=endpoint)
        assert "password" not in err.details.get("endpoint", "")
        assert "db.example.com" in err.details.get("endpoint", "")

    def test_endpoint_without_at_not_modified(self):
        endpoint = "db.example.com:5432/mydb"
        err = RAGConnectionError("failed", endpoint=endpoint)
        assert err.details.get("endpoint") == endpoint

    def test_original_endpoint_stored_on_self(self):
        endpoint = "user:pass@host/db"
        err = RAGConnectionError("failed", endpoint=endpoint)
        assert err.endpoint == endpoint

    def test_default_error_code(self):
        err = RAGConnectionError("failed")
        assert err.error_code == RAGErrorCodes.CONNECTION_FAILED

    def test_recoverable_defaults_true(self):
        err = RAGConnectionError("failed")
        assert err.recoverable is True


# ===========================================================================
# RAGConfigurationError
# ===========================================================================

class TestRAGConfigurationError:
    def test_is_rag_error(self):
        assert issubclass(RAGConfigurationError, RAGError)

    def test_recoverable_defaults_false(self):
        err = RAGConfigurationError("bad config")
        assert err.recoverable is False

    def test_config_key_stored(self):
        err = RAGConfigurationError("bad config", config_key="neon_url")
        assert err.config_key == "neon_url"

    def test_config_key_in_details(self):
        err = RAGConfigurationError("bad config", config_key="neon_url")
        assert "config_key" in err.details

    def test_expected_stored(self):
        err = RAGConfigurationError("bad config", expected="postgresql://...")
        assert err.expected == "postgresql://..."

    def test_actual_stored(self):
        err = RAGConfigurationError("bad config", actual="")
        assert err.actual == ""

    def test_default_error_code(self):
        err = RAGConfigurationError("bad config")
        assert err.error_code == RAGErrorCodes.CONFIGURATION_ERROR


# ===========================================================================
# RateLimitError
# ===========================================================================

class TestRateLimitError:
    def test_is_rag_error(self):
        assert issubclass(RateLimitError, RAGError)

    def test_retry_after_stored(self):
        err = RateLimitError("rate limited", retry_after=30)
        assert err.retry_after == 30

    def test_retry_after_in_details(self):
        err = RateLimitError("rate limited", retry_after=30)
        assert "retry_after" in err.details

    def test_limit_type_defaults_requests(self):
        err = RateLimitError("rate limited")
        assert err.limit_type == "requests"

    def test_limit_type_in_details(self):
        err = RateLimitError("rate limited")
        assert "limit_type" in err.details

    def test_recoverable_defaults_true(self):
        err = RateLimitError("rate limited")
        assert err.recoverable is True

    def test_default_error_code(self):
        err = RateLimitError("rate limited")
        assert err.error_code == RAGErrorCodes.RATE_LIMIT_EXCEEDED


# ===========================================================================
# CircuitBreakerOpenError
# ===========================================================================

class TestCircuitBreakerOpenError:
    def test_is_rag_error(self):
        assert issubclass(CircuitBreakerOpenError, RAGError)

    def test_service_stored(self):
        err = CircuitBreakerOpenError("circuit open", service="neon")
        assert err.service == "neon"

    def test_recovery_time_stored(self):
        err = CircuitBreakerOpenError("circuit open", recovery_time=15.0)
        assert err.recovery_time == pytest.approx(15.0)

    def test_recoverable_defaults_true(self):
        err = CircuitBreakerOpenError("circuit open")
        assert err.recoverable is True

    def test_default_error_code(self):
        err = CircuitBreakerOpenError("circuit open")
        assert err.error_code == RAGErrorCodes.CIRCUIT_BREAKER_OPEN


# ===========================================================================
# RAGErrorCodes
# ===========================================================================

class TestRAGErrorCodes:
    def test_base_code(self):
        assert RAGErrorCodes.RAG_ERROR == "RAG_E000"

    def test_embedding_failed_code(self):
        assert RAGErrorCodes.EMBEDDING_FAILED == "RAG_E001"

    def test_vector_search_failed_code(self):
        assert RAGErrorCodes.VECTOR_SEARCH_FAILED == "RAG_E100"

    def test_graph_query_failed_code(self):
        assert RAGErrorCodes.GRAPH_QUERY_FAILED == "RAG_E200"

    def test_document_processing_failed_code(self):
        assert RAGErrorCodes.DOCUMENT_PROCESSING_FAILED == "RAG_E300"

    def test_connection_failed_code(self):
        assert RAGErrorCodes.CONNECTION_FAILED == "RAG_E400"

    def test_configuration_error_code(self):
        assert RAGErrorCodes.CONFIGURATION_ERROR == "RAG_E500"

    def test_rate_limit_exceeded_code(self):
        assert RAGErrorCodes.RATE_LIMIT_EXCEEDED == "RAG_E600"

    def test_circuit_breaker_open_code(self):
        assert RAGErrorCodes.CIRCUIT_BREAKER_OPEN == "RAG_E601"


# ===========================================================================
# wrap_exception
# ===========================================================================

class TestWrapException:
    def test_returns_rag_error(self):
        original = ValueError("original error")
        result = wrap_exception(original, EmbeddingError)
        assert isinstance(result, RAGError)

    def test_returns_correct_subclass(self):
        original = ValueError("original error")
        result = wrap_exception(original, EmbeddingError)
        assert isinstance(result, EmbeddingError)

    def test_cause_is_set(self):
        original = ValueError("original error")
        result = wrap_exception(original, EmbeddingError)
        assert result.__cause__ is original

    def test_uses_original_message_when_none(self):
        original = ValueError("original message")
        result = wrap_exception(original, EmbeddingError)
        assert "original message" in result.message

    def test_uses_custom_message_when_provided(self):
        original = ValueError("original message")
        result = wrap_exception(original, EmbeddingError, message="Custom msg")
        assert result.message == "Custom msg"

    def test_can_wrap_connection_error(self):
        original = ConnectionError("connection refused")
        result = wrap_exception(original, RAGConnectionError)
        assert isinstance(result, RAGConnectionError)


# ===========================================================================
# is_retriable_error
# ===========================================================================

class TestIsRetriableError:
    def test_rag_error_recoverable_true_returns_true(self):
        err = RAGError("test", recoverable=True)
        assert is_retriable_error(err) is True

    def test_rag_error_recoverable_false_returns_false(self):
        err = RAGError("test", recoverable=False)
        assert is_retriable_error(err) is False

    def test_configuration_error_not_retriable(self):
        err = RAGConfigurationError("bad config")
        assert is_retriable_error(err) is False

    def test_rate_limit_error_retriable(self):
        err = RateLimitError("too fast")
        assert is_retriable_error(err) is True

    def test_connection_error_retriable(self):
        assert is_retriable_error(ConnectionError("refused")) is True

    def test_timeout_error_retriable(self):
        assert is_retriable_error(TimeoutError("timed out")) is True

    def test_os_error_retriable(self):
        assert is_retriable_error(OSError("network issue")) is True

    def test_message_rate_limit_retriable(self):
        err = Exception("API rate limit exceeded")
        assert is_retriable_error(err) is True

    def test_message_timeout_retriable(self):
        err = Exception("connection timeout occurred")
        assert is_retriable_error(err) is True

    def test_message_unavailable_retriable(self):
        err = Exception("service temporarily unavailable")
        assert is_retriable_error(err) is True

    def test_generic_value_error_not_retriable(self):
        err = ValueError("invalid argument")
        assert is_retriable_error(err) is False

    def test_returns_bool(self):
        assert isinstance(is_retriable_error(RAGError("test")), bool)


# ===========================================================================
# get_retry_delay
# ===========================================================================

class TestGetRetryDelay:
    def test_rate_limit_with_retry_after_returns_retry_after(self):
        err = RateLimitError("limited", retry_after=30)
        assert get_retry_delay(err) == pytest.approx(30.0)

    def test_circuit_breaker_with_recovery_time_returns_recovery_time(self):
        err = CircuitBreakerOpenError("open", recovery_time=15.0)
        assert get_retry_delay(err) == pytest.approx(15.0)

    def test_generic_attempt_1_base_delay(self):
        # Attempt 1: base * 2^0 = 1.0 + small jitter
        err = ValueError("generic")
        delay = get_retry_delay(err, attempt=1)
        assert 1.0 <= delay <= 1.15  # 1.0 + up to 10% jitter

    def test_generic_attempt_2_doubled(self):
        # Attempt 2: base * 2^1 = 2.0 + small jitter
        err = ValueError("generic")
        delay = get_retry_delay(err, attempt=2)
        assert 2.0 <= delay <= 2.3

    def test_generic_attempt_3_quadrupled(self):
        # Attempt 3: base * 2^2 = 4.0 + small jitter
        err = ValueError("generic")
        delay = get_retry_delay(err, attempt=3)
        assert 4.0 <= delay <= 4.5

    def test_delay_capped_at_60_seconds(self):
        # Very large attempt number → capped at 60
        err = ValueError("generic")
        delay = get_retry_delay(err, attempt=100)
        assert delay <= 60.0

    def test_returns_float(self):
        err = ValueError("generic")
        assert isinstance(get_retry_delay(err), float)

    def test_rate_limit_without_retry_after_falls_back_to_backoff(self):
        err = RateLimitError("limited", retry_after=None)
        delay = get_retry_delay(err, attempt=1)
        assert delay > 0.0

    def test_circuit_breaker_without_recovery_time_falls_back_to_backoff(self):
        err = CircuitBreakerOpenError("open", recovery_time=None)
        delay = get_retry_delay(err, attempt=1)
        assert delay > 0.0

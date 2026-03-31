"""
Tests for src/rag/rag_resilience.py

Covers CircuitOpenError, get_effective_weights (weight redistribution under
various availability scenarios), get_circuit_breaker_states, reset_circuit_breaker,
reset_all_circuit_breakers, and the three singleton getter functions.
No network I/O — circuit breaker availability functions are patched.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import rag.rag_resilience as rr_module
from rag.rag_resilience import (
    CircuitOpenError,
    get_effective_weights,
    get_circuit_breaker_states,
    reset_circuit_breaker,
    reset_all_circuit_breakers,
    get_neo4j_circuit_breaker,
    get_neon_circuit_breaker,
    get_openai_embedding_circuit_breaker,
    is_neo4j_available,
    is_neon_available,
    is_openai_embedding_available,
)
from utils.resilience import CircuitBreaker, CircuitState
from utils.exceptions import ServiceUnavailableError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_singletons():
    """Reset all module-level circuit breaker singletons."""
    rr_module._neo4j_circuit_breaker = None
    rr_module._neon_circuit_breaker = None
    rr_module._openai_embedding_circuit_breaker = None


@pytest.fixture(autouse=True)
def reset_singletons():
    _reset_singletons()
    yield
    _reset_singletons()


def _patch_availability(neon=True, embedding=True, neo4j=True):
    """Return context managers patching all three availability functions."""
    return (
        patch.object(rr_module, "is_neon_available", return_value=neon),
        patch.object(rr_module, "is_openai_embedding_available", return_value=embedding),
        patch.object(rr_module, "is_neo4j_available", return_value=neo4j),
    )


# ===========================================================================
# CircuitOpenError
# ===========================================================================

class TestCircuitOpenError:
    def test_is_service_unavailable_error(self):
        err = CircuitOpenError("neo4j", 30)
        assert isinstance(err, ServiceUnavailableError)

    def test_service_attribute(self):
        err = CircuitOpenError("neon", 60)
        assert err.service == "neon"

    def test_recovery_timeout_attribute(self):
        err = CircuitOpenError("neo4j", 45)
        assert err.recovery_timeout == 45

    def test_message_contains_service_name(self):
        err = CircuitOpenError("neo4j", 30)
        assert "neo4j" in str(err)

    def test_message_contains_timeout(self):
        err = CircuitOpenError("neo4j", 30)
        assert "30" in str(err)

    def test_message_mentions_circuit_open(self):
        err = CircuitOpenError("neon", 30)
        assert "OPEN" in str(err) or "open" in str(err).lower()


# ===========================================================================
# get_effective_weights — all components available
# ===========================================================================

class TestGetEffectiveWeightsAllLive:
    def test_all_live_returns_original_weights(self):
        with _patch_availability(neon=True, embedding=True, neo4j=True)[0], \
             _patch_availability(neon=True, embedding=True, neo4j=True)[1], \
             _patch_availability(neon=True, embedding=True, neo4j=True)[2]:
            v, b, g = get_effective_weights(0.5, 0.3, 0.2)
        assert v == 0.5
        assert b == 0.3
        assert g == 0.2

    def test_all_live_sums_preserved(self):
        with _patch_availability(neon=True, embedding=True, neo4j=True)[0], \
             _patch_availability(neon=True, embedding=True, neo4j=True)[1], \
             _patch_availability(neon=True, embedding=True, neo4j=True)[2]:
            v, b, g = get_effective_weights(0.5, 0.3, 0.2)
        assert abs(v + b + g - 1.0) < 1e-9


# ===========================================================================
# get_effective_weights — using context manager helper
# ===========================================================================

class TestGetEffectiveWeightsCombined:
    def _run(self, neon, embedding, neo4j, v=0.5, b=0.3, g=0.2):
        with patch.object(rr_module, "is_neon_available", return_value=neon), \
             patch.object(rr_module, "is_openai_embedding_available", return_value=embedding), \
             patch.object(rr_module, "is_neo4j_available", return_value=neo4j):
            return get_effective_weights(v, b, g)

    def test_all_live_no_change(self):
        v, b, g = self._run(neon=True, embedding=True, neo4j=True)
        assert v == 0.5 and b == 0.3 and g == 0.2

    def test_neo4j_down_graph_zero(self):
        v, b, g = self._run(neon=True, embedding=True, neo4j=False)
        assert g == 0.0

    def test_neo4j_down_vector_bm25_increased(self):
        v, b, g = self._run(neon=True, embedding=True, neo4j=False)
        assert v > 0.5
        assert b > 0.3

    def test_neo4j_down_weights_sum_to_one(self):
        v, b, g = self._run(neon=True, embedding=True, neo4j=False)
        assert abs(v + b + g - 1.0) < 1e-9

    def test_embedding_down_vector_zero(self):
        # Embedding down → vector unavailable (but BM25 still works)
        v, b, g = self._run(neon=True, embedding=False, neo4j=True)
        assert v == 0.0

    def test_embedding_down_bm25_and_graph_increased(self):
        v, b, g = self._run(neon=True, embedding=False, neo4j=True)
        assert b > 0.3
        assert g > 0.2

    def test_embedding_down_weights_sum_to_one(self):
        v, b, g = self._run(neon=True, embedding=False, neo4j=True)
        assert abs(v + b + g - 1.0) < 1e-9

    def test_neon_down_vector_and_bm25_zero(self):
        # Neon down → both vector and BM25 unavailable
        v, b, g = self._run(neon=False, embedding=True, neo4j=True)
        assert v == 0.0
        assert b == 0.0

    def test_neon_down_graph_gets_all_weight(self):
        v, b, g = self._run(neon=False, embedding=True, neo4j=True)
        assert abs(g - 1.0) < 1e-9

    def test_all_down_returns_original_weights(self):
        # All dead → live_weight = 0 → return originals unchanged
        v, b, g = self._run(neon=False, embedding=False, neo4j=False)
        assert v == 0.5 and b == 0.3 and g == 0.2

    def test_returns_tuple_of_three(self):
        result = self._run(neon=True, embedding=True, neo4j=True)
        assert len(result) == 3

    def test_all_floats(self):
        v, b, g = self._run(neon=True, embedding=True, neo4j=True)
        for val in (v, b, g):
            assert isinstance(val, float)

    def test_different_initial_weights_preserved_when_all_live(self):
        v, b, g = self._run(neon=True, embedding=True, neo4j=True, v=0.6, b=0.25, g=0.15)
        assert v == 0.6 and b == 0.25 and g == 0.15

    def test_neo4j_and_embedding_both_down(self):
        # vector down (embedding + neon both needed), graph down, bm25 still OK
        v, b, g = self._run(neon=True, embedding=False, neo4j=False)
        assert v == 0.0
        assert g == 0.0
        assert abs(b - 1.0) < 1e-9


# ===========================================================================
# Singleton getters
# ===========================================================================

class TestSingletonGetters:
    def test_get_neo4j_returns_circuit_breaker(self):
        cb = get_neo4j_circuit_breaker()
        assert isinstance(cb, CircuitBreaker)

    def test_get_neon_returns_circuit_breaker(self):
        cb = get_neon_circuit_breaker()
        assert isinstance(cb, CircuitBreaker)

    def test_get_openai_embedding_returns_circuit_breaker(self):
        cb = get_openai_embedding_circuit_breaker()
        assert isinstance(cb, CircuitBreaker)

    def test_neo4j_singleton_same_instance(self):
        c1 = get_neo4j_circuit_breaker()
        c2 = get_neo4j_circuit_breaker()
        assert c1 is c2

    def test_neon_singleton_same_instance(self):
        c1 = get_neon_circuit_breaker()
        c2 = get_neon_circuit_breaker()
        assert c1 is c2

    def test_openai_embedding_singleton_same_instance(self):
        c1 = get_openai_embedding_circuit_breaker()
        c2 = get_openai_embedding_circuit_breaker()
        assert c1 is c2

    def test_different_singletons_are_different(self):
        neo4j_cb = get_neo4j_circuit_breaker()
        neon_cb = get_neon_circuit_breaker()
        assert neo4j_cb is not neon_cb


# ===========================================================================
# is_*_available
# ===========================================================================

class TestAvailabilityChecks:
    def test_is_neo4j_available_when_closed(self):
        cb = get_neo4j_circuit_breaker()
        assert cb.state == CircuitState.CLOSED
        assert is_neo4j_available() is True

    def test_is_neon_available_when_closed(self):
        cb = get_neon_circuit_breaker()
        assert cb.state == CircuitState.CLOSED
        assert is_neon_available() is True

    def test_is_openai_embedding_available_when_closed(self):
        cb = get_openai_embedding_circuit_breaker()
        assert cb.state == CircuitState.CLOSED
        assert is_openai_embedding_available() is True

    def test_returns_bool(self):
        assert isinstance(is_neo4j_available(), bool)
        assert isinstance(is_neon_available(), bool)
        assert isinstance(is_openai_embedding_available(), bool)


# ===========================================================================
# get_circuit_breaker_states
# ===========================================================================

class TestGetCircuitBreakerStates:
    def test_returns_dict(self):
        result = get_circuit_breaker_states()
        assert isinstance(result, dict)

    def test_has_neo4j_key(self):
        assert "neo4j" in get_circuit_breaker_states()

    def test_has_neon_key(self):
        assert "neon" in get_circuit_breaker_states()

    def test_has_openai_embedding_key(self):
        assert "openai_embedding" in get_circuit_breaker_states()

    def test_all_initially_closed(self):
        states = get_circuit_breaker_states()
        for key, state in states.items():
            assert state == CircuitState.CLOSED.value, f"{key} should be CLOSED"


# ===========================================================================
# reset_circuit_breaker
# ===========================================================================

class TestResetCircuitBreaker:
    def test_neo4j_reset_returns_true(self):
        assert reset_circuit_breaker("neo4j") is True

    def test_neon_reset_returns_true(self):
        assert reset_circuit_breaker("neon") is True

    def test_openai_embedding_reset_returns_true(self):
        assert reset_circuit_breaker("openai_embedding") is True

    def test_unknown_service_returns_false(self):
        assert reset_circuit_breaker("unknown_service") is False

    def test_empty_string_returns_false(self):
        assert reset_circuit_breaker("") is False


# ===========================================================================
# reset_all_circuit_breakers
# ===========================================================================

class TestResetAllCircuitBreakers:
    def test_runs_without_error(self):
        reset_all_circuit_breakers()

    def test_all_remain_closed_after_reset(self):
        reset_all_circuit_breakers()
        states = get_circuit_breaker_states()
        for key, state in states.items():
            assert state == CircuitState.CLOSED.value

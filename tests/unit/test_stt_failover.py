"""
Tests for STTFailoverManager in src/stt_providers/failover.py

Covers initialization (defaults, provider list), _record_success (reset count,
set last_successful), _record_failure (increment count, set skip_until at
threshold), get_provider_status (all keys, configured/failure/disabled flags),
reset_provider (clears counts), reset_all_providers (clears all),
get_available_providers (excludes disabled/unconfigured).
No network, no audio I/O, no Tkinter.
"""

import sys
import time
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from stt_providers.failover import STTFailoverManager
from stt_providers.base import BaseSTTProvider


# ---------------------------------------------------------------------------
# Minimal stub providers
# ---------------------------------------------------------------------------

class _Stub(BaseSTTProvider):
    def __init__(self, name, key="key", configured=True):
        super().__init__(api_key=key)
        self._name = name
        self._configured = configured

    @property
    def provider_name(self):
        return self._name

    @property
    def is_configured(self):
        return self._configured

    def transcribe(self, segment):
        return "hello"

    def test_connection(self):
        return self._configured


def _manager(providers=None, max_fail=3, skip_sec=300.0) -> STTFailoverManager:
    if providers is None:
        providers = [_Stub("primary"), _Stub("secondary")]
    return STTFailoverManager(providers, max_failures_before_skip=max_fail,
                              skip_duration_seconds=skip_sec)


# ===========================================================================
# Initialization
# ===========================================================================

class TestInit:
    def test_providers_stored(self):
        p1, p2 = _Stub("a"), _Stub("b")
        fm = STTFailoverManager([p1, p2])
        assert fm.providers == [p1, p2]

    def test_max_failures_stored(self):
        fm = STTFailoverManager([_Stub("x")], max_failures_before_skip=5)
        assert fm.max_failures_before_skip == 5

    def test_skip_duration_stored(self):
        fm = STTFailoverManager([_Stub("x")], skip_duration_seconds=60.0)
        assert fm.skip_duration_seconds == pytest.approx(60.0)

    def test_failure_counts_empty(self):
        fm = _manager()
        assert fm._failure_counts == {}

    def test_skip_until_empty(self):
        fm = _manager()
        assert fm._skip_until == {}

    def test_last_successful_none(self):
        fm = _manager()
        assert fm._last_successful_provider is None


# ===========================================================================
# _record_success
# ===========================================================================

class TestRecordSuccess:
    def test_sets_last_successful_provider(self):
        fm = _manager()
        fm._record_success("primary")
        assert fm._last_successful_provider == "primary"

    def test_resets_failure_count_to_zero(self):
        fm = _manager()
        fm._failure_counts["primary"] = 5
        fm._record_success("primary")
        assert fm._failure_counts["primary"] == 0

    def test_resets_skip_until_to_zero(self):
        fm = _manager()
        fm._skip_until["primary"] = time.time() + 9999
        fm._record_success("primary")
        assert fm._skip_until["primary"] == 0

    def test_updates_last_successful_to_newest(self):
        fm = _manager()
        fm._record_success("primary")
        fm._record_success("secondary")
        assert fm._last_successful_provider == "secondary"


# ===========================================================================
# _record_failure
# ===========================================================================

class TestRecordFailure:
    def test_increments_failure_count(self):
        fm = _manager(max_fail=5)
        fm._record_failure("primary")
        assert fm._failure_counts["primary"] == 1

    def test_increments_from_existing_count(self):
        fm = _manager(max_fail=5)
        fm._failure_counts["primary"] = 2
        fm._record_failure("primary")
        assert fm._failure_counts["primary"] == 3

    def test_sets_skip_until_at_threshold(self):
        fm = _manager(max_fail=2, skip_sec=300.0)
        fm._record_failure("primary")
        fm._record_failure("primary")
        assert fm._skip_until.get("primary", 0) > time.time()

    def test_no_skip_before_threshold(self):
        fm = _manager(max_fail=3, skip_sec=300.0)
        fm._record_failure("primary")
        fm._record_failure("primary")
        # Only 2 failures, threshold is 3 — no skip yet
        assert fm._skip_until.get("primary", 0) == 0

    def test_skip_until_is_in_future(self):
        fm = _manager(max_fail=1, skip_sec=300.0)
        before = time.time()
        fm._record_failure("primary")
        assert fm._skip_until["primary"] >= before + 299


# ===========================================================================
# get_provider_status
# ===========================================================================

class TestGetProviderStatus:
    def test_returns_dict(self):
        fm = _manager()
        assert isinstance(fm.get_provider_status(), dict)

    def test_all_providers_in_status(self):
        fm = _manager()
        status = fm.get_provider_status()
        assert "primary" in status
        assert "secondary" in status

    def test_status_has_configured_key(self):
        fm = _manager()
        assert "configured" in fm.get_provider_status()["primary"]

    def test_status_has_failure_count_key(self):
        fm = _manager()
        assert "failure_count" in fm.get_provider_status()["primary"]

    def test_status_has_temporarily_disabled_key(self):
        fm = _manager()
        assert "temporarily_disabled" in fm.get_provider_status()["primary"]

    def test_configured_true_for_stub_with_key(self):
        fm = _manager()
        assert fm.get_provider_status()["primary"]["configured"] is True

    def test_configured_false_for_unconfigured_provider(self):
        fm = STTFailoverManager([_Stub("prov", key="", configured=False)])
        assert fm.get_provider_status()["prov"]["configured"] is False

    def test_failure_count_zero_initially(self):
        fm = _manager()
        assert fm.get_provider_status()["primary"]["failure_count"] == 0

    def test_temporarily_disabled_false_initially(self):
        fm = _manager()
        assert fm.get_provider_status()["primary"]["temporarily_disabled"] is False

    def test_temporarily_disabled_true_after_threshold(self):
        fm = _manager(max_fail=1, skip_sec=300)
        fm._record_failure("primary")
        assert fm.get_provider_status()["primary"]["temporarily_disabled"] is True

    def test_last_successful_flag(self):
        fm = _manager()
        fm._record_success("secondary")
        status = fm.get_provider_status()
        assert status["secondary"]["last_successful"] is True
        assert status["primary"]["last_successful"] is False


# ===========================================================================
# reset_provider
# ===========================================================================

class TestResetProvider:
    def test_resets_failure_count_to_zero(self):
        fm = _manager()
        fm._failure_counts["primary"] = 5
        fm.reset_provider("primary")
        assert fm._failure_counts["primary"] == 0

    def test_resets_skip_until_to_zero(self):
        fm = _manager()
        fm._skip_until["primary"] = time.time() + 9999
        fm.reset_provider("primary")
        assert fm._skip_until["primary"] == 0

    def test_does_not_affect_other_providers(self):
        fm = _manager()
        fm._failure_counts["secondary"] = 3
        fm.reset_provider("primary")
        assert fm._failure_counts.get("secondary", 0) == 3

    def test_reset_nonexistent_no_error(self):
        fm = _manager()
        fm.reset_provider("nonexistent")  # Should not raise


# ===========================================================================
# reset_all_providers
# ===========================================================================

class TestResetAllProviders:
    def test_clears_all_failure_counts(self):
        fm = _manager()
        fm._failure_counts["primary"] = 5
        fm._failure_counts["secondary"] = 2
        fm.reset_all_providers()
        assert fm._failure_counts == {}

    def test_clears_all_skip_until(self):
        fm = _manager()
        fm._skip_until["primary"] = time.time() + 9999
        fm.reset_all_providers()
        assert fm._skip_until == {}

    def test_empty_state_no_error(self):
        fm = _manager()
        fm.reset_all_providers()  # Should not raise


# ===========================================================================
# get_available_providers
# ===========================================================================

class TestGetAvailableProviders:
    def test_returns_list(self):
        fm = _manager()
        assert isinstance(fm.get_available_providers(), list)

    def test_configured_providers_included(self):
        fm = _manager()
        available = fm.get_available_providers()
        assert "primary" in available
        assert "secondary" in available

    def test_unconfigured_provider_excluded(self):
        providers = [_Stub("p1"), _Stub("p2", key="", configured=False)]
        fm = STTFailoverManager(providers)
        available = fm.get_available_providers()
        assert "p1" in available
        assert "p2" not in available

    def test_temporarily_disabled_provider_excluded(self):
        fm = _manager(max_fail=1, skip_sec=300)
        fm._record_failure("primary")  # Hits threshold → disabled
        available = fm.get_available_providers()
        assert "primary" not in available

    def test_re_enabled_provider_included(self):
        fm = _manager(max_fail=1, skip_sec=0.001)  # Minimal skip duration
        fm._record_failure("primary")
        time.sleep(0.01)  # Allow skip period to expire
        available = fm.get_available_providers()
        assert "primary" in available

    def test_empty_providers_list_returns_empty(self):
        fm = STTFailoverManager([])
        assert fm.get_available_providers() == []

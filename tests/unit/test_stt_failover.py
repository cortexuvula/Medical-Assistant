"""
Tests for src/stt_providers/failover.py
No network, no Tkinter, no real audio I/O.
"""
import sys
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from stt_providers.failover import STTFailoverManager


# ---------------------------------------------------------------------------
# Provider factory helper
# ---------------------------------------------------------------------------

def _make_provider(name, configured=True, transcribe_result="hello", fail=False):
    p = MagicMock()
    p.provider_name = name
    p.is_configured = configured
    if fail:
        p.transcribe_with_result.side_effect = Exception("provider error")
    else:
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.text = transcribe_result
        mock_result.metadata = {}
        p.transcribe_with_result.return_value = mock_result
    return p


# ---------------------------------------------------------------------------
# TestSTTFailoverManagerInit
# ---------------------------------------------------------------------------

class TestSTTFailoverManagerInit:
    def test_default_max_failures_is_3(self):
        manager = STTFailoverManager([])
        assert manager.max_failures_before_skip == 3

    def test_default_skip_duration_is_300(self):
        manager = STTFailoverManager([])
        assert manager.skip_duration_seconds == 300.0

    def test_providers_stored(self):
        p1 = _make_provider("p1")
        p2 = _make_provider("p2")
        manager = STTFailoverManager([p1, p2])
        assert manager.providers == [p1, p2]

    def test_empty_providers_list_stored(self):
        manager = STTFailoverManager([])
        assert manager.providers == []

    def test_failure_counts_empty_on_init(self):
        manager = STTFailoverManager([_make_provider("x")])
        assert manager._failure_counts == {}

    def test_skip_until_empty_on_init(self):
        manager = STTFailoverManager([_make_provider("x")])
        assert manager._skip_until == {}

    def test_last_successful_provider_none_on_init(self):
        manager = STTFailoverManager([_make_provider("x")])
        assert manager._last_successful_provider is None

    def test_custom_max_failures_stored(self):
        manager = STTFailoverManager([], max_failures_before_skip=5)
        assert manager.max_failures_before_skip == 5

    def test_custom_skip_duration_stored(self):
        manager = STTFailoverManager([], skip_duration_seconds=60.0)
        assert manager.skip_duration_seconds == 60.0

    def test_single_provider_stored(self):
        p = _make_provider("only")
        manager = STTFailoverManager([p])
        assert len(manager.providers) == 1


# ---------------------------------------------------------------------------
# TestRecordSuccess
# ---------------------------------------------------------------------------

class TestRecordSuccess:
    def setup_method(self):
        self.manager = STTFailoverManager([_make_provider("alpha")])

    def test_resets_failure_count_to_zero(self):
        self.manager._failure_counts["alpha"] = 5
        self.manager._record_success("alpha")
        assert self.manager._failure_counts["alpha"] == 0

    def test_clears_skip_until(self):
        self.manager._skip_until["alpha"] = time.time() + 9999
        self.manager._record_success("alpha")
        assert self.manager._skip_until["alpha"] == 0

    def test_sets_last_successful_provider(self):
        self.manager._record_success("alpha")
        assert self.manager._last_successful_provider == "alpha"

    def test_sets_last_successful_to_newest_provider(self):
        self.manager._record_success("alpha")
        self.manager._record_success("beta")
        assert self.manager._last_successful_provider == "beta"

    def test_records_success_for_previously_unseen_provider(self):
        self.manager._record_success("new_provider")
        assert self.manager._failure_counts["new_provider"] == 0

    def test_skip_until_set_to_zero_not_deleted(self):
        self.manager._skip_until["alpha"] = 99999
        self.manager._record_success("alpha")
        assert "alpha" in self.manager._skip_until
        assert self.manager._skip_until["alpha"] == 0


# ---------------------------------------------------------------------------
# TestRecordFailure
# ---------------------------------------------------------------------------

class TestRecordFailure:
    def setup_method(self):
        self.manager = STTFailoverManager(
            [_make_provider("alpha")],
            max_failures_before_skip=3,
            skip_duration_seconds=300.0
        )

    def test_increments_failure_count_from_zero(self):
        self.manager._record_failure("alpha")
        assert self.manager._failure_counts["alpha"] == 1

    def test_increments_failure_count_again(self):
        self.manager._failure_counts["alpha"] = 2
        self.manager._record_failure("alpha")
        assert self.manager._failure_counts["alpha"] == 3

    def test_before_max_failures_no_skip_set(self):
        # 2 failures < max_failures_before_skip=3
        self.manager._record_failure("alpha")
        self.manager._record_failure("alpha")
        skip_until = self.manager._skip_until.get("alpha", 0)
        assert skip_until == 0

    def test_at_max_failures_sets_skip_until_in_future(self):
        before = time.time()
        for _ in range(3):
            self.manager._record_failure("alpha")
        assert self.manager._skip_until.get("alpha", 0) > before

    def test_skip_until_approximately_skip_duration_seconds_ahead(self):
        for _ in range(3):
            self.manager._record_failure("alpha")
        skip_until = self.manager._skip_until["alpha"]
        # Should be ~300s ahead; allow 5s slop
        assert abs(skip_until - (time.time() + 300)) < 5

    def test_beyond_max_failures_still_skipped(self):
        for _ in range(5):
            self.manager._record_failure("alpha")
        assert self.manager._skip_until.get("alpha", 0) > time.time()

    def test_increments_for_unseen_provider(self):
        self.manager._record_failure("newone")
        assert self.manager._failure_counts["newone"] == 1

    def test_failure_count_one_below_max_no_skip(self):
        # max=3, so 2 failures should not set skip
        for _ in range(2):
            self.manager._record_failure("alpha")
        assert self.manager._skip_until.get("alpha", 0) == 0

    def test_failure_count_exactly_max_sets_skip(self):
        for _ in range(3):
            self.manager._record_failure("alpha")
        assert self.manager._skip_until.get("alpha", 0) > 0


# ---------------------------------------------------------------------------
# TestGetProviderStatus
# ---------------------------------------------------------------------------

class TestGetProviderStatus:
    def test_returns_dict_per_provider(self):
        p1 = _make_provider("p1")
        p2 = _make_provider("p2")
        manager = STTFailoverManager([p1, p2])
        status = manager.get_provider_status()
        assert "p1" in status
        assert "p2" in status

    def test_status_contains_configured_key(self):
        p = _make_provider("p1", configured=True)
        manager = STTFailoverManager([p])
        status = manager.get_provider_status()
        assert "configured" in status["p1"]

    def test_configured_true_reflected(self):
        p = _make_provider("p1", configured=True)
        manager = STTFailoverManager([p])
        assert manager.get_provider_status()["p1"]["configured"] is True

    def test_configured_false_reflected(self):
        p = _make_provider("p1", configured=False)
        manager = STTFailoverManager([p])
        assert manager.get_provider_status()["p1"]["configured"] is False

    def test_failure_count_zero_initially(self):
        p = _make_provider("p1")
        manager = STTFailoverManager([p])
        assert manager.get_provider_status()["p1"]["failure_count"] == 0

    def test_failure_count_reflects_recorded_failures(self):
        p = _make_provider("p1")
        manager = STTFailoverManager([p])
        manager._failure_counts["p1"] = 2
        assert manager.get_provider_status()["p1"]["failure_count"] == 2

    def test_temporarily_disabled_false_initially(self):
        p = _make_provider("p1")
        manager = STTFailoverManager([p])
        assert manager.get_provider_status()["p1"]["temporarily_disabled"] is False

    def test_temporarily_disabled_true_when_skip_in_future(self):
        p = _make_provider("p1")
        manager = STTFailoverManager([p])
        manager._skip_until["p1"] = time.time() + 9999
        assert manager.get_provider_status()["p1"]["temporarily_disabled"] is True

    def test_temporarily_disabled_false_after_skip_expired(self):
        p = _make_provider("p1")
        manager = STTFailoverManager([p])
        manager._skip_until["p1"] = time.time() - 1  # past
        assert manager.get_provider_status()["p1"]["temporarily_disabled"] is False

    def test_status_has_last_successful_key(self):
        p = _make_provider("p1")
        manager = STTFailoverManager([p])
        status = manager.get_provider_status()
        assert "last_successful" in status["p1"]

    def test_last_successful_false_when_different_provider_succeeded(self):
        p1 = _make_provider("p1")
        p2 = _make_provider("p2")
        manager = STTFailoverManager([p1, p2])
        manager._last_successful_provider = "p2"
        status = manager.get_provider_status()
        assert status["p1"]["last_successful"] is False
        assert status["p2"]["last_successful"] is True

    def test_empty_providers_returns_empty_dict(self):
        manager = STTFailoverManager([])
        assert manager.get_provider_status() == {}


# ---------------------------------------------------------------------------
# TestResetProvider
# ---------------------------------------------------------------------------

class TestResetProvider:
    def test_resets_failure_count_to_zero(self):
        manager = STTFailoverManager([])
        manager._failure_counts["alpha"] = 7
        manager.reset_provider("alpha")
        assert manager._failure_counts["alpha"] == 0

    def test_resets_skip_until_to_zero(self):
        manager = STTFailoverManager([])
        manager._skip_until["alpha"] = time.time() + 9999
        manager.reset_provider("alpha")
        assert manager._skip_until["alpha"] == 0

    def test_reset_unseen_provider_sets_zeros(self):
        manager = STTFailoverManager([])
        manager.reset_provider("brand_new")
        assert manager._failure_counts["brand_new"] == 0
        assert manager._skip_until["brand_new"] == 0

    def test_reset_one_provider_does_not_affect_another(self):
        manager = STTFailoverManager([])
        manager._failure_counts["alpha"] = 3
        manager._failure_counts["beta"] = 5
        manager.reset_provider("alpha")
        assert manager._failure_counts["beta"] == 5

    def test_reset_allows_provider_to_be_used_again(self):
        p = _make_provider("alpha")
        manager = STTFailoverManager([p], max_failures_before_skip=1)
        manager._failure_counts["alpha"] = 5
        manager._skip_until["alpha"] = time.time() + 9999
        manager.reset_provider("alpha")
        assert manager.get_available_providers() == ["alpha"]


# ---------------------------------------------------------------------------
# TestResetAllProviders
# ---------------------------------------------------------------------------

class TestResetAllProviders:
    def test_clears_all_failure_counts(self):
        manager = STTFailoverManager([])
        manager._failure_counts = {"a": 3, "b": 7}
        manager.reset_all_providers()
        assert manager._failure_counts == {}

    def test_clears_all_skip_untils(self):
        manager = STTFailoverManager([])
        manager._skip_until = {"a": 99999, "b": 88888}
        manager.reset_all_providers()
        assert manager._skip_until == {}

    def test_already_empty_is_fine(self):
        manager = STTFailoverManager([])
        manager.reset_all_providers()  # Should not raise
        assert manager._failure_counts == {}
        assert manager._skip_until == {}

    def test_all_providers_become_available_after_reset(self):
        p1 = _make_provider("p1")
        p2 = _make_provider("p2")
        manager = STTFailoverManager([p1, p2])
        manager._skip_until["p1"] = time.time() + 9999
        manager._skip_until["p2"] = time.time() + 9999
        manager.reset_all_providers()
        available = manager.get_available_providers()
        assert "p1" in available
        assert "p2" in available


# ---------------------------------------------------------------------------
# TestGetAvailableProviders
# ---------------------------------------------------------------------------

class TestGetAvailableProviders:
    def test_configured_non_skipped_provider_returned(self):
        p = _make_provider("p1", configured=True)
        manager = STTFailoverManager([p])
        assert "p1" in manager.get_available_providers()

    def test_unconfigured_provider_excluded(self):
        p = _make_provider("p1", configured=False)
        manager = STTFailoverManager([p])
        assert "p1" not in manager.get_available_providers()

    def test_skipped_provider_excluded(self):
        p = _make_provider("p1", configured=True)
        manager = STTFailoverManager([p])
        manager._skip_until["p1"] = time.time() + 9999
        assert "p1" not in manager.get_available_providers()

    def test_expired_skip_provider_included(self):
        p = _make_provider("p1", configured=True)
        manager = STTFailoverManager([p])
        manager._skip_until["p1"] = time.time() - 1  # already past
        assert "p1" in manager.get_available_providers()

    def test_empty_providers_returns_empty_list(self):
        manager = STTFailoverManager([])
        assert manager.get_available_providers() == []

    def test_mixed_providers_returns_only_valid(self):
        p1 = _make_provider("p1", configured=True)
        p2 = _make_provider("p2", configured=False)
        p3 = _make_provider("p3", configured=True)
        manager = STTFailoverManager([p1, p2, p3])
        manager._skip_until["p3"] = time.time() + 9999
        available = manager.get_available_providers()
        assert available == ["p1"]

    def test_returns_list_type(self):
        manager = STTFailoverManager([])
        assert isinstance(manager.get_available_providers(), list)

    def test_order_preserved(self):
        p1 = _make_provider("p1")
        p2 = _make_provider("p2")
        p3 = _make_provider("p3")
        manager = STTFailoverManager([p1, p2, p3])
        available = manager.get_available_providers()
        assert available == ["p1", "p2", "p3"]


# ---------------------------------------------------------------------------
# TestTranscribeWithResult
# ---------------------------------------------------------------------------

class TestTranscribeWithResult:
    def test_calls_first_provider(self):
        p = _make_provider("p1", transcribe_result="hello")
        manager = STTFailoverManager([p])
        segment = MagicMock()
        manager.transcribe_with_result(segment)
        p.transcribe_with_result.assert_called_once_with(segment)

    def test_returns_successful_result(self):
        p = _make_provider("p1", transcribe_result="world")
        manager = STTFailoverManager([p])
        result = manager.transcribe_with_result(MagicMock())
        assert result.success is True
        assert result.text == "world"

    def test_skips_unconfigured_provider(self):
        p_bad = _make_provider("bad", configured=False)
        p_good = _make_provider("good", transcribe_result="yes")
        manager = STTFailoverManager([p_bad, p_good])
        result = manager.transcribe_with_result(MagicMock())
        p_bad.transcribe_with_result.assert_not_called()
        assert result.success is True

    def test_skips_temporarily_disabled_provider(self):
        p1 = _make_provider("p1", transcribe_result="skip me")
        p2 = _make_provider("p2", transcribe_result="use me")
        manager = STTFailoverManager([p1, p2])
        manager._skip_until["p1"] = time.time() + 9999
        result = manager.transcribe_with_result(MagicMock())
        p1.transcribe_with_result.assert_not_called()
        assert result.text == "use me"

    def test_records_success_after_successful_transcription(self):
        p = _make_provider("p1", transcribe_result="success")
        manager = STTFailoverManager([p])
        manager.transcribe_with_result(MagicMock())
        assert manager._last_successful_provider == "p1"
        assert manager._failure_counts.get("p1", 0) == 0

    def test_records_failure_after_exception(self):
        p = _make_provider("p1", fail=True)
        manager = STTFailoverManager([p])
        manager.transcribe_with_result(MagicMock())
        assert manager._failure_counts.get("p1", 0) == 1

    def test_falls_over_to_second_provider_after_first_fails(self):
        p1 = _make_provider("p1", fail=True)
        p2 = _make_provider("p2", transcribe_result="fallback")
        manager = STTFailoverManager([p1, p2])
        result = manager.transcribe_with_result(MagicMock())
        assert result.success is True
        assert result.text == "fallback"

    def test_all_fail_returns_failure_result(self):
        p1 = _make_provider("p1", fail=True)
        p2 = _make_provider("p2", fail=True)
        manager = STTFailoverManager([p1, p2])
        result = manager.transcribe_with_result(MagicMock())
        assert result.success is False

    def test_all_fail_result_has_error_message(self):
        p = _make_provider("p1", fail=True)
        manager = STTFailoverManager([p])
        result = manager.transcribe_with_result(MagicMock())
        assert result.error is not None
        assert len(result.error) > 0

    def test_provider_metadata_set_on_success(self):
        p = _make_provider("p1", transcribe_result="text")
        manager = STTFailoverManager([p])
        result = manager.transcribe_with_result(MagicMock())
        assert result.metadata.get("provider") == "p1"

    def test_failover_attempts_in_metadata(self):
        p = _make_provider("p1", transcribe_result="text")
        manager = STTFailoverManager([p])
        result = manager.transcribe_with_result(MagicMock())
        assert result.metadata.get("failover_attempts") == 1

    def test_all_unconfigured_returns_failure(self):
        p1 = _make_provider("p1", configured=False)
        p2 = _make_provider("p2", configured=False)
        manager = STTFailoverManager([p1, p2])
        result = manager.transcribe_with_result(MagicMock())
        assert result.success is False

    def test_records_failure_when_result_not_success(self):
        p = _make_provider("p1")
        failing_result = MagicMock()
        failing_result.success = False
        failing_result.text = ""
        failing_result.error = "no audio"
        p.transcribe_with_result.return_value = failing_result
        manager = STTFailoverManager([p])
        manager.transcribe_with_result(MagicMock())
        assert manager._failure_counts.get("p1", 0) == 1

    def test_second_provider_tried_after_first_returns_empty(self):
        p1 = _make_provider("p1")
        empty_result = MagicMock()
        empty_result.success = True
        empty_result.text = ""
        empty_result.error = None
        empty_result.metadata = {}
        p1.transcribe_with_result.return_value = empty_result

        p2 = _make_provider("p2", transcribe_result="non-empty")
        manager = STTFailoverManager([p1, p2])
        result = manager.transcribe_with_result(MagicMock())
        p2.transcribe_with_result.assert_called_once()
        assert result.text == "non-empty"

    def test_empty_providers_list_returns_failure(self):
        manager = STTFailoverManager([])
        result = manager.transcribe_with_result(MagicMock())
        assert result.success is False


# ---------------------------------------------------------------------------
# TestTranscribe (thin wrapper)
# ---------------------------------------------------------------------------

class TestTranscribe:
    def test_returns_text_on_success(self):
        p = _make_provider("p1", transcribe_result="hello world")
        manager = STTFailoverManager([p])
        text = manager.transcribe(MagicMock())
        assert text == "hello world"

    def test_returns_empty_string_on_all_fail(self):
        p = _make_provider("p1", fail=True)
        manager = STTFailoverManager([p])
        text = manager.transcribe(MagicMock())
        assert text == ""

    def test_returns_string_type(self):
        p = _make_provider("p1", transcribe_result="some text")
        manager = STTFailoverManager([p])
        result = manager.transcribe(MagicMock())
        assert isinstance(result, str)

    def test_returns_empty_string_for_empty_providers(self):
        manager = STTFailoverManager([])
        assert manager.transcribe(MagicMock()) == ""

    def test_falls_over_and_returns_second_provider_text(self):
        p1 = _make_provider("p1", fail=True)
        p2 = _make_provider("p2", transcribe_result="backup text")
        manager = STTFailoverManager([p1, p2])
        assert manager.transcribe(MagicMock()) == "backup text"

    def test_delegates_to_transcribe_with_result(self):
        p = _make_provider("p1", transcribe_result="delegated")
        manager = STTFailoverManager([p])
        with patch.object(
            manager,
            "transcribe_with_result",
            wraps=manager.transcribe_with_result
        ) as spy:
            manager.transcribe(MagicMock())
        spy.assert_called_once()

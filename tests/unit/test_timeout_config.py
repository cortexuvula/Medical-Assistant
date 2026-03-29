"""
Tests for src/utils/timeout_config.py

Covers TimeoutConfig singleton, DEFAULT_TIMEOUTS, DEFAULT_CONNECT_TIMEOUT,
get_timeout, get_timeout_tuple, update_timeout, update_connect_timeout,
connect_timeout property, get_all_timeouts, reset_to_defaults, and the
module-level convenience functions get_timeout_config / get_timeout /
get_timeout_tuple.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))


# ---------------------------------------------------------------------------
# Singleton reset helpers
# ---------------------------------------------------------------------------

def _reset_timeout_config():
    """Reset all singleton/module-level state so each test gets a fresh instance."""
    import utils.timeout_config as tc_mod
    tc_mod.TimeoutConfig._instance = None
    tc_mod._timeout_config = None


@pytest.fixture(autouse=True)
def reset_timeout_singleton():
    """Reset TimeoutConfig singleton between tests."""
    _reset_timeout_config()
    yield
    _reset_timeout_config()


@pytest.fixture
def config():
    """Return a fresh TimeoutConfig with settings_manager stubbed out."""
    with patch("utils.timeout_config.settings_manager") as mock_sm:
        mock_sm.get.return_value = {}
        from utils.timeout_config import TimeoutConfig
        return TimeoutConfig()


# ===========================================================================
# DEFAULT_TIMEOUTS constant
# ===========================================================================

class TestDefaultTimeoutsConstant:
    def test_is_dict(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert isinstance(DEFAULT_TIMEOUTS, dict)

    def test_not_empty(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert len(DEFAULT_TIMEOUTS) > 0

    def test_openai_key_exists(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert "openai" in DEFAULT_TIMEOUTS

    def test_anthropic_key_exists(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert "anthropic" in DEFAULT_TIMEOUTS

    def test_ollama_key_exists(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert "ollama" in DEFAULT_TIMEOUTS

    def test_default_key_exists(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert "default" in DEFAULT_TIMEOUTS

    def test_openai_value_is_float(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert isinstance(DEFAULT_TIMEOUTS["openai"], float)

    def test_anthropic_value_is_float(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert isinstance(DEFAULT_TIMEOUTS["anthropic"], float)

    def test_ollama_value_is_float(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert isinstance(DEFAULT_TIMEOUTS["ollama"], float)

    def test_default_value_is_float(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert isinstance(DEFAULT_TIMEOUTS["default"], float)

    def test_all_values_positive(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        for key, val in DEFAULT_TIMEOUTS.items():
            assert val > 0, f"Timeout for '{key}' must be positive, got {val}"

    def test_default_value_is_60(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert DEFAULT_TIMEOUTS["default"] == 60.0

    def test_openai_value_positive(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert DEFAULT_TIMEOUTS["openai"] > 0

    def test_anthropic_longer_than_openai(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        # Anthropic is documented as slower
        assert DEFAULT_TIMEOUTS["anthropic"] >= DEFAULT_TIMEOUTS["openai"]

    def test_ollama_longer_than_anthropic(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert DEFAULT_TIMEOUTS["ollama"] >= DEFAULT_TIMEOUTS["anthropic"]

    def test_short_key_less_than_default(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert DEFAULT_TIMEOUTS["short"] < DEFAULT_TIMEOUTS["default"]

    def test_long_key_greater_than_default(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert DEFAULT_TIMEOUTS["long"] > DEFAULT_TIMEOUTS["default"]

    def test_mutating_copy_does_not_change_original(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        original_openai = DEFAULT_TIMEOUTS["openai"]
        copy = dict(DEFAULT_TIMEOUTS)
        copy["openai"] = 0.001
        assert DEFAULT_TIMEOUTS["openai"] == original_openai


# ===========================================================================
# DEFAULT_CONNECT_TIMEOUT constant
# ===========================================================================

class TestDefaultConnectTimeout:
    def test_is_float(self):
        from utils.timeout_config import DEFAULT_CONNECT_TIMEOUT
        assert isinstance(DEFAULT_CONNECT_TIMEOUT, float)

    def test_is_10(self):
        from utils.timeout_config import DEFAULT_CONNECT_TIMEOUT
        assert DEFAULT_CONNECT_TIMEOUT == 10.0

    def test_is_positive(self):
        from utils.timeout_config import DEFAULT_CONNECT_TIMEOUT
        assert DEFAULT_CONNECT_TIMEOUT > 0


# ===========================================================================
# TimeoutConfig initialisation
# ===========================================================================

class TestTimeoutConfigInit:
    def test_instance_created(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import TimeoutConfig
            cfg = TimeoutConfig()
            assert cfg is not None

    def test_starts_with_default_timeouts(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import TimeoutConfig, DEFAULT_TIMEOUTS
            cfg = TimeoutConfig()
            assert cfg.get_timeout("openai") == DEFAULT_TIMEOUTS["openai"]

    def test_starts_with_default_connect_timeout(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import TimeoutConfig, DEFAULT_CONNECT_TIMEOUT
            cfg = TimeoutConfig()
            assert cfg.connect_timeout == DEFAULT_CONNECT_TIMEOUT

    def test_initialized_flag_set(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import TimeoutConfig
            cfg = TimeoutConfig()
            assert cfg._initialized is True


# ===========================================================================
# Singleton behaviour
# ===========================================================================

class TestSingleton:
    def test_two_calls_return_same_object(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import TimeoutConfig
            a = TimeoutConfig()
            b = TimeoutConfig()
            assert a is b

    def test_second_call_does_not_re_initialise(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import TimeoutConfig
            a = TimeoutConfig()
            a.update_timeout("openai", 12345.0)
            # Second construction must not reset the value
            b = TimeoutConfig()
            assert b.get_timeout("openai") == 12345.0

    def test_get_timeout_config_returns_instance(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import get_timeout_config, TimeoutConfig
            tc = get_timeout_config()
            assert isinstance(tc, TimeoutConfig)

    def test_get_timeout_config_returns_same_object(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import get_timeout_config
            tc1 = get_timeout_config()
            tc2 = get_timeout_config()
            assert tc1 is tc2


# ===========================================================================
# get_timeout
# ===========================================================================

class TestGetTimeout:
    def test_known_service_returns_float(self, config):
        val = config.get_timeout("openai")
        assert isinstance(val, float)

    def test_known_service_returns_positive(self, config):
        val = config.get_timeout("openai")
        assert val > 0

    def test_anthropic_returns_correct_value(self, config):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert config.get_timeout("anthropic") == DEFAULT_TIMEOUTS["anthropic"]

    def test_ollama_returns_correct_value(self, config):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert config.get_timeout("ollama") == DEFAULT_TIMEOUTS["ollama"]

    def test_unknown_service_returns_default_60(self, config):
        val = config.get_timeout("nonexistent_service_xyz")
        assert val == 60.0

    def test_unknown_service_with_custom_default(self, config):
        val = config.get_timeout("nonexistent_service_xyz", default=99.0)
        assert val == 99.0

    def test_custom_default_not_used_for_known_service(self, config):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        val = config.get_timeout("openai", default=9999.0)
        assert val == DEFAULT_TIMEOUTS["openai"]

    def test_short_timeout_is_small(self, config):
        assert config.get_timeout("short") < 60.0

    def test_long_timeout_is_large(self, config):
        assert config.get_timeout("long") > 60.0

    def test_default_zero_custom_default_honored(self, config):
        val = config.get_timeout("__missing__", default=0.0)
        assert val == 0.0


# ===========================================================================
# get_timeout_tuple
# ===========================================================================

class TestGetTimeoutTuple:
    def test_returns_tuple(self, config):
        result = config.get_timeout_tuple("openai")
        assert isinstance(result, tuple)

    def test_tuple_has_two_elements(self, config):
        result = config.get_timeout_tuple("openai")
        assert len(result) == 2

    def test_first_element_is_connect_timeout(self, config):
        from utils.timeout_config import DEFAULT_CONNECT_TIMEOUT
        connect, _ = config.get_timeout_tuple("openai")
        assert connect == DEFAULT_CONNECT_TIMEOUT

    def test_second_element_is_read_timeout(self, config):
        _, read = config.get_timeout_tuple("openai")
        assert read == config.get_timeout("openai")

    def test_both_elements_are_floats(self, config):
        connect, read = config.get_timeout_tuple("anthropic")
        assert isinstance(connect, float)
        assert isinstance(read, float)

    def test_unknown_service_uses_default_read(self, config):
        _, read = config.get_timeout_tuple("__no_such_service__")
        assert read == 60.0

    def test_reflects_updated_connect_timeout(self, config):
        config.update_connect_timeout(7.5)
        connect, _ = config.get_timeout_tuple("openai")
        assert connect == 7.5


# ===========================================================================
# update_timeout
# ===========================================================================

class TestUpdateTimeout:
    def test_update_existing_service(self, config):
        config.update_timeout("openai", 999.0)
        assert config.get_timeout("openai") == 999.0

    def test_update_new_service(self, config):
        config.update_timeout("my_custom_service", 42.0)
        assert config.get_timeout("my_custom_service") == 42.0

    def test_updated_value_appears_in_get_all(self, config):
        config.update_timeout("openai", 888.0)
        assert config.get_all_timeouts()["openai"] == 888.0

    def test_zero_rejected(self, config):
        original = config.get_timeout("openai")
        config.update_timeout("openai", 0)
        assert config.get_timeout("openai") == original

    def test_negative_rejected(self, config):
        original = config.get_timeout("openai")
        config.update_timeout("openai", -5.0)
        assert config.get_timeout("openai") == original

    def test_very_small_positive_accepted(self, config):
        config.update_timeout("openai", 0.001)
        assert config.get_timeout("openai") == 0.001

    def test_large_value_accepted(self, config):
        config.update_timeout("openai", 3600.0)
        assert config.get_timeout("openai") == 3600.0

    def test_zero_does_not_crash(self, config):
        try:
            config.update_timeout("openai", 0)
        except Exception as exc:
            pytest.fail(f"update_timeout(0) raised: {exc}")

    def test_negative_does_not_crash(self, config):
        try:
            config.update_timeout("openai", -100.0)
        except Exception as exc:
            pytest.fail(f"update_timeout(-100) raised: {exc}")


# ===========================================================================
# update_connect_timeout
# ===========================================================================

class TestUpdateConnectTimeout:
    def test_updates_connect_timeout(self, config):
        config.update_connect_timeout(99.0)
        assert config.connect_timeout == 99.0

    def test_propagates_to_tuple(self, config):
        config.update_connect_timeout(7.5)
        connect, _ = config.get_timeout_tuple("openai")
        assert connect == 7.5

    def test_zero_rejected(self, config):
        original = config.connect_timeout
        config.update_connect_timeout(0)
        assert config.connect_timeout == original

    def test_negative_rejected(self, config):
        original = config.connect_timeout
        config.update_connect_timeout(-1.0)
        assert config.connect_timeout == original

    def test_zero_does_not_crash(self, config):
        try:
            config.update_connect_timeout(0)
        except Exception as exc:
            pytest.fail(f"update_connect_timeout(0) raised: {exc}")

    def test_small_positive_accepted(self, config):
        config.update_connect_timeout(0.5)
        assert config.connect_timeout == 0.5


# ===========================================================================
# connect_timeout property
# ===========================================================================

class TestConnectTimeoutProperty:
    def test_initial_value_is_default(self, config):
        from utils.timeout_config import DEFAULT_CONNECT_TIMEOUT
        assert config.connect_timeout == DEFAULT_CONNECT_TIMEOUT

    def test_returns_float(self, config):
        assert isinstance(config.connect_timeout, float)

    def test_reflects_update(self, config):
        config.update_connect_timeout(5.5)
        assert config.connect_timeout == 5.5


# ===========================================================================
# get_all_timeouts
# ===========================================================================

class TestGetAllTimeouts:
    def test_returns_dict(self, config):
        result = config.get_all_timeouts()
        assert isinstance(result, dict)

    def test_not_empty(self, config):
        assert len(config.get_all_timeouts()) > 0

    def test_contains_openai(self, config):
        assert "openai" in config.get_all_timeouts()

    def test_contains_default(self, config):
        assert "default" in config.get_all_timeouts()

    def test_returns_copy(self, config):
        all1 = config.get_all_timeouts()
        all2 = config.get_all_timeouts()
        assert all1 is not all2

    def test_copies_are_equal(self, config):
        assert config.get_all_timeouts() == config.get_all_timeouts()

    def test_mutation_does_not_affect_internal_state(self, config):
        original_val = config.get_timeout("openai")
        returned = config.get_all_timeouts()
        returned["openai"] = 0.001
        assert config.get_timeout("openai") == original_val

    def test_reflects_updates(self, config):
        config.update_timeout("openai", 777.0)
        assert config.get_all_timeouts()["openai"] == 777.0


# ===========================================================================
# reset_to_defaults
# ===========================================================================

class TestResetToDefaults:
    def test_restores_modified_read_timeout(self, config):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        config.update_timeout("openai", 9999.0)
        config.reset_to_defaults()
        assert config.get_timeout("openai") == DEFAULT_TIMEOUTS["openai"]

    def test_restores_connect_timeout(self, config):
        from utils.timeout_config import DEFAULT_CONNECT_TIMEOUT
        config.update_connect_timeout(999.0)
        config.reset_to_defaults()
        assert config.connect_timeout == DEFAULT_CONNECT_TIMEOUT

    def test_all_timeouts_equal_defaults_after_reset(self, config):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        config.update_timeout("openai", 1.0)
        config.update_timeout("anthropic", 2.0)
        config.reset_to_defaults()
        assert config.get_all_timeouts() == DEFAULT_TIMEOUTS

    def test_custom_service_removed_after_reset(self, config):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        config.update_timeout("__custom_svc__", 55.0)
        config.reset_to_defaults()
        # After reset only DEFAULT_TIMEOUTS keys should remain
        assert "__custom_svc__" not in config.get_all_timeouts()

    def test_reset_does_not_crash(self, config):
        try:
            config.reset_to_defaults()
        except Exception as exc:
            pytest.fail(f"reset_to_defaults raised: {exc}")


# ===========================================================================
# Settings integration (_load_from_settings)
# ===========================================================================

class TestLoadFromSettings:
    def test_settings_override_read_timeout(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {"openai": 999.0}
            _reset_timeout_config()
            from utils.timeout_config import TimeoutConfig
            cfg = TimeoutConfig()
            assert cfg.get_timeout("openai") == 999.0

    def test_settings_override_connect_timeout(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {"connect": 3.0}
            _reset_timeout_config()
            from utils.timeout_config import TimeoutConfig
            cfg = TimeoutConfig()
            assert cfg.connect_timeout == 3.0

    def test_settings_error_falls_back_to_defaults(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.side_effect = Exception("settings unavailable")
            _reset_timeout_config()
            from utils.timeout_config import TimeoutConfig, DEFAULT_TIMEOUTS
            cfg = TimeoutConfig()
            assert cfg.get_timeout("openai") == DEFAULT_TIMEOUTS["openai"]

    def test_negative_setting_ignored(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {"openai": -5}
            _reset_timeout_config()
            from utils.timeout_config import TimeoutConfig, DEFAULT_TIMEOUTS
            cfg = TimeoutConfig()
            assert cfg.get_timeout("openai") == DEFAULT_TIMEOUTS["openai"]

    def test_zero_setting_ignored(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {"openai": 0}
            _reset_timeout_config()
            from utils.timeout_config import TimeoutConfig, DEFAULT_TIMEOUTS
            cfg = TimeoutConfig()
            assert cfg.get_timeout("openai") == DEFAULT_TIMEOUTS["openai"]

    def test_new_service_loaded_from_settings(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {"custom_api": 45.0}
            _reset_timeout_config()
            from utils.timeout_config import TimeoutConfig
            cfg = TimeoutConfig()
            assert cfg.get_timeout("custom_api") == 45.0


# ===========================================================================
# Module-level convenience functions
# ===========================================================================

class TestModuleFunctions:
    def test_get_timeout_function_returns_float(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import get_timeout
            val = get_timeout("openai")
            assert isinstance(val, float)

    def test_get_timeout_function_known_service(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import get_timeout
            val = get_timeout("openai")
            assert val > 0

    def test_get_timeout_function_unknown_returns_default(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import get_timeout
            val = get_timeout("__no_such_service__")
            assert val == 60.0

    def test_get_timeout_function_custom_default(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import get_timeout
            val = get_timeout("__no_such_service__", default=77.0)
            assert val == 77.0

    def test_get_timeout_tuple_function_returns_tuple(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import get_timeout_tuple
            result = get_timeout_tuple("openai")
            assert isinstance(result, tuple)

    def test_get_timeout_tuple_function_length_two(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import get_timeout_tuple
            result = get_timeout_tuple("openai")
            assert len(result) == 2

    def test_get_timeout_tuple_function_first_is_connect(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import get_timeout_tuple, DEFAULT_CONNECT_TIMEOUT
            connect, _ = get_timeout_tuple("openai")
            assert connect == DEFAULT_CONNECT_TIMEOUT

    def test_get_timeout_config_returns_timeout_config(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import get_timeout_config, TimeoutConfig
            tc = get_timeout_config()
            assert isinstance(tc, TimeoutConfig)

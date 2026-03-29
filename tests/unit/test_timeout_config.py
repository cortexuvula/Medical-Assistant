"""
Tests for src/utils/timeout_config.py

Covers TimeoutConfig singleton, get_timeout, update_timeout, reset, and
module-level convenience functions.
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


# ---------------------------------------------------------------------------
# Helpers — reset singleton between tests
# ---------------------------------------------------------------------------

def _reset_timeout_config():
    """Reset the TimeoutConfig singleton so each test gets a fresh instance."""
    import utils.timeout_config as tc_mod
    tc_mod.TimeoutConfig._instance = None
    tc_mod._timeout_config = None


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before and after every test."""
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
    def test_defaults_dict_not_empty(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert len(DEFAULT_TIMEOUTS) > 0

    def test_default_key_exists(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert "default" in DEFAULT_TIMEOUTS
        assert DEFAULT_TIMEOUTS["default"] > 0

    def test_openai_default(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert DEFAULT_TIMEOUTS.get("openai", 0) > 0

    def test_anthropic_default(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert DEFAULT_TIMEOUTS.get("anthropic", 0) > 0

    def test_all_values_positive(self):
        from utils.timeout_config import DEFAULT_TIMEOUTS
        for key, val in DEFAULT_TIMEOUTS.items():
            assert val > 0, f"Timeout for {key} must be positive"

    def test_connect_timeout_constant(self):
        from utils.timeout_config import DEFAULT_CONNECT_TIMEOUT
        assert DEFAULT_CONNECT_TIMEOUT > 0


# ===========================================================================
# TimeoutConfig singleton
# ===========================================================================

class TestTimeoutConfigSingleton:
    def test_same_instance(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import TimeoutConfig
            a = TimeoutConfig()
            b = TimeoutConfig()
            assert a is b

    def test_get_timeout_config_returns_same(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import get_timeout_config, TimeoutConfig
            tc = get_timeout_config()
            assert isinstance(tc, TimeoutConfig)
            assert get_timeout_config() is tc


# ===========================================================================
# get_timeout
# ===========================================================================

class TestGetTimeout:
    def test_known_service(self, config):
        val = config.get_timeout("openai")
        assert val > 0

    def test_unknown_service_returns_default(self, config):
        val = config.get_timeout("nonexistent_service_xyz")
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert val == DEFAULT_TIMEOUTS["default"]

    def test_unknown_service_with_custom_default(self, config):
        val = config.get_timeout("nonexistent_service_xyz", default=99.0)
        assert val == 99.0

    def test_explicit_default_overrides_dict_default(self, config):
        val = config.get_timeout("neo4j", default=1234.5)
        # neo4j is in DEFAULT_TIMEOUTS so it should return that value, not 1234.5
        assert val != 1234.5

    def test_short_timeout(self, config):
        val = config.get_timeout("short")
        assert val < 60

    def test_long_timeout(self, config):
        val = config.get_timeout("long")
        assert val >= 60


# ===========================================================================
# get_timeout_tuple
# ===========================================================================

class TestGetTimeoutTuple:
    def test_returns_tuple(self, config):
        result = config.get_timeout_tuple("openai")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_first_element_is_connect_timeout(self, config):
        from utils.timeout_config import DEFAULT_CONNECT_TIMEOUT
        connect, read = config.get_timeout_tuple("openai")
        assert connect == DEFAULT_CONNECT_TIMEOUT

    def test_second_element_is_read_timeout(self, config):
        _, read = config.get_timeout_tuple("openai")
        assert read == config.get_timeout("openai")


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

    def test_update_zero_is_rejected(self, config):
        original = config.get_timeout("openai")
        config.update_timeout("openai", 0)
        assert config.get_timeout("openai") == original

    def test_update_negative_is_rejected(self, config):
        original = config.get_timeout("openai")
        config.update_timeout("openai", -5.0)
        assert config.get_timeout("openai") == original


# ===========================================================================
# update_connect_timeout
# ===========================================================================

class TestUpdateConnectTimeout:
    def test_update_connect_timeout(self, config):
        config.update_connect_timeout(99.0)
        assert config.connect_timeout == 99.0

    def test_connect_timeout_propagates_to_tuple(self, config):
        config.update_connect_timeout(7.5)
        connect, _ = config.get_timeout_tuple("openai")
        assert connect == 7.5

    def test_zero_connect_timeout_rejected(self, config):
        original = config.connect_timeout
        config.update_connect_timeout(0)
        assert config.connect_timeout == original

    def test_negative_connect_timeout_rejected(self, config):
        original = config.connect_timeout
        config.update_connect_timeout(-1.0)
        assert config.connect_timeout == original


# ===========================================================================
# reset_to_defaults
# ===========================================================================

class TestResetToDefaults:
    def test_reset_restores_modified_values(self, config):
        config.update_timeout("openai", 9999.0)
        config.reset_to_defaults()
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert config.get_timeout("openai") == DEFAULT_TIMEOUTS["openai"]

    def test_reset_restores_connect_timeout(self, config):
        config.update_connect_timeout(999.0)
        config.reset_to_defaults()
        from utils.timeout_config import DEFAULT_CONNECT_TIMEOUT
        assert config.connect_timeout == DEFAULT_CONNECT_TIMEOUT

    def test_get_all_timeouts_after_reset(self, config):
        config.update_timeout("openai", 1.0)
        config.reset_to_defaults()
        all_timeouts = config.get_all_timeouts()
        from utils.timeout_config import DEFAULT_TIMEOUTS
        assert all_timeouts == DEFAULT_TIMEOUTS


# ===========================================================================
# get_all_timeouts
# ===========================================================================

class TestGetAllTimeouts:
    def test_returns_copy(self, config):
        all1 = config.get_all_timeouts()
        all2 = config.get_all_timeouts()
        assert all1 is not all2
        assert all1 == all2

    def test_mutating_returned_dict_does_not_affect_config(self, config):
        all_timeouts = config.get_all_timeouts()
        original = config.get_timeout("openai")
        all_timeouts["openai"] = 0.001
        assert config.get_timeout("openai") == original


# ===========================================================================
# Settings integration (load_from_settings)
# ===========================================================================

class TestLoadFromSettings:
    def test_settings_override_applied(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {"openai": 999.0}
            _reset_timeout_config()
            from utils.timeout_config import TimeoutConfig
            cfg = TimeoutConfig()
            assert cfg.get_timeout("openai") == 999.0

    def test_settings_connect_timeout_override(self):
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

    def test_invalid_timeout_value_ignored(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            # Negative timeout should not be loaded
            mock_sm.get.return_value = {"openai": -5}
            _reset_timeout_config()
            from utils.timeout_config import TimeoutConfig, DEFAULT_TIMEOUTS
            cfg = TimeoutConfig()
            assert cfg.get_timeout("openai") == DEFAULT_TIMEOUTS["openai"]

    def test_zero_timeout_value_ignored(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {"openai": 0}
            _reset_timeout_config()
            from utils.timeout_config import TimeoutConfig, DEFAULT_TIMEOUTS
            cfg = TimeoutConfig()
            assert cfg.get_timeout("openai") == DEFAULT_TIMEOUTS["openai"]


# ===========================================================================
# Module-level convenience functions
# ===========================================================================

class TestModuleFunctions:
    def test_get_timeout_function(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import get_timeout
            val = get_timeout("openai")
            assert val > 0

    def test_get_timeout_with_default(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import get_timeout
            val = get_timeout("__no_such_service__", default=77.0)
            assert val == 77.0

    def test_get_timeout_tuple_function(self):
        with patch("utils.timeout_config.settings_manager") as mock_sm:
            mock_sm.get.return_value = {}
            from utils.timeout_config import get_timeout_tuple
            result = get_timeout_tuple("openai")
            assert isinstance(result, tuple)
            assert len(result) == 2

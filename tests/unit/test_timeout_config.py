"""Tests for TimeoutConfig singleton and module-level helpers."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

import pytest
from unittest.mock import patch, MagicMock

import utils.timeout_config as tc_module
from utils.timeout_config import (
    TimeoutConfig,
    get_timeout_config,
    get_timeout,
    get_timeout_tuple,
    DEFAULT_TIMEOUTS,
    DEFAULT_CONNECT_TIMEOUT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_and_mock():
    """Reset singleton state and patch settings_manager before every test."""
    # Clear singletons before the test
    TimeoutConfig._instance = None
    tc_module._timeout_config = None
    with patch('utils.timeout_config.settings_manager') as mock_sm:
        mock_sm.get.return_value = {}
        yield mock_sm
    # Clear singletons after the test to avoid cross-test contamination
    TimeoutConfig._instance = None
    tc_module._timeout_config = None


# ---------------------------------------------------------------------------
# TestTimeoutConfigDefaults
# ---------------------------------------------------------------------------

class TestTimeoutConfigDefaults:
    """Tests for default constant values and instance creation."""

    def test_instance_created(self):
        config = TimeoutConfig()
        assert config is not None

    def test_default_timeouts_default_key(self):
        assert DEFAULT_TIMEOUTS["default"] == 60.0

    def test_default_connect_timeout(self):
        assert DEFAULT_CONNECT_TIMEOUT == 10.0

    def test_openai_in_defaults(self):
        assert "openai" in DEFAULT_TIMEOUTS

    def test_anthropic_in_defaults(self):
        assert "anthropic" in DEFAULT_TIMEOUTS

    def test_defaults_has_at_least_10_keys(self):
        assert len(DEFAULT_TIMEOUTS) >= 10


# ---------------------------------------------------------------------------
# TestTimeoutConfigGetTimeout
# ---------------------------------------------------------------------------

class TestTimeoutConfigGetTimeout:
    """Tests for the get_timeout() instance method."""

    def test_get_timeout_default_service(self):
        config = TimeoutConfig()
        assert config.get_timeout("default") == 60.0

    def test_get_timeout_openai(self):
        config = TimeoutConfig()
        assert config.get_timeout("openai") == 60.0

    def test_get_timeout_anthropic(self):
        config = TimeoutConfig()
        assert config.get_timeout("anthropic") == 90.0

    def test_get_timeout_unknown_returns_default(self):
        config = TimeoutConfig()
        result = config.get_timeout("unknown_service_xyz")
        assert result == DEFAULT_TIMEOUTS["default"]

    def test_get_timeout_unknown_with_custom_default(self):
        config = TimeoutConfig()
        assert config.get_timeout("unknown_service_xyz", default=45.0) == 45.0

    def test_get_timeout_rag(self):
        config = TimeoutConfig()
        assert config.get_timeout("rag") == 30.0


# ---------------------------------------------------------------------------
# TestTimeoutConfigGetTimeoutTuple
# ---------------------------------------------------------------------------

class TestTimeoutConfigGetTimeoutTuple:
    """Tests for the get_timeout_tuple() instance method."""

    def test_returns_tuple(self):
        config = TimeoutConfig()
        result = config.get_timeout_tuple("openai")
        assert isinstance(result, tuple)

    def test_tuple_has_length_2(self):
        config = TimeoutConfig()
        result = config.get_timeout_tuple("openai")
        assert len(result) == 2

    def test_first_element_is_connect_timeout(self):
        config = TimeoutConfig()
        result = config.get_timeout_tuple("openai")
        assert result[0] == DEFAULT_CONNECT_TIMEOUT

    def test_second_element_is_read_timeout(self):
        config = TimeoutConfig()
        result = config.get_timeout_tuple("openai")
        assert result[1] == config.get_timeout("openai")

    def test_unknown_service_still_returns_2_tuple(self):
        config = TimeoutConfig()
        result = config.get_timeout_tuple("totally_unknown")
        assert isinstance(result, tuple) and len(result) == 2


# ---------------------------------------------------------------------------
# TestTimeoutConfigUpdate
# ---------------------------------------------------------------------------

class TestTimeoutConfigUpdate:
    """Tests for update_timeout() and update_connect_timeout()."""

    def test_update_existing_service(self):
        config = TimeoutConfig()
        config.update_timeout("openai", 120.0)
        assert config.get_timeout("openai") == 120.0

    def test_update_new_service(self):
        config = TimeoutConfig()
        config.update_timeout("new_service", 45.0)
        assert config.get_timeout("new_service") == 45.0

    def test_update_negative_timeout_rejected(self):
        config = TimeoutConfig()
        original = config.get_timeout("openai")
        config.update_timeout("openai", -1)
        assert config.get_timeout("openai") == original

    def test_update_zero_timeout_rejected(self):
        config = TimeoutConfig()
        original = config.get_timeout("openai")
        config.update_timeout("openai", 0)
        assert config.get_timeout("openai") == original

    def test_update_connect_timeout(self):
        config = TimeoutConfig()
        config.update_connect_timeout(5.0)
        assert config.connect_timeout == 5.0

    def test_update_connect_timeout_negative_rejected(self):
        config = TimeoutConfig()
        config.update_connect_timeout(-1)
        assert config.connect_timeout == DEFAULT_CONNECT_TIMEOUT


# ---------------------------------------------------------------------------
# TestTimeoutConfigReset
# ---------------------------------------------------------------------------

class TestTimeoutConfigReset:
    """Tests for reset_to_defaults() and get_all_timeouts()."""

    def test_reset_restores_modified_service(self):
        config = TimeoutConfig()
        config.update_timeout("openai", 999.0)
        config.reset_to_defaults()
        assert config.get_timeout("openai") == DEFAULT_TIMEOUTS["openai"]

    def test_reset_restores_connect_timeout(self):
        config = TimeoutConfig()
        config.update_connect_timeout(99.0)
        config.reset_to_defaults()
        assert config.connect_timeout == DEFAULT_CONNECT_TIMEOUT

    def test_get_all_timeouts_returns_dict(self):
        config = TimeoutConfig()
        result = config.get_all_timeouts()
        assert isinstance(result, dict)

    def test_get_all_timeouts_is_copy(self):
        config = TimeoutConfig()
        all_t = config.get_all_timeouts()
        all_t["openai"] = 9999.0
        # Original must be unaffected
        assert config.get_timeout("openai") == DEFAULT_TIMEOUTS["openai"]

    def test_get_all_timeouts_includes_default_key(self):
        config = TimeoutConfig()
        assert "default" in config.get_all_timeouts()


# ---------------------------------------------------------------------------
# TestTimeoutConfigSingleton
# ---------------------------------------------------------------------------

class TestTimeoutConfigSingleton:
    """Tests for singleton behaviour."""

    def test_two_instances_are_same_object(self):
        config1 = TimeoutConfig()
        config2 = TimeoutConfig()
        assert config1 is config2

    def test_get_timeout_config_returns_timeout_config_instance(self):
        result = get_timeout_config()
        assert isinstance(result, TimeoutConfig)

    def test_get_timeout_config_called_twice_same_instance(self):
        result1 = get_timeout_config()
        result2 = get_timeout_config()
        assert result1 is result2


# ---------------------------------------------------------------------------
# TestModuleLevelHelpers
# ---------------------------------------------------------------------------

class TestModuleLevelHelpers:
    """Tests for module-level convenience functions."""

    def test_module_get_timeout_returns_float(self):
        result = get_timeout("openai")
        assert isinstance(result, float)

    def test_module_get_timeout_tuple_returns_2_tuple(self):
        result = get_timeout_tuple("openai")
        assert isinstance(result, tuple) and len(result) == 2

    def test_module_get_timeout_with_custom_default(self):
        result = get_timeout("nonexistent", default=99.0)
        assert result == 99.0

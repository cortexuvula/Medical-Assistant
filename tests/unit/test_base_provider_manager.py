"""
Tests for src/managers/base_provider_manager.py

Covers ProviderManager abstract base class (via concrete subclass):
_get_default_provider, _get_api_key, _get_cache_key, get_provider (lazy init +
caching + cache invalidation), get_provider_safe, _create_provider,
clear_provider_cache, get_available_providers, is_provider_available,
test_connection, test_connection_safe, and create_thread_safe_singleton.
"""

import sys
import threading
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))


# ---------------------------------------------------------------------------
# Concrete test helpers
# ---------------------------------------------------------------------------

class FakeProvider:
    """Minimal provider for testing."""
    def __init__(self, name="default"):
        self.name = name

    def test_connection(self):
        return True


class FakeProviderNoTestConnection:
    """Provider without test_connection method."""
    def __init__(self, name="basic"):
        self.name = name


def _make_manager(providers_map=None, default_provider=None):
    """Factory — returns (manager, mock_security_manager) with no real deps."""
    from managers.base_provider_manager import ProviderManager

    providers = providers_map if providers_map is not None else {"fake": FakeProvider, "other": FakeProvider}

    mock_security = MagicMock()
    mock_security.get_api_key.return_value = "test_api_key"

    default = default_provider

    with patch("managers.base_provider_manager.get_security_manager",
               return_value=mock_security):
        class TestManager(ProviderManager):
            def _get_providers(self):
                return dict(providers)

            def _create_provider_instance(self, provider_class, provider_name):
                return provider_class(name=provider_name)

            def _get_settings_key(self):
                return "test"

            def _get_provider_name_from_settings(self):
                return default or (list(providers.keys())[0] if providers else "")

        mgr = TestManager()
    return mgr, mock_security


# ===========================================================================
# Initialization
# ===========================================================================

class TestProviderManagerInit:
    def test_providers_populated(self):
        mgr, _ = _make_manager()
        assert "fake" in mgr.providers
        assert "other" in mgr.providers

    def test_current_provider_none_initially(self):
        mgr, _ = _make_manager()
        assert mgr._current_provider is None

    def test_provider_instance_none_initially(self):
        mgr, _ = _make_manager()
        assert mgr._provider_instance is None

    def test_security_manager_set(self):
        mgr, mock_sec = _make_manager()
        assert mgr.security_manager is mock_sec


# ===========================================================================
# _get_default_provider
# ===========================================================================

class TestGetDefaultProvider:
    def test_returns_first_provider_name(self):
        mgr, _ = _make_manager({"alpha": FakeProvider, "beta": FakeProvider})
        assert mgr._get_default_provider() == "alpha"

    def test_returns_empty_string_when_no_providers(self):
        mgr, _ = _make_manager({})
        assert mgr._get_default_provider() == ""


# ===========================================================================
# _get_api_key
# ===========================================================================

class TestGetApiKey:
    def test_returns_api_key_from_security_manager(self):
        mgr, mock_sec = _make_manager()
        mock_sec.get_api_key.return_value = "sk-abc123"
        key = mgr._get_api_key("fake")
        assert key == "sk-abc123"

    def test_returns_empty_string_when_key_is_none(self):
        mgr, mock_sec = _make_manager()
        mock_sec.get_api_key.return_value = None
        key = mgr._get_api_key("fake")
        assert key == ""

    def test_returns_empty_string_on_exception(self):
        mgr, mock_sec = _make_manager()
        mock_sec.get_api_key.side_effect = RuntimeError("vault error")
        key = mgr._get_api_key("fake")
        assert key == ""


# ===========================================================================
# get_available_providers
# ===========================================================================

class TestGetAvailableProviders:
    def test_returns_list(self):
        mgr, _ = _make_manager()
        result = mgr.get_available_providers()
        assert isinstance(result, list)

    def test_contains_all_registered_providers(self):
        mgr, _ = _make_manager({"a": FakeProvider, "b": FakeProvider, "c": FakeProvider})
        providers = mgr.get_available_providers()
        assert set(providers) == {"a", "b", "c"}

    def test_empty_when_no_providers(self):
        mgr, _ = _make_manager({})
        assert mgr.get_available_providers() == []


# ===========================================================================
# is_provider_available
# ===========================================================================

class TestIsProviderAvailable:
    def test_true_for_registered_provider(self):
        mgr, _ = _make_manager()
        assert mgr.is_provider_available("fake") is True

    def test_false_for_unregistered_provider(self):
        mgr, _ = _make_manager()
        assert mgr.is_provider_available("nonexistent") is False

    def test_case_sensitive(self):
        mgr, _ = _make_manager({"Fake": FakeProvider})
        assert mgr.is_provider_available("fake") is False
        assert mgr.is_provider_available("Fake") is True


# ===========================================================================
# clear_provider_cache
# ===========================================================================

class TestClearProviderCache:
    def test_clears_current_provider(self):
        mgr, _ = _make_manager()
        mgr._current_provider = "fake"
        mgr.clear_provider_cache()
        assert mgr._current_provider is None

    def test_clears_provider_instance(self):
        mgr, _ = _make_manager()
        mgr._provider_instance = FakeProvider()
        mgr.clear_provider_cache()
        assert mgr._provider_instance is None

    def test_does_not_raise_when_already_clear(self):
        mgr, _ = _make_manager()
        mgr.clear_provider_cache()  # Should not raise


# ===========================================================================
# get_provider (lazy init + caching)
# ===========================================================================

class TestGetProvider:
    def test_returns_provider_instance(self):
        mgr, _ = _make_manager()
        provider = mgr.get_provider()
        assert isinstance(provider, FakeProvider)

    def test_caches_instance_on_second_call(self):
        mgr, _ = _make_manager()
        first = mgr.get_provider()
        second = mgr.get_provider()
        assert first is second

    def test_creates_new_instance_after_cache_clear(self):
        mgr, _ = _make_manager()
        first = mgr.get_provider()
        mgr.clear_provider_cache()
        second = mgr.get_provider()
        assert first is not second

    def test_sets_current_provider(self):
        mgr, _ = _make_manager()
        mgr.get_provider()
        assert mgr._current_provider is not None

    def test_raises_value_error_for_unknown_provider(self):
        from managers.base_provider_manager import ProviderManager
        from utils.error_handling import OperationResult

        mock_security = MagicMock()
        mock_security.get_api_key.return_value = ""

        with patch("managers.base_provider_manager.get_security_manager",
                   return_value=mock_security):
            class BadManager(ProviderManager):
                def _get_providers(self):
                    return {"real": FakeProvider}

                def _create_provider_instance(self, cls, name):
                    return cls()

                def _get_settings_key(self):
                    return "bad"

                def _get_provider_name_from_settings(self):
                    return "does_not_exist"

            mgr = BadManager()

        with pytest.raises(ValueError, match="Unknown provider"):
            mgr.get_provider()

    def test_provider_name_passed_to_create_instance(self):
        mgr, _ = _make_manager()
        provider = mgr.get_provider()
        assert provider.name == "fake"  # First provider in map

    def test_recreates_when_cache_key_changes(self):
        """If _get_cache_key changes, provider should be recreated."""
        from managers.base_provider_manager import ProviderManager

        call_count = [0]
        mock_security = MagicMock()
        mock_security.get_api_key.return_value = ""
        keys = ["fake", "other"]

        with patch("managers.base_provider_manager.get_security_manager",
                   return_value=mock_security):
            class SwitchingManager(ProviderManager):
                def _get_providers(self):
                    return {"fake": FakeProvider, "other": FakeProvider}

                def _create_provider_instance(self, cls, name):
                    call_count[0] += 1
                    return cls(name=name)

                def _get_settings_key(self):
                    return "switch"

                def _get_provider_name_from_settings(self):
                    return keys[0]

                def _get_cache_key(self):
                    return keys[0]

            mgr = SwitchingManager()

        first = mgr.get_provider()
        assert call_count[0] == 1

        keys[0] = "other"  # Simulate settings change
        second = mgr.get_provider()
        assert call_count[0] == 2
        assert second is not first


# ===========================================================================
# get_provider_safe
# ===========================================================================

class TestGetProviderSafe:
    def test_returns_operation_result(self):
        from utils.error_handling import OperationResult
        mgr, _ = _make_manager()
        result = mgr.get_provider_safe()
        assert isinstance(result, OperationResult)

    def test_success_when_provider_exists(self):
        mgr, _ = _make_manager()
        result = mgr.get_provider_safe()
        assert result.success is True

    def test_success_contains_provider(self):
        mgr, _ = _make_manager()
        result = mgr.get_provider_safe()
        assert isinstance(result.value, FakeProvider)

    def test_failure_when_get_provider_raises(self):
        mgr, _ = _make_manager()
        with patch.object(mgr, "get_provider", side_effect=ValueError("bad provider")):
            result = mgr.get_provider_safe()
        assert result.success is False

    def test_failure_has_error_message(self):
        mgr, _ = _make_manager()
        with patch.object(mgr, "get_provider", side_effect=ValueError("bad provider")):
            result = mgr.get_provider_safe()
        assert "bad provider" in result.error


# ===========================================================================
# test_connection
# ===========================================================================

class TestTestConnection:
    def test_returns_true_when_provider_has_test_connection(self):
        mgr, _ = _make_manager()
        assert mgr.test_connection() is True

    def test_returns_true_when_provider_lacks_test_connection(self):
        mgr, _ = _make_manager({"basic": FakeProviderNoTestConnection})
        assert mgr.test_connection() is True

    def test_returns_false_when_provider_test_connection_returns_false(self):
        class FailingProvider:
            def __init__(self, name="fail"):
                pass
            def test_connection(self):
                return False

        mgr, _ = _make_manager({"fail": FailingProvider})
        assert mgr.test_connection() is False

    def test_returns_false_on_exception(self):
        mgr, _ = _make_manager()
        with patch.object(mgr, "get_provider", side_effect=RuntimeError("network down")):
            assert mgr.test_connection() is False


# ===========================================================================
# test_connection_safe
# ===========================================================================

class TestTestConnectionSafe:
    def test_returns_operation_result(self):
        from utils.error_handling import OperationResult
        mgr, _ = _make_manager()
        result = mgr.test_connection_safe()
        assert isinstance(result, OperationResult)

    def test_success_when_connection_ok(self):
        mgr, _ = _make_manager()
        result = mgr.test_connection_safe()
        assert result.success is True
        assert result.value is True

    def test_failure_when_connection_fails(self):
        mgr, _ = _make_manager()
        with patch.object(mgr, "test_connection", return_value=False):
            result = mgr.test_connection_safe()
        assert result.success is False

    def test_failure_when_exception_raised(self):
        mgr, _ = _make_manager()
        with patch.object(mgr, "test_connection", side_effect=RuntimeError("timeout")):
            result = mgr.test_connection_safe()
        assert result.success is False


# ===========================================================================
# _create_provider (internal)
# ===========================================================================

class TestCreateProvider:
    def test_creates_correct_provider_type(self):
        mgr, _ = _make_manager({"fake": FakeProvider})
        mgr._create_provider("fake")
        assert isinstance(mgr._provider_instance, FakeProvider)

    def test_raises_for_unknown_provider(self):
        mgr, _ = _make_manager()
        with pytest.raises(ValueError, match="Unknown provider"):
            mgr._create_provider("nonexistent")

    def test_error_message_lists_available(self):
        mgr, _ = _make_manager({"a": FakeProvider, "b": FakeProvider})
        with pytest.raises(ValueError) as exc_info:
            mgr._create_provider("z")
        assert "a" in str(exc_info.value) or "b" in str(exc_info.value)


# ===========================================================================
# create_thread_safe_singleton
# ===========================================================================

class TestCreateThreadSafeSingleton:
    def _make_singleton_getter(self):
        from managers.base_provider_manager import ProviderManager, create_thread_safe_singleton

        mock_security = MagicMock()
        mock_security.get_api_key.return_value = ""

        with patch("managers.base_provider_manager.get_security_manager",
                   return_value=mock_security):
            class SimpleManager(ProviderManager):
                def _get_providers(self):
                    return {"fake": FakeProvider}

                def _create_provider_instance(self, cls, name):
                    return cls()

                def _get_settings_key(self):
                    return "simple"

                def _get_provider_name_from_settings(self):
                    return "fake"

        # Patch inside create_thread_safe_singleton instantiation
        with patch("managers.base_provider_manager.get_security_manager",
                   return_value=mock_security):
            getter = create_thread_safe_singleton(SimpleManager)

        return getter, mock_security

    def test_returns_callable(self):
        getter, _ = self._make_singleton_getter()
        assert callable(getter)

    def test_returns_manager_instance(self):
        from managers.base_provider_manager import ProviderManager
        getter, mock_sec = self._make_singleton_getter()
        with patch("managers.base_provider_manager.get_security_manager",
                   return_value=mock_sec):
            instance = getter()
        assert isinstance(instance, ProviderManager)

    def test_returns_same_instance_on_repeated_calls(self):
        getter, mock_sec = self._make_singleton_getter()
        with patch("managers.base_provider_manager.get_security_manager",
                   return_value=mock_sec):
            first = getter()
            second = getter()
        assert first is second

    def test_thread_safe_singleton(self):
        """Concurrent calls all return the same instance."""
        getter, mock_sec = self._make_singleton_getter()
        instances = []
        errors = []

        def get_instance():
            try:
                with patch("managers.base_provider_manager.get_security_manager",
                           return_value=mock_sec):
                    instances.append(getter())
            except Exception as e:
                errors.append(e)

        # Create first instance outside threads so patch works
        with patch("managers.base_provider_manager.get_security_manager",
                   return_value=mock_sec):
            first = getter()

        threads = [threading.Thread(target=get_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # All instances should be the same object
        for inst in instances:
            assert inst is first

    def test_different_classes_get_different_singletons(self):
        from managers.base_provider_manager import ProviderManager, create_thread_safe_singleton

        mock_security = MagicMock()
        mock_security.get_api_key.return_value = ""

        with patch("managers.base_provider_manager.get_security_manager",
                   return_value=mock_security):
            class ManagerA(ProviderManager):
                def _get_providers(self): return {"a": FakeProvider}
                def _create_provider_instance(self, cls, name): return cls()
                def _get_settings_key(self): return "a"
                def _get_provider_name_from_settings(self): return "a"

            class ManagerB(ProviderManager):
                def _get_providers(self): return {"a": FakeProvider}
                def _create_provider_instance(self, cls, name): return cls()
                def _get_settings_key(self): return "b"
                def _get_provider_name_from_settings(self): return "a"

        with patch("managers.base_provider_manager.get_security_manager",
                   return_value=mock_security):
            getter_a = create_thread_safe_singleton(ManagerA)
            getter_b = create_thread_safe_singleton(ManagerB)
            a = getter_a()
            b = getter_b()

        assert a is not b
        assert type(a) is ManagerA
        assert type(b) is ManagerB

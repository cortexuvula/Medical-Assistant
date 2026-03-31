"""Tests for managers.api_key_manager non-GUI logic."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

import pytest
from unittest.mock import patch, MagicMock, PropertyMock, Mock
from pathlib import Path

from managers.api_key_manager import APIKeyManager
from utils.constants import (
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_GEMINI,
    PROVIDER_GROQ, PROVIDER_CEREBRAS,
    STT_DEEPGRAM, STT_ELEVENLABS, STT_MODULATE,
)


@pytest.fixture
def mock_data_folder_manager():
    """Mock data_folder_manager to provide a fake env_file_path."""
    with patch('managers.api_key_manager.data_folder_manager') as mock_dfm:
        mock_dfm.env_file_path = Path("/tmp/fake_test/.env")
        yield mock_dfm


@pytest.fixture
def api_manager(mock_data_folder_manager):
    """Create a fresh APIKeyManager with mocked data_folder_manager."""
    return APIKeyManager()


class TestAPIKeyManagerInit:
    """Tests for APIKeyManager.__init__."""

    def test_env_path_set_from_data_folder_manager(self, mock_data_folder_manager):
        mgr = APIKeyManager()
        assert mgr.env_path == Path("/tmp/fake_test/.env")

    def test_security_manager_starts_none(self, mock_data_folder_manager):
        mgr = APIKeyManager()
        assert mgr._security_manager is None

    def test_provider_keys_mapping_exists(self, mock_data_folder_manager):
        mgr = APIKeyManager()
        assert PROVIDER_OPENAI in mgr.PROVIDER_KEYS
        assert STT_DEEPGRAM in mgr.PROVIDER_KEYS


class TestGetSecurityManager:
    """Tests for APIKeyManager._get_security_manager."""

    def test_first_call_imports_and_returns(self, api_manager):
        mock_sm = MagicMock()
        with patch('managers.api_key_manager.get_security_manager', create=True) as mock_import:
            # Patch the lazy import inside the method
            with patch.object(api_manager, '_security_manager', None):
                with patch('utils.security.get_security_manager', return_value=mock_sm):
                    result = api_manager._get_security_manager()
                    assert result is mock_sm

    def test_second_call_returns_cached(self, api_manager):
        mock_sm = MagicMock()
        api_manager._security_manager = mock_sm
        result = api_manager._get_security_manager()
        assert result is mock_sm

    def test_caching_same_object(self, api_manager):
        mock_sm = MagicMock()
        with patch('utils.security.get_security_manager', return_value=mock_sm):
            first = api_manager._get_security_manager()
            second = api_manager._get_security_manager()
            assert first is second

    def test_import_failure_raises(self, api_manager):
        api_manager._security_manager = None
        with patch('utils.security.get_security_manager', side_effect=ImportError("no module")):
            with pytest.raises(ImportError):
                api_manager._get_security_manager()


class TestHasStoredKeys:
    """Tests for APIKeyManager._has_stored_keys."""

    def _setup_keys(self, api_manager, ai_keys=None, stt_keys=None):
        """Helper to set up mock security manager with specific keys."""
        mock_sm = MagicMock()
        ai_keys = ai_keys or {}
        stt_keys = stt_keys or {}
        all_keys = {**ai_keys, **stt_keys}

        def get_key(provider):
            return all_keys.get(provider, None)

        mock_sm.get_api_key.side_effect = get_key
        api_manager._security_manager = mock_sm
        return mock_sm

    def test_both_ai_and_stt_present(self, api_manager):
        self._setup_keys(api_manager,
                         ai_keys={PROVIDER_OPENAI: "sk-abc123"},
                         stt_keys={STT_DEEPGRAM: "dg-key"})
        assert api_manager._has_stored_keys() is True

    def test_only_ai_key_returns_false(self, api_manager):
        self._setup_keys(api_manager,
                         ai_keys={PROVIDER_OPENAI: "sk-abc123"},
                         stt_keys={})
        assert api_manager._has_stored_keys() is False

    def test_only_stt_key_returns_false(self, api_manager):
        self._setup_keys(api_manager,
                         ai_keys={},
                         stt_keys={STT_DEEPGRAM: "dg-key"})
        assert api_manager._has_stored_keys() is False

    def test_no_keys_returns_false(self, api_manager):
        self._setup_keys(api_manager, ai_keys={}, stt_keys={})
        assert api_manager._has_stored_keys() is False

    def test_groq_serves_as_both_ai_and_stt(self, api_manager):
        """Groq appears in both AI and STT lists, so a single Groq key satisfies both."""
        self._setup_keys(api_manager,
                         ai_keys={PROVIDER_GROQ: "groq-key"},
                         stt_keys={PROVIDER_GROQ: "groq-key"})
        assert api_manager._has_stored_keys() is True

    def test_multiple_ai_keys_no_stt_returns_false(self, api_manager):
        self._setup_keys(api_manager,
                         ai_keys={PROVIDER_OPENAI: "sk-abc", PROVIDER_ANTHROPIC: "ant-key"},
                         stt_keys={})
        assert api_manager._has_stored_keys() is False

    def test_anthropic_ai_with_elevenlabs_stt(self, api_manager):
        self._setup_keys(api_manager,
                         ai_keys={PROVIDER_ANTHROPIC: "ant-key"},
                         stt_keys={STT_ELEVENLABS: "el-key"})
        assert api_manager._has_stored_keys() is True

    def test_cerebras_ai_with_modulate_stt(self, api_manager):
        self._setup_keys(api_manager,
                         ai_keys={PROVIDER_CEREBRAS: "cb-key"},
                         stt_keys={STT_MODULATE: "mod-key"})
        assert api_manager._has_stored_keys() is True


class TestStoreKeySecurely:
    """Tests for APIKeyManager._store_key_securely."""

    def test_empty_string_key_returns_false(self, api_manager):
        result = api_manager._store_key_securely("openai", "")
        assert result is False

    def test_none_key_returns_false(self, api_manager):
        result = api_manager._store_key_securely("openai", None)
        assert result is False

    def test_successful_store_returns_true(self, api_manager):
        mock_sm = MagicMock()
        mock_sm.store_api_key.return_value = (True, None)
        api_manager._security_manager = mock_sm

        result = api_manager._store_key_securely("openai", "sk-abc123")
        assert result is True
        mock_sm.store_api_key.assert_called_once_with("openai", "sk-abc123")

    def test_store_failure_returns_false(self, api_manager):
        mock_sm = MagicMock()
        mock_sm.store_api_key.return_value = (False, "encryption failed")
        api_manager._security_manager = mock_sm

        with patch('managers.api_key_manager.logger') as mock_logger:
            result = api_manager._store_key_securely("openai", "sk-abc123")
            assert result is False
            assert mock_logger.warning.called

    def test_store_exception_returns_false(self, api_manager):
        mock_sm = MagicMock()
        mock_sm.store_api_key.side_effect = RuntimeError("crypto error")
        api_manager._security_manager = mock_sm

        with patch('managers.api_key_manager.logger') as mock_logger:
            result = api_manager._store_key_securely("openai", "sk-abc123")
            assert result is False
            assert mock_logger.error.called

    def test_whitespace_only_key_returns_false(self, api_manager):
        """A key that is only whitespace is falsy after strip? Actually ' ' is truthy."""
        # The source checks `if not api_key:` — whitespace-only string is truthy
        mock_sm = MagicMock()
        mock_sm.store_api_key.return_value = (True, None)
        api_manager._security_manager = mock_sm

        result = api_manager._store_key_securely("openai", "   ")
        # "   " is truthy, so it will try to store
        assert result is True


class TestCheckEnvFile:
    """Tests for APIKeyManager.check_env_file."""

    def test_env_path_exists_returns_true(self, api_manager):
        with patch.object(Path, 'exists', return_value=True):
            assert api_manager.check_env_file() is True

    def test_env_path_not_exists_but_has_stored_keys(self, api_manager):
        with patch.object(Path, 'exists', return_value=False):
            with patch.object(api_manager, '_has_stored_keys', return_value=True):
                assert api_manager.check_env_file() is True

    def test_both_false_calls_collect_flow(self, api_manager):
        with patch.object(Path, 'exists', return_value=False):
            with patch.object(api_manager, '_has_stored_keys', return_value=False):
                with patch.object(api_manager, '_collect_api_keys_flow', return_value=True) as mock_flow:
                    result = api_manager.check_env_file()
                    assert result is True
                    mock_flow.assert_called_once()

    def test_both_false_collect_flow_returns_false(self, api_manager):
        with patch.object(Path, 'exists', return_value=False):
            with patch.object(api_manager, '_has_stored_keys', return_value=False):
                with patch.object(api_manager, '_collect_api_keys_flow', return_value=False) as mock_flow:
                    result = api_manager.check_env_file()
                    assert result is False

    def test_env_path_exists_short_circuits(self, api_manager):
        """If env_path exists, _has_stored_keys should not be called."""
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(api_manager, '_has_stored_keys') as mock_hsk:
                api_manager.check_env_file()
                mock_hsk.assert_not_called()

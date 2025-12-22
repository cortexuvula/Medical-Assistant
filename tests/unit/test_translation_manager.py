"""
Unit tests for TranslationManager.

Tests cover provider management, translation operations,
language detection, and settings management.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestTranslationManagerInitialization:
    """Tests for TranslationManager initialization."""

    @patch('src.managers.translation_manager.get_security_manager')
    def test_initialization(self, mock_security):
        """Test basic initialization."""
        from src.managers.translation_manager import TranslationManager

        mock_security.return_value = Mock()

        manager = TranslationManager()

        assert manager.logger is not None
        assert "deep_translator" in manager.providers
        assert manager._current_provider is None
        assert manager._provider_instance is None

    @patch('src.managers.translation_manager.get_security_manager')
    def test_initialization_gets_security_manager(self, mock_security):
        """Test that security manager is obtained during init."""
        from src.managers.translation_manager import TranslationManager

        mock_sm = Mock()
        mock_security.return_value = mock_sm

        manager = TranslationManager()

        mock_security.assert_called_once()
        assert manager.security_manager is mock_sm


class TestGetProvider:
    """Tests for provider retrieval and caching."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.managers.translation_manager import TranslationManager

        with patch('src.managers.translation_manager.get_security_manager') as mock_security:
            mock_security.return_value = Mock()
            self.manager = TranslationManager()

    @patch('src.managers.translation_manager.SETTINGS', {'translation': {'provider': 'deep_translator', 'sub_provider': 'google'}})
    def test_get_provider_creates_instance(self):
        """Test that get_provider creates a new instance."""
        with patch.object(self.manager, '_create_provider') as mock_create:
            self.manager.get_provider()
            mock_create.assert_called_once_with('deep_translator', 'google')

    @patch('src.managers.translation_manager.SETTINGS', {'translation': {'provider': 'deep_translator', 'sub_provider': 'google'}})
    def test_get_provider_caches_instance(self):
        """Test that provider instance is cached."""
        mock_provider = Mock()

        with patch.object(self.manager, '_create_provider') as mock_create:
            self.manager._provider_instance = mock_provider
            self.manager._current_provider = 'deep_translator:google'

            result = self.manager.get_provider()

            # Should not create a new provider
            mock_create.assert_not_called()
            assert result is mock_provider

    @patch('src.managers.translation_manager.SETTINGS', {'translation': {'provider': 'deep_translator', 'sub_provider': 'deepl'}})
    def test_get_provider_recreates_on_sub_provider_change(self):
        """Test that provider is recreated when sub_provider changes."""
        self.manager._current_provider = 'deep_translator:google'
        self.manager._provider_instance = Mock()

        with patch.object(self.manager, '_create_provider') as mock_create:
            self.manager.get_provider()
            mock_create.assert_called_once_with('deep_translator', 'deepl')

    @patch('src.managers.translation_manager.SETTINGS', {'translation': {}})
    def test_get_provider_uses_defaults(self):
        """Test that default provider settings are used."""
        with patch.object(self.manager, '_create_provider') as mock_create:
            self.manager.get_provider()
            mock_create.assert_called_once_with('deep_translator', 'google')

    @patch('src.managers.translation_manager.SETTINGS', {'translation': {'provider': 'deep_translator'}})
    def test_get_provider_handles_exception(self):
        """Test that exceptions are wrapped in TranslationError."""
        from src.utils.exceptions import TranslationError

        with patch.object(self.manager, '_create_provider') as mock_create:
            mock_create.side_effect = Exception("Provider creation failed")

            with pytest.raises(TranslationError):
                self.manager.get_provider()


class TestCreateProvider:
    """Tests for provider creation."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.managers.translation_manager import TranslationManager

        with patch('src.managers.translation_manager.get_security_manager') as mock_security:
            self.mock_security_manager = Mock()
            mock_security.return_value = self.mock_security_manager
            self.manager = TranslationManager()

    def test_create_provider_unknown_provider(self):
        """Test that unknown provider raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            self.manager._create_provider("unknown_provider")

        assert "Unknown provider" in str(exc_info.value)

    @patch('src.managers.translation_manager.DeepTranslatorProvider')
    def test_create_provider_deep_translator_google(self, mock_provider_class):
        """Test creating DeepTranslator with Google."""
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider

        self.manager._create_provider("deep_translator", "google")

        mock_provider_class.assert_called_once_with(
            provider_type="google",
            api_key=""
        )
        assert self.manager._provider_instance is mock_provider

    @patch('src.managers.translation_manager.DeepTranslatorProvider')
    def test_create_provider_deep_translator_deepl(self, mock_provider_class):
        """Test creating DeepTranslator with DeepL (requires API key)."""
        self.mock_security_manager.get_api_key.return_value = "deepl-api-key"
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider

        self.manager._create_provider("deep_translator", "deepl")

        self.mock_security_manager.get_api_key.assert_called_with("deepl_translation")
        mock_provider_class.assert_called_once_with(
            provider_type="deepl",
            api_key="deepl-api-key"
        )

    @patch('src.managers.translation_manager.DeepTranslatorProvider')
    def test_create_provider_deep_translator_microsoft(self, mock_provider_class):
        """Test creating DeepTranslator with Microsoft (requires API key)."""
        self.mock_security_manager.get_api_key.return_value = "ms-api-key"
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider

        self.manager._create_provider("deep_translator", "microsoft")

        self.mock_security_manager.get_api_key.assert_called_with("microsoft_translation")
        mock_provider_class.assert_called_once_with(
            provider_type="microsoft",
            api_key="ms-api-key"
        )

    @patch('src.managers.translation_manager.DeepTranslatorProvider')
    def test_create_provider_handles_none_api_key(self, mock_provider_class):
        """Test handling when API key is None."""
        self.mock_security_manager.get_api_key.return_value = None
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider

        self.manager._create_provider("deep_translator", "deepl")

        mock_provider_class.assert_called_once_with(
            provider_type="deepl",
            api_key=""
        )

    @patch('src.managers.translation_manager.DeepTranslatorProvider')
    def test_create_provider_default_sub_provider(self, mock_provider_class):
        """Test default sub-provider when None is passed."""
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider

        self.manager._create_provider("deep_translator", None)

        mock_provider_class.assert_called_once_with(
            provider_type="google",
            api_key=""
        )


class TestTranslate:
    """Tests for translation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.managers.translation_manager import TranslationManager

        with patch('src.managers.translation_manager.get_security_manager') as mock_security:
            mock_security.return_value = Mock()
            self.manager = TranslationManager()

        self.mock_provider = Mock()
        self.manager._provider_instance = self.mock_provider
        self.manager._current_provider = 'deep_translator:google'

    def test_translate_empty_text(self):
        """Test that empty text returns empty string."""
        result = self.manager.translate("")

        assert result == ""
        self.mock_provider.translate.assert_not_called()

    def test_translate_none_text(self):
        """Test that None text returns empty string."""
        result = self.manager.translate(None)

        assert result == ""

    @patch('src.managers.translation_manager.SETTINGS', {'translation': {'patient_language': 'es', 'doctor_language': 'en'}})
    def test_translate_with_auto_detect(self):
        """Test translation with automatic language detection."""
        self.mock_provider.detect_language.return_value = "fr"
        self.mock_provider.translate.return_value = "Translated text"

        result = self.manager.translate("Bonjour le monde")

        self.mock_provider.detect_language.assert_called_once_with("Bonjour le monde")
        self.mock_provider.translate.assert_called_once_with("Bonjour le monde", "fr", "en")
        assert result == "Translated text"

    @patch('src.managers.translation_manager.SETTINGS', {'translation': {'patient_language': 'es', 'doctor_language': 'en'}})
    def test_translate_with_explicit_languages(self):
        """Test translation with explicit language codes."""
        self.mock_provider.translate.return_value = "Translated text"

        result = self.manager.translate("Hello", source_lang="en", target_lang="de")

        self.mock_provider.detect_language.assert_not_called()
        self.mock_provider.translate.assert_called_once_with("Hello", "en", "de")
        assert result == "Translated text"

    @patch('src.managers.translation_manager.SETTINGS', {'translation': {'patient_language': 'es', 'doctor_language': 'en'}})
    def test_translate_uses_default_target_lang(self):
        """Test that default target language is used from settings."""
        self.mock_provider.translate.return_value = "Texto traducido"

        result = self.manager.translate("Hello world", source_lang="en")

        self.mock_provider.translate.assert_called_once_with("Hello world", "en", "en")

    @patch('src.managers.translation_manager.SETTINGS', {'translation': {'patient_language': 'es', 'doctor_language': 'en'}})
    def test_translate_uses_fallback_source_lang(self):
        """Test fallback to settings when language detection fails."""
        self.mock_provider.detect_language.return_value = None
        self.mock_provider.translate.return_value = "Translated"

        result = self.manager.translate("Some text")

        # Should use patient_language from settings as fallback
        self.mock_provider.translate.assert_called_once_with("Some text", "es", "en")

    @patch('src.managers.translation_manager.SETTINGS', {'translation': {'patient_language': 'es', 'doctor_language': 'en'}})
    def test_translate_raises_on_error(self):
        """Test that translation errors are propagated."""
        self.mock_provider.detect_language.return_value = "en"
        self.mock_provider.translate.side_effect = Exception("Translation API error")

        with pytest.raises(Exception) as exc_info:
            self.manager.translate("Hello")

        assert "Translation API error" in str(exc_info.value)


class TestDetectLanguage:
    """Tests for language detection."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.managers.translation_manager import TranslationManager

        with patch('src.managers.translation_manager.get_security_manager') as mock_security:
            mock_security.return_value = Mock()
            self.manager = TranslationManager()

        self.mock_provider = Mock()
        self.manager._provider_instance = self.mock_provider
        self.manager._current_provider = 'deep_translator:google'

    def test_detect_language_success(self):
        """Test successful language detection."""
        self.mock_provider.detect_language.return_value = "de"

        result = self.manager.detect_language("Guten Tag")

        self.mock_provider.detect_language.assert_called_once_with("Guten Tag")
        assert result == "de"

    def test_detect_language_returns_none_on_error(self):
        """Test that None is returned on detection error."""
        self.mock_provider.detect_language.side_effect = Exception("Detection failed")

        result = self.manager.detect_language("Some text")

        assert result is None


class TestGetSupportedLanguages:
    """Tests for supported languages retrieval."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.managers.translation_manager import TranslationManager

        with patch('src.managers.translation_manager.get_security_manager') as mock_security:
            mock_security.return_value = Mock()
            self.manager = TranslationManager()

        self.mock_provider = Mock()
        self.manager._provider_instance = self.mock_provider
        self.manager._current_provider = 'deep_translator:google'

    def test_get_supported_languages_success(self):
        """Test successful retrieval of supported languages."""
        expected = [("en", "English"), ("es", "Spanish"), ("de", "German")]
        self.mock_provider.get_supported_languages.return_value = expected

        result = self.manager.get_supported_languages()

        assert result == expected

    def test_get_supported_languages_returns_empty_on_error(self):
        """Test that empty list is returned on error."""
        self.mock_provider.get_supported_languages.side_effect = Exception("API error")

        result = self.manager.get_supported_languages()

        assert result == []


class TestTestConnection:
    """Tests for connection testing."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.managers.translation_manager import TranslationManager

        with patch('src.managers.translation_manager.get_security_manager') as mock_security:
            mock_security.return_value = Mock()
            self.manager = TranslationManager()

        self.mock_provider = Mock()
        self.manager._provider_instance = self.mock_provider
        self.manager._current_provider = 'deep_translator:google'

    def test_test_connection_success(self):
        """Test successful connection test."""
        self.mock_provider.test_connection.return_value = True

        result = self.manager.test_connection()

        assert result is True

    def test_test_connection_failure(self):
        """Test connection test failure."""
        self.mock_provider.test_connection.return_value = False

        result = self.manager.test_connection()

        assert result is False

    def test_test_connection_returns_false_on_error(self):
        """Test that False is returned on connection error."""
        self.mock_provider.test_connection.side_effect = Exception("Connection failed")

        result = self.manager.test_connection()

        assert result is False


class TestUpdateSettings:
    """Tests for settings update."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.managers.translation_manager import TranslationManager

        with patch('src.managers.translation_manager.get_security_manager') as mock_security:
            mock_security.return_value = Mock()
            self.manager = TranslationManager()

        # Set up initial state
        self.manager._current_provider = 'deep_translator:google'
        self.manager._provider_instance = Mock()

    @patch('src.managers.translation_manager.SETTINGS', {})
    def test_update_settings_updates_settings_dict(self):
        """Test that settings dictionary is updated."""
        from src.managers.translation_manager import SETTINGS

        new_settings = {'provider': 'deep_translator', 'sub_provider': 'deepl'}

        self.manager.update_settings(new_settings)

        assert SETTINGS['translation'] == new_settings

    @patch('src.managers.translation_manager.SETTINGS', {})
    def test_update_settings_clears_provider(self):
        """Test that current provider is cleared on settings update."""
        self.manager.update_settings({'provider': 'deep_translator'})

        assert self.manager._current_provider is None
        assert self.manager._provider_instance is None


class TestGetTranslationManager:
    """Tests for the global singleton getter."""

    def test_get_translation_manager_returns_instance(self):
        """Test that get_translation_manager returns an instance."""
        import src.managers.translation_manager as tm

        # Reset singleton for testing
        tm._translation_manager = None

        with patch.object(tm.TranslationManager, '__init__', return_value=None):
            manager = tm.get_translation_manager()
            assert manager is not None

    def test_get_translation_manager_returns_same_instance(self):
        """Test that get_translation_manager returns same instance."""
        import src.managers.translation_manager as tm

        # Reset singleton for testing
        tm._translation_manager = None

        with patch.object(tm.TranslationManager, '__init__', return_value=None):
            manager1 = tm.get_translation_manager()
            manager2 = tm.get_translation_manager()

            assert manager1 is manager2


class TestProviderCacheKey:
    """Tests for provider caching by provider:sub_provider key."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.managers.translation_manager import TranslationManager

        with patch('src.managers.translation_manager.get_security_manager') as mock_security:
            mock_security.return_value = Mock()
            self.manager = TranslationManager()

    @patch('src.managers.translation_manager.SETTINGS', {'translation': {'provider': 'deep_translator', 'sub_provider': 'google'}})
    def test_cache_key_includes_provider_and_sub_provider(self):
        """Test that cache key includes both provider and sub_provider."""
        with patch.object(self.manager, '_create_provider') as mock_create:
            self.manager.get_provider()

            assert self.manager._current_provider == 'deep_translator:google'

    @patch('src.managers.translation_manager.DeepTranslatorProvider')
    def test_provider_not_recreated_when_same_key(self, mock_provider_class):
        """Test provider is not recreated when key matches."""
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider

        # First call creates provider
        with patch('src.managers.translation_manager.SETTINGS', {'translation': {'provider': 'deep_translator', 'sub_provider': 'google'}}):
            self.manager.get_provider()
            assert mock_provider_class.call_count == 1

            # Second call with same settings should not recreate
            self.manager.get_provider()
            assert mock_provider_class.call_count == 1

    @patch('src.managers.translation_manager.DeepTranslatorProvider')
    def test_provider_recreated_when_key_changes(self, mock_provider_class):
        """Test provider is recreated when key changes."""
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider

        # First call creates provider
        with patch('src.managers.translation_manager.SETTINGS', {'translation': {'provider': 'deep_translator', 'sub_provider': 'google'}}):
            self.manager.get_provider()
            assert mock_provider_class.call_count == 1

        # Change sub_provider
        with patch('src.managers.translation_manager.SETTINGS', {'translation': {'provider': 'deep_translator', 'sub_provider': 'deepl'}}):
            with patch.object(self.manager, 'security_manager') as mock_sm:
                mock_sm.get_api_key.return_value = "key"
                self.manager.get_provider()
                assert mock_provider_class.call_count == 2


class TestEdgeCases:
    """Edge case tests for TranslationManager."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.managers.translation_manager import TranslationManager

        with patch('src.managers.translation_manager.get_security_manager') as mock_security:
            mock_security.return_value = Mock()
            self.manager = TranslationManager()

    @patch('src.managers.translation_manager.SETTINGS', {})
    def test_empty_settings_uses_defaults(self):
        """Test that empty settings use default values."""
        with patch.object(self.manager, '_create_provider') as mock_create:
            self.manager.get_provider()
            mock_create.assert_called_with('deep_translator', 'google')

    @patch('src.managers.translation_manager.SETTINGS', {'translation': {'provider': 'deep_translator', 'sub_provider': 'google'}})
    def test_translate_whitespace_only(self):
        """Test translation of whitespace-only text."""
        # Whitespace is not empty, so should be translated
        self.mock_provider = Mock()
        self.mock_provider.detect_language.return_value = "en"
        self.mock_provider.translate.return_value = "   "
        self.manager._provider_instance = self.mock_provider
        self.manager._current_provider = 'deep_translator:google'

        result = self.manager.translate("   ")

        # Provider should be called for whitespace
        self.mock_provider.translate.assert_called_once()

    @patch('src.managers.translation_manager.SETTINGS', {'translation': {'patient_language': 'es', 'doctor_language': 'en'}})
    def test_translate_very_long_text(self):
        """Test translation of very long text."""
        self.mock_provider = Mock()
        self.mock_provider.detect_language.return_value = "en"
        self.mock_provider.translate.return_value = "Translated"
        self.manager._provider_instance = self.mock_provider
        self.manager._current_provider = 'deep_translator:google'

        long_text = "Hello world. " * 1000

        result = self.manager.translate(long_text, source_lang="en")

        self.mock_provider.translate.assert_called_once()
        # Verify the full text was passed
        call_args = self.mock_provider.translate.call_args
        assert len(call_args[0][0]) == len(long_text)

    @patch('src.managers.translation_manager.SETTINGS', {'translation': {'patient_language': 'es', 'doctor_language': 'en'}})
    def test_translate_with_special_characters(self):
        """Test translation of text with special characters."""
        self.mock_provider = Mock()
        self.mock_provider.detect_language.return_value = "en"
        self.mock_provider.translate.return_value = "Translated"
        self.manager._provider_instance = self.mock_provider
        self.manager._current_provider = 'deep_translator:google'

        text_with_special = "Hello! @#$%^&*() 你好 مرحبا"

        result = self.manager.translate(text_with_special, source_lang="en")

        self.mock_provider.translate.assert_called_once_with(text_with_special, "en", "en")


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before each test."""
    import src.managers.translation_manager as tm
    original = tm._translation_manager
    tm._translation_manager = None
    yield
    tm._translation_manager = original

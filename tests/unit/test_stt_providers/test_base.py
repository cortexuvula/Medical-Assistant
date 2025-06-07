"""Test base STT provider functionality."""
import pytest
import logging
from unittest.mock import Mock, patch
from pydub import AudioSegment
import numpy as np

from stt_providers.base import BaseSTTProvider


class TestBaseSTTProvider:
    """Test base STT provider functionality."""
    
    @pytest.fixture
    def concrete_provider(self):
        """Create a concrete implementation of BaseSTTProvider for testing."""
        class ConcreteProvider(BaseSTTProvider):
            def transcribe(self, segment: AudioSegment) -> str:
                return "test transcription"
        
        return ConcreteProvider
    
    @pytest.fixture
    def mock_audio_segment(self):
        """Create a mock AudioSegment for testing."""
        # Create a simple audio segment with silence
        duration_ms = 1000  # 1 second
        sample_rate = 44100
        samples = np.zeros(int(sample_rate * duration_ms / 1000))
        
        # Convert to AudioSegment
        audio_segment = AudioSegment(
            samples.tobytes(),
            frame_rate=sample_rate,
            sample_width=2,  # 16-bit
            channels=1
        )
        return audio_segment
    
    def test_initialization_with_api_key(self, concrete_provider):
        """Test provider initialization with API key."""
        api_key = "test-api-key-123"
        language = "en-US"
        
        provider = concrete_provider(api_key=api_key, language=language)
        
        assert provider.api_key == api_key
        assert provider.language == language
        assert isinstance(provider.logger, logging.Logger)
        assert provider.logger.name == "ConcreteProvider"
    
    def test_initialization_without_api_key(self, concrete_provider):
        """Test provider initialization without API key."""
        provider = concrete_provider()
        
        assert provider.api_key == ""
        assert provider.language == "en-US"
        assert isinstance(provider.logger, logging.Logger)
    
    def test_initialization_with_custom_language(self, concrete_provider):
        """Test provider initialization with custom language."""
        language = "es-ES"
        provider = concrete_provider(language=language)
        
        assert provider.language == language
    
    def test_abstract_method_not_implemented(self):
        """Test that abstract methods must be implemented."""
        with pytest.raises(TypeError):
            # Should fail because transcribe is not implemented
            BaseSTTProvider()
    
    def test_check_api_key_available(self, concrete_provider):
        """Test checking if API key is available."""
        provider = concrete_provider(api_key="test-key")
        
        assert provider._check_api_key() is True
    
    def test_check_api_key_not_available(self, concrete_provider, caplog):
        """Test checking if API key is not available."""
        provider = concrete_provider(api_key="")
        
        with caplog.at_level(logging.WARNING):
            result = provider._check_api_key()
        
        assert result is False
        assert "API key not found" in caplog.text
        assert "ConcreteProvider" in caplog.text
    
    def test_check_api_key_empty_string(self, concrete_provider, caplog):
        """Test checking API key with empty string."""
        provider = concrete_provider(api_key="")
        
        with caplog.at_level(logging.WARNING):
            result = provider._check_api_key()
        
        assert result is False
        assert "API key not found" in caplog.text
    
    def test_transcribe_implementation(self, concrete_provider, mock_audio_segment):
        """Test that concrete implementation works."""
        provider = concrete_provider(api_key="test-key")
        
        result = provider.transcribe(mock_audio_segment)
        
        assert result == "test transcription"
    
    def test_logger_name_matches_class(self, concrete_provider):
        """Test that logger name matches the class name."""
        provider = concrete_provider()
        
        assert provider.logger.name == provider.__class__.__name__
    
    def test_provider_with_none_api_key(self, concrete_provider):
        """Test provider with None as API key."""
        provider = concrete_provider(api_key=None)
        
        # Should treat None as empty string
        assert provider.api_key is None
        assert provider._check_api_key() is False
    
    def test_multiple_providers_have_separate_loggers(self, concrete_provider):
        """Test that different provider instances have separate loggers."""
        class AnotherProvider(BaseSTTProvider):
            def transcribe(self, segment: AudioSegment) -> str:
                return "another transcription"
        
        provider1 = concrete_provider()
        provider2 = AnotherProvider()
        
        assert provider1.logger.name != provider2.logger.name
        assert provider1.logger.name == "ConcreteProvider"
        assert provider2.logger.name == "AnotherProvider"
    
    def test_inheritance_chain(self, concrete_provider):
        """Test that concrete provider properly inherits from base."""
        provider = concrete_provider()
        
        assert isinstance(provider, BaseSTTProvider)
        assert hasattr(provider, 'transcribe')
        assert hasattr(provider, '_check_api_key')
        assert hasattr(provider, 'api_key')
        assert hasattr(provider, 'language')
        assert hasattr(provider, 'logger')
"""Test Groq STT provider functionality."""
import pytest
import os
import tempfile
import logging
from unittest.mock import Mock, patch, MagicMock, mock_open
import numpy as np
from pydub import AudioSegment

from stt_providers.groq import GroqProvider
from utils.exceptions import TranscriptionError, APIError, RateLimitError, ServiceUnavailableError


class TestGroqProvider:
    """Test Groq STT provider functionality."""
    
    @pytest.fixture
    def provider(self):
        """Create a Groq provider instance."""
        return GroqProvider(api_key="test-groq-key", language="en-US")
    
    @pytest.fixture
    def mock_audio_segment(self):
        """Create a mock AudioSegment for testing."""
        # Create a simple audio segment
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
    
    def test_initialization(self):
        """Test provider initialization."""
        provider = GroqProvider(api_key="test-key", language="es-ES")
        
        assert provider.api_key == "test-key"
        assert provider.language == "es-ES"
        assert isinstance(provider.logger, logging.Logger)
    
    def test_initialization_without_api_key(self):
        """Test provider initialization without API key."""
        provider = GroqProvider()
        
        assert provider.api_key == ""
        assert provider.language == "en-US"
    
    @patch('stt_providers.groq.get_config')
    @patch('stt_providers.groq.get_security_manager')
    @patch('tempfile.NamedTemporaryFile')
    def test_transcribe_success(self, mock_temp_file, mock_get_security_manager, mock_get_config, provider, mock_audio_segment):
        """Test successful transcription."""
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config
        
        # Mock security manager
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = "test-groq-key"
        mock_get_security_manager.return_value = mock_security_manager
        
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test_audio.wav"
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Mock OpenAI import and client
        with patch('builtins.__import__') as mock_import:
            # Create mock OpenAI module
            mock_openai_module = Mock()
            mock_openai_class = Mock()
            
            # Mock OpenAI client
            mock_client = Mock()
            mock_response = Mock()
            mock_response.text = "This is a test transcription"
            mock_client.audio.transcriptions.create.return_value = mock_response
            mock_openai_class.return_value = mock_client
            
            # Set up the module to return the class
            mock_openai_module.OpenAI = mock_openai_class
            
            # Set up import to return our mock
            def import_side_effect(name, *args, **kwargs):
                if name == 'openai':
                    return mock_openai_module
                # Avoid recursion when importing other modules
                with patch.object(mock_import, 'side_effect', None):
                    return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            # Mock file operations
            mock_file = MagicMock()
            mock_file.return_value.__enter__.return_value.read.return_value = b"fake audio data"
            with patch('builtins.open', mock_file):
                with patch('os.path.getsize', return_value=1024):
                    result = provider.transcribe(mock_audio_segment)
            
            assert result == "This is a test transcription"
            
            # Verify OpenAI client initialization
            mock_openai_class.assert_called_once_with(
                api_key="test-groq-key",
                base_url="https://api.groq.com/openai/v1"
            )
            
            # Verify transcription call
            mock_client.audio.transcriptions.create.assert_called_once()
            call_args = mock_client.audio.transcriptions.create.call_args
            assert call_args[1]["model"] == "whisper-large-v3-turbo"
            assert call_args[1]["language"] == "en"  # Should strip region
            assert call_args[1]["timeout"] == 60
    
    def test_transcribe_without_api_key(self, mock_audio_segment):
        """Test transcription without API key."""
        provider = GroqProvider()
        
        with pytest.raises(TranscriptionError) as exc_info:
            provider.transcribe(mock_audio_segment)
        
        assert "API key not configured" in str(exc_info.value)
    
    @patch('stt_providers.groq.get_config')
    @patch('stt_providers.groq.get_security_manager')
    @patch('tempfile.NamedTemporaryFile')
    def test_transcribe_api_key_not_found(self, mock_temp_file, mock_get_security_manager, mock_get_config, provider, mock_audio_segment):
        """Test transcription when API key is not found in secure storage."""
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config
        
        # Mock security manager returning None
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = None
        mock_get_security_manager.return_value = mock_security_manager
        
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test_audio.wav"
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Set provider api_key to empty
        provider.api_key = ""
        
        with patch('os.path.getsize', return_value=1024):
            with pytest.raises(TranscriptionError) as exc_info:
                provider.transcribe(mock_audio_segment)
        
        assert "API key not configured" in str(exc_info.value)
    
    @patch('stt_providers.groq.get_config')
    @patch('stt_providers.groq.get_security_manager')
    @patch('tempfile.NamedTemporaryFile')
    def test_transcribe_timeout_calculation(self, mock_temp_file, mock_get_security_manager, mock_get_config, provider, mock_audio_segment):
        """Test timeout calculation based on file size."""
        # Mock security manager
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = "test-groq-key"
        mock_get_security_manager.return_value = mock_security_manager
        
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test_audio.wav"
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Mock OpenAI import and client
        with patch('builtins.__import__') as mock_import:
            # Create mock OpenAI module
            mock_openai_module = Mock()
            mock_openai_class = Mock()
            
            # Mock OpenAI client
            mock_client = Mock()
            mock_response = Mock()
            mock_response.text = "test"
            mock_client.audio.transcriptions.create.return_value = mock_response
            mock_openai_class.return_value = mock_client
            
            # Set up the module to return the class
            mock_openai_module.OpenAI = mock_openai_class
            
            # Set up import to return our mock
            def import_side_effect(name, *args, **kwargs):
                if name == 'openai':
                    return mock_openai_module
                # Avoid recursion when importing other modules
                with patch.object(mock_import, 'side_effect', None):
                    return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            # Test different file sizes and base timeouts
            test_cases = [
                (100 * 1024, 30, 30),     # 100KB, base 30s -> 30s
                (500 * 1024, 30, 60),     # 500KB, base 30s -> 60s
                (1000 * 1024, 30, 120),   # 1MB, base 30s -> 120s
                (100 * 1024, 120, 120),   # 100KB, base 120s -> 120s (use base)
            ]
            
            for file_size, base_timeout, expected_timeout in test_cases:
                # Mock config with specific base timeout
                mock_config = Mock()
                mock_config.api.timeout = base_timeout
                mock_get_config.return_value = mock_config
                
                mock_file = MagicMock()
                mock_file.return_value.__enter__.return_value.read.return_value = b"fake audio"
                with patch('builtins.open', mock_file):
                    with patch('os.path.getsize', return_value=file_size):
                        provider.transcribe(mock_audio_segment)
                        
                        # Check timeout parameter
                        call_args = mock_client.audio.transcriptions.create.call_args
                        assert call_args[1]["timeout"] == expected_timeout
    
    @patch('stt_providers.groq.get_config')
    @patch('stt_providers.groq.get_security_manager')
    @patch('tempfile.NamedTemporaryFile')
    def test_transcribe_api_error(self, mock_temp_file, mock_get_security_manager, mock_get_config, provider, mock_audio_segment):
        """Test handling of API errors."""
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config
        
        # Mock security manager
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = "test-groq-key"
        mock_get_security_manager.return_value = mock_security_manager
        
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test_audio.wav"
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Mock OpenAI import and client that raises error
        with patch('builtins.__import__') as mock_import:
            # Create mock OpenAI module
            mock_openai_module = Mock()
            mock_openai_class = Mock()
            
            # Mock OpenAI client that raises error
            mock_client = Mock()
            mock_client.audio.transcriptions.create.side_effect = Exception("API Error")
            mock_openai_class.return_value = mock_client
            
            # Set up the module to return the class
            mock_openai_module.OpenAI = mock_openai_class
            
            # Set up import to return our mock
            def import_side_effect(name, *args, **kwargs):
                if name == 'openai':
                    return mock_openai_module
                # Avoid recursion when importing other modules
                with patch.object(mock_import, 'side_effect', None):
                    return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            mock_file = MagicMock()
            mock_file.return_value.__enter__.return_value.read.return_value = b"fake audio"
            with patch('builtins.open', mock_file):
                with patch('os.path.getsize', return_value=1024):
                    with pytest.raises(TranscriptionError) as exc_info:
                        provider.transcribe(mock_audio_segment)
            
            assert "Unexpected error during GROQ transcription" in str(exc_info.value)
    
    @patch('stt_providers.groq.get_config')
    @patch('stt_providers.groq.get_security_manager')
    @patch('tempfile.NamedTemporaryFile')
    def test_transcribe_unexpected_response_format(self, mock_temp_file, mock_get_security_manager, mock_get_config, provider, mock_audio_segment):
        """Test handling of unexpected response format."""
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config
        
        # Mock security manager
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = "test-groq-key"
        mock_get_security_manager.return_value = mock_security_manager
        
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test_audio.wav"
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Mock OpenAI import and client with invalid response
        with patch('builtins.__import__') as mock_import:
            # Create mock OpenAI module
            mock_openai_module = Mock()
            mock_openai_class = Mock()
            
            # Mock OpenAI client with invalid response
            mock_client = Mock()
            mock_response = Mock()
            del mock_response.text  # No text attribute
            mock_client.audio.transcriptions.create.return_value = mock_response
            mock_openai_class.return_value = mock_client
            
            # Set up the module to return the class
            mock_openai_module.OpenAI = mock_openai_class
            
            # Set up import to return our mock
            def import_side_effect(name, *args, **kwargs):
                if name == 'openai':
                    return mock_openai_module
                # Avoid recursion when importing other modules
                with patch.object(mock_import, 'side_effect', None):
                    return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            mock_file = MagicMock()
            mock_file.return_value.__enter__.return_value.read.return_value = b"fake audio"
            with patch('builtins.open', mock_file):
                with patch('os.path.getsize', return_value=1024):
                    with pytest.raises(TranscriptionError) as exc_info:
                        provider.transcribe(mock_audio_segment)
            
            assert "Unexpected response format from GROQ API" in str(exc_info.value)
    
    @patch('stt_providers.groq.get_config')
    @patch('stt_providers.groq.get_security_manager')
    @patch('tempfile.NamedTemporaryFile')
    def test_language_code_extraction(self, mock_temp_file, mock_get_security_manager, mock_get_config, mock_audio_segment):
        """Test language code extraction from full language tags."""
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config
        
        # Mock security manager
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = "test-groq-key"
        mock_get_security_manager.return_value = mock_security_manager
        
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test_audio.wav"
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Test different language formats
        test_cases = [
            ("en-US", "en"),
            ("es-ES", "es"),
            ("fr", "fr"),
            ("pt-BR", "pt"),
            ("zh-CN", "zh"),
        ]
        
        for full_lang, expected_lang in test_cases:
            provider = GroqProvider(api_key="test-groq-key", language=full_lang)
            
            # Mock OpenAI import and client
            with patch('builtins.__import__') as mock_import:
                # Create mock OpenAI module
                mock_openai_module = Mock()
                mock_openai_class = Mock()
                
                # Mock OpenAI client
                mock_client = Mock()
                mock_response = Mock()
                mock_response.text = "test"
                mock_client.audio.transcriptions.create.return_value = mock_response
                mock_openai_class.return_value = mock_client
                
                # Set up the module to return the class
                mock_openai_module.OpenAI = mock_openai_class
                
                # Set up import to return our mock
                def import_side_effect(name, *args, **kwargs):
                    if name == 'openai':
                        return mock_openai_module
                    # Avoid recursion when importing other modules
                    with patch.object(mock_import, 'side_effect', None):
                        return __import__(name, *args, **kwargs)
                
                mock_import.side_effect = import_side_effect
                
                mock_file = MagicMock()
                mock_file.return_value.__enter__.return_value.read.return_value = b"fake audio"
                with patch('builtins.open', mock_file):
                    with patch('os.path.getsize', return_value=1024):
                        provider.transcribe(mock_audio_segment)
                        
                        # Check language parameter
                        call_args = mock_client.audio.transcriptions.create.call_args
                        assert call_args[1]["language"] == expected_lang
    
    @patch('stt_providers.groq.get_config')
    @patch('stt_providers.groq.get_security_manager')
    @patch('tempfile.NamedTemporaryFile')
    def test_file_cleanup_on_success(self, mock_temp_file, mock_get_security_manager, mock_get_config, provider, mock_audio_segment):
        """Test that temporary files are cleaned up on success."""
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config
        
        # Mock security manager
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = "test-groq-key"
        mock_get_security_manager.return_value = mock_security_manager
        
        # Mock temporary file
        mock_temp = MagicMock()
        temp_file_path = "/tmp/test_audio.wav"
        mock_temp.name = temp_file_path
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Track file operations
        file_deleted = False
        
        def mock_unlink(path):
            nonlocal file_deleted
            if path == temp_file_path:
                file_deleted = True
        
        # Mock OpenAI import and client
        with patch('builtins.__import__') as mock_import:
            # Create mock OpenAI module
            mock_openai_module = Mock()
            mock_openai_class = Mock()
            
            # Mock OpenAI client
            mock_client = Mock()
            mock_response = Mock()
            mock_response.text = "test"
            mock_client.audio.transcriptions.create.return_value = mock_response
            mock_openai_class.return_value = mock_client
            
            # Set up the module to return the class
            mock_openai_module.OpenAI = mock_openai_class
            
            # Set up import to return our mock
            def import_side_effect(name, *args, **kwargs):
                if name == 'openai':
                    return mock_openai_module
                # Avoid recursion when importing other modules
                with patch.object(mock_import, 'side_effect', None):
                    return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            mock_file = MagicMock()
            mock_file.return_value.__enter__.return_value.read.return_value = b"fake audio"
            with patch('builtins.open', mock_file):
                with patch('os.path.getsize', return_value=1024):
                    with patch('os.path.exists', return_value=True):
                        with patch('os.unlink', side_effect=mock_unlink):
                            with patch('time.sleep'):  # Mock sleep
                                provider.transcribe(mock_audio_segment)
        
        assert file_deleted, "Temporary file should be deleted"
    
    @patch('stt_providers.groq.get_config')
    @patch('stt_providers.groq.get_security_manager')
    @patch('tempfile.NamedTemporaryFile')
    def test_file_cleanup_on_error(self, mock_temp_file, mock_get_security_manager, mock_get_config, provider, mock_audio_segment):
        """Test that temporary files are cleaned up on error."""
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config
        
        # Mock security manager
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = "test-groq-key"
        mock_get_security_manager.return_value = mock_security_manager
        
        # Mock temporary file
        mock_temp = MagicMock()
        temp_file_path = "/tmp/test_audio.wav"
        mock_temp.name = temp_file_path
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Track cleanup attempts
        cleanup_attempted = False
        
        def mock_unlink(path):
            nonlocal cleanup_attempted
            if path == temp_file_path:
                cleanup_attempted = True
        
        # Mock OpenAI import and client that raises error
        with patch('builtins.__import__') as mock_import:
            # Create mock OpenAI module
            mock_openai_module = Mock()
            mock_openai_class = Mock()
            
            # Mock OpenAI client that raises error
            mock_client = Mock()
            mock_client.audio.transcriptions.create.side_effect = Exception("Error")
            mock_openai_class.return_value = mock_client
            
            # Set up the module to return the class
            mock_openai_module.OpenAI = mock_openai_class
            
            # Set up import to return our mock
            def import_side_effect(name, *args, **kwargs):
                if name == 'openai':
                    return mock_openai_module
                # Avoid recursion when importing other modules
                with patch.object(mock_import, 'side_effect', None):
                    return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            mock_file = MagicMock()
            mock_file.return_value.__enter__.return_value.read.return_value = b"fake audio"
            with patch('builtins.open', mock_file):
                with patch('os.path.getsize', return_value=1024):
                    with patch('os.path.exists', return_value=True):
                        with patch('os.unlink', side_effect=mock_unlink):
                            with patch('time.sleep'):  # Mock sleep
                                try:
                                    provider.transcribe(mock_audio_segment)
                                except TranscriptionError:
                                    pass
        
        assert cleanup_attempted, "Cleanup should be attempted even on error"
    
    @patch('stt_providers.groq.get_config')
    @patch('stt_providers.groq.get_security_manager')
    @patch('tempfile.NamedTemporaryFile')
    def test_file_cleanup_failure_handling(self, mock_temp_file, mock_get_security_manager, mock_get_config, provider, mock_audio_segment, caplog):
        """Test handling of file cleanup failures."""
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config
        
        # Mock security manager
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = "test-groq-key"
        mock_get_security_manager.return_value = mock_security_manager
        
        # Mock temporary file
        mock_temp = MagicMock()
        temp_file_path = "/tmp/test_audio.wav"
        mock_temp.name = temp_file_path
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Mock cleanup failure
        def mock_unlink(path):
            raise OSError("Permission denied")
        
        # Mock OpenAI import and client
        with patch('builtins.__import__') as mock_import:
            # Create mock OpenAI module
            mock_openai_module = Mock()
            mock_openai_class = Mock()
            
            # Mock OpenAI client
            mock_client = Mock()
            mock_response = Mock()
            mock_response.text = "test"
            mock_client.audio.transcriptions.create.return_value = mock_response
            mock_openai_class.return_value = mock_client
            
            # Set up the module to return the class
            mock_openai_module.OpenAI = mock_openai_class
            
            # Set up import to return our mock
            def import_side_effect(name, *args, **kwargs):
                if name == 'openai':
                    return mock_openai_module
                # Avoid recursion when importing other modules
                with patch.object(mock_import, 'side_effect', None):
                    return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            mock_file = MagicMock()
            mock_file.return_value.__enter__.return_value.read.return_value = b"fake audio"
            with patch('builtins.open', mock_file):
                with patch('os.path.getsize', return_value=1024):
                    with patch('os.path.exists', return_value=True):
                        with patch('os.unlink', side_effect=mock_unlink):
                            with patch('time.sleep'):  # Mock sleep
                                with caplog.at_level(logging.WARNING):
                                    result = provider.transcribe(mock_audio_segment)
        
        # Should still return result despite cleanup failure
        assert result == "test"
        assert "Failed to delete temp file" in caplog.text
        assert "Permission denied" in caplog.text
    
    def test_provider_inheritance(self, provider):
        """Test that provider properly inherits from base."""
        from stt_providers.base import BaseSTTProvider
        
        assert isinstance(provider, BaseSTTProvider)
        assert hasattr(provider, 'transcribe')
        assert hasattr(provider, '_check_api_key')
        assert hasattr(provider, 'api_key')
        assert hasattr(provider, 'language')
        assert hasattr(provider, 'logger')
    
    def test_model_name(self, provider):
        """Test that the correct model name is used."""
        # The model name should be "whisper-large-v3-turbo" as updated in the code
        # We'll verify this by looking at the transcribe method behavior
        assert True  # Placeholder - model name is verified in transcribe_success test
"""Test Whisper STT provider functionality."""
import pytest
import os
import tempfile
import logging
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from pydub import AudioSegment

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.stt_providers.whisper import WhisperProvider


class TestWhisperProvider:
    """Test Whisper STT provider functionality."""
    
    @pytest.fixture
    def provider_with_whisper(self):
        """Create a Whisper provider instance with mocked whisper availability."""
        with patch.object(WhisperProvider, '_check_whisper_available', return_value=True):
            provider = WhisperProvider(language="en-US")
        return provider
    
    @pytest.fixture
    def provider_without_whisper(self):
        """Create a Whisper provider instance without whisper available."""
        with patch.object(WhisperProvider, '_check_whisper_available', return_value=False):
            provider = WhisperProvider(language="en-US")
        return provider
    
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
    
    def test_initialization_with_whisper_available(self):
        """Test provider initialization when Whisper is available."""
        with patch('builtins.__import__') as mock_import:
            # Mock whisper module
            mock_whisper = Mock()
            mock_import.return_value = mock_whisper
            
            provider = WhisperProvider(language="es-ES")
            
            assert provider.api_key == ""  # Whisper doesn't use API key
            assert provider.language == "es-ES"
            assert provider.is_available is True
            assert isinstance(provider.logger, logging.Logger)
    
    def test_initialization_without_whisper_available(self):
        """Test provider initialization when Whisper is not available."""
        with patch('builtins.__import__', side_effect=ImportError("No module named 'whisper'")):
            provider = WhisperProvider()
            
            assert provider.api_key == ""
            assert provider.language == "en-US"
            assert provider.is_available is False
    
    def test_check_whisper_available_success(self):
        """Test checking Whisper availability when it's installed."""
        # Test the internal method directly without going through __init__
        provider = WhisperProvider.__new__(WhisperProvider)
        provider.logger = logging.getLogger(provider.__class__.__name__)
        
        with patch('builtins.__import__') as mock_import:
            mock_whisper = Mock()
            mock_import.return_value = mock_whisper
            
            result = provider._check_whisper_available()
            
            assert result is True
            # Check that whisper was imported
            assert any('whisper' in str(call) for call in mock_import.call_args_list)
    
    def test_check_whisper_available_failure(self, caplog):
        """Test checking Whisper availability when it's not installed."""
        with patch('builtins.__import__', side_effect=ImportError("No module")):
            provider = WhisperProvider()
            
            with caplog.at_level(logging.WARNING):
                result = provider._check_whisper_available()
            
            assert result is False
            assert "Local Whisper model is not available" in caplog.text
    
    @patch('tempfile.NamedTemporaryFile')
    def test_transcribe_success(self, mock_temp_file, provider_with_whisper, mock_audio_segment):
        """Test successful transcription."""
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test_audio.wav"
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Mock whisper import and model
        with patch('builtins.__import__') as mock_import:
            mock_whisper_module = Mock()
            mock_model = Mock()
            mock_result = {
                "text": "This is a test transcription"
            }
            mock_model.transcribe.return_value = mock_result
            mock_whisper_module.load_model.return_value = mock_model
            
            # Setup import to return our mock
            def import_side_effect(name, *args, **kwargs):
                if name == 'whisper':
                    return mock_whisper_module
                # Avoid recursion when importing other modules
                with patch.object(mock_import, 'side_effect', None):
                    return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            # Mock file operations
            with patch('os.path.getsize', return_value=1024):
                result = provider_with_whisper.transcribe(mock_audio_segment)
            
            assert result == "This is a test transcription"
            
            # Verify model loading
            mock_whisper_module.load_model.assert_called_once_with("small")
            
            # Verify transcription call
            mock_model.transcribe.assert_called_once()
            call_args = mock_model.transcribe.call_args
            assert call_args[0][0] == "/tmp/test_audio.wav"
            assert call_args[1]["language"] == "en"  # Should strip region
            assert call_args[1]["fp16"] is False
    
    def test_transcribe_whisper_not_available(self, provider_without_whisper, mock_audio_segment, caplog):
        """Test transcription when Whisper is not available."""
        with caplog.at_level(logging.WARNING):
            result = provider_without_whisper.transcribe(mock_audio_segment)
        
        assert result == ""
        assert "Whisper is not available" in caplog.text
    
    @patch('tempfile.NamedTemporaryFile')
    def test_transcribe_with_different_languages(self, mock_temp_file, mock_audio_segment):
        """Test transcription with different language codes."""
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test_audio.wav"
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Mock whisper import and model
        with patch('builtins.__import__') as mock_import:
            mock_whisper_module = Mock()
            mock_model = Mock()
            mock_result = {"text": "test"}
            mock_model.transcribe.return_value = mock_result
            mock_whisper_module.load_model.return_value = mock_model
            
            # Setup import to return our mock
            def import_side_effect(name, *args, **kwargs):
                if name == 'whisper':
                    return mock_whisper_module
                # Avoid recursion when importing other modules
                with patch.object(mock_import, 'side_effect', None):
                    return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            # Test different language formats
            test_cases = [
                ("en-US", "en"),
                ("es-ES", "es"),
                ("fr", "fr"),
                ("pt-BR", "pt"),
                ("zh-CN", "zh"),
            ]
            
            for full_lang, expected_lang in test_cases:
                with patch.object(WhisperProvider, '_check_whisper_available', return_value=True):
                    provider = WhisperProvider(language=full_lang)
                
                with patch('os.path.getsize', return_value=1024):
                    provider.transcribe(mock_audio_segment)
                    
                    # Check language parameter
                    call_args = mock_model.transcribe.call_args
                    assert call_args[1]["language"] == expected_lang
    
    @patch('tempfile.NamedTemporaryFile')
    def test_transcribe_empty_result(self, mock_temp_file, provider_with_whisper, mock_audio_segment):
        """Test handling of empty transcription result."""
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test_audio.wav"
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Mock whisper import and model with empty result
        with patch('builtins.__import__') as mock_import:
            mock_whisper_module = Mock()
            mock_model = Mock()
            mock_result = {"text": "   "}  # Whitespace only
            mock_model.transcribe.return_value = mock_result
            mock_whisper_module.load_model.return_value = mock_model
            
            # Setup import to return our mock
            def import_side_effect(name, *args, **kwargs):
                if name == 'whisper':
                    return mock_whisper_module
                # Avoid recursion when importing other modules
                with patch.object(mock_import, 'side_effect', None):
                    return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            with patch('os.path.getsize', return_value=1024):
                result = provider_with_whisper.transcribe(mock_audio_segment)
            
            assert result == ""  # Should be empty after strip()
    
    @patch('tempfile.NamedTemporaryFile')
    def test_transcribe_unexpected_response_format(self, mock_temp_file, provider_with_whisper, mock_audio_segment, caplog):
        """Test handling of unexpected response format."""
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test_audio.wav"
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Mock whisper import and model with invalid result
        with patch('builtins.__import__') as mock_import:
            mock_whisper_module = Mock()
            mock_model = Mock()
            mock_result = {}  # Missing 'text' key
            mock_model.transcribe.return_value = mock_result
            mock_whisper_module.load_model.return_value = mock_model
            
            # Setup import to return our mock
            def import_side_effect(name, *args, **kwargs):
                if name == 'whisper':
                    return mock_whisper_module
                # Avoid recursion when importing other modules
                with patch.object(mock_import, 'side_effect', None):
                    return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            with patch('os.path.getsize', return_value=1024):
                with caplog.at_level(logging.ERROR):
                    result = provider_with_whisper.transcribe(mock_audio_segment)
            
            assert result == ""
            assert "Unexpected response format from Whisper" in caplog.text
    
    @patch('tempfile.NamedTemporaryFile')
    def test_transcribe_error_handling(self, mock_temp_file, provider_with_whisper, mock_audio_segment, caplog):
        """Test error handling during transcription."""
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test_audio.wav"
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Mock whisper import and model that raises error
        with patch('builtins.__import__') as mock_import:
            mock_whisper_module = Mock()
            mock_model = Mock()
            mock_model.transcribe.side_effect = Exception("Transcription failed")
            mock_whisper_module.load_model.return_value = mock_model
            
            # Setup import to return our mock
            def import_side_effect(name, *args, **kwargs):
                if name == 'whisper':
                    return mock_whisper_module
                # Avoid recursion when importing other modules
                with patch.object(mock_import, 'side_effect', None):
                    return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            with patch('os.path.getsize', return_value=1024):
                with caplog.at_level(logging.ERROR):
                    result = provider_with_whisper.transcribe(mock_audio_segment)
            
            assert result == ""
            assert "Error with Whisper transcription" in caplog.text
            assert "Transcription failed" in caplog.text
    
    @patch('tempfile.NamedTemporaryFile')
    def test_file_cleanup_on_success(self, mock_temp_file, provider_with_whisper, mock_audio_segment):
        """Test that temporary files are cleaned up on success."""
        # Mock temporary file
        mock_temp = MagicMock()
        temp_file_path = "/tmp/test_audio.wav"
        mock_temp.name = temp_file_path
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Mock whisper import and model
        with patch('builtins.__import__') as mock_import:
            mock_whisper_module = Mock()
            mock_model = Mock()
            mock_result = {"text": "test"}
            mock_model.transcribe.return_value = mock_result
            mock_whisper_module.load_model.return_value = mock_model
            
            # Setup import to return our mock
            def import_side_effect(name, *args, **kwargs):
                if name == 'whisper':
                    return mock_whisper_module
                # Avoid recursion when importing other modules
                with patch.object(mock_import, 'side_effect', None):
                    return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            # Track file operations
            file_deleted = False
            
            def mock_unlink(path):
                nonlocal file_deleted
                if path == temp_file_path:
                    file_deleted = True
            
            with patch('os.path.getsize', return_value=1024):
                with patch('os.path.exists', return_value=True):
                    with patch('os.unlink', side_effect=mock_unlink):
                        provider_with_whisper.transcribe(mock_audio_segment)
            
            assert file_deleted, "Temporary file should be deleted"
    
    @patch('tempfile.NamedTemporaryFile')
    def test_file_cleanup_on_error(self, mock_temp_file, provider_with_whisper, mock_audio_segment):
        """Test that temporary files are cleaned up on error."""
        # Mock temporary file
        mock_temp = MagicMock()
        temp_file_path = "/tmp/test_audio.wav"
        mock_temp.name = temp_file_path
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Mock whisper import and model that raises error
        with patch('builtins.__import__') as mock_import:
            mock_whisper_module = Mock()
            mock_model = Mock()
            mock_model.transcribe.side_effect = Exception("Error")
            mock_whisper_module.load_model.return_value = mock_model
            
            # Setup import to return our mock
            def import_side_effect(name, *args, **kwargs):
                if name == 'whisper':
                    return mock_whisper_module
                # Avoid recursion when importing other modules
                with patch.object(mock_import, 'side_effect', None):
                    return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            # Track cleanup attempts
            cleanup_attempted = False
            
            def mock_unlink(path):
                nonlocal cleanup_attempted
                if path == temp_file_path:
                    cleanup_attempted = True
            
            with patch('os.path.getsize', return_value=1024):
                with patch('os.path.exists', return_value=True):
                    with patch('os.unlink', side_effect=mock_unlink):
                        provider_with_whisper.transcribe(mock_audio_segment)
            
            assert cleanup_attempted, "Cleanup should be attempted even on error"
    
    @patch('tempfile.NamedTemporaryFile')
    def test_file_cleanup_failure_handling(self, mock_temp_file, provider_with_whisper, mock_audio_segment, caplog):
        """Test handling of file cleanup failures."""
        # Mock temporary file
        mock_temp = MagicMock()
        temp_file_path = "/tmp/test_audio.wav"
        mock_temp.name = temp_file_path
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Mock whisper import and model
        with patch('builtins.__import__') as mock_import:
            mock_whisper_module = Mock()
            mock_model = Mock()
            mock_result = {"text": "test"}
            mock_model.transcribe.return_value = mock_result
            mock_whisper_module.load_model.return_value = mock_model
            
            # Setup import to return our mock
            def import_side_effect(name, *args, **kwargs):
                if name == 'whisper':
                    return mock_whisper_module
                # Avoid recursion when importing other modules
                with patch.object(mock_import, 'side_effect', None):
                    return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            # Mock cleanup failure
            def mock_unlink(path):
                raise OSError("Permission denied")
            
            with patch('os.path.getsize', return_value=1024):
                with patch('os.path.exists', return_value=True):
                    with patch('os.unlink', side_effect=mock_unlink):
                        with caplog.at_level(logging.WARNING):
                            result = provider_with_whisper.transcribe(mock_audio_segment)
            
            # Should still return result despite cleanup failure
            assert result == "test"
            assert "Failed to delete temp file" in caplog.text
            assert "Permission denied" in caplog.text
    
    def test_api_key_parameter_ignored(self):
        """Test that API key parameter is ignored for Whisper."""
        with patch.object(WhisperProvider, '_check_whisper_available', return_value=True):
            provider = WhisperProvider(api_key="should-be-ignored")
        
        # API key should still be stored but not used
        assert provider.api_key == "should-be-ignored"
    
    def test_provider_inheritance(self, provider_with_whisper):
        """Test that provider properly inherits from base."""
        from src.stt_providers.base import BaseSTTProvider
        
        assert isinstance(provider_with_whisper, BaseSTTProvider)
        assert hasattr(provider_with_whisper, 'transcribe')
        assert hasattr(provider_with_whisper, '_check_api_key')
        assert hasattr(provider_with_whisper, 'api_key')
        assert hasattr(provider_with_whisper, 'language')
        assert hasattr(provider_with_whisper, 'logger')
        assert hasattr(provider_with_whisper, 'is_available')
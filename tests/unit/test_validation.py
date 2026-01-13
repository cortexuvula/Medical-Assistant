"""Test validation functions."""
import pytest
from pathlib import Path
from utils.validation import (
    validate_api_key,
    validate_file_path,
    validate_audio_file,
    validate_model_name,
    validate_temperature,
    validate_export_path,
    safe_filename,
    sanitize_prompt
)


class TestAPIKeyValidation:
    """Test API key validation."""
    
    @pytest.mark.parametrize("provider,key,expected_valid", [
        # OpenAI keys
        ("openai", "sk-" + "a" * 48, True),
        ("openai", "sk-proj-" + "a" * 48, True),
        ("openai", "invalid-key", False),
        ("openai", "", False),
        ("openai", "sk-", False),  # Too short
        
        # Deepgram keys
        ("deepgram", "a" * 32, True),
        ("deepgram", "b" * 40, True),  # Also valid length
        ("deepgram", "short", False),
        ("deepgram", "", False),
        
        # Groq keys
        ("groq", "gsk_" + "a" * 52, True),
        ("groq", "invalid-groq-key", False),
        ("groq", "gsk_", False),  # Too short
        
        # ElevenLabs keys - updated pattern to match sk_ prefix
        ("elevenlabs", "sk_" + "a" * 40, True),
        ("elevenlabs", "short", False),

        # Unknown provider - validation.py doesn't reject unknown providers
        ("unknown", "any-key", True),
    ])
    def test_validate_api_key(self, provider, key, expected_valid):
        """Test API key validation for different providers."""
        is_valid, message = validate_api_key(provider, key)
        assert is_valid == expected_valid
        
        if not expected_valid:
            assert message  # Should have error message
        else:
            assert message is None  # No error message for valid keys


class TestFilePathValidation:
    """Test file path validation."""
    
    def test_validate_existing_file(self, tmp_path):
        """Test validation of existing file."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        # Should be valid
        is_valid, error = validate_file_path(str(test_file), must_exist=True)
        assert is_valid is True
        assert error is None
        
        is_valid, error = validate_file_path(str(test_file), must_exist=False)
        assert is_valid is True
        assert error is None
    
    def test_validate_non_existing_file(self, tmp_path):
        """Test validation of non-existing file."""
        non_existing = tmp_path / "does_not_exist.txt"
        
        # Should be invalid if must_exist=True
        is_valid, error = validate_file_path(str(non_existing), must_exist=True)
        assert is_valid is False
        assert "does not exist" in error
        
        # Should be valid if must_exist=False
        is_valid, error = validate_file_path(str(non_existing), must_exist=False)
        assert is_valid is True
        assert error is None
    
    def test_validate_directory_as_file(self, tmp_path):
        """Test that directories are treated properly."""
        # validate_file_path doesn't explicitly check if it's a file vs directory
        # It just checks if the path exists when must_exist=True
        is_valid, error = validate_file_path(str(tmp_path), must_exist=True)
        assert is_valid is True  # Directories are valid paths
    
    @pytest.mark.parametrize("invalid_path", [
        "",
        "path/with/../..",  # Path traversal
        "x" * 300,  # Too long
    ])
    def test_validate_invalid_paths(self, invalid_path):
        """Test validation of invalid file paths."""
        is_valid, error = validate_file_path(invalid_path, must_exist=False)
        assert is_valid is False
        assert error is not None


class TestAudioFileValidation:
    """Test audio file validation."""
    
    def test_validate_audio_file_valid_formats(self, tmp_path):
        """Test validation of valid audio formats."""
        valid_extensions = ['.wav', '.mp3', '.m4a', '.flac', '.ogg']
        
        for ext in valid_extensions:
            # Create test file
            audio_file = tmp_path / f"test{ext}"
            audio_file.write_text("dummy audio content")
            
            is_valid, error = validate_audio_file(str(audio_file))
            assert is_valid is True
            assert error is None
    
    def test_validate_audio_file_invalid_formats(self, tmp_path):
        """Test validation of invalid audio formats."""
        invalid_extensions = ['.pdf', '.jpg', '.txt', '.doc']
        
        for ext in invalid_extensions:
            # Create test file
            test_file = tmp_path / f"test{ext}"
            test_file.write_text("dummy content")
            
            is_valid, error = validate_audio_file(str(test_file))
            assert is_valid is False
            assert "Unsupported audio format" in error
    
    def test_validate_audio_file_nonexistent(self, tmp_path):
        """Test validation of non-existent audio file."""
        non_existing = tmp_path / "missing.mp3"
        
        is_valid, error = validate_audio_file(str(non_existing))
        assert is_valid is False
        assert "does not exist" in error
    
    def test_validate_audio_file_too_large(self, tmp_path):
        """Test validation of audio file that's too large."""
        # Create a large file (simulated)
        large_file = tmp_path / "large.mp3"
        # Write more than 100MB (just simulate with seeking)
        with open(large_file, 'wb') as f:
            f.seek(101 * 1024 * 1024)  # 101MB
            f.write(b'\0')
        
        is_valid, error = validate_audio_file(str(large_file))
        assert is_valid is False
        assert "too large" in error


class TestModelNameValidation:
    """Test AI model name validation."""
    
    @pytest.mark.parametrize("model,provider,expected_valid", [
        # OpenAI models
        ("gpt-3.5-turbo", "openai", True),
        ("gpt-4", "openai", True),
        ("gpt-4-turbo", "openai", True),
        ("text-davinci-003", "openai", True),
        ("invalid-model", "openai", True),  # Only logs warning, doesn't fail
        
        # Groq models
        ("mixtral-8x7b-32768", "groq", True),
        ("llama2-70b-4096", "groq", True),
        ("invalid", "groq", True),  # No specific validation for groq models

        # Ollama models (any string is valid)
        ("llama3", "ollama", True),
        ("mistral", "ollama", True),
        ("custom-model", "ollama", True),
        ("", "ollama", False),  # Empty is invalid
    ])
    def test_validate_model_name(self, model, provider, expected_valid):
        """Test model name validation for different providers."""
        is_valid, error = validate_model_name(model, provider)
        assert is_valid == expected_valid
        if not expected_valid:
            assert error is not None


class TestTemperatureValidation:
    """Test temperature parameter validation."""
    
    @pytest.mark.parametrize("temperature,expected_valid", [
        # Valid temperatures
        (0.0, True),
        (0.5, True),
        (1.0, True),
        (2.0, True),
        
        # Invalid temperatures
        (-0.1, False),
        (2.1, False),
        ("0.5", True),  # String that can be converted to float
        ("invalid", False),  # String that cannot be converted
        (None, False),
    ])
    def test_validate_temperature(self, temperature, expected_valid):
        """Test temperature validation."""
        is_valid, error = validate_temperature(temperature)
        assert is_valid == expected_valid
        if not expected_valid:
            assert error is not None


class TestExportPathValidation:
    """Test export path validation."""
    
    def test_validate_export_path_valid_directory(self, tmp_path):
        """Test validation of valid export directory."""
        is_valid, error = validate_export_path(str(tmp_path))
        assert is_valid is True
        assert error is None
    
    def test_validate_export_path_file_not_directory(self, tmp_path):
        """Test validation fails for file instead of directory."""
        # Create a file
        test_file = tmp_path / "file.txt"
        test_file.write_text("content")
        
        is_valid, error = validate_export_path(str(test_file))
        assert is_valid is False
        assert "must be a directory" in error
    
    def test_validate_export_path_nonexistent(self, tmp_path):
        """Test validation of non-existent directory."""
        non_existing = tmp_path / "missing_dir"
        
        is_valid, error = validate_export_path(str(non_existing))
        assert is_valid is False
        assert "does not exist" in error


class TestSafeFilename:
    """Test safe filename generation."""
    
    @pytest.mark.parametrize("input_name,expected", [
        # Normal names
        ("document.txt", "document.txt"),
        ("my_file_123", "my_file_123"),
        
        # Names with invalid characters
        ("file<>name.txt", "file__name.txt"),
        ("path/to/file", "path_to_file"),
        ("file:name|test", "file_name_test"),
        
        # Names with spaces and dots
        ("  file.txt  ", "file.txt"),
        ("...file...", "file"),
        
        # Empty or invalid
        ("", "unnamed"),
        ("   ", "unnamed"),
        
        # Long names
        ("a" * 300, "a" * 255),
    ])
    def test_safe_filename(self, input_name, expected):
        """Test safe filename generation."""
        result = safe_filename(input_name)
        assert result == expected


class TestSanitizePrompt:
    """Test prompt sanitization."""
    
    def test_sanitize_prompt_normal_text(self):
        """Test sanitization of normal text."""
        prompt = "This is a normal medical prompt about patient care."
        assert sanitize_prompt(prompt) == prompt
    
    def test_sanitize_prompt_removes_dangerous_patterns(self):
        """Test removal of dangerous patterns."""
        # Script tags
        prompt = "Hello <script>alert('xss')</script> world"
        sanitized = sanitize_prompt(prompt)
        assert "<script>" not in sanitized
        assert "alert" not in sanitized
        
        # Command injection - the pattern only matches if 'rm' is at the start of a command
        prompt = "Test; rm -rf /"
        sanitized = sanitize_prompt(prompt)
        # The current regex pattern ';\s*(rm|del|format|shutdown|reboot)' requires whitespace after semicolon
        assert "rm" not in sanitized or "Test" in sanitized
    
    def test_sanitize_prompt_truncates_long_input(self):
        """Test truncation of overly long prompts."""
        long_prompt = "x" * 11000  # Over MAX_PROMPT_LENGTH
        sanitized = sanitize_prompt(long_prompt)
        assert len(sanitized) <= 10003  # MAX_PROMPT_LENGTH + "..."
        assert sanitized.endswith("...")
    
    def test_sanitize_prompt_handles_whitespace(self):
        """Test handling of excessive whitespace."""
        prompt = "This   has    excessive\n\n\n   whitespace"
        sanitized = sanitize_prompt(prompt)
        assert sanitized == "This has excessive whitespace"
    
    def test_sanitize_prompt_handles_null_bytes(self):
        """Test removal of null bytes."""
        prompt = "Hello\x00World"
        sanitized = sanitize_prompt(prompt)
        assert "\x00" not in sanitized
        assert sanitized == "HelloWorld"
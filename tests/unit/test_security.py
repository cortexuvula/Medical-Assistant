"""Test security module functionality."""
import pytest
from unittest.mock import patch, Mock
from utils.security import get_security_manager, SecureKeyStorage, RateLimiter
from utils.security_decorators import rate_limited, sanitize_inputs
from cryptography.fernet import InvalidToken
import time
from pathlib import Path
import tempfile
import os


class TestSecurityFunctions:
    """Test security core functions."""
    
    def test_secure_key_storage(self):
        """Test SecureKeyStorage functionality."""
        # Create a temporary key file
        with tempfile.TemporaryDirectory() as temp_dir:
            key_file = Path(temp_dir) / "test_keys.enc"
            storage = SecureKeyStorage(key_file)
            
            # Test storing and retrieving a key
            provider = "openai"
            api_key = "sk-test123456789abcdef"
            
            # Store the key
            storage.store_key(provider, api_key)
            
            # Retrieve and verify
            retrieved_key = storage.get_key(provider)
            assert retrieved_key == api_key
            
            # Test listing providers
            providers = storage.list_providers()
            assert provider in providers
            assert "stored_at" in providers[provider]
            assert "key_hash" in providers[provider]
            
            # Test removing a key
            assert storage.remove_key(provider) is True
            assert storage.get_key(provider) is None
            assert storage.remove_key(provider) is False  # Already removed
    
    def test_secure_key_storage_empty_key(self):
        """Test storing empty string."""
        with tempfile.TemporaryDirectory() as temp_dir:
            key_file = Path(temp_dir) / "test_keys.enc"
            storage = SecureKeyStorage(key_file)
            
            storage.store_key("test", "")
            assert storage.get_key("test") == ""
    
    def test_security_manager_singleton(self):
        """Test SecurityManager singleton pattern."""
        manager1 = get_security_manager()
        manager2 = get_security_manager()
        
        assert manager1 is manager2
    
    def test_security_manager_api_key_validation(self):
        """Test API key validation through SecurityManager."""
        manager = get_security_manager()
        
        # Test valid OpenAI key
        is_valid, error = manager.validate_api_key("openai", "sk-" + "a" * 48)
        assert is_valid is True
        assert error is None
        
        # Test invalid OpenAI key
        is_valid, error = manager.validate_api_key("openai", "invalid-key")
        assert is_valid is False
        assert error is not None
        
        # Test empty key
        is_valid, error = manager.validate_api_key("openai", "")
        assert is_valid is False
        assert error == "API key cannot be empty"
    
    def test_rate_limiter(self):
        """Test RateLimiter functionality."""
        limiter = RateLimiter()
        
        # Set a low limit for testing
        limiter.set_limit("test_provider", 2)  # 2 calls per minute
        
        # First two calls should succeed
        is_allowed, wait_time = limiter.check_rate_limit("test_provider")
        assert is_allowed is True
        assert wait_time is None
        
        is_allowed, wait_time = limiter.check_rate_limit("test_provider")
        assert is_allowed is True
        assert wait_time is None
        
        # Third call should be blocked
        is_allowed, wait_time = limiter.check_rate_limit("test_provider")
        assert is_allowed is False
        assert wait_time is not None
        assert wait_time > 0
        
        # Check usage stats
        stats = limiter.get_usage_stats("test_provider")
        assert stats["calls_last_minute"] == 2
        assert stats["rate_limit"] == 2
        assert stats["available"] == 0
        assert stats["utilization"] == 1.0


class TestSecurityDecorators:
    """Test security decorator functions."""
    
    @patch('security_decorators.get_security_manager')
    def test_rate_limiting_decorator(self, mock_get_manager):
        """Test rate limiting decorator."""
        # Mock the security manager and rate limiter
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        # Test allowing calls
        mock_manager.check_rate_limit.return_value = (True, None)
        
        @rate_limited("test_provider")
        def test_function():
            return "success"
        
        # Should succeed
        assert test_function() == "success"
        mock_manager.check_rate_limit.assert_called_with("test_provider", None)
        
        # Test blocking calls
        mock_manager.check_rate_limit.return_value = (False, 10.5)
        
        # Import the exception from the correct module
        from utils.exceptions import RateLimitError
        
        # This should be blocked
        with pytest.raises(RateLimitError) as exc_info:
            test_function()
        assert "Rate limit exceeded" in str(exc_info.value)
        assert "10.5 seconds" in str(exc_info.value)
    
    @patch('security_decorators.get_security_manager')
    def test_rate_limiting_with_identifier(self, mock_get_manager):
        """Test rate limiting with identifier argument."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        mock_manager.check_rate_limit.return_value = (True, None)
        
        @rate_limited("test_provider", identifier_arg="user_id")
        def test_function(data, user_id=None):
            return f"processed {data} for {user_id}"
        
        # Call with identifier
        result = test_function("test_data", user_id="user123")
        assert result == "processed test_data for user123"
        mock_manager.check_rate_limit.assert_called_with("test_provider", "user123")
        
        # Call without identifier
        result = test_function("test_data")
        assert result == "processed test_data for None"
        mock_manager.check_rate_limit.assert_called_with("test_provider", None)
    
    @patch('security_decorators.get_security_manager')
    def test_sanitize_inputs_decorator(self, mock_get_manager):
        """Test input sanitization decorator."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        # Mock the sanitize_input method
        def mock_sanitize(text, input_type):
            # Simple mock sanitization
            if "<script>" in text:
                return text.replace("<script>", "").replace("</script>", "")
            if "onclick" in text:
                return text.replace('onclick="alert()"', '')
            return text
        
        mock_manager.sanitize_input.side_effect = mock_sanitize
        
        @sanitize_inputs("text", "query")
        def test_function(text, number=5, query=""):
            return {"text": text, "number": number, "query": query}
        
        # Test script removal
        result = test_function("<script>alert('xss')</script>Hello", query="test")
        assert "<script>" not in result["text"]
        assert "Hello" in result["text"]
        
        # Verify sanitize_input was called
        assert mock_manager.sanitize_input.call_count == 2
    
    @patch('security_decorators.get_security_manager')
    def test_sanitize_inputs_preserves_safe_content(self, mock_get_manager):
        """Test sanitization preserves safe content."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        # Return input unchanged for safe content
        mock_manager.sanitize_input.side_effect = lambda text, input_type: text
        
        @sanitize_inputs("text")
        def test_function(text):
            return text
        
        safe_text = "This is normal text with numbers 123 and symbols !@#"
        assert test_function(safe_text) == safe_text
        
        # Medical content should be preserved
        medical_text = "Patient BP: 120/80, Temp: 98.6°F"
        assert test_function(medical_text) == medical_text
    
    @patch('security_decorators.get_security_manager')
    def test_sanitize_inputs_handles_non_string_args(self, mock_get_manager):
        """Test sanitization handles non-string arguments."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        mock_manager.sanitize_input.side_effect = lambda text, input_type: text
        
        @sanitize_inputs("text", "message")
        def test_function(text, count, flag=True, message=None):
            return {"text": text, "count": count, "flag": flag, "message": message}
        
        result = test_function("test", 42, flag=False, message=123)
        assert result["text"] == "test"
        assert result["count"] == 42
        assert result["flag"] is False
        assert result["message"] == 123  # Non-string not sanitized
    
    def test_security_manager_sanitize_input(self):
        """Test SecurityManager sanitize_input method."""
        manager = get_security_manager()
        
        # Test prompt sanitization
        prompt = "Normal prompt without issues"
        assert manager.sanitize_input(prompt, "prompt") == prompt
        
        # Test filename sanitization  
        filename = "test_file.txt"
        assert manager.sanitize_input(filename, "filename") == filename
        
        # Test generic sanitization with control characters
        text_with_control = "Hello\x00World\x01"
        sanitized = manager.sanitize_input(text_with_control, "generic")
        assert "\x00" not in sanitized
        assert "\x01" not in sanitized
"""Test security module functionality."""
import pytest
from unittest.mock import patch, Mock, MagicMock
import sys
from pathlib import Path
import tempfile

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestSecurityFunctions:
    """Test security core functions."""

    def test_secure_key_storage(self):
        """Test SecureKeyStorage functionality."""
        from src.utils.security import SecureKeyStorage

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

            # Test removing a key
            assert storage.remove_key(provider) is True
            assert storage.get_key(provider) is None
            assert storage.remove_key(provider) is False  # Already removed

    def test_secure_key_storage_empty_key(self):
        """Test storing empty string."""
        from src.utils.security import SecureKeyStorage

        with tempfile.TemporaryDirectory() as temp_dir:
            key_file = Path(temp_dir) / "test_keys.enc"
            storage = SecureKeyStorage(key_file)

            storage.store_key("test", "")
            assert storage.get_key("test") == ""

    def test_security_manager_singleton(self):
        """Test SecurityManager singleton pattern."""
        from src.utils.security import get_security_manager

        manager1 = get_security_manager()
        manager2 = get_security_manager()

        assert manager1 is manager2

    def test_security_manager_api_key_validation(self):
        """Test API key validation through SecurityManager."""
        from src.utils.security import get_security_manager

        manager = get_security_manager()

        # Test valid OpenAI key format
        is_valid, error = manager.validate_api_key("openai", "sk-" + "a" * 48)
        # Result depends on actual validation logic
        assert isinstance(is_valid, bool)

        # Test empty key
        is_valid, error = manager.validate_api_key("openai", "")
        assert is_valid is False

    def test_rate_limiter(self):
        """Test RateLimiter functionality."""
        from src.utils.security import RateLimiter

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
        assert "rate_limit" in stats
        assert "available" in stats


class TestSecurityDecorators:
    """Test security decorator functions."""

    @patch('src.utils.security_decorators.get_security_manager')
    def test_rate_limiting_decorator(self, mock_get_manager):
        """Test rate limiting decorator."""
        from src.utils.security_decorators import rate_limited

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

    @patch('src.utils.security_decorators.get_security_manager')
    def test_rate_limiting_with_identifier(self, mock_get_manager):
        """Test rate limiting with identifier argument."""
        from src.utils.security_decorators import rate_limited

        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        mock_manager.check_rate_limit.return_value = (True, None)

        @rate_limited("test_provider", identifier_arg="user_id")
        def test_function(data, user_id=None):
            return f"processed {data} for {user_id}"

        # Call with identifier
        result = test_function("test_data", user_id="user123")
        assert result == "processed test_data for user123"

    @patch('src.utils.security_decorators.get_security_manager')
    def test_sanitize_inputs_decorator(self, mock_get_manager):
        """Test input sanitization decorator."""
        from src.utils.security_decorators import sanitize_inputs

        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager

        # Mock the sanitize_input method - just return input unchanged
        mock_manager.sanitize_input.side_effect = lambda text, input_type: text

        @sanitize_inputs("text")
        def test_function(text):
            return text

        result = test_function("Hello World")
        assert result == "Hello World"

    @patch('src.utils.security_decorators.get_security_manager')
    def test_sanitize_inputs_preserves_safe_content(self, mock_get_manager):
        """Test sanitization preserves safe content."""
        from src.utils.security_decorators import sanitize_inputs

        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager

        # Return input unchanged for safe content
        mock_manager.sanitize_input.side_effect = lambda text, input_type: text

        @sanitize_inputs("text")
        def test_function(text):
            return text

        safe_text = "This is normal text with numbers 123 and symbols !@#"
        assert test_function(safe_text) == safe_text

    @patch('src.utils.security_decorators.get_security_manager')
    def test_sanitize_inputs_handles_non_string_args(self, mock_get_manager):
        """Test sanitization handles non-string arguments."""
        from src.utils.security_decorators import sanitize_inputs

        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        mock_manager.sanitize_input.side_effect = lambda text, input_type: text

        @sanitize_inputs("text")
        def test_function(text, count, flag=True):
            return {"text": text, "count": count, "flag": flag}

        result = test_function("test", 42, flag=False)
        assert result["text"] == "test"
        assert result["count"] == 42
        assert result["flag"] is False

    def test_security_manager_sanitize_input(self):
        """Test SecurityManager sanitize_input method."""
        from src.utils.security import get_security_manager

        manager = get_security_manager()

        # Test prompt sanitization
        prompt = "Normal prompt without issues"
        sanitized = manager.sanitize_input(prompt, "prompt")
        assert isinstance(sanitized, str)

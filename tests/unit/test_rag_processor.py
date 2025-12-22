"""
Unit tests for RagProcessor.

Tests cover N8N webhook integration, URL validation, response parsing,
markdown rendering, and security features.
"""

import pytest
import threading
import json
import re
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from datetime import datetime
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestRagProcessorInitialization:
    """Tests for RagProcessor initialization."""

    @patch.dict('os.environ', {'N8N_URL': 'https://n8n.example.com/webhook/test', 'N8N_AUTHORIZATION_SECRET': 'Bearer secret123'})
    @patch('src.ai.rag_processor.load_dotenv')
    def test_initialization_with_valid_env(self, mock_dotenv):
        """Test initialization with valid environment variables."""
        from src.ai.rag_processor import RagProcessor

        mock_app = Mock()
        processor = RagProcessor(mock_app)

        assert processor.app is mock_app
        assert processor.is_processing is False
        assert processor.n8n_webhook_url == 'https://n8n.example.com/webhook/test'
        assert processor.n8n_auth_header == 'Bearer secret123'

    @patch.dict('os.environ', {}, clear=True)
    @patch('src.ai.rag_processor.load_dotenv')
    def test_initialization_without_env(self, mock_dotenv):
        """Test initialization without environment variables."""
        # Clear any existing env vars for our test
        import os
        os.environ.pop('N8N_URL', None)
        os.environ.pop('N8N_AUTHORIZATION_SECRET', None)

        from src.ai.rag_processor import RagProcessor

        mock_app = Mock()
        processor = RagProcessor(mock_app)

        assert processor.n8n_webhook_url is None
        assert processor.n8n_auth_header is None

    @patch.dict('os.environ', {'N8N_URL': 'invalid-url', 'N8N_AUTHORIZATION_SECRET': 'secret'})
    @patch('src.ai.rag_processor.load_dotenv')
    def test_initialization_with_invalid_url(self, mock_dotenv):
        """Test initialization with invalid webhook URL."""
        from src.ai.rag_processor import RagProcessor

        mock_app = Mock()
        processor = RagProcessor(mock_app)

        # Invalid URL should result in None
        assert processor.n8n_webhook_url is None


class TestUrlValidation:
    """Tests for webhook URL validation and SSRF protection."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.ai.rag_processor import RagProcessor
        with patch.dict('os.environ', {'N8N_URL': '', 'N8N_AUTHORIZATION_SECRET': ''}):
            with patch('src.ai.rag_processor.load_dotenv'):
                self.processor = RagProcessor(Mock())

    def test_validate_empty_url(self):
        """Test validation of empty URL."""
        is_valid, url, error = self.processor._validate_webhook_url("")
        assert is_valid is False
        assert url is None
        assert "empty" in error.lower()

    def test_validate_none_url(self):
        """Test validation of None URL."""
        is_valid, url, error = self.processor._validate_webhook_url(None)
        assert is_valid is False
        assert url is None

    def test_validate_valid_https_url(self):
        """Test validation of valid HTTPS URL."""
        is_valid, url, error = self.processor._validate_webhook_url("https://n8n.example.com/webhook/test")
        assert is_valid is True
        assert url == "https://n8n.example.com/webhook/test"
        assert error is None

    def test_validate_valid_http_url(self):
        """Test validation of valid HTTP URL."""
        is_valid, url, error = self.processor._validate_webhook_url("http://n8n.example.com/webhook/test")
        assert is_valid is True
        assert url == "http://n8n.example.com/webhook/test"
        assert error is None

    def test_validate_invalid_scheme_ftp(self):
        """Test validation rejects FTP scheme."""
        is_valid, url, error = self.processor._validate_webhook_url("ftp://n8n.example.com/webhook")
        assert is_valid is False
        assert "scheme" in error.lower()

    def test_validate_invalid_scheme_file(self):
        """Test validation rejects file scheme."""
        is_valid, url, error = self.processor._validate_webhook_url("file:///etc/passwd")
        assert is_valid is False
        assert "scheme" in error.lower()

    def test_validate_missing_hostname(self):
        """Test validation rejects URL without hostname."""
        is_valid, url, error = self.processor._validate_webhook_url("https:///webhook")
        assert is_valid is False
        assert "hostname" in error.lower()

    def test_ssrf_protection_localhost(self):
        """Test SSRF protection blocks localhost."""
        is_valid, url, error = self.processor._validate_webhook_url("https://127.0.0.1/webhook")
        assert is_valid is False
        assert "blocked" in error.lower() or "private" in error.lower()

    def test_ssrf_protection_localhost_hostname(self):
        """Test SSRF protection blocks localhost hostname."""
        is_valid, url, error = self.processor._validate_webhook_url("https://localhost/webhook")
        assert is_valid is False
        assert "blocked" in error.lower() or "private" in error.lower()

    def test_ssrf_protection_private_class_a(self):
        """Test SSRF protection blocks private class A addresses."""
        is_valid, url, error = self.processor._validate_webhook_url("https://10.0.0.1/webhook")
        assert is_valid is False
        assert "blocked" in error.lower() or "private" in error.lower()

    def test_ssrf_protection_private_class_b(self):
        """Test SSRF protection blocks private class B addresses."""
        is_valid, url, error = self.processor._validate_webhook_url("https://172.16.0.1/webhook")
        assert is_valid is False
        assert "blocked" in error.lower() or "private" in error.lower()

    def test_ssrf_protection_private_class_c(self):
        """Test SSRF protection blocks private class C addresses."""
        is_valid, url, error = self.processor._validate_webhook_url("https://192.168.1.1/webhook")
        assert is_valid is False
        assert "blocked" in error.lower() or "private" in error.lower()

    def test_ssrf_protection_link_local(self):
        """Test SSRF protection blocks link-local addresses."""
        is_valid, url, error = self.processor._validate_webhook_url("https://169.254.1.1/webhook")
        assert is_valid is False
        assert "blocked" in error.lower() or "private" in error.lower()

    def test_validate_url_with_port(self):
        """Test validation of URL with valid port."""
        is_valid, url, error = self.processor._validate_webhook_url("https://n8n.example.com:8080/webhook")
        assert is_valid is True
        assert ":8080" in url

    def test_validate_url_with_query_string(self):
        """Test validation preserves query string."""
        is_valid, url, error = self.processor._validate_webhook_url("https://n8n.example.com/webhook?token=abc")
        assert is_valid is True
        assert "?token=abc" in url

    def test_validate_url_strips_whitespace(self):
        """Test validation strips leading/trailing whitespace."""
        is_valid, url, error = self.processor._validate_webhook_url("  https://n8n.example.com/webhook  ")
        assert is_valid is True
        assert url == "https://n8n.example.com/webhook"


class TestResponseSanitization:
    """Tests for response sanitization security features."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.ai.rag_processor import RagProcessor
        with patch.dict('os.environ', {'N8N_URL': '', 'N8N_AUTHORIZATION_SECRET': ''}):
            with patch('src.ai.rag_processor.load_dotenv'):
                self.processor = RagProcessor(Mock())

    def test_sanitize_empty_response(self):
        """Test sanitization of empty response."""
        result = self.processor._sanitize_response("")
        assert result == ""

    def test_sanitize_none_response(self):
        """Test sanitization of None response."""
        result = self.processor._sanitize_response(None)
        assert result == ""

    def test_sanitize_normal_text(self):
        """Test sanitization preserves normal text."""
        text = "This is a normal response with medical information."
        result = self.processor._sanitize_response(text)
        assert result == text

    def test_sanitize_removes_script_tags(self):
        """Test sanitization removes script tags."""
        text = "Normal text<script>alert('xss')</script>More text"
        result = self.processor._sanitize_response(text)
        assert "<script" not in result.lower()
        assert "alert" not in result

    def test_sanitize_removes_event_handlers(self):
        """Test sanitization removes event handlers."""
        text = "<div onclick=alert(1)>Content</div>"
        result = self.processor._sanitize_response(text)
        assert "onclick" not in result.lower()

    def test_sanitize_removes_iframe(self):
        """Test sanitization removes iframes."""
        text = "Before<iframe src='evil.com'></iframe>After"
        result = self.processor._sanitize_response(text)
        assert "<iframe" not in result.lower()

    def test_sanitize_removes_object_tags(self):
        """Test sanitization removes object tags."""
        text = "Text<object data='evil.swf'></object>More"
        result = self.processor._sanitize_response(text)
        assert "<object" not in result.lower()

    def test_sanitize_removes_embed_tags(self):
        """Test sanitization removes embed tags."""
        text = "Text<embed src='evil.swf'>More"
        result = self.processor._sanitize_response(text)
        assert "<embed" not in result.lower()

    def test_sanitize_removes_control_characters(self):
        """Test sanitization removes control characters."""
        text = "Normal\x00\x01\x02text"
        result = self.processor._sanitize_response(text)
        assert "\x00" not in result
        assert "\x01" not in result
        assert "\x02" not in result

    def test_sanitize_preserves_newlines_and_tabs(self):
        """Test sanitization preserves newlines and tabs."""
        text = "Line1\nLine2\tTabbed"
        result = self.processor._sanitize_response(text)
        assert "\n" in result
        assert "\t" in result

    def test_sanitize_removes_ansi_escape_sequences(self):
        """Test sanitization removes ANSI escape sequences."""
        text = "Normal\x1b[31mRed\x1b[0mText"
        result = self.processor._sanitize_response(text)
        assert "\x1b[" not in result

    def test_sanitize_truncates_long_response(self):
        """Test sanitization truncates excessively long responses."""
        text = "x" * 150000
        result = self.processor._sanitize_response(text)
        assert len(result) <= self.processor.MAX_RESPONSE_LENGTH + 50  # Allow for truncation message

    def test_sanitize_truncates_long_lines(self):
        """Test sanitization truncates excessively long lines."""
        long_line = "x" * 10000
        text = f"Short line\n{long_line}\nAnother short line"
        result = self.processor._sanitize_response(text)
        lines = result.split('\n')
        for line in lines:
            assert len(line) <= self.processor.MAX_LINE_LENGTH + 20  # Allow for truncation indicator


class TestMessageProcessing:
    """Tests for message processing functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.ai.rag_processor import RagProcessor
        self.mock_app = Mock()
        with patch.dict('os.environ', {'N8N_URL': 'https://n8n.example.com/webhook', 'N8N_AUTHORIZATION_SECRET': 'Bearer token'}):
            with patch('src.ai.rag_processor.load_dotenv'):
                self.processor = RagProcessor(self.mock_app)

    def test_process_message_blocks_when_already_processing(self):
        """Test that processing is blocked when already in progress."""
        self.processor.is_processing = True
        callback = Mock()

        self.processor.process_message("test query", callback)

        # Callback should NOT be called when blocked
        callback.assert_not_called()

    def test_process_message_shows_error_without_url(self):
        """Test error is shown when webhook URL is not configured."""
        self.processor.n8n_webhook_url = None
        callback = Mock()

        with patch.object(self.processor, '_display_error') as mock_error:
            self.processor.process_message("test query", callback)
            mock_error.assert_called_once()
            assert "not configured" in mock_error.call_args[0][0].lower()

    @patch('src.ai.rag_processor.threading.Thread')
    def test_process_message_starts_thread(self, mock_thread_class):
        """Test that processing starts a new thread."""
        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread

        self.processor.process_message("test query")

        mock_thread_class.assert_called_once()
        mock_thread.start.assert_called_once()

    @patch('src.ai.rag_processor.threading.Thread')
    def test_process_message_thread_is_daemon(self, mock_thread_class):
        """Test that processing thread is a daemon thread."""
        self.processor.process_message("test query")

        call_kwargs = mock_thread_class.call_args[1]
        assert call_kwargs.get('daemon') is True


class TestAsyncProcessing:
    """Tests for async message processing."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.ai.rag_processor import RagProcessor
        self.mock_app = Mock()
        self.mock_app.after = Mock()
        self.mock_app.rag_text = Mock()

        with patch.dict('os.environ', {'N8N_URL': 'https://n8n.example.com/webhook', 'N8N_AUTHORIZATION_SECRET': 'Bearer token'}):
            with patch('src.ai.rag_processor.load_dotenv'):
                self.processor = RagProcessor(self.mock_app)

    def _create_mock_session(self, mock_response):
        """Create a mock HTTP session that returns the given response."""
        mock_session = Mock()
        mock_session.post.return_value = mock_response
        return mock_session

    @patch('src.ai.rag_processor.get_http_client_manager')
    def test_async_processing_adds_user_message(self, mock_get_manager):
        """Test that user message is added to RAG tab."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"output": "test response"}'
        mock_response.json.return_value = {"output": "test response"}
        mock_get_manager.return_value.get_requests_session.return_value = self._create_mock_session(mock_response)

        with patch.object(self.processor, '_add_message_to_rag_tab') as mock_add:
            self.processor._process_message_async("test query", None)

            # First call should be for user message
            calls = mock_add.call_args_list
            assert any("User" in str(call) for call in calls)

    @patch('src.ai.rag_processor.get_http_client_manager')
    def test_async_processing_generates_session_id(self, mock_get_manager):
        """Test that session ID is generated and reused."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"output": "test"}'
        mock_response.json.return_value = {"output": "test"}
        mock_get_manager.return_value.get_requests_session.return_value = self._create_mock_session(mock_response)

        with patch.object(self.processor, '_add_message_to_rag_tab'):
            self.processor._process_message_async("query 1", None)
            session_id_1 = self.processor.session_id

            self.processor._process_message_async("query 2", None)
            session_id_2 = self.processor.session_id

            assert session_id_1 == session_id_2

    @patch('src.ai.rag_processor.get_http_client_manager')
    def test_async_processing_includes_auth_header(self, mock_get_manager):
        """Test that authorization header is included."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"output": "test"}'
        mock_response.json.return_value = {"output": "test"}
        mock_session = self._create_mock_session(mock_response)
        mock_get_manager.return_value.get_requests_session.return_value = mock_session

        with patch.object(self.processor, '_add_message_to_rag_tab'):
            self.processor._process_message_async("test query", None)

            call_kwargs = mock_session.post.call_args[1]
            headers = call_kwargs.get('headers', {})
            assert 'Authorization' in headers

    @patch('src.ai.rag_processor.get_http_client_manager')
    def test_async_processing_handles_list_response(self, mock_get_manager):
        """Test handling of list response format."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '[{"output": "list response"}]'
        mock_response.json.return_value = [{"output": "list response"}]
        mock_get_manager.return_value.get_requests_session.return_value = self._create_mock_session(mock_response)

        with patch.object(self.processor, '_add_message_to_rag_tab') as mock_add:
            self.processor._process_message_async("test query", None)

            # Check that the response was added
            calls = mock_add.call_args_list
            assert any("list response" in str(call) for call in calls)

    @patch('src.ai.rag_processor.get_http_client_manager')
    def test_async_processing_handles_dict_response(self, mock_get_manager):
        """Test handling of dict response format."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"output": "dict response"}'
        mock_response.json.return_value = {"output": "dict response"}
        mock_get_manager.return_value.get_requests_session.return_value = self._create_mock_session(mock_response)

        with patch.object(self.processor, '_add_message_to_rag_tab') as mock_add:
            self.processor._process_message_async("test query", None)

            calls = mock_add.call_args_list
            assert any("dict response" in str(call) for call in calls)

    @patch('src.ai.rag_processor.get_http_client_manager')
    def test_async_processing_handles_empty_response(self, mock_get_manager):
        """Test handling of empty response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = ""
        mock_get_manager.return_value.get_requests_session.return_value = self._create_mock_session(mock_response)

        with patch.object(self.processor, '_add_message_to_rag_tab') as mock_add:
            self.processor._process_message_async("test query", None)

            calls = mock_add.call_args_list
            assert any("didn't return" in str(call).lower() or "processed" in str(call).lower() for call in calls)

    @patch('src.ai.rag_processor.get_http_client_manager')
    def test_async_processing_handles_timeout(self, mock_get_manager):
        """Test handling of request timeout."""
        import requests
        mock_session = Mock()
        mock_session.post.side_effect = requests.exceptions.Timeout()
        mock_get_manager.return_value.get_requests_session.return_value = mock_session

        with patch.object(self.processor, '_display_error') as mock_error:
            self.processor._process_message_async("test query", None)

            mock_error.assert_called()
            assert "timed out" in mock_error.call_args[0][0].lower()

    @patch('src.ai.rag_processor.get_http_client_manager')
    def test_async_processing_handles_connection_error(self, mock_get_manager):
        """Test handling of connection error."""
        import requests
        mock_session = Mock()
        mock_session.post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        mock_get_manager.return_value.get_requests_session.return_value = mock_session

        with patch.object(self.processor, '_display_error') as mock_error:
            self.processor._process_message_async("test query", None)

            mock_error.assert_called()
            assert "error" in mock_error.call_args[0][0].lower()

    @patch('src.ai.rag_processor.get_http_client_manager')
    def test_async_processing_handles_json_decode_error(self, mock_get_manager):
        """Test handling of invalid JSON response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "not valid json {"
        mock_response.json.side_effect = json.JSONDecodeError("test", "test", 0)
        mock_get_manager.return_value.get_requests_session.return_value = self._create_mock_session(mock_response)

        with patch.object(self.processor, '_add_message_to_rag_tab') as mock_add:
            self.processor._process_message_async("test query", None)

            # Should handle gracefully and show the raw text
            calls = mock_add.call_args_list
            assert len(calls) >= 1

    @patch('src.ai.rag_processor.get_http_client_manager')
    def test_async_processing_resets_is_processing_flag(self, mock_get_manager):
        """Test that is_processing flag is reset after completion."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"output": "test"}'
        mock_response.json.return_value = {"output": "test"}
        mock_get_manager.return_value.get_requests_session.return_value = self._create_mock_session(mock_response)

        self.processor.is_processing = True

        with patch.object(self.processor, '_add_message_to_rag_tab'):
            self.processor._process_message_async("test query", None)

        assert self.processor.is_processing is False

    @patch('src.ai.rag_processor.get_http_client_manager')
    def test_async_processing_calls_callback(self, mock_get_manager):
        """Test that callback is called after processing."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"output": "test"}'
        mock_response.json.return_value = {"output": "test"}
        mock_get_manager.return_value.get_requests_session.return_value = self._create_mock_session(mock_response)

        callback = Mock()

        with patch.object(self.processor, '_add_message_to_rag_tab'):
            self.processor._process_message_async("test query", callback)

        self.mock_app.after.assert_called()

    @patch('src.ai.rag_processor.get_http_client_manager')
    def test_async_processing_strips_auth_quotes(self, mock_get_manager):
        """Test that auth header has quotes stripped."""
        self.processor.n8n_auth_header = "'Bearer token'"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"output": "test"}'
        mock_response.json.return_value = {"output": "test"}
        mock_session = self._create_mock_session(mock_response)
        mock_get_manager.return_value.get_requests_session.return_value = mock_session

        with patch.object(self.processor, '_add_message_to_rag_tab'):
            self.processor._process_message_async("test query", None)

            call_kwargs = mock_session.post.call_args[1]
            headers = call_kwargs.get('headers', {})
            assert headers.get('Authorization') == 'Bearer token'


class TestMarkdownRendering:
    """Tests for markdown rendering functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.ai.rag_processor import RagProcessor

        self.mock_app = Mock()
        self.mock_text = Mock()
        self.mock_app.rag_text = self.mock_text

        with patch.dict('os.environ', {'N8N_URL': '', 'N8N_AUTHORIZATION_SECRET': ''}):
            with patch('src.ai.rag_processor.load_dotenv'):
                self.processor = RagProcessor(self.mock_app)

    def test_render_h1_header(self):
        """Test rendering of H1 header."""
        self.processor._render_markdown("# Header 1")

        # Check that insert was called with h1 tag
        calls = self.mock_text.insert.call_args_list
        assert any("h1" in str(call) for call in calls)

    def test_render_h2_header(self):
        """Test rendering of H2 header."""
        self.processor._render_markdown("## Header 2")

        calls = self.mock_text.insert.call_args_list
        assert any("h2" in str(call) for call in calls)

    def test_render_h3_header(self):
        """Test rendering of H3 header."""
        self.processor._render_markdown("### Header 3")

        calls = self.mock_text.insert.call_args_list
        assert any("h3" in str(call) for call in calls)

    def test_render_bold_text(self):
        """Test rendering of bold text."""
        self.processor._render_markdown("This is **bold** text")

        calls = self.mock_text.insert.call_args_list
        assert any("bold" in str(call) for call in calls)

    def test_render_bullet_point_dash(self):
        """Test rendering of bullet point with dash."""
        self.processor._render_markdown("- Bullet item")

        calls = self.mock_text.insert.call_args_list
        assert any("bullet" in str(call) for call in calls)

    def test_render_bullet_point_asterisk(self):
        """Test rendering of bullet point with asterisk."""
        self.processor._render_markdown("* Bullet item")

        calls = self.mock_text.insert.call_args_list
        assert any("bullet" in str(call) for call in calls)

    def test_render_numbered_list(self):
        """Test rendering of numbered list."""
        self.processor._render_markdown("1. First item")

        calls = self.mock_text.insert.call_args_list
        assert any("numbered" in str(call) for call in calls)

    def test_render_code_block(self):
        """Test rendering of code block."""
        self.processor._render_markdown("```python\ncode here\n```")

        calls = self.mock_text.insert.call_args_list
        assert any("code" in str(call) for call in calls)

    def test_render_plain_text(self):
        """Test rendering of plain text."""
        self.processor._render_markdown("Just plain text")

        calls = self.mock_text.insert.call_args_list
        assert any("message" in str(call) for call in calls)

    def test_render_mixed_content(self):
        """Test rendering of mixed markdown content."""
        content = """# Title

This is a paragraph with **bold** text.

## Section

- Item 1
- Item 2

1. First
2. Second
"""
        self.processor._render_markdown(content)

        # Should have multiple different tag types
        calls = self.mock_text.insert.call_args_list
        call_str = str(calls)
        assert "h1" in call_str or "h2" in call_str
        assert len(calls) > 5  # Should have multiple inserts

    def test_render_sanitizes_input(self):
        """Test that markdown rendering sanitizes input."""
        with patch.object(self.processor, '_sanitize_response') as mock_sanitize:
            mock_sanitize.return_value = "sanitized text"
            self.processor._render_markdown("<script>evil</script>Normal text")
            mock_sanitize.assert_called_once()


class TestUIHelpers:
    """Tests for UI helper methods."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.ai.rag_processor import RagProcessor

        self.mock_app = Mock()
        self.mock_text = Mock()
        self.mock_app.rag_text = self.mock_text
        self.mock_app.after = Mock(side_effect=lambda delay, func: func())

        with patch.dict('os.environ', {'N8N_URL': '', 'N8N_AUTHORIZATION_SECRET': ''}):
            with patch('src.ai.rag_processor.load_dotenv'):
                self.processor = RagProcessor(self.mock_app)

    def test_add_message_without_rag_text(self):
        """Test adding message when rag_text doesn't exist."""
        del self.mock_app.rag_text

        # Should not raise
        self.processor._add_message_to_rag_tab("User", "test message")

    def test_add_user_message(self):
        """Test adding user message to RAG tab."""
        self.mock_text.index.return_value = "1.0"

        self.processor._add_message_to_rag_tab("User", "test message")

        # Should insert the message
        assert self.mock_text.insert.called

    def test_add_assistant_message_renders_markdown(self):
        """Test adding assistant message renders markdown."""
        self.mock_text.index.return_value = "1.0"

        with patch.object(self.processor, '_render_markdown') as mock_render:
            with patch.object(self.processor, '_add_copy_button'):
                self.processor._add_message_to_rag_tab("RAG Assistant", "**bold** response")
                mock_render.assert_called_once()

    def test_add_assistant_message_adds_copy_button(self):
        """Test adding assistant message includes copy button."""
        self.mock_text.index.return_value = "1.0"

        with patch.object(self.processor, '_render_markdown'):
            with patch.object(self.processor, '_add_copy_button') as mock_copy:
                self.processor._add_message_to_rag_tab("RAG Assistant", "response text")
                mock_copy.assert_called_once()

    def test_display_error(self):
        """Test error display."""
        with patch.object(self.processor, '_add_message_to_rag_tab') as mock_add:
            self.processor._display_error("Test error message")
            mock_add.assert_called_once_with("System Error", "Test error message")


class TestCopyToClipboard:
    """Tests for clipboard functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.ai.rag_processor import RagProcessor

        self.mock_app = Mock()

        with patch.dict('os.environ', {'N8N_URL': '', 'N8N_AUTHORIZATION_SECRET': ''}):
            with patch('src.ai.rag_processor.load_dotenv'):
                self.processor = RagProcessor(self.mock_app)

    def test_copy_to_clipboard_success(self):
        """Test successful copy to clipboard."""
        self.mock_app.status_manager = Mock()

        self.processor._copy_to_clipboard("Test text")

        self.mock_app.clipboard_clear.assert_called_once()
        self.mock_app.clipboard_append.assert_called_once_with("Test text")
        self.mock_app.update.assert_called_once()

    def test_copy_to_clipboard_shows_success_message(self):
        """Test that success message is shown."""
        self.mock_app.status_manager = Mock()

        self.processor._copy_to_clipboard("Test text")

        self.mock_app.status_manager.success.assert_called_once()

    def test_copy_to_clipboard_handles_error(self):
        """Test error handling during clipboard copy."""
        self.mock_app.clipboard_clear.side_effect = Exception("Clipboard error")
        self.mock_app.status_manager = Mock()

        # Should not raise
        self.processor._copy_to_clipboard("Test text")

        self.mock_app.status_manager.error.assert_called_once()

    def test_copy_to_clipboard_without_status_manager(self):
        """Test copy works without status manager."""
        # Remove status_manager attribute
        delattr(self.mock_app, 'status_manager') if hasattr(self.mock_app, 'status_manager') else None

        # Should not raise
        self.processor._copy_to_clipboard("Test text")


class TestHistoryManagement:
    """Tests for history management."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.ai.rag_processor import RagProcessor

        self.mock_app = Mock()
        self.mock_text = Mock()
        self.mock_app.rag_text = self.mock_text
        self.mock_app.after = Mock(side_effect=lambda delay, func: func())

        with patch.dict('os.environ', {'N8N_URL': '', 'N8N_AUTHORIZATION_SECRET': ''}):
            with patch('src.ai.rag_processor.load_dotenv'):
                self.processor = RagProcessor(self.mock_app)

    def test_clear_history(self):
        """Test clearing history."""
        self.processor.clear_history()

        self.mock_text.delete.assert_called_once_with("1.0", "end")

    def test_clear_history_adds_welcome_message(self):
        """Test that clearing history adds welcome message."""
        self.processor.clear_history()

        # Should have multiple inserts for welcome content
        assert self.mock_text.insert.called

    def test_clear_history_without_rag_text(self):
        """Test clearing history when rag_text doesn't exist."""
        del self.mock_app.rag_text

        # Should not raise
        self.processor.clear_history()


class TestSessionManagement:
    """Tests for session ID management."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.ai.rag_processor import RagProcessor

        self.mock_app = Mock()
        self.mock_app.after = Mock()
        self.mock_app.rag_text = Mock()

        with patch.dict('os.environ', {'N8N_URL': 'https://test.com/webhook', 'N8N_AUTHORIZATION_SECRET': 'token'}):
            with patch('src.ai.rag_processor.load_dotenv'):
                self.processor = RagProcessor(self.mock_app)

    def _create_mock_session(self, mock_response):
        """Create a mock HTTP session that returns the given response."""
        mock_session = Mock()
        mock_session.post.return_value = mock_response
        return mock_session

    @patch('src.ai.rag_processor.get_http_client_manager')
    def test_session_id_generated_on_first_request(self, mock_get_manager):
        """Test that session ID is generated on first request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"output": "test"}'
        mock_response.json.return_value = {"output": "test"}
        mock_get_manager.return_value.get_requests_session.return_value = self._create_mock_session(mock_response)

        assert not hasattr(self.processor, 'session_id') or self.processor.session_id is None

        with patch.object(self.processor, '_add_message_to_rag_tab'):
            self.processor._process_message_async("test", None)

        assert hasattr(self.processor, 'session_id')
        assert self.processor.session_id is not None

    @patch('src.ai.rag_processor.get_http_client_manager')
    def test_session_id_sent_in_payload(self, mock_get_manager):
        """Test that session ID is included in request payload."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"output": "test"}'
        mock_response.json.return_value = {"output": "test"}
        mock_session = self._create_mock_session(mock_response)
        mock_get_manager.return_value.get_requests_session.return_value = mock_session

        with patch.object(self.processor, '_add_message_to_rag_tab'):
            self.processor._process_message_async("test", None)

        call_kwargs = mock_session.post.call_args[1]
        payload = call_kwargs.get('json', {})
        assert 'sessionId' in payload

    @patch('src.ai.rag_processor.get_http_client_manager')
    def test_session_id_is_uuid_format(self, mock_get_manager):
        """Test that session ID is in UUID format."""
        import uuid

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"output": "test"}'
        mock_response.json.return_value = {"output": "test"}
        mock_get_manager.return_value.get_requests_session.return_value = self._create_mock_session(mock_response)

        with patch.object(self.processor, '_add_message_to_rag_tab'):
            self.processor._process_message_async("test", None)

        # Should be valid UUID format
        try:
            uuid.UUID(self.processor.session_id)
        except ValueError:
            pytest.fail("Session ID is not a valid UUID")


class TestDangerousPatterns:
    """Tests for dangerous pattern detection."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.ai.rag_processor import RagProcessor
        with patch.dict('os.environ', {'N8N_URL': '', 'N8N_AUTHORIZATION_SECRET': ''}):
            with patch('src.ai.rag_processor.load_dotenv'):
                self.processor = RagProcessor(Mock())

    def test_pattern_removes_script_with_content(self):
        """Test removal of script tags with content."""
        text = "Before<script type='text/javascript'>alert('xss');</script>After"
        result = self.processor._sanitize_response(text)
        assert "script" not in result.lower()
        assert "alert" not in result
        assert "Before" in result
        assert "After" in result

    def test_pattern_removes_multiline_script(self):
        """Test removal of multiline script tags."""
        text = """Before
<script>
function evil() {
    document.cookie;
}
</script>
After"""
        result = self.processor._sanitize_response(text)
        assert "script" not in result.lower()
        assert "Before" in result
        assert "After" in result

    def test_pattern_removes_onerror_handler(self):
        """Test removal of onerror event handler."""
        text = '<img src="x" onerror="alert(1)">'
        result = self.processor._sanitize_response(text)
        assert "onerror" not in result.lower()

    def test_pattern_removes_onload_handler(self):
        """Test removal of onload event handler."""
        text = '<body onload="evil()">'
        result = self.processor._sanitize_response(text)
        assert "onload" not in result.lower()


@pytest.fixture(autouse=True)
def reset_processor_state():
    """Reset processor state before each test."""
    yield
    # Cleanup after test if needed

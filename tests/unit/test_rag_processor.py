"""
Unit tests for RagProcessor.

Tests cover local RAG functionality, response parsing,
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

    @patch.dict('os.environ', {'NEON_DATABASE_URL': 'postgresql://user:pass@host/db'})
    @patch('src.ai.rag_processor.load_dotenv')
    def test_initialization_with_local_rag(self, mock_dotenv):
        """Test initialization with local RAG configured."""
        from src.ai.rag_processor import RagProcessor

        mock_app = Mock()
        processor = RagProcessor(mock_app)

        assert processor.app is mock_app
        assert processor.is_processing is False
        assert processor.use_local_rag is True
        assert processor.get_rag_mode() == "local"

    @patch.dict('os.environ', {}, clear=True)
    @patch('src.ai.rag_processor.load_dotenv')
    def test_initialization_without_env(self, mock_dotenv):
        """Test initialization without environment variables."""
        # Clear any existing env vars for our test
        import os
        os.environ.pop('NEON_DATABASE_URL', None)

        from src.ai.rag_processor import RagProcessor

        mock_app = Mock()
        processor = RagProcessor(mock_app)

        assert processor.use_local_rag is False
        assert processor.get_rag_mode() == "none"


class TestResponseSanitization:
    """Tests for response sanitization security features."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.ai.rag_processor import RagProcessor
        with patch.dict('os.environ', {}, clear=True):
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
        with patch.dict('os.environ', {'NEON_DATABASE_URL': 'postgresql://user:pass@host/db'}):
            with patch('src.ai.rag_processor.load_dotenv'):
                self.processor = RagProcessor(self.mock_app)

    def test_process_message_blocks_when_already_processing(self):
        """Test that processing is blocked when already in progress."""
        self.processor.is_processing = True
        callback = Mock()

        self.processor.process_message("test query", callback)

        # Callback should NOT be called when blocked
        callback.assert_not_called()

    def test_process_message_shows_error_without_config(self):
        """Test error is shown when RAG system is not configured."""
        self.processor.use_local_rag = False
        callback = Mock()

        with patch.object(self.processor, '_display_error') as mock_error:
            self.processor.process_message("test query", callback)
            mock_error.assert_called_once()
            error_msg = mock_error.call_args[0][0].lower()
            assert "not configured" in error_msg or "neon_database_url" in error_msg

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


class TestMarkdownRendering:
    """Tests for markdown rendering functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.ai.rag_processor import RagProcessor

        self.mock_app = Mock()
        self.mock_text = Mock()
        self.mock_app.rag_text = self.mock_text

        with patch.dict('os.environ', {}, clear=True):
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

        with patch.dict('os.environ', {}, clear=True):
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

        with patch.dict('os.environ', {}, clear=True):
            with patch('src.ai.rag_processor.load_dotenv'):
                self.processor = RagProcessor(self.mock_app)

    def test_copy_to_clipboard_success(self):
        """Test successful copy to clipboard via pyperclip."""
        self.mock_app.status_manager = Mock()

        with patch('pyperclip.copy') as mock_pyperclip:
            self.processor._copy_to_clipboard("Test text")
            mock_pyperclip.assert_called_once_with("Test text")

    def test_copy_to_clipboard_shows_success_message(self):
        """Test that success message is shown."""
        self.mock_app.status_manager = Mock()

        with patch('pyperclip.copy'):
            self.processor._copy_to_clipboard("Test text")

        self.mock_app.status_manager.success.assert_called_once()

    def test_copy_to_clipboard_handles_error(self):
        """Test error handling during clipboard copy."""
        import tkinter as tk
        self.mock_app.status_manager = Mock()

        with patch('pyperclip.copy', side_effect=ImportError("Clipboard error")):
            # pyperclip fails, falls back to tkinter which also fails
            self.mock_app.clipboard_clear.side_effect = tk.TclError("Tk error")
            # Should not raise
            self.processor._copy_to_clipboard("Test text")

        self.mock_app.status_manager.error.assert_called_once()

    def test_copy_to_clipboard_without_status_manager(self):
        """Test copy works without status manager."""
        # Remove status_manager attribute
        delattr(self.mock_app, 'status_manager') if hasattr(self.mock_app, 'status_manager') else None

        with patch('pyperclip.copy'):
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

        with patch.dict('os.environ', {}, clear=True):
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


class TestDangerousPatterns:
    """Tests for dangerous pattern detection."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.ai.rag_processor import RagProcessor
        with patch.dict('os.environ', {}, clear=True):
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

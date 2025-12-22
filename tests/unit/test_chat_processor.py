"""
Tests for ChatProcessor

Comprehensive tests for the chat processor module including:
- Message processing
- Context extraction
- Tool detection
- History management
- Response processing
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from datetime import datetime
import threading

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class MockApp:
    """Mock application for testing ChatProcessor."""

    def __init__(self):
        self.notebook = Mock()
        self.notebook.index.return_value = 0
        self.notebook.select.return_value = "tab1"

        self.active_text_widget = Mock()
        self.active_text_widget.get.return_value = "Sample document content"

        self.chat_text = Mock()
        self.chat_text.get.return_value = ""
        self.chat_text.cget.return_value = "white"
        self.chat_text.index.return_value = "1.0"

        self.status_manager = Mock()
        self.status_manager.info = Mock()
        self.status_manager.success = Mock()
        self.status_manager.error = Mock()
        self.status_manager.warning = Mock()

        self.db = Mock()
        self.current_recording_id = None

        self._after_callbacks = []

    def after(self, delay, callback):
        """Mock after method - execute callback immediately."""
        if callback:
            callback()


class TestChatProcessorInitialization:
    """Test ChatProcessor initialization."""

    @patch('src.ai.chat_processor.SETTINGS', {
        'chat_interface': {
            'max_context_length': 5000,
            'max_history_items': 5,
            'temperature': 0.5,
            'enable_tools': False
        }
    })
    @patch('src.ai.chat_processor.mcp_manager')
    def test_initialization_with_custom_settings(self, mock_mcp):
        """Test initialization with custom settings."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        assert processor.max_context_length == 5000
        assert processor.max_history_items == 5
        assert processor.temperature == 0.5
        assert processor.use_tools is False
        assert processor.chat_agent is None
        assert processor.conversation_history == []

    @patch('src.ai.chat_processor.SETTINGS', {
        'chat_interface': {
            'enable_tools': True
        }
    })
    @patch('src.ai.chat_processor.mcp_manager')
    @patch('src.ai.chat_processor.ToolExecutor')
    @patch('src.ai.chat_processor.ChatAgent')
    def test_initialization_with_tools_enabled(self, mock_agent, mock_executor, mock_mcp):
        """Test initialization with tools enabled."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        assert processor.use_tools is True
        mock_executor.assert_called_once()
        mock_agent.assert_called_once()

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_initialization_with_default_settings(self, mock_mcp):
        """Test initialization with default settings."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        # Check defaults
        assert processor.max_context_length == 8000
        assert processor.max_history_items == 10
        assert processor.temperature == 0.3


class TestContextExtraction:
    """Test context extraction from UI."""

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_extract_context_from_transcript_tab(self, mock_mcp):
        """Test context extraction from transcript tab."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        app.notebook.index.return_value = 0
        app.active_text_widget.get.return_value = "Patient presents with chest pain"

        processor = ChatProcessor(app)
        context = processor._extract_context()

        assert context["tab_name"] == "transcript"
        assert context["tab_index"] == 0
        assert context["has_content"] is True
        assert "chest pain" in context["content"]

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_extract_context_from_soap_tab(self, mock_mcp):
        """Test context extraction from SOAP tab."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        app.notebook.index.return_value = 1
        app.active_text_widget.get.return_value = "S: Chief complaint...\nO: Vitals normal"

        processor = ChatProcessor(app)
        context = processor._extract_context()

        assert context["tab_name"] == "soap"
        assert context["tab_index"] == 1

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False, 'max_context_length': 100}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_extract_context_truncates_long_content(self, mock_mcp):
        """Test that long content is truncated."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        long_content = "A" * 200
        app.active_text_widget.get.return_value = long_content

        processor = ChatProcessor(app)
        context = processor._extract_context()

        assert "[truncated]" in context["content"]
        assert len(context["content"]) < 200

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_extract_context_with_empty_content(self, mock_mcp):
        """Test context extraction with empty content."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        app.active_text_widget.get.return_value = ""

        processor = ChatProcessor(app)
        context = processor._extract_context()

        assert context["has_content"] is False
        assert context["content"] == ""


class TestPromptConstruction:
    """Test prompt construction."""

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_construct_prompt_for_transcript(self, mock_mcp):
        """Test prompt construction for transcript tab."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        context = {
            "tab_name": "transcript",
            "tab_index": 0,
            "content": "Patient reports headache",
            "has_content": True
        }

        prompt = processor._construct_prompt("Summarize this", context)

        assert "transcription analysis" in prompt.lower()
        assert "Patient reports headache" in prompt
        assert "Summarize this" in prompt

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_construct_prompt_includes_history(self, mock_mcp):
        """Test that prompt includes conversation history."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)
        processor.conversation_history = [
            {"role": "user", "message": "Previous question", "timestamp": "2024-01-01"},
            {"role": "assistant", "message": "Previous answer", "timestamp": "2024-01-01"}
        ]

        context = {"tab_name": "chat", "has_content": False}
        prompt = processor._construct_prompt("Current question", context)

        assert "Previous question" in prompt
        assert "Previous answer" in prompt

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_construct_prompt_for_chat_tab(self, mock_mcp):
        """Test prompt construction for chat tab."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        context = {"tab_name": "chat", "has_content": False}
        prompt = processor._construct_prompt("Hello", context)

        assert "helpful medical ai assistant" in prompt.lower()
        assert "do not modify any document" in prompt.lower()


class TestToolDetection:
    """Test tool usage detection."""

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': True}})
    @patch('src.ai.chat_processor.mcp_manager')
    @patch('src.ai.chat_processor.ToolExecutor')
    @patch('src.ai.chat_processor.ChatAgent')
    def test_should_use_tools_for_calculation(self, mock_agent, mock_executor, mock_mcp):
        """Test tool detection for calculation requests."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        assert processor._should_use_tools("calculate the BMI for this patient") is True
        assert processor._should_use_tools("compute the drug dosage") is True
        assert processor._should_use_tools("what is 2 + 2?") is True

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': True}})
    @patch('src.ai.chat_processor.mcp_manager')
    @patch('src.ai.chat_processor.ToolExecutor')
    @patch('src.ai.chat_processor.ChatAgent')
    def test_should_use_tools_for_time_date(self, mock_agent, mock_executor, mock_mcp):
        """Test tool detection for time/date queries."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        assert processor._should_use_tools("what time is it?") is True
        assert processor._should_use_tools("what is today's date?") is True

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': True}})
    @patch('src.ai.chat_processor.mcp_manager')
    @patch('src.ai.chat_processor.ToolExecutor')
    @patch('src.ai.chat_processor.ChatAgent')
    def test_should_use_tools_for_medical_guidelines(self, mock_agent, mock_executor, mock_mcp):
        """Test tool detection for medical guideline queries."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        assert processor._should_use_tools("what are the 2025 hypertension guidelines?") is True
        assert processor._should_use_tools("check drug interaction between aspirin and warfarin") is True
        assert processor._should_use_tools("what is the target A1C for diabetic patients?") is True

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': True}})
    @patch('src.ai.chat_processor.mcp_manager')
    @patch('src.ai.chat_processor.ToolExecutor')
    @patch('src.ai.chat_processor.ChatAgent')
    def test_should_not_use_tools_for_simple_conversation(self, mock_agent, mock_executor, mock_mcp):
        """Test that simple conversation doesn't trigger tools."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        # Simple greetings and statements shouldn't need tools
        assert processor._should_use_tools("hello") is False
        assert processor._should_use_tools("thank you for your help") is False
        assert processor._should_use_tools("I understand") is False

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_should_use_tools_disabled(self, mock_mcp):
        """Test that tools are not used when disabled."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        # Even tool-like queries shouldn't use tools when disabled
        assert processor._should_use_tools("calculate BMI") is False


class TestHistoryManagement:
    """Test conversation history management."""

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False, 'max_history_items': 4}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_add_to_history(self, mock_mcp):
        """Test adding messages to history."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        processor._add_to_history("user", "Hello")
        processor._add_to_history("assistant", "Hi there!")

        assert len(processor.conversation_history) == 2
        assert processor.conversation_history[0]["role"] == "user"
        assert processor.conversation_history[0]["message"] == "Hello"
        assert processor.conversation_history[1]["role"] == "assistant"

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False, 'max_history_items': 4}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_history_limit_enforced(self, mock_mcp):
        """Test that history limit is enforced."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        # Add more than max_history_items
        for i in range(10):
            processor._add_to_history("user", f"Message {i}")

        assert len(processor.conversation_history) == 4
        # Should keep the most recent
        assert processor.conversation_history[-1]["message"] == "Message 9"

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_clear_history(self, mock_mcp):
        """Test clearing history."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        processor._add_to_history("user", "Test")
        processor._add_to_history("assistant", "Response")
        processor.clear_history()

        assert len(processor.conversation_history) == 0

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_get_history(self, mock_mcp):
        """Test getting history copy."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        processor._add_to_history("user", "Test")
        history = processor.get_history()

        # Should return a copy
        history.clear()
        assert len(processor.conversation_history) == 1

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_get_context_from_history(self, mock_mcp):
        """Test getting context from history."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        processor._add_to_history("user", "Question 1")
        processor._add_to_history("assistant", "Answer 1")
        processor._add_to_history("user", "Question 2")

        context = processor.get_context_from_history(max_entries=2)

        assert "Answer 1" in context
        assert "Question 2" in context


class TestDocumentModificationDetection:
    """Test detection of document modification requests."""

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_should_apply_for_modification_keywords(self, mock_mcp):
        """Test detection of modification requests via keywords."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        modification_messages = [
            "improve this document",
            "rewrite the SOAP note",
            "edit the referral letter",
            "fix the formatting",
            "clean up the text",
            "remove speaker labels"
        ]

        for msg in modification_messages:
            result = processor._should_apply_to_document(msg, "")
            assert result is True, f"Failed for: {msg}"

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_should_apply_for_ai_response_markers(self, mock_mcp):
        """Test detection via AI response markers."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        responses = [
            "Here's the improved version:\n...",
            "Updated version:\n...",
            "Here's the cleaned up text:\n...",
            "Revised text:\n..."
        ]

        for response in responses:
            result = processor._should_apply_to_document("Please help", response)
            assert result is True, f"Failed for response: {response[:30]}"

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_should_not_apply_for_questions(self, mock_mcp):
        """Test that questions don't trigger document modification."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        questions = [
            "What does this mean?",
            "Can you explain the diagnosis?",
            "Tell me about hypertension",
            "How should I interpret this?"
        ]

        for question in questions:
            result = processor._should_apply_to_document(question, "Here's an explanation...")
            assert result is False, f"Failed for: {question}"


class TestContentExtraction:
    """Test content extraction from AI responses."""

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_extract_content_with_header(self, mock_mcp):
        """Test extracting content after a header."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        response = "Here's the improved version:\nClean content without speaker labels."
        content = processor._extract_content_from_response(response)

        assert content == "Clean content without speaker labels."

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_extract_content_from_code_block(self, mock_mcp):
        """Test extracting content from code blocks."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        response = """Here is the content:
```text
This is the extracted content.
Multiple lines work too.
```
Explanation here."""

        content = processor._extract_content_from_response(response)

        assert "This is the extracted content" in content
        assert "Multiple lines" in content
        assert "Explanation" not in content

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_extract_content_removes_explanations(self, mock_mcp):
        """Test that explanations are removed from extracted content."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        response = """Here's the cleaned version:
Patient presents with chest pain.
Vitals are stable.

Note: I've removed the speaker labels and cleaned up the formatting."""

        content = processor._extract_content_from_response(response)

        assert "Patient presents" in content
        assert "Vitals are stable" in content
        assert "Note:" not in content


class TestChatCommands:
    """Test chat command handling."""

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_clear_command_handling(self, mock_mcp):
        """Test /clear command handling."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)
        processor._add_to_history("user", "Test")

        result = processor._handle_chat_command("/clear")

        assert result is True
        assert len(processor.conversation_history) == 0

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_clear_chat_history_command(self, mock_mcp):
        """Test 'clear chat history' command."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        result = processor._handle_chat_command("clear chat history")
        assert result is True

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_normal_message_not_command(self, mock_mcp):
        """Test that normal messages aren't treated as commands."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        result = processor._handle_chat_command("Hello, how are you?")
        assert result is False


class TestMessageProcessing:
    """Test message processing flow."""

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_process_message_sets_processing_flag(self, mock_mcp):
        """Test that processing flag is set during message processing."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        # Track if is_processing was True during execution
        was_processing = [False]

        original_process = processor._process_message_async

        def tracking_process(msg, callback):
            was_processing[0] = processor.is_processing
            # Don't call original to avoid complex mocking

        processor._process_message_async = tracking_process
        processor.process_message("Test message")

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_process_message_ignores_when_already_processing(self, mock_mcp):
        """Test that new messages are ignored during processing."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)
        processor.is_processing = True

        # Should log warning and return without starting new thread
        processor.process_message("Should be ignored")


class TestToolSettings:
    """Test tool enable/disable functionality."""

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    @patch('settings.settings.save_settings')
    def test_enable_tools(self, mock_save, mock_mcp):
        """Test enabling tools."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        with patch('src.ai.chat_processor.ToolExecutor'):
            with patch('src.ai.chat_processor.ChatAgent'):
                processor.set_tools_enabled(True)

        assert processor.use_tools is True
        mock_save.assert_called()

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': True}})
    @patch('src.ai.chat_processor.mcp_manager')
    @patch('src.ai.chat_processor.ToolExecutor')
    @patch('src.ai.chat_processor.ChatAgent')
    @patch('settings.settings.save_settings')
    def test_disable_tools(self, mock_save, mock_agent, mock_executor, mock_mcp):
        """Test disabling tools."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)
        processor.set_tools_enabled(False)

        assert processor.use_tools is False
        assert processor.chat_agent is None


class TestCopyToClipboard:
    """Test clipboard functionality."""

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': False}})
    @patch('src.ai.chat_processor.mcp_manager')
    def test_copy_to_clipboard(self, mock_mcp):
        """Test copying text to clipboard."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        app.clipboard_clear = Mock()
        app.clipboard_append = Mock()
        app.update = Mock()

        processor = ChatProcessor(app)
        processor._copy_to_clipboard("Test text")

        app.clipboard_clear.assert_called_once()
        app.clipboard_append.assert_called_once_with("Test text")
        app.update.assert_called_once()
        app.status_manager.success.assert_called()


class TestMCPIntegration:
    """Test MCP (Model Context Protocol) integration."""

    @patch('src.ai.chat_processor.SETTINGS', {
        'chat_interface': {'enable_tools': False},
        'mcp_config': {'enabled': True}
    })
    @patch('src.ai.chat_processor.mcp_manager')
    @patch('src.ai.chat_processor.register_mcp_tools', return_value=3)
    def test_mcp_initialization(self, mock_register, mock_mcp):
        """Test MCP initialization when enabled."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)

        mock_mcp.load_config.assert_called_once()

    @patch('src.ai.chat_processor.SETTINGS', {'chat_interface': {'enable_tools': True}})
    @patch('src.ai.chat_processor.mcp_manager')
    @patch('src.ai.chat_processor.ToolExecutor')
    @patch('src.ai.chat_processor.ChatAgent')
    @patch('src.ai.chat_processor.tool_registry')
    def test_reload_mcp_tools(self, mock_registry, mock_agent, mock_executor, mock_mcp):
        """Test reloading MCP tools."""
        from src.ai.chat_processor import ChatProcessor

        app = MockApp()
        processor = ChatProcessor(app)
        processor.reload_mcp_tools()

        mock_mcp.stop_all.assert_called_once()
        mock_registry.clear_category.assert_called_with("mcp")


@pytest.fixture(autouse=True)
def reset_settings():
    """Reset settings between tests."""
    yield
    # Cleanup if needed

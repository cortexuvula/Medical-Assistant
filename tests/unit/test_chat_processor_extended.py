"""
Extended tests for ChatProcessor

Targets the uncovered lines in chat_processor.py, focusing on:
- _process_message_async full flow
- _get_ai_response with retries, circuit breaker, tool agent path
- _process_ai_response dispatch logic
- _apply_response_to_document and _apply_response_with_confirmation
- _extract_content_from_response edge cases
- _get_widget_for_tab mapping
- get_circuit_breaker_status / reset_circuit_breaker
- Error handling paths throughout
"""

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call, PropertyMock

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

        self.transcript_text = Mock()
        self.soap_text = Mock()
        self.referral_text = Mock()
        self.letter_text = Mock()

        self.status_manager = Mock()
        self.status_manager.info = Mock()
        self.status_manager.success = Mock()
        self.status_manager.error = Mock()
        self.status_manager.warning = Mock()

        self.db = Mock()
        self.current_recording_id = None

    def after(self, delay, callback=None):
        """Mock after method - execute callback immediately for delay=0 only.

        Callbacks scheduled with delay > 0 (e.g. typing animation at 500ms)
        are not executed to avoid infinite recursion in tests.
        """
        if callback and delay == 0:
            callback()
        return "after_id"

    def after_cancel(self, _id):
        pass


def _make_processor(settings_override=None, tools_enabled=False):
    """Helper to create a ChatProcessor with standard mocks."""
    defaults = {
        'max_context_length': 8000,
        'max_history_items': 10,
        'temperature': 0.3,
        'enable_tools': tools_enabled,
    }
    if settings_override:
        defaults.update(settings_override)

    with patch('src.ai.chat_processor.mcp_manager'), \
         patch('src.ai.chat_processor.settings_manager') as mock_settings, \
         patch('src.ai.chat_processor.ToolExecutor') as mock_exec, \
         patch('src.ai.chat_processor.ChatAgent') as mock_agent:
        mock_settings.get_chat_settings.return_value = defaults

        from src.ai.chat_processor import ChatProcessor
        app = MockApp()
        processor = ChatProcessor(app)

    return processor, app


# ── Circuit Breaker Status & Reset ─────────────────────────────────


class TestCircuitBreakerStatusAndReset(unittest.TestCase):
    """Tests for get_circuit_breaker_status and reset_circuit_breaker."""

    def test_get_circuit_breaker_status_closed(self):
        processor, app = _make_processor()
        status = processor.get_circuit_breaker_status()
        self.assertEqual(status, "closed")

    def test_get_circuit_breaker_status_open(self):
        processor, app = _make_processor()
        # Force circuit breaker open
        for _ in range(5):
            processor._ai_circuit_breaker._on_failure()
        status = processor.get_circuit_breaker_status()
        self.assertEqual(status, "open")

    def test_reset_circuit_breaker(self):
        processor, app = _make_processor()
        # Open the breaker
        for _ in range(5):
            processor._ai_circuit_breaker._on_failure()
        self.assertEqual(processor.get_circuit_breaker_status(), "open")

        processor.reset_circuit_breaker()
        self.assertEqual(processor.get_circuit_breaker_status(), "closed")
        app.status_manager.success.assert_called_with("AI service circuit breaker reset")


# ── _get_widget_for_tab ────────────────────────────────────────────


class TestGetWidgetForTab(unittest.TestCase):
    """Tests for the tab-index-to-widget mapping."""

    def test_returns_transcript_for_tab_0(self):
        processor, app = _make_processor()
        widget = processor._get_widget_for_tab(0)
        self.assertIs(widget, app.transcript_text)

    def test_returns_soap_for_tab_1(self):
        processor, app = _make_processor()
        widget = processor._get_widget_for_tab(1)
        self.assertIs(widget, app.soap_text)

    def test_returns_referral_for_tab_2(self):
        processor, app = _make_processor()
        widget = processor._get_widget_for_tab(2)
        self.assertIs(widget, app.referral_text)

    def test_returns_letter_for_tab_3(self):
        processor, app = _make_processor()
        widget = processor._get_widget_for_tab(3)
        self.assertIs(widget, app.letter_text)

    def test_returns_none_for_unknown_tab(self):
        processor, app = _make_processor()
        widget = processor._get_widget_for_tab(99)
        self.assertIsNone(widget)

    def test_returns_none_when_widget_missing(self):
        processor, app = _make_processor()
        del app.transcript_text
        widget = processor._get_widget_for_tab(0)
        self.assertIsNone(widget)


# ── _extract_content_from_response edge cases ─────────────────────


class TestExtractContentEdgeCases(unittest.TestCase):
    """Additional content extraction tests for uncovered branches."""

    def setUp(self):
        self.processor, self.app = _make_processor()

    def test_removes_leading_separator(self):
        response = "Here's the improved version:\n---\nClean content here."
        result = self.processor._extract_content_from_response(response)
        self.assertEqual(result, "Clean content here.")

    def test_removes_leading_separator_with_newline(self):
        response = "Here's the improved version:\n---\n\nClean content here."
        result = self.processor._extract_content_from_response(response)
        self.assertEqual(result, "Clean content here.")

    def test_removes_trailing_separator(self):
        response = "Here's the improved version:\nClean content here.\n---"
        result = self.processor._extract_content_from_response(response)
        self.assertEqual(result, "Clean content here.")

    def test_stops_at_explanation_lines(self):
        response = (
            "Here's the improved version:\n"
            "Line one\n"
            "Line two\n"
            "I've made the following adjustments"
        )
        result = self.processor._extract_content_from_response(response)
        self.assertIn("Line one", result)
        self.assertIn("Line two", result)
        self.assertNotIn("I've made", result)

    def test_stops_at_this_version_explanation(self):
        response = (
            "Updated version:\n"
            "Good content\n"
            "This version is cleaner now"
        )
        result = self.processor._extract_content_from_response(response)
        self.assertIn("Good content", result)
        self.assertNotIn("This version", result)

    def test_stops_at_the_changes_explanation(self):
        response = (
            "Updated version:\n"
            "Good content\n"
            "The changes include better formatting"
        )
        result = self.processor._extract_content_from_response(response)
        self.assertIn("Good content", result)
        self.assertNotIn("The changes", result)

    def test_stops_at_summary_line(self):
        response = (
            "Updated version:\n"
            "Good content\n"
            "Summary: several items were adjusted"
        )
        result = self.processor._extract_content_from_response(response)
        self.assertIn("Good content", result)
        self.assertNotIn("Summary:", result)

    def test_stops_at_changes_made(self):
        response = (
            "Updated version:\n"
            "Good content\n"
            "Here are the changes made to the document"
        )
        result = self.processor._extract_content_from_response(response)
        self.assertIn("Good content", result)
        self.assertNotIn("changes made", result)

    def test_skips_separator_lines_in_body(self):
        response = (
            "Updated version:\n"
            "Section 1\n"
            "---\n"
            "Section 2"
        )
        result = self.processor._extract_content_from_response(response)
        self.assertIn("Section 1", result)
        self.assertIn("Section 2", result)
        self.assertNotIn("---", result)

    def test_extracts_from_markdown_code_block(self):
        response = "Here:\n```markdown\nMarkdown content\n```\nMore stuff"
        result = self.processor._extract_content_from_response(response)
        self.assertEqual(result, "Markdown content")

    def test_extracts_longest_quoted_content(self):
        response = 'Some "short" text and "this is the longer quoted content" here.'
        result = self.processor._extract_content_from_response(response)
        self.assertEqual(result, "this is the longer quoted content")

    def test_fallback_skips_intro_line_with_here(self):
        response = "Here is what you asked for\nActual content line 1\nActual content line 2"
        result = self.processor._extract_content_from_response(response)
        self.assertIn("Actual content line 1", result)
        self.assertIn("Actual content line 2", result)

    def test_fallback_skips_intro_line_with_ive(self):
        response = "I've cleaned the text\nLine one\nLine two"
        result = self.processor._extract_content_from_response(response)
        self.assertIn("Line one", result)
        self.assertIn("Line two", result)

    def test_fallback_skips_intro_line_with_speaker(self):
        response = "Removed speaker_01 labels\nClean text"
        result = self.processor._extract_content_from_response(response)
        self.assertIn("Clean text", result)

    def test_returns_stripped_response_when_no_pattern(self):
        # A single-line response with no markers triggers the final return
        response = "Just a plain response."
        result = self.processor._extract_content_from_response(response)
        self.assertEqual(result, "Just a plain response.")

    def test_multiple_patterns_uses_first_match(self):
        # "as follows:" appears first in the scan
        response = "The text as follows:\nContent A\nBelow:\nContent B"
        result = self.processor._extract_content_from_response(response)
        self.assertIn("Content A", result)

    def test_pattern_cleaned_text(self):
        response = "Cleaned text:\nFresh content"
        result = self.processor._extract_content_from_response(response)
        self.assertEqual(result, "Fresh content")

    def test_pattern_formatted_version(self):
        response = "Formatted version:\nFormatted content"
        result = self.processor._extract_content_from_response(response)
        self.assertEqual(result, "Formatted content")

    def test_pattern_following(self):
        response = "The output is the following:\nOutput content"
        result = self.processor._extract_content_from_response(response)
        self.assertEqual(result, "Output content")

    def test_pattern_below(self):
        response = "See below:\nBelow content"
        result = self.processor._extract_content_from_response(response)
        self.assertEqual(result, "Below content")


# ── _should_apply_to_document extended ─────────────────────────────


class TestShouldApplyToDocumentExtended(unittest.TestCase):
    """Additional keyword and pattern coverage."""

    def setUp(self):
        self.processor, _ = _make_processor()

    def test_keyword_delete(self):
        self.assertTrue(self.processor._should_apply_to_document("delete that paragraph", "ok"))

    def test_keyword_replace(self):
        self.assertTrue(self.processor._should_apply_to_document("replace typos", "ok"))

    def test_keyword_substitute(self):
        self.assertTrue(self.processor._should_apply_to_document("substitute the word", "ok"))

    def test_keyword_format(self):
        self.assertTrue(self.processor._should_apply_to_document("format the text properly", "ok"))

    def test_keyword_make_it(self):
        self.assertTrue(self.processor._should_apply_to_document("make it more concise", "ok"))

    def test_keyword_make_more(self):
        self.assertTrue(self.processor._should_apply_to_document("make more professional", "ok"))

    def test_keyword_make_less(self):
        self.assertTrue(self.processor._should_apply_to_document("make less verbose", "ok"))

    def test_keyword_add_to(self):
        self.assertTrue(self.processor._should_apply_to_document("add to the assessment", "ok"))

    def test_keyword_remove_from(self):
        self.assertTrue(self.processor._should_apply_to_document("remove from the plan", "ok"))

    def test_pattern_delete_speaker(self):
        self.assertTrue(self.processor._should_apply_to_document("delete speaker_01 labels", "ok"))

    def test_pattern_format_this(self):
        self.assertTrue(self.processor._should_apply_to_document("format this as a SOAP note", "ok"))

    def test_pattern_fix_the_formatting(self):
        self.assertTrue(self.processor._should_apply_to_document("fix the formatting please", "ok"))

    def test_pattern_make_this_better(self):
        self.assertTrue(self.processor._should_apply_to_document("make this better", "ok"))

    def test_response_marker_revised_text(self):
        self.assertTrue(
            self.processor._should_apply_to_document("help me", "Revised text:\nContent")
        )

    def test_response_marker_corrected_text(self):
        self.assertTrue(
            self.processor._should_apply_to_document("help me", "Corrected text:\nContent")
        )

    def test_response_marker_cleaned_up_version(self):
        self.assertTrue(
            self.processor._should_apply_to_document("help me", "Cleaned up version:\nContent")
        )

    def test_response_marker_formatted_version(self):
        self.assertTrue(
            self.processor._should_apply_to_document("help me", "Formatted version:\nContent")
        )

    def test_no_match_returns_false(self):
        self.assertFalse(
            self.processor._should_apply_to_document(
                "explain the diagnosis",
                "The diagnosis suggests hypertension."
            )
        )


# ── _get_ai_response ──────────────────────────────────────────────


class TestGetAiResponse(unittest.TestCase):
    """Tests for the core _get_ai_response method."""

    def _make_processor_with_tools(self):
        return _make_processor(tools_enabled=True)

    # --- Circuit breaker OPEN returns (None, None) ---

    def test_circuit_breaker_open_returns_none(self):
        processor, app = _make_processor()
        # Open the breaker
        for _ in range(5):
            processor._ai_circuit_breaker._on_failure()

        result = processor._get_ai_response("prompt text")
        self.assertEqual(result, (None, None))
        app.status_manager.warning.assert_called()

    # --- Chat agent path: success ---

    def test_agent_path_success(self):
        processor, app = self._make_processor_with_tools()

        mock_response = Mock()
        mock_response.success = True
        mock_response.result = "Agent answer"
        mock_response.tool_calls = []
        mock_response.metadata = {}

        processor.chat_agent = Mock()
        processor.chat_agent.execute.return_value = mock_response
        processor._should_use_tools = Mock(return_value=True)

        prompt = "Context\nUser Request: What is the BMI?\n\nPlease help."
        text, tool_info = processor._get_ai_response(prompt)

        self.assertEqual(text, "Agent answer")
        self.assertIsNotNone(tool_info)
        self.assertEqual(tool_info["tool_calls"], [])

    # --- Chat agent path: success with tool calls ---

    def test_agent_path_success_with_tool_calls(self):
        processor, app = self._make_processor_with_tools()

        mock_tool_call = Mock()
        mock_tool_call.tool_name = "calculator"
        mock_tool_call.arguments = {"expression": "2+2"}

        mock_response = Mock()
        mock_response.success = True
        mock_response.result = "The answer is 4"
        mock_response.tool_calls = [mock_tool_call]
        mock_response.metadata = {"timing": 0.5}

        processor.chat_agent = Mock()
        processor.chat_agent.execute.return_value = mock_response
        processor._should_use_tools = Mock(return_value=True)

        prompt = "User Request: calculate 2+2\n\nPlease help."
        text, tool_info = processor._get_ai_response(prompt)

        self.assertEqual(text, "The answer is 4")
        self.assertEqual(len(tool_info["tool_calls"]), 1)
        self.assertEqual(tool_info["metadata"], {"timing": 0.5})

    # --- Chat agent path: failure falls through to regular AI ---

    def test_agent_path_failure_falls_through(self):
        processor, app = self._make_processor_with_tools()

        mock_response = Mock()
        mock_response.success = False
        mock_response.error = "Agent failed"

        processor.chat_agent = Mock()
        processor.chat_agent.execute.return_value = mock_response
        processor._should_use_tools = Mock(return_value=True)

        mock_ai_result = Mock()
        mock_ai_result.text = "Fallback response"

        with patch('src.ai.chat_processor.settings_manager') as mock_settings, \
             patch('ai.ai.call_openai', return_value=mock_ai_result):
            mock_settings.get_ai_provider.return_value = "openai"
            mock_settings.get_nested.return_value = "gpt-4"
            prompt = "User Request: calculate BMI\n\nHelp."
            text, tool_info = processor._get_ai_response(prompt)

        self.assertEqual(text, "Fallback response")
        self.assertIsNone(tool_info)

    # --- Chat agent path: context included ---

    def test_agent_path_includes_context(self):
        processor, app = self._make_processor_with_tools()

        mock_response = Mock()
        mock_response.success = True
        mock_response.result = "Answer with context"
        mock_response.tool_calls = []
        mock_response.metadata = {}

        processor.chat_agent = Mock()
        processor.chat_agent.execute.return_value = mock_response
        processor._should_use_tools = Mock(return_value=True)
        processor._add_to_history("user", "old question")
        processor._add_to_history("assistant", "old answer")

        context_data = {
            "tab_name": "soap",
            "has_content": True,
            "content": "S: Chief complaint of headache"
        }
        prompt = "User Request: summarize\n\nHelp."
        text, tool_info = processor._get_ai_response(prompt, context_data=context_data)

        self.assertEqual(text, "Answer with context")
        # Check the AgentTask passed to execute
        task_arg = processor.chat_agent.execute.call_args[0][0]
        self.assertIn("Soap", task_arg.context)
        self.assertIn("headache", task_arg.context)

    # --- OpenAI provider path ---

    def test_openai_provider_success(self):
        processor, app = _make_processor()

        mock_ai_result = Mock()
        mock_ai_result.text = "OpenAI response"

        with patch('src.ai.chat_processor.settings_manager') as mock_settings, \
             patch('ai.ai.call_openai', return_value=mock_ai_result):
            mock_settings.get_ai_provider.return_value = "openai"
            mock_settings.get_nested.return_value = "gpt-4"
            text, tool_info = processor._get_ai_response("prompt")

        self.assertEqual(text, "OpenAI response")
        self.assertIsNone(tool_info)

    # --- OpenAI provider returns object without .text attribute ---

    def test_openai_provider_returns_plain_string(self):
        processor, app = _make_processor()

        # A response object without .text
        mock_result = "plain string result"

        with patch('src.ai.chat_processor.settings_manager') as mock_settings, \
             patch('ai.ai.call_openai', return_value=mock_result):
            mock_settings.get_ai_provider.return_value = "openai"
            mock_settings.get_nested.return_value = "gpt-4"
            text, tool_info = processor._get_ai_response("prompt")

        self.assertEqual(text, "plain string result")

    # --- Fallback provider (unknown) ---

    def test_fallback_provider(self):
        processor, app = _make_processor()

        mock_ai_result = Mock()
        mock_ai_result.text = "Fallback response"

        with patch('src.ai.chat_processor.settings_manager') as mock_settings, \
             patch('ai.ai.call_ai', return_value=mock_ai_result):
            mock_settings.get_ai_provider.return_value = "unknown_provider"
            text, tool_info = processor._get_ai_response("prompt")

        self.assertEqual(text, "Fallback response")
        self.assertIsNone(tool_info)

    # --- Empty response triggers ValueError ---

    def test_empty_response_retries(self):
        processor, app = _make_processor()

        # First two calls return None (empty), third succeeds
        mock_result = Mock()
        mock_result.text = "Eventually works"

        with patch('src.ai.chat_processor.settings_manager') as mock_settings, \
             patch('ai.ai.call_openai', side_effect=[None, None, mock_result]), \
             patch('time.sleep'):
            mock_settings.get_ai_provider.return_value = "openai"
            mock_settings.get_nested.return_value = "gpt-4"
            text, tool_info = processor._get_ai_response("prompt", max_retries=3)

        self.assertEqual(text, "Eventually works")

    # --- Retryable error with exponential backoff ---

    def test_retryable_error_backoff(self):
        processor, app = _make_processor()

        mock_result = Mock()
        mock_result.text = "Success"

        with patch('src.ai.chat_processor.settings_manager') as mock_settings, \
             patch('ai.ai.call_openai',
                   side_effect=[Exception("rate limit exceeded"), mock_result]), \
             patch('time.sleep') as mock_sleep:
            mock_settings.get_ai_provider.return_value = "openai"
            mock_settings.get_nested.return_value = "gpt-4"
            text, tool_info = processor._get_ai_response("prompt", max_retries=3)

        self.assertEqual(text, "Success")
        # First retry should sleep 1 second (2^0)
        mock_sleep.assert_called_with(1)

    # --- Non-retryable error still retries with short delay ---

    def test_non_retryable_error_minimal_delay(self):
        processor, app = _make_processor()

        mock_result = Mock()
        mock_result.text = "Success"

        with patch('src.ai.chat_processor.settings_manager') as mock_settings, \
             patch('ai.ai.call_openai',
                   side_effect=[Exception("unexpected error"), mock_result]), \
             patch('time.sleep') as mock_sleep:
            mock_settings.get_ai_provider.return_value = "openai"
            mock_settings.get_nested.return_value = "gpt-4"
            text, tool_info = processor._get_ai_response("prompt", max_retries=3)

        self.assertEqual(text, "Success")
        mock_sleep.assert_called_with(0.5)

    # --- All retries exhausted opens circuit breaker ---

    def test_all_retries_exhausted_records_failure(self):
        processor, app = _make_processor()

        with patch('src.ai.chat_processor.settings_manager') as mock_settings, \
             patch('ai.ai.call_openai', side_effect=Exception("persistent error")), \
             patch('time.sleep'):
            mock_settings.get_ai_provider.return_value = "openai"
            mock_settings.get_nested.return_value = "gpt-4"
            text, tool_info = processor._get_ai_response("prompt", max_retries=2)

        self.assertIsNone(text)
        self.assertIsNone(tool_info)
        # Circuit breaker should have recorded a failure
        self.assertGreater(processor._ai_circuit_breaker._failure_count, 0)

    # --- System message defaults when not provided ---

    def test_default_system_message(self):
        processor, app = _make_processor()

        mock_result = Mock()
        mock_result.text = "Response"

        with patch('src.ai.chat_processor.settings_manager') as mock_settings, \
             patch('ai.ai.call_openai', return_value=mock_result) as mock_call:
            mock_settings.get_ai_provider.return_value = "openai"
            mock_settings.get_nested.return_value = "gpt-4"
            processor._get_ai_response("prompt", system_message=None)

        _, kwargs = mock_call.call_args
        self.assertIn("medical AI assistant", kwargs.get('system_message', ''))

    # --- System message custom is passed through ---

    def test_custom_system_message_passed(self):
        processor, app = _make_processor()

        mock_result = Mock()
        mock_result.text = "Response"

        with patch('src.ai.chat_processor.settings_manager') as mock_settings, \
             patch('ai.ai.call_openai', return_value=mock_result) as mock_call:
            mock_settings.get_ai_provider.return_value = "openai"
            mock_settings.get_nested.return_value = "gpt-4"
            processor._get_ai_response("prompt", system_message="Custom system msg")

        _, kwargs = mock_call.call_args
        self.assertEqual(kwargs.get('system_message'), "Custom system msg")

    # --- User message extraction from prompt ---

    def test_user_message_extraction_from_prompt(self):
        """Verify the code correctly parses 'User Request: ...' from the prompt."""
        processor, app = self._make_processor_with_tools()

        mock_response = Mock()
        mock_response.success = True
        mock_response.result = "Answer"
        mock_response.tool_calls = []
        mock_response.metadata = {}

        processor.chat_agent = Mock()
        processor.chat_agent.execute.return_value = mock_response
        processor._should_use_tools = Mock(return_value=True)

        prompt = "Some context\nUser Request: What is hypertension?\n\nMore text"
        processor._get_ai_response(prompt)

        task_arg = processor.chat_agent.execute.call_args[0][0]
        self.assertEqual(task_arg.task_description, "What is hypertension?")

    # --- No User Request in prompt skips agent path ---

    def test_no_user_request_skips_agent(self):
        processor, app = self._make_processor_with_tools()

        processor.chat_agent = Mock()
        processor._should_use_tools = Mock(return_value=True)

        mock_result = Mock()
        mock_result.text = "Direct response"

        # No "User Request: " in the prompt so user_message is None
        with patch('src.ai.chat_processor.settings_manager') as mock_settings, \
             patch('ai.ai.call_openai', return_value=mock_result):
            mock_settings.get_ai_provider.return_value = "openai"
            mock_settings.get_nested.return_value = "gpt-4"
            text, _ = processor._get_ai_response("plain prompt without user request marker")

        # Agent should NOT have been called
        processor.chat_agent.execute.assert_not_called()
        self.assertEqual(text, "Direct response")


# ── _get_ai_response_with_tools ────────────────────────────────────


class TestGetAiResponseWithTools(unittest.TestCase):
    """Tests for the _get_ai_response_with_tools wrapper."""

    def test_delegates_to_get_ai_response(self):
        processor, app = _make_processor()
        processor._get_ai_response = Mock(return_value=("response", {"tool": "info"}))

        text, tool_info = processor._get_ai_response_with_tools(
            "prompt", system_message="sys", context_data={"tab_name": "chat"}
        )

        processor._get_ai_response.assert_called_once_with(
            "prompt", system_message="sys", context_data={"tab_name": "chat"}
        )
        self.assertEqual(text, "response")
        self.assertEqual(tool_info, {"tool": "info"})


# ── _process_message_async ─────────────────────────────────────────


class TestProcessMessageAsync(unittest.TestCase):
    """Tests for the async message processing pipeline."""

    def _make_processor(self, **kw):
        return _make_processor(**kw)

    def test_full_happy_path_with_context_data(self):
        processor, app = self._make_processor()

        context = {
            "tab_name": "soap",
            "tab_index": 1,
            "content": "S: Headache",
            "content_length": 11,
            "has_content": True,
        }

        processor._show_typing_indicator = Mock()
        processor._hide_typing_indicator = Mock()
        processor._get_ai_response_with_tools = Mock(
            return_value=("AI says hello", None)
        )
        processor._process_ai_response = Mock()

        callback = Mock()
        processor._process_message_async("Hello", callback, context_data=context)

        # Verify processing sequence
        processor._show_typing_indicator.assert_called_once()
        processor._get_ai_response_with_tools.assert_called_once()
        processor._hide_typing_indicator.assert_called_once()
        processor._process_ai_response.assert_called_once_with(
            "Hello", "AI says hello", context, None
        )
        self.assertFalse(processor.is_processing)
        callback.assert_called_once()

    def test_falls_back_to_extract_context_when_none(self):
        processor, app = self._make_processor()

        processor._extract_context = Mock(return_value={
            "tab_name": "transcript",
            "tab_index": 0,
            "content": "",
            "content_length": 0,
            "has_content": False,
        })
        processor._show_typing_indicator = Mock()
        processor._hide_typing_indicator = Mock()
        processor._get_ai_response_with_tools = Mock(return_value=("resp", None))
        processor._process_ai_response = Mock()

        processor._process_message_async("Hi", None, context_data=None)

        processor._extract_context.assert_called_once()

    def test_chat_command_short_circuits(self):
        processor, app = self._make_processor()

        context = {"tab_name": "chat", "has_content": False}
        processor._handle_chat_command = Mock(return_value=True)
        processor._show_typing_indicator = Mock()

        processor._process_message_async("/clear", None, context_data=context)

        processor._handle_chat_command.assert_called_once_with("/clear")
        # Typing indicator should NOT be shown for commands
        processor._show_typing_indicator.assert_not_called()

    def test_none_ai_response_shows_error(self):
        processor, app = self._make_processor()

        context = {"tab_name": "transcript", "has_content": False}
        processor._show_typing_indicator = Mock()
        processor._hide_typing_indicator = Mock()
        processor._get_ai_response_with_tools = Mock(return_value=(None, None))

        processor._process_message_async("msg", None, context_data=context)

        app.status_manager.error.assert_called_with("Failed to get AI response")
        processor._hide_typing_indicator.assert_called_once()

    def test_exception_shows_error_and_hides_indicator(self):
        processor, app = self._make_processor()

        context = {"tab_name": "transcript", "has_content": False}
        processor._show_typing_indicator = Mock()
        processor._hide_typing_indicator = Mock()
        processor._get_ai_response_with_tools = Mock(
            side_effect=ConnectionError("Network down")
        )

        processor._process_message_async("msg", None, context_data=context)

        app.status_manager.error.assert_called()
        processor._hide_typing_indicator.assert_called()
        self.assertFalse(processor.is_processing)

    def test_timeout_error_handled(self):
        processor, app = self._make_processor()
        context = {"tab_name": "transcript", "has_content": False}
        processor._show_typing_indicator = Mock()
        processor._hide_typing_indicator = Mock()
        processor._get_ai_response_with_tools = Mock(
            side_effect=TimeoutError("Timed out")
        )

        processor._process_message_async("msg", None, context_data=context)

        app.status_manager.error.assert_called()
        self.assertFalse(processor.is_processing)

    def test_value_error_handled(self):
        processor, app = self._make_processor()
        context = {"tab_name": "transcript", "has_content": False}
        processor._show_typing_indicator = Mock()
        processor._hide_typing_indicator = Mock()
        processor._get_ai_response_with_tools = Mock(
            side_effect=ValueError("Bad value")
        )

        processor._process_message_async("msg", None, context_data=context)

        app.status_manager.error.assert_called()
        self.assertFalse(processor.is_processing)

    def test_runtime_error_handled(self):
        processor, app = self._make_processor()
        context = {"tab_name": "transcript", "has_content": False}
        processor._show_typing_indicator = Mock()
        processor._hide_typing_indicator = Mock()
        processor._get_ai_response_with_tools = Mock(
            side_effect=RuntimeError("Runtime issue")
        )

        processor._process_message_async("msg", None, context_data=context)

        app.status_manager.error.assert_called()
        self.assertFalse(processor.is_processing)

    def test_is_processing_flag_lifecycle(self):
        """Verify is_processing is True during execution and False after."""
        processor, app = self._make_processor()
        context = {"tab_name": "transcript", "has_content": False}

        flags = []

        def capture_flag(*args, **kwargs):
            flags.append(processor.is_processing)
            return ("resp", None)

        processor._show_typing_indicator = Mock()
        processor._hide_typing_indicator = Mock()
        processor._get_ai_response_with_tools = capture_flag
        processor._process_ai_response = Mock()

        processor._process_message_async("msg", None, context_data=context)

        self.assertTrue(flags[0])  # Was True during AI call
        self.assertFalse(processor.is_processing)  # False after

    def test_history_updated_on_success(self):
        processor, app = self._make_processor()
        context = {"tab_name": "transcript", "has_content": False}
        processor._show_typing_indicator = Mock()
        processor._hide_typing_indicator = Mock()
        processor._get_ai_response_with_tools = Mock(
            return_value=("AI response", None)
        )
        processor._process_ai_response = Mock()

        processor._process_message_async("user msg", None, context_data=context)

        self.assertEqual(len(processor.conversation_history), 2)
        self.assertEqual(processor.conversation_history[0]["role"], "user")
        self.assertEqual(processor.conversation_history[0]["message"], "user msg")
        self.assertEqual(processor.conversation_history[1]["role"], "assistant")
        self.assertEqual(processor.conversation_history[1]["message"], "AI response")


# ── _process_ai_response ──────────────────────────────────────────


class TestProcessAiResponse(unittest.TestCase):
    """Tests for _process_ai_response dispatch logic."""

    def setUp(self):
        self.processor, self.app = _make_processor()
        self.processor._show_ai_response = Mock()
        self.processor._append_to_chat_tab = Mock()
        self.processor._apply_response_to_document = Mock()
        self.processor._apply_response_with_confirmation = Mock()

    def test_chat_tab_appends_to_chat(self):
        context = {"tab_name": "chat"}
        self.processor._process_ai_response("hi", "hello", context, None)

        self.processor._show_ai_response.assert_called_once_with("hello")
        self.processor._append_to_chat_tab.assert_called_once_with("hi", "hello", None)
        self.processor._apply_response_to_document.assert_not_called()

    def test_chat_tab_with_tool_info(self):
        context = {"tab_name": "chat"}
        tool_info = {"tool_calls": [Mock()], "metadata": {}}
        self.processor._process_ai_response("hi", "hello", context, tool_info)

        self.processor._append_to_chat_tab.assert_called_once_with("hi", "hello", tool_info)

    @patch('src.ai.chat_processor.settings_manager')
    def test_document_tab_auto_apply(self, mock_settings):
        mock_settings.get_chat_settings.return_value = {"auto_apply_changes": True}

        context = {"tab_name": "soap"}
        self.processor._should_apply_to_document = Mock(return_value=True)

        self.processor._process_ai_response("improve this", "Improved version", context)

        self.processor._apply_response_to_document.assert_called_once_with(
            "Improved version", context
        )
        self.processor._apply_response_with_confirmation.assert_not_called()

    @patch('src.ai.chat_processor.settings_manager')
    def test_document_tab_confirmation_mode(self, mock_settings):
        mock_settings.get_chat_settings.return_value = {"auto_apply_changes": False}

        context = {"tab_name": "soap"}
        self.processor._should_apply_to_document = Mock(return_value=True)

        self.processor._process_ai_response("improve this", "Improved version", context)

        self.processor._apply_response_with_confirmation.assert_called_once_with(
            "Improved version", context
        )
        self.processor._apply_response_to_document.assert_not_called()

    @patch('src.ai.chat_processor.settings_manager')
    def test_document_tab_auto_apply_default_true(self, mock_settings):
        """auto_apply_changes defaults to True when not in settings."""
        mock_settings.get_chat_settings.return_value = {}

        context = {"tab_name": "soap"}
        self.processor._should_apply_to_document = Mock(return_value=True)

        self.processor._process_ai_response("improve this", "Improved version", context)

        self.processor._apply_response_to_document.assert_called_once()

    def test_no_apply_when_not_modification(self):
        context = {"tab_name": "soap"}
        self.processor._should_apply_to_document = Mock(return_value=False)

        self.processor._process_ai_response("what is this?", "explanation", context)

        self.processor._apply_response_to_document.assert_not_called()
        self.processor._apply_response_with_confirmation.assert_not_called()


# ── _apply_response_to_document ────────────────────────────────────


class TestApplyResponseToDocument(unittest.TestCase):
    """Tests for auto-applying AI response to documents."""

    def setUp(self):
        self.processor, self.app = _make_processor()

    def test_applies_content_to_soap_tab(self):
        context = {"tab_name": "soap", "tab_index": 1}
        self.processor._extract_content_from_response = Mock(return_value="Clean content")

        self.processor._apply_response_to_document("AI says: Clean content", context)

        self.app.soap_text.delete.assert_called_once_with("1.0", "end")
        self.app.soap_text.insert.assert_called_once_with("1.0", "Clean content")
        self.app.status_manager.success.assert_called()

    def test_applies_content_to_transcript_tab(self):
        context = {"tab_name": "transcript", "tab_index": 0}
        self.processor._extract_content_from_response = Mock(return_value="Cleaned transcript")

        self.processor._apply_response_to_document("result", context)

        self.app.transcript_text.delete.assert_called_once()
        self.app.transcript_text.insert.assert_called_once_with("1.0", "Cleaned transcript")

    def test_no_content_shows_warning(self):
        context = {"tab_name": "soap", "tab_index": 1}
        self.processor._extract_content_from_response = Mock(return_value="")

        self.processor._apply_response_to_document("empty response", context)

        self.app.status_manager.warning.assert_called_with("No content to apply to document")

    def test_no_widget_shows_warning(self):
        context = {"tab_name": "unknown", "tab_index": 99}
        self.processor._extract_content_from_response = Mock(return_value="Some content")

        self.processor._apply_response_to_document("response", context)

        self.app.status_manager.warning.assert_called_with("No content to apply to document")

    def test_tcl_error_shows_failure(self):
        import tkinter as tk
        context = {"tab_name": "soap", "tab_index": 1}
        self.processor._extract_content_from_response = Mock(return_value="content")
        self.app.soap_text.delete.side_effect = tk.TclError("widget destroyed")

        self.processor._apply_response_to_document("response", context)

        self.app.status_manager.error.assert_called_with("Failed to apply changes")


# ── _apply_response_with_confirmation ──────────────────────────────


class TestApplyResponseWithConfirmation(unittest.TestCase):
    """Tests for applying response with user confirmation dialog."""

    def setUp(self):
        self.processor, self.app = _make_processor()

    @patch('tkinter.messagebox.askyesno', return_value=True)
    def test_applies_when_user_confirms(self, mock_dialog):
        context = {"tab_name": "soap", "tab_index": 1}
        self.processor._extract_content_from_response = Mock(return_value="New content")

        self.processor._apply_response_with_confirmation("AI response", context)

        self.app.soap_text.delete.assert_called_once_with("1.0", "end")
        self.app.soap_text.insert.assert_called_once_with("1.0", "New content")
        self.app.status_manager.success.assert_called()

    @patch('tkinter.messagebox.askyesno', return_value=False)
    def test_does_not_apply_when_user_declines(self, mock_dialog):
        context = {"tab_name": "soap", "tab_index": 1}
        self.processor._extract_content_from_response = Mock(return_value="New content")

        self.processor._apply_response_with_confirmation("AI response", context)

        self.app.soap_text.delete.assert_not_called()
        self.app.status_manager.info.assert_called_with("Changes not applied")

    def test_no_content_shows_warning(self):
        context = {"tab_name": "soap", "tab_index": 1}
        self.processor._extract_content_from_response = Mock(return_value="")

        self.processor._apply_response_with_confirmation("AI response", context)

        self.app.status_manager.warning.assert_called_with("No content to apply to document")

    def test_no_widget_shows_warning(self):
        context = {"tab_name": "unknown", "tab_index": 99}
        self.processor._extract_content_from_response = Mock(return_value="content")

        self.processor._apply_response_with_confirmation("AI response", context)

        self.app.status_manager.warning.assert_called_with("No content to apply to document")

    def test_tcl_error_shows_failure(self):
        import tkinter as tk
        context = {"tab_name": "soap", "tab_index": 1}
        self.processor._extract_content_from_response = Mock(return_value="content")
        self.app.soap_text.delete.side_effect = tk.TclError("widget destroyed")

        # messagebox.askyesno would be called but delete raises
        with patch('tkinter.messagebox.askyesno', return_value=True):
            self.processor._apply_response_with_confirmation("AI response", context)

        self.app.status_manager.error.assert_called_with("Failed to apply changes")


# ── _show_ai_response ─────────────────────────────────────────────


class TestShowAiResponse(unittest.TestCase):
    """Tests for the notification display method."""

    def test_shows_status_info(self):
        processor, app = _make_processor()
        # Call the real method (not the mixin override, but the processor's)
        processor._show_ai_response("Short response")
        app.status_manager.info.assert_called()

    def test_handles_long_response(self):
        processor, app = _make_processor()
        long_response = "A" * 500
        processor._show_ai_response(long_response)
        app.status_manager.info.assert_called()

    def test_handles_attribute_error(self):
        """If app doesn't have status_manager, should not raise."""
        processor, app = _make_processor()
        app.status_manager.info.side_effect = AttributeError("no status_manager")
        # Should not raise
        processor._show_ai_response("response")


# ── process_message (threading) ────────────────────────────────────


class TestProcessMessage(unittest.TestCase):
    """Tests for the process_message entry point."""

    def test_rejects_when_already_processing(self):
        processor, app = _make_processor()
        processor.is_processing = True

        processor._process_message_async = Mock()
        processor.process_message("Should be ignored")

        processor._process_message_async.assert_not_called()

    def test_starts_thread(self):
        processor, app = _make_processor()

        with patch('threading.Thread') as mock_thread:
            mock_instance = Mock()
            mock_thread.return_value = mock_instance

            processor.process_message("Test", callback=Mock(), context_data={"tab_name": "chat"})

            mock_thread.assert_called_once()
            mock_instance.start.assert_called_once()
            # Verify daemon=True
            _, kwargs = mock_thread.call_args
            self.assertTrue(kwargs.get('daemon', False))


# ── Retryable error patterns ──────────────────────────────────────


class TestRetryableErrorPatterns(unittest.TestCase):
    """Test that various HTTP error codes and messages are correctly identified as retryable."""

    def _run_with_error(self, error_msg, expect_retried=True):
        processor, app = _make_processor()

        mock_result = Mock()
        mock_result.text = "Success"

        effects = [Exception(error_msg), mock_result]

        with patch('src.ai.chat_processor.settings_manager') as mock_settings, \
             patch('ai.ai.call_openai', side_effect=effects), \
             patch('time.sleep') as mock_sleep:
            mock_settings.get_ai_provider.return_value = "openai"
            mock_settings.get_nested.return_value = "gpt-4"
            text, _ = processor._get_ai_response("prompt", max_retries=2)

        if expect_retried:
            self.assertEqual(text, "Success")
            mock_sleep.assert_called()
        return text

    def test_429_retried(self):
        self._run_with_error("429 Too Many Requests")

    def test_timeout_retried(self):
        self._run_with_error("connection timeout")

    def test_503_retried(self):
        self._run_with_error("503 Service Unavailable")

    def test_502_retried(self):
        self._run_with_error("502 Bad Gateway")

    def test_500_retried(self):
        self._run_with_error("500 Internal Server Error")

    def test_overloaded_retried(self):
        self._run_with_error("server overloaded")

    def test_temporarily_unavailable_retried(self):
        self._run_with_error("service temporarily unavailable")


# ── Integration-style scenario tests ──────────────────────────────


class TestEndToEndScenarios(unittest.TestCase):
    """Integration-style tests that exercise multiple methods together."""

    def test_full_document_improvement_flow(self):
        """Simulate: user asks to improve SOAP note, AI responds, content applied."""
        processor, app = _make_processor()

        mock_result = Mock()
        mock_result.text = "Here's the improved version:\nS: Better subjective note."

        context = {
            "tab_name": "soap",
            "tab_index": 1,
            "content": "S: Bad note",
            "content_length": 11,
            "has_content": True,
        }

        with patch('src.ai.chat_processor.settings_manager') as mock_settings, \
             patch('ai.ai.call_openai', return_value=mock_result):
            mock_settings.get_ai_provider.return_value = "openai"
            mock_settings.get_nested.return_value = "gpt-4"
            mock_settings.get_chat_settings.return_value = {"auto_apply_changes": True}
            processor._process_message_async("improve this", None, context_data=context)

        # Content should have been applied to SOAP text widget
        app.soap_text.delete.assert_called_once_with("1.0", "end")
        app.soap_text.insert.assert_called_once()
        insert_content = app.soap_text.insert.call_args[0][1]
        self.assertIn("Better subjective note", insert_content)

    def test_full_chat_conversation_flow(self):
        """Simulate: user chats, AI responds, response appended to chat tab."""
        processor, app = _make_processor()

        mock_result = Mock()
        mock_result.text = "I can help with that."

        context = {
            "tab_name": "chat",
            "tab_index": 4,
            "content": "",
            "content_length": 0,
            "has_content": False,
        }

        processor._append_to_chat_tab = Mock()

        with patch('src.ai.chat_processor.settings_manager') as mock_settings, \
             patch('ai.ai.call_openai', return_value=mock_result):
            mock_settings.get_ai_provider.return_value = "openai"
            mock_settings.get_nested.return_value = "gpt-4"
            processor._process_message_async("Tell me about hypertension", None, context_data=context)

        processor._append_to_chat_tab.assert_called_once()
        # History should have both messages
        self.assertEqual(len(processor.conversation_history), 2)

    def test_circuit_breaker_prevents_repeated_failures(self):
        """After 5 failures, subsequent calls should be rejected immediately."""
        processor, app = _make_processor()

        # Simulate 5 consecutive failures
        for _ in range(5):
            processor._ai_circuit_breaker._on_failure()

        # Next call should be rejected immediately
        result = processor._get_ai_response("prompt")
        self.assertEqual(result, (None, None))
        app.status_manager.warning.assert_called()

        # Reset and verify recovery
        processor.reset_circuit_breaker()
        self.assertEqual(processor.get_circuit_breaker_status(), "closed")


if __name__ == "__main__":
    unittest.main()

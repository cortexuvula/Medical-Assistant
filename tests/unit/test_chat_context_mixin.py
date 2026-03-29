"""
Tests for src/ai/chat_context_mixin.py

Covers _construct_prompt() (system message selection, prompt structure,
history inclusion, content inclusion), _add_to_history() (appending,
timestamp, size capping), clear_history(), get_history() (returns copy),
and get_context_from_history() (formatting, max_entries).
No network, no Tkinter, no file I/O.
"""

import sys
import pytest
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.chat_context_mixin import ChatContextMixin


# ---------------------------------------------------------------------------
# Minimal stand-in for ChatProcessor that uses the mixin
# ---------------------------------------------------------------------------

class _FakeChat(ChatContextMixin):
    def __init__(self):
        self.conversation_history: list = []
        self.max_history_items: int = 10
        self.max_context_length: int = 1000


def _chat() -> _FakeChat:
    return _FakeChat()


# ===========================================================================
# _construct_prompt
# ===========================================================================

class TestConstructPrompt:
    def setup_method(self):
        self.c = _chat()

    def _ctx(self, tab_name="soap", has_content=False, content=""):
        return {
            "tab_name": tab_name,
            "has_content": has_content,
            "content": content,
            "content_length": len(content),
        }

    def test_returns_tuple_of_two_strings(self):
        result = self.c._construct_prompt("hello", self._ctx())
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)

    def test_soap_tab_system_message(self):
        sys_msg, _ = self.c._construct_prompt("improve this", self._ctx("soap"))
        assert "SOAP" in sys_msg or "soap" in sys_msg.lower()

    def test_transcript_tab_system_message(self):
        sys_msg, _ = self.c._construct_prompt("clean this up", self._ctx("transcript"))
        assert "transcript" in sys_msg.lower()

    def test_referral_tab_system_message(self):
        sys_msg, _ = self.c._construct_prompt("improve", self._ctx("referral"))
        assert "referral" in sys_msg.lower()

    def test_letter_tab_system_message(self):
        sys_msg, _ = self.c._construct_prompt("fix", self._ctx("letter"))
        assert "letter" in sys_msg.lower()

    def test_chat_tab_system_message(self):
        sys_msg, _ = self.c._construct_prompt("hello", self._ctx("chat"))
        assert "chat" in sys_msg.lower() or "conversation" in sys_msg.lower()

    def test_unknown_tab_uses_fallback_system_message(self):
        sys_msg, _ = self.c._construct_prompt("hi", self._ctx("unknown_tab"))
        assert isinstance(sys_msg, str)
        assert len(sys_msg.strip()) > 0

    def test_prompt_contains_user_message(self):
        _, prompt = self.c._construct_prompt("What is the diagnosis?", self._ctx())
        assert "What is the diagnosis?" in prompt

    def test_prompt_mentions_document_type(self):
        _, prompt = self.c._construct_prompt("ok", self._ctx("soap"))
        assert "Soap" in prompt or "soap" in prompt.lower()

    def test_prompt_has_content_when_has_content_true(self):
        ctx = self._ctx("soap", has_content=True, content="Patient presents with chest pain")
        _, prompt = self.c._construct_prompt("analyze", ctx)
        assert "Patient presents with chest pain" in prompt

    def test_prompt_no_content_section_when_no_content(self):
        ctx = self._ctx("soap", has_content=False, content="")
        _, prompt = self.c._construct_prompt("analyze", ctx)
        # The content block (---) should not appear when there's no content
        assert "Has Content: No" in prompt

    def test_prompt_includes_conversation_history(self):
        self.c.conversation_history = [
            {"role": "user", "message": "What is diabetes?", "timestamp": "t1"},
            {"role": "assistant", "message": "Diabetes is a metabolic disease.", "timestamp": "t2"},
        ]
        _, prompt = self.c._construct_prompt("follow up question", self._ctx())
        assert "What is diabetes?" in prompt or "Diabetes is" in prompt

    def test_prompt_excludes_history_when_empty(self):
        self.c.conversation_history = []
        _, prompt = self.c._construct_prompt("question", self._ctx())
        assert "Recent Conversation:" not in prompt

    def test_long_history_message_truncated_in_prompt(self):
        long_msg = "x" * 300
        self.c.conversation_history = [
            {"role": "user", "message": long_msg, "timestamp": "t1"},
        ]
        _, prompt = self.c._construct_prompt("q", self._ctx())
        # Should be truncated to 200 chars + "..."
        assert "..." in prompt

    def test_system_message_differs_by_tab(self):
        soap_sys, _ = self.c._construct_prompt("q", self._ctx("soap"))
        transcript_sys, _ = self.c._construct_prompt("q", self._ctx("transcript"))
        assert soap_sys != transcript_sys


# ===========================================================================
# _add_to_history
# ===========================================================================

class TestAddToHistory:
    def setup_method(self):
        self.c = _chat()

    def test_appends_entry(self):
        self.c._add_to_history("user", "hello")
        assert len(self.c.conversation_history) == 1

    def test_entry_has_role(self):
        self.c._add_to_history("user", "hello")
        assert self.c.conversation_history[0]["role"] == "user"

    def test_entry_has_message(self):
        self.c._add_to_history("assistant", "hi there")
        assert self.c.conversation_history[0]["message"] == "hi there"

    def test_entry_has_timestamp(self):
        self.c._add_to_history("user", "msg")
        ts = self.c.conversation_history[0]["timestamp"]
        assert isinstance(ts, str)
        assert len(ts) > 0
        # Should be parseable as ISO datetime
        datetime.fromisoformat(ts)

    def test_multiple_entries_appended_in_order(self):
        self.c._add_to_history("user", "first")
        self.c._add_to_history("assistant", "second")
        assert self.c.conversation_history[0]["message"] == "first"
        assert self.c.conversation_history[1]["message"] == "second"

    def test_history_capped_at_max_history_items(self):
        self.c.max_history_items = 3
        for i in range(10):
            self.c._add_to_history("user", f"message {i}")
        assert len(self.c.conversation_history) == 3

    def test_oldest_entries_removed_when_capped(self):
        self.c.max_history_items = 2
        self.c._add_to_history("user", "first")
        self.c._add_to_history("user", "second")
        self.c._add_to_history("user", "third")
        messages = [e["message"] for e in self.c.conversation_history]
        assert "first" not in messages
        assert "second" in messages
        assert "third" in messages


# ===========================================================================
# clear_history
# ===========================================================================

class TestClearHistory:
    def test_clears_all_entries(self):
        c = _chat()
        c._add_to_history("user", "hello")
        c._add_to_history("assistant", "world")
        c.clear_history()
        assert c.conversation_history == []

    def test_clear_empty_history_no_error(self):
        c = _chat()
        c.clear_history()  # Should not raise
        assert c.conversation_history == []


# ===========================================================================
# get_history
# ===========================================================================

class TestGetHistory:
    def test_returns_list(self):
        c = _chat()
        assert isinstance(c.get_history(), list)

    def test_returns_copy_not_original(self):
        c = _chat()
        c._add_to_history("user", "hello")
        copy = c.get_history()
        copy.append({"role": "fake", "message": "fake"})
        assert len(c.conversation_history) == 1

    def test_empty_returns_empty_list(self):
        c = _chat()
        assert c.get_history() == []

    def test_contents_match(self):
        c = _chat()
        c._add_to_history("user", "msg1")
        c._add_to_history("assistant", "msg2")
        history = c.get_history()
        assert history[0]["message"] == "msg1"
        assert history[1]["message"] == "msg2"


# ===========================================================================
# get_context_from_history
# ===========================================================================

class TestGetContextFromHistory:
    def setup_method(self):
        self.c = _chat()

    def test_returns_string(self):
        assert isinstance(self.c.get_context_from_history(), str)

    def test_empty_history_returns_empty_string(self):
        assert self.c.get_context_from_history() == ""

    def test_includes_role_and_message(self):
        self.c._add_to_history("user", "What is diabetes?")
        ctx = self.c.get_context_from_history()
        assert "User" in ctx
        assert "What is diabetes?" in ctx

    def test_includes_multiple_entries(self):
        self.c._add_to_history("user", "first question")
        self.c._add_to_history("assistant", "first answer")
        ctx = self.c.get_context_from_history()
        assert "first question" in ctx
        assert "first answer" in ctx

    def test_max_entries_limits_output(self):
        for i in range(10):
            self.c._add_to_history("user", f"question {i}")
        ctx = self.c.get_context_from_history(max_entries=2)
        # Only the last 2 questions should appear
        assert "question 8" in ctx
        assert "question 9" in ctx
        assert "question 0" not in ctx

    def test_separator_between_entries(self):
        self.c._add_to_history("user", "q1")
        self.c._add_to_history("assistant", "a1")
        ctx = self.c.get_context_from_history()
        # Entries joined with "\n\n"
        assert "\n\n" in ctx

    def test_default_max_entries_is_5(self):
        for i in range(10):
            self.c._add_to_history("user", f"msg {i}")
        ctx = self.c.get_context_from_history()
        # Default max is 5, so first 5 messages should not appear
        assert "msg 0" not in ctx
        assert "msg 9" in ctx

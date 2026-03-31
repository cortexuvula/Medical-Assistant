"""
Tests for src/processing/text_processor.py

Covers TextProcessor: initial state, clean_command_text, handle_text_command
(known/unknown commands, text insertion, capitalize-after-full-stop), and
_insert_with_capitalize. Widget interactions are tested using MagicMock.
"""

import sys
import pytest
import string
from pathlib import Path
from unittest.mock import MagicMock, call

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from processing.text_processor import TextProcessor


# ---------------------------------------------------------------------------
# Helper — mock widget that tracks insertions
# ---------------------------------------------------------------------------

def _make_widget(initial_text=""):
    """Return a mock widget that accumulates insertions."""
    widget = MagicMock()
    _content = [initial_text]

    def get(start, end):
        return _content[0]

    def insert(pos, text):
        _content[0] += text

    def delete(start, end):
        _content[0] = ""

    widget.get.side_effect = get
    widget.insert.side_effect = insert
    widget.delete.side_effect = delete
    widget._content = _content
    return widget


# ===========================================================================
# Initialization
# ===========================================================================

class TestTextProcessorInit:
    def test_capitalize_next_is_false(self):
        tp = TextProcessor()
        assert tp.capitalize_next is False

    def test_text_chunks_is_empty_list(self):
        tp = TextProcessor()
        assert tp.text_chunks == []


# ===========================================================================
# clean_command_text
# ===========================================================================

class TestCleanCommandText:
    def test_lowercases_text(self):
        tp = TextProcessor()
        result = tp.clean_command_text("HELLO")
        assert result == "hello"

    def test_strips_whitespace(self):
        tp = TextProcessor()
        result = tp.clean_command_text("  hello world  ")
        assert result == "hello world"

    def test_removes_punctuation(self):
        tp = TextProcessor()
        result = tp.clean_command_text("hello, world!")
        assert result == "hello world"

    def test_removes_all_punctuation_chars(self):
        tp = TextProcessor()
        for char in string.punctuation:
            result = tp.clean_command_text(f"abc{char}def")
            assert char not in result

    def test_empty_string_returns_empty(self):
        tp = TextProcessor()
        assert tp.clean_command_text("") == ""

    def test_already_clean_string_unchanged(self):
        tp = TextProcessor()
        assert tp.clean_command_text("new paragraph") == "new paragraph"

    def test_mixed_case_with_punctuation(self):
        tp = TextProcessor()
        result = tp.clean_command_text("Full Stop.")
        assert result == "full stop"

    def test_numbers_preserved(self):
        tp = TextProcessor()
        result = tp.clean_command_text("test 123")
        assert result == "test 123"


# ===========================================================================
# handle_text_command — known commands return True
# ===========================================================================

class TestHandleTextCommandKnownCommands:
    def _run(self, command):
        tp = TextProcessor()
        widget = _make_widget()
        result = tp.handle_text_command(command, widget)
        return result, tp, widget

    def test_new_paragraph_returns_true(self):
        result, _, _ = self._run("new paragraph")
        assert result is True

    def test_new_line_returns_true(self):
        result, _, _ = self._run("new line")
        assert result is True

    def test_full_stop_returns_true(self):
        result, _, _ = self._run("full stop")
        assert result is True

    def test_comma_returns_true(self):
        result, _, _ = self._run("comma")
        assert result is True

    def test_question_mark_returns_true(self):
        result, _, _ = self._run("question mark")
        assert result is True

    def test_exclamation_point_returns_true(self):
        result, _, _ = self._run("exclamation point")
        assert result is True

    def test_semicolon_returns_true(self):
        result, _, _ = self._run("semicolon")
        assert result is True

    def test_colon_returns_true(self):
        result, _, _ = self._run("colon")
        assert result is True

    def test_open_quote_returns_true(self):
        result, _, _ = self._run("open quote")
        assert result is True

    def test_close_quote_returns_true(self):
        result, _, _ = self._run("close quote")
        assert result is True

    def test_open_parenthesis_returns_true(self):
        result, _, _ = self._run("open parenthesis")
        assert result is True

    def test_close_parenthesis_returns_true(self):
        result, _, _ = self._run("close parenthesis")
        assert result is True


# ===========================================================================
# handle_text_command — unknown command returns False
# ===========================================================================

class TestHandleTextCommandUnknown:
    def test_unknown_command_returns_false(self):
        tp = TextProcessor()
        widget = _make_widget()
        result = tp.handle_text_command("delete word", widget)
        assert result is False

    def test_empty_command_returns_false(self):
        tp = TextProcessor()
        widget = _make_widget()
        result = tp.handle_text_command("", widget)
        assert result is False

    def test_partial_command_returns_false(self):
        tp = TextProcessor()
        widget = _make_widget()
        result = tp.handle_text_command("new", widget)
        assert result is False

    def test_case_sensitive_mismatch_returns_false(self):
        tp = TextProcessor()
        widget = _make_widget()
        result = tp.handle_text_command("New Paragraph", widget)
        assert result is False


# ===========================================================================
# handle_text_command — correct text inserted
# ===========================================================================

class TestHandleTextCommandInsertion:
    def _inserted_text(self, command, initial=""):
        tp = TextProcessor()
        widget = MagicMock()
        tp.handle_text_command(command, widget)
        return widget.insert.call_args_list

    def test_new_paragraph_inserts_two_newlines(self):
        tp = TextProcessor()
        widget = MagicMock()
        tp.handle_text_command("new paragraph", widget)
        # Check that insert was called with "\n\n" as the text argument
        inserted_texts = [c.args[1] for c in widget.insert.call_args_list]
        assert any("\n\n" in t for t in inserted_texts)

    def test_new_line_inserts_newline(self):
        tp = TextProcessor()
        widget = MagicMock()
        tp.handle_text_command("new line", widget)
        inserted_texts = [c.args[1] for c in widget.insert.call_args_list]
        assert any("\n" in t for t in inserted_texts)

    def test_comma_inserts_comma_space(self):
        calls = self._inserted_text("comma")
        assert any(", " in str(c) for c in calls)

    def test_question_mark_inserts_question_space(self):
        calls = self._inserted_text("question mark")
        assert any("? " in str(c) for c in calls)

    def test_exclamation_inserts_exclamation_space(self):
        calls = self._inserted_text("exclamation point")
        assert any("! " in str(c) for c in calls)

    def test_semicolon_inserts_semicolon_space(self):
        calls = self._inserted_text("semicolon")
        assert any("; " in str(c) for c in calls)

    def test_colon_inserts_colon_space(self):
        calls = self._inserted_text("colon")
        assert any(": " in str(c) for c in calls)

    def test_open_quote_inserts_double_quote(self):
        calls = self._inserted_text("open quote")
        assert any('"' in str(c) for c in calls)

    def test_open_paren_inserts_open_paren(self):
        calls = self._inserted_text("open parenthesis")
        assert any("(" in str(c) for c in calls)

    def test_close_paren_inserts_close_paren(self):
        calls = self._inserted_text("close parenthesis")
        assert any(")" in str(c) for c in calls)


# ===========================================================================
# full stop sets capitalize_next
# ===========================================================================

class TestFullStopCapitalize:
    def test_full_stop_sets_capitalize_next(self):
        tp = TextProcessor()
        widget = MagicMock()
        tp.handle_text_command("full stop", widget)
        assert tp.capitalize_next is True

    def test_other_commands_do_not_set_capitalize_next(self):
        tp = TextProcessor()
        widget = MagicMock()
        tp.handle_text_command("comma", widget)
        assert tp.capitalize_next is False


# ===========================================================================
# _insert_with_capitalize
# ===========================================================================

class TestInsertWithCapitalize:
    def test_inserts_text(self):
        tp = TextProcessor()
        widget = MagicMock()
        tp._insert_with_capitalize(widget, ". ")
        widget.insert.assert_called_once()

    def test_sets_capitalize_next_true(self):
        tp = TextProcessor()
        widget = MagicMock()
        tp._insert_with_capitalize(widget, ". ")
        assert tp.capitalize_next is True


# ===========================================================================
# append_text_to_widget
# ===========================================================================

class TestAppendTextToWidget:
    def test_appends_text_to_empty_widget(self):
        tp = TextProcessor()
        widget = _make_widget("")
        tp.append_text_to_widget("hello", widget)
        # Should insert "Hello" (auto-capitalized since widget is empty)
        calls = widget.insert.call_args_list
        inserted = "".join(str(c) for c in calls)
        assert "hello" in inserted.lower()

    def test_skips_whitespace_only_text(self):
        tp = TextProcessor()
        widget = _make_widget("")
        tp.append_text_to_widget("   ", widget)
        widget.insert.assert_not_called()

    def test_capitalizes_first_char_when_widget_empty(self):
        tp = TextProcessor()
        widget = _make_widget("")
        tp.append_text_to_widget("hello", widget)
        # When widget is empty, text is auto-capitalized
        call_text = widget.insert.call_args[0][1]
        assert call_text[0] == "H"

    def test_adds_space_before_text_when_previous_ends_with_word(self):
        tp = TextProcessor()
        widget = _make_widget("existing text")
        tp.append_text_to_widget("more", widget)
        call_text = widget.insert.call_args[0][1]
        assert call_text.startswith(" ")

    def test_no_leading_space_after_newline(self):
        tp = TextProcessor()
        widget = _make_widget("line one\n")
        tp.append_text_to_widget("line two", widget)
        call_text = widget.insert.call_args[0][1]
        # After newline, no space prefix
        assert not call_text.startswith(" ")

    def test_capitalize_next_flag_respected(self):
        tp = TextProcessor()
        tp.capitalize_next = True
        widget = _make_widget("some text")  # Doesn't end with .!?
        tp.append_text_to_widget("word", widget)
        call_text = widget.insert.call_args[0][1]
        # Should be capitalized
        assert "W" in call_text

    def test_capitalize_next_cleared_after_use(self):
        tp = TextProcessor()
        tp.capitalize_next = True
        widget = _make_widget("")
        tp.append_text_to_widget("word", widget)
        assert tp.capitalize_next is False


# ===========================================================================
# delete_last_word
# ===========================================================================

class TestDeleteLastWord:
    def test_deletes_last_word(self):
        tp = TextProcessor()
        widget = _make_widget("hello world")
        tp.delete_last_word(widget)
        # delete should have been called, then insert with remaining words
        widget.delete.assert_called_once()
        widget.insert.assert_called_once()
        call_text = widget.insert.call_args[0][1]
        assert call_text == "hello"

    def test_no_op_on_empty_widget(self):
        tp = TextProcessor()
        widget = _make_widget("")
        tp.delete_last_word(widget)
        # Empty content — no delete or insert
        widget.delete.assert_not_called()

    def test_single_word_results_in_empty(self):
        tp = TextProcessor()
        widget = _make_widget("word")
        tp.delete_last_word(widget)
        # After deleting the only word, insert should be called with empty string
        call_text = widget.insert.call_args[0][1]
        assert call_text == ""

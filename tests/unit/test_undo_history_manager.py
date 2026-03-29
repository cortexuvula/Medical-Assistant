"""
Tests for src/ui/undo_history_manager.py

Covers UndoHistoryEntry (dataclass fields, get_display_text formatting);
UndoHistoryManager (record_change, get_history, get_undoable_count,
record_undo, record_redo, clear_history, clear_all_history,
get_widget_names, max_entries cap); get_undo_history_manager singleton.
No network, no Tkinter, no I/O.
"""

import sys
import pytest
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ui.undo_history_manager import (
    UndoHistoryEntry, UndoHistoryManager, get_undo_history_manager
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(action="typing", preview="hello", widget="soap_text"):
    return UndoHistoryEntry(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        action_type=action,
        preview=preview,
        widget_name=widget,
    )


def _manager(max_entries=50):
    return UndoHistoryManager(max_entries=max_entries)


# ===========================================================================
# UndoHistoryEntry
# ===========================================================================

class TestUndoHistoryEntry:
    def test_timestamp_stored(self):
        ts = datetime(2024, 6, 15, 10, 30, 0)
        e = UndoHistoryEntry(timestamp=ts, action_type="typing", preview="test", widget_name="w")
        assert e.timestamp == ts

    def test_action_type_stored(self):
        e = _entry(action="paste")
        assert e.action_type == "paste"

    def test_preview_stored(self):
        e = _entry(preview="some preview text")
        assert e.preview == "some preview text"

    def test_widget_name_stored(self):
        e = _entry(widget="letter_text")
        assert e.widget_name == "letter_text"

    def test_get_display_text_returns_string(self):
        assert isinstance(_entry().get_display_text(), str)

    def test_get_display_text_contains_time(self):
        e = _entry()
        text = e.get_display_text()
        assert "12:00:00" in text

    def test_get_display_text_typing_shows_text_input(self):
        e = _entry(action="typing")
        assert "Text input" in e.get_display_text()

    def test_get_display_text_delete_shows_delete(self):
        e = _entry(action="delete")
        assert "Delete" in e.get_display_text()

    def test_get_display_text_paste_shows_paste(self):
        e = _entry(action="paste")
        assert "Paste" in e.get_display_text()

    def test_get_display_text_ai_refine(self):
        e = _entry(action="ai_refine")
        assert "AI Refine" in e.get_display_text()

    def test_get_display_text_ai_improve(self):
        e = _entry(action="ai_improve")
        assert "AI Improve" in e.get_display_text()

    def test_get_display_text_clear(self):
        e = _entry(action="clear")
        assert "Clear all" in e.get_display_text()

    def test_get_display_text_unknown_action_title_case(self):
        e = _entry(action="custom_action")
        text = e.get_display_text()
        assert "Custom_Action" in text or "custom_action" in text.lower()

    def test_get_display_text_long_preview_truncated(self):
        long_preview = "x" * 50
        e = _entry(preview=long_preview)
        text = e.get_display_text()
        assert "..." in text

    def test_get_display_text_short_preview_not_truncated(self):
        e = _entry(preview="short")
        assert "..." not in e.get_display_text()

    def test_get_display_text_newline_replaced(self):
        e = _entry(preview="line1\nline2")
        assert "\n" not in e.get_display_text()

    def test_get_display_text_contains_preview_content(self):
        e = _entry(preview="patient has hypertension")
        assert "patient has hypertension" in e.get_display_text()


# ===========================================================================
# UndoHistoryManager — init
# ===========================================================================

class TestUndoHistoryManagerInit:
    def test_max_entries_stored(self):
        m = _manager(max_entries=25)
        assert m._max_entries == 25

    def test_history_empty_initially(self):
        m = _manager()
        assert m._history == {}

    def test_undo_counts_empty_initially(self):
        m = _manager()
        assert m._undo_counts == {}


# ===========================================================================
# record_change
# ===========================================================================

class TestRecordChange:
    def test_creates_history_for_new_widget(self):
        m = _manager()
        m.record_change("w1", "typing", "hello")
        assert "w1" in m._history

    def test_entry_has_correct_action(self):
        m = _manager()
        m.record_change("w1", "paste", "pasted text")
        entries = m.get_history("w1")
        assert entries[0].action_type == "paste"

    def test_entry_has_correct_preview(self):
        m = _manager()
        m.record_change("w1", "typing", "some text")
        entries = m.get_history("w1")
        assert entries[0].preview == "some text"

    def test_empty_preview_stored_as_empty_placeholder(self):
        m = _manager()
        m.record_change("w1", "typing", "")
        entries = m.get_history("w1")
        assert entries[0].preview == "(empty)"

    def test_multiple_changes_appended(self):
        m = _manager()
        m.record_change("w1", "typing", "first")
        m.record_change("w1", "paste", "second")
        assert len(m.get_history("w1")) == 2

    def test_record_resets_undo_count(self):
        m = _manager()
        m.record_change("w1", "typing", "first")
        m.record_undo("w1")
        assert m._undo_counts["w1"] == 1
        m.record_change("w1", "typing", "second")
        assert m._undo_counts["w1"] == 0

    def test_max_entries_cap(self):
        m = _manager(max_entries=5)
        for i in range(10):
            m.record_change("w1", "typing", f"change {i}")
        assert len(m.get_history("w1")) == 5

    def test_multiple_widgets_tracked_separately(self):
        m = _manager()
        m.record_change("widget_a", "typing", "a text")
        m.record_change("widget_b", "paste", "b text")
        assert len(m.get_history("widget_a")) == 1
        assert len(m.get_history("widget_b")) == 1


# ===========================================================================
# get_history
# ===========================================================================

class TestGetHistory:
    def test_returns_empty_for_unknown_widget(self):
        m = _manager()
        assert m.get_history("nonexistent") == []

    def test_returns_list(self):
        m = _manager()
        m.record_change("w1", "typing", "text")
        assert isinstance(m.get_history("w1"), list)

    def test_most_recent_first(self):
        m = _manager()
        m.record_change("w1", "typing", "first")
        m.record_change("w1", "paste", "second")
        history = m.get_history("w1")
        assert history[0].action_type == "paste"
        assert history[1].action_type == "typing"

    def test_entries_are_undo_history_entry(self):
        m = _manager()
        m.record_change("w1", "typing", "text")
        entries = m.get_history("w1")
        assert isinstance(entries[0], UndoHistoryEntry)


# ===========================================================================
# get_undoable_count
# ===========================================================================

class TestGetUndoableCount:
    def test_zero_for_unknown_widget(self):
        m = _manager()
        assert m.get_undoable_count("unknown") == 0

    def test_equals_history_length_initially(self):
        m = _manager()
        m.record_change("w1", "typing", "a")
        m.record_change("w1", "typing", "b")
        assert m.get_undoable_count("w1") == 2

    def test_decrements_after_undo(self):
        m = _manager()
        m.record_change("w1", "typing", "a")
        m.record_change("w1", "typing", "b")
        m.record_undo("w1")
        assert m.get_undoable_count("w1") == 1


# ===========================================================================
# record_undo
# ===========================================================================

class TestRecordUndo:
    def test_increments_undo_count(self):
        m = _manager()
        m.record_change("w1", "typing", "a")
        m.record_undo("w1")
        assert m._undo_counts["w1"] == 1

    def test_caps_at_history_length(self):
        m = _manager()
        m.record_change("w1", "typing", "a")
        m.record_undo("w1")
        m.record_undo("w1")
        m.record_undo("w1")  # Beyond history length
        assert m._undo_counts["w1"] == 1  # Max is 1 (one entry)

    def test_no_error_for_unknown_widget(self):
        m = _manager()
        m.record_undo("nonexistent")  # Should not raise


# ===========================================================================
# record_redo
# ===========================================================================

class TestRecordRedo:
    def test_decrements_undo_count(self):
        m = _manager()
        m.record_change("w1", "typing", "a")
        m.record_undo("w1")
        m.record_redo("w1")
        assert m._undo_counts["w1"] == 0

    def test_does_not_go_below_zero(self):
        m = _manager()
        m.record_change("w1", "typing", "a")
        m.record_redo("w1")
        assert m._undo_counts["w1"] == 0

    def test_no_error_for_unknown_widget(self):
        m = _manager()
        m.record_redo("nonexistent")  # Should not raise


# ===========================================================================
# clear_history
# ===========================================================================

class TestClearHistory:
    def test_empties_widget_history(self):
        m = _manager()
        m.record_change("w1", "typing", "text")
        m.clear_history("w1")
        assert m.get_history("w1") == []

    def test_resets_undo_count(self):
        m = _manager()
        m.record_change("w1", "typing", "text")
        m.record_undo("w1")
        m.clear_history("w1")
        assert m._undo_counts["w1"] == 0

    def test_no_error_for_unknown_widget(self):
        m = _manager()
        m.clear_history("nonexistent")  # Should not raise

    def test_does_not_affect_other_widgets(self):
        m = _manager()
        m.record_change("w1", "typing", "a")
        m.record_change("w2", "typing", "b")
        m.clear_history("w1")
        assert len(m.get_history("w2")) == 1


# ===========================================================================
# clear_all_history
# ===========================================================================

class TestClearAllHistory:
    def test_empties_all_histories(self):
        m = _manager()
        m.record_change("w1", "typing", "a")
        m.record_change("w2", "typing", "b")
        m.clear_all_history()
        assert m.get_history("w1") == []
        assert m.get_history("w2") == []

    def test_clears_undo_counts(self):
        m = _manager()
        m.record_change("w1", "typing", "a")
        m.record_undo("w1")
        m.clear_all_history()
        assert m._undo_counts == {}

    def test_no_error_when_empty(self):
        m = _manager()
        m.clear_all_history()  # Should not raise


# ===========================================================================
# get_widget_names
# ===========================================================================

class TestGetWidgetNames:
    def test_empty_initially(self):
        m = _manager()
        assert m.get_widget_names() == []

    def test_returns_registered_widgets(self):
        m = _manager()
        m.record_change("widget_a", "typing", "a")
        m.record_change("widget_b", "paste", "b")
        names = m.get_widget_names()
        assert "widget_a" in names
        assert "widget_b" in names

    def test_returns_list(self):
        m = _manager()
        m.record_change("w1", "typing", "text")
        assert isinstance(m.get_widget_names(), list)

    def test_after_clear_all_empty(self):
        m = _manager()
        m.record_change("w1", "typing", "text")
        m.clear_all_history()
        assert m.get_widget_names() == []


# ===========================================================================
# get_undo_history_manager
# ===========================================================================

class TestGetUndoHistoryManager:
    def test_returns_undo_history_manager(self):
        mgr = get_undo_history_manager()
        assert isinstance(mgr, UndoHistoryManager)

    def test_same_instance_each_call(self):
        mgr1 = get_undo_history_manager()
        mgr2 = get_undo_history_manager()
        assert mgr1 is mgr2

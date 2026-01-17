"""
Undo History Manager Module

Tracks text modifications for undo history display since tkinter's
Text widget doesn't expose its internal undo stack.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque
from utils.structured_logging import get_logger

logger = get_logger(__name__)


@dataclass
class UndoHistoryEntry:
    """Represents a single entry in the undo history."""
    timestamp: datetime
    action_type: str  # "typing", "delete", "paste", "ai_refine", "ai_improve", "clear", etc.
    preview: str      # First 50 chars of changed text
    widget_name: str  # Name of the text widget

    def get_display_text(self) -> str:
        """Get formatted text for display in history list."""
        time_str = self.timestamp.strftime("%H:%M:%S")
        action_display = {
            "typing": "Text input",
            "delete": "Delete",
            "paste": "Paste",
            "ai_refine": "AI Refine",
            "ai_improve": "AI Improve",
            "clear": "Clear all",
            "replace": "Replace",
            "scratch_that": "Scratch that",
            "load": "Load content",
        }.get(self.action_type, self.action_type.title())

        preview = self.preview[:40] + "..." if len(self.preview) > 40 else self.preview
        preview = preview.replace("\n", " ")

        return f"[{time_str}] {action_display}: {preview}"


class UndoHistoryManager:
    """Manages undo history tracking for text widgets.

    Since tkinter's Text widget doesn't expose its undo stack,
    this class tracks changes manually for display purposes.
    The actual undo/redo is still performed by tkinter.
    """

    def __init__(self, max_entries: int = 50):
        """Initialize the undo history manager.

        Args:
            max_entries: Maximum number of history entries to keep per widget
        """
        self._history: Dict[str, deque] = {}
        self._max_entries = max_entries
        self._undo_counts: Dict[str, int] = {}  # Track how many undos have been performed

    def record_change(
        self,
        widget_name: str,
        action_type: str,
        text_preview: str
    ) -> None:
        """Record a change in the undo history.

        Args:
            widget_name: Name/identifier of the text widget
            action_type: Type of action (typing, delete, paste, ai_refine, etc.)
            text_preview: Preview text of the change
        """
        if widget_name not in self._history:
            self._history[widget_name] = deque(maxlen=self._max_entries)
            self._undo_counts[widget_name] = 0

        entry = UndoHistoryEntry(
            timestamp=datetime.now(),
            action_type=action_type,
            preview=text_preview or "(empty)",
            widget_name=widget_name
        )

        self._history[widget_name].append(entry)
        # Reset undo count when new change is recorded
        self._undo_counts[widget_name] = 0

        logger.debug(f"Recorded {action_type} for {widget_name}: {text_preview[:30]}...")

    def get_history(self, widget_name: str) -> List[UndoHistoryEntry]:
        """Get the undo history for a widget.

        Args:
            widget_name: Name/identifier of the text widget

        Returns:
            List of history entries, most recent first
        """
        if widget_name not in self._history:
            return []

        # Return in reverse order (most recent first)
        return list(reversed(self._history[widget_name]))

    def get_undoable_count(self, widget_name: str) -> int:
        """Get the number of entries that can be undone.

        Args:
            widget_name: Name/identifier of the text widget

        Returns:
            Number of undoable entries
        """
        if widget_name not in self._history:
            return 0

        return len(self._history[widget_name]) - self._undo_counts.get(widget_name, 0)

    def record_undo(self, widget_name: str) -> None:
        """Record that an undo was performed.

        Args:
            widget_name: Name/identifier of the text widget
        """
        if widget_name in self._undo_counts:
            max_undos = len(self._history.get(widget_name, []))
            self._undo_counts[widget_name] = min(
                self._undo_counts[widget_name] + 1,
                max_undos
            )

    def record_redo(self, widget_name: str) -> None:
        """Record that a redo was performed.

        Args:
            widget_name: Name/identifier of the text widget
        """
        if widget_name in self._undo_counts:
            self._undo_counts[widget_name] = max(
                self._undo_counts[widget_name] - 1,
                0
            )

    def clear_history(self, widget_name: str) -> None:
        """Clear the undo history for a widget.

        Args:
            widget_name: Name/identifier of the text widget
        """
        if widget_name in self._history:
            self._history[widget_name].clear()
            self._undo_counts[widget_name] = 0
            logger.debug(f"Cleared history for {widget_name}")

    def clear_all_history(self) -> None:
        """Clear all undo history."""
        self._history.clear()
        self._undo_counts.clear()
        logger.debug("Cleared all undo history")

    def get_widget_names(self) -> List[str]:
        """Get all widget names that have history.

        Returns:
            List of widget names
        """
        return list(self._history.keys())


# Global instance for the application
_undo_history_manager: Optional[UndoHistoryManager] = None


def get_undo_history_manager() -> UndoHistoryManager:
    """Get the global undo history manager instance.

    Returns:
        The global UndoHistoryManager instance
    """
    global _undo_history_manager
    if _undo_history_manager is None:
        _undo_history_manager = UndoHistoryManager()
    return _undo_history_manager

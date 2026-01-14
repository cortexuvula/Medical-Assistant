"""
Recordings Tab Component for Medical Assistant
Handles recordings management UI and operations

This module has been refactored to use mixins for better separation of concerns:
- RecordingsTabUIMixin: Widget creation and layout
- RecordingsTabDataMixin: Data loading, caching, filtering
- RecordingsTabEventsMixin: Event handlers and batch processing
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import Dict, Callable, Optional, List, Protocol, runtime_checkable, Any
import logging

from ui.components.recordings_tab_ui import RecordingsTabUIMixin
from ui.components.recordings_tab_data import RecordingsTabDataMixin
from ui.components.recordings_tab_events import RecordingsTabEventsMixin


@runtime_checkable
class RecordingsDataProvider(Protocol):
    """Protocol defining the interface for recordings data access.

    This protocol decouples the RecordingsTab UI from the database layer,
    allowing for easier testing and potential swapping of data sources.
    """

    def get_all_recordings(self) -> List[Dict[str, Any]]:
        """Get all recordings from the data source."""
        ...

    def get_recording(self, recording_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific recording by ID."""
        ...

    def delete_recording(self, recording_id: int) -> bool:
        """Delete a recording by ID."""
        ...

    def clear_all_recordings(self) -> bool:
        """Clear all recordings from the data source."""
        ...


class RecordingsTab(RecordingsTabUIMixin, RecordingsTabDataMixin, RecordingsTabEventsMixin):
    """Manages the Recordings workflow tab UI components.

    This class combines three mixins:
    - RecordingsTabUIMixin: Widget creation, layout, display states
    - RecordingsTabDataMixin: Data loading, caching, filtering, export
    - RecordingsTabEventsMixin: Delete, reprocess, batch processing handlers
    """

    def __init__(self, parent_ui, data_provider: Optional[RecordingsDataProvider] = None):
        """Initialize the RecordingsTab component.

        Args:
            parent_ui: Reference to the parent WorkflowUI instance
            data_provider: Optional data provider for recordings. If None,
                          falls back to parent.db for backwards compatibility.
        """
        self.parent_ui = parent_ui
        self.parent = parent_ui.parent
        self.components = parent_ui.components

        # Data provider - use injected provider or fall back to parent.db
        self._data_provider = data_provider

        # Recording tree components (set by UI mixin)
        self.recordings_tree = None
        self.recordings_search_var = None
        self.recording_count_label = None
        self.recordings_context_menu = None

        # Recordings cache (used by data mixin)
        self._recordings_cache: Optional[List[Dict[str, Any]]] = None
        self._recordings_cache_time: float = 0.0
        self.RECORDINGS_CACHE_TTL = 10.0  # seconds

        # Batch processing state (used by events mixin)
        self.batch_progress_dialog = None
        self.batch_failed_count = 0

        # Auto-refresh timer state (used by data mixin)
        self._auto_refresh_interval = 60000  # 60 seconds in milliseconds
        self._auto_refresh_job = None

        # Refresh-in-progress flag (used by data mixin)
        self._refresh_in_progress = False

    @property
    def data_provider(self) -> RecordingsDataProvider:
        """Get the data provider, falling back to parent.db if not set.

        This property enables gradual migration from tight coupling to
        dependency injection without breaking existing code.
        """
        if self._data_provider is not None:
            return self._data_provider
        return self.parent.db

    @data_provider.setter
    def data_provider(self, provider: RecordingsDataProvider) -> None:
        """Set the data provider."""
        self._data_provider = provider


__all__ = ["RecordingsTab", "RecordingsDataProvider"]

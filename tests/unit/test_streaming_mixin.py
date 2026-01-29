"""
Unit tests for StreamingMixin.

Tests cover:
- _append_streaming_chunk schedules on main thread
- Widget enable/disable during streaming
- Auto-scroll behavior
- Start/finish streaming display
- Text widget content updates
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import threading

from processing.generators.base import StreamingMixin


@pytest.fixture
def mock_app():
    """Create mock application instance."""
    app = Mock()
    app.after = Mock(side_effect=lambda delay, fn: fn())  # Execute immediately
    app.status_manager = Mock()
    app.progress_bar = Mock()
    return app


@pytest.fixture
def mock_text_widget():
    """Create mock text widget."""
    widget = Mock()
    widget.cget.return_value = 'normal'
    widget.configure = Mock()
    widget.insert = Mock()
    widget.delete = Mock()
    widget.see = Mock()
    widget.update_idletasks = Mock()
    widget.edit_separator = Mock()
    return widget


@pytest.fixture
def streaming_mixin(mock_app):
    """Create StreamingMixin instance."""
    mixin = StreamingMixin()
    mixin.app = mock_app
    return mixin


class TestAppendStreamingChunk:
    """Tests for _append_streaming_chunk method."""

    def test_schedules_on_main_thread(self, streaming_mixin, mock_app, mock_text_widget):
        """Test that chunk appending is scheduled via app.after."""
        streaming_mixin._append_streaming_chunk(mock_text_widget, "test chunk")

        mock_app.after.assert_called_once()
        # First arg should be 0 (immediate)
        assert mock_app.after.call_args[0][0] == 0

    def test_inserts_chunk_at_end(self, streaming_mixin, mock_text_widget):
        """Test that chunk is inserted at end of widget."""
        streaming_mixin._append_streaming_chunk(mock_text_widget, "new content")

        mock_text_widget.insert.assert_called_once_with('end', 'new content')

    def test_enables_widget_before_insert(self, streaming_mixin, mock_text_widget):
        """Test that widget is enabled before inserting."""
        mock_text_widget.cget.return_value = 'disabled'

        streaming_mixin._append_streaming_chunk(mock_text_widget, "chunk")

        # Should configure to normal before insert
        configure_calls = [c[1] for c in mock_text_widget.configure.call_args_list]
        assert any(call.get('state') == 'normal' for call in configure_calls)

    def test_restores_disabled_state(self, streaming_mixin, mock_text_widget):
        """Test that disabled state is restored after insert."""
        mock_text_widget.cget.return_value = 'disabled'

        streaming_mixin._append_streaming_chunk(mock_text_widget, "chunk")

        # Should configure back to disabled after insert
        configure_calls = mock_text_widget.configure.call_args_list
        # Last configure should set back to disabled
        assert configure_calls[-1][1].get('state') == 'disabled'

    def test_auto_scrolls_to_end(self, streaming_mixin, mock_text_widget):
        """Test that widget scrolls to show new content."""
        streaming_mixin._append_streaming_chunk(mock_text_widget, "chunk")

        mock_text_widget.see.assert_called_once_with('end')

    def test_forces_update(self, streaming_mixin, mock_text_widget):
        """Test that widget update is forced."""
        streaming_mixin._append_streaming_chunk(mock_text_widget, "chunk")

        mock_text_widget.update_idletasks.assert_called_once()

    def test_handles_widget_exception(self, streaming_mixin, mock_text_widget):
        """Test that exceptions in widget updates are handled."""
        mock_text_widget.insert.side_effect = Exception("Widget error")

        # Should not raise
        streaming_mixin._append_streaming_chunk(mock_text_widget, "chunk")

    def test_preserves_normal_state(self, streaming_mixin, mock_text_widget):
        """Test that normal state is preserved when widget was already normal."""
        mock_text_widget.cget.return_value = 'normal'

        streaming_mixin._append_streaming_chunk(mock_text_widget, "chunk")

        # Should not set to disabled if it wasn't disabled
        configure_calls = mock_text_widget.configure.call_args_list
        final_states = [c[1].get('state') for c in configure_calls if 'state' in c[1]]
        # Should only have one state change (to normal) since it was already normal
        assert 'disabled' not in final_states


class TestStartStreamingDisplay:
    """Tests for _start_streaming_display method."""

    def test_schedules_setup_on_main_thread(self, streaming_mixin, mock_app, mock_text_widget):
        """Test that setup is scheduled via app.after."""
        streaming_mixin._start_streaming_display(mock_text_widget, "Loading...")

        # Should have scheduled at least once
        assert mock_app.after.called

    def test_clears_widget_content(self, streaming_mixin, mock_text_widget):
        """Test that widget content is cleared."""
        streaming_mixin._start_streaming_display(mock_text_widget, "Status")

        mock_text_widget.delete.assert_called_once_with('1.0', 'end')

    def test_enables_widget(self, streaming_mixin, mock_text_widget):
        """Test that widget is enabled for editing."""
        streaming_mixin._start_streaming_display(mock_text_widget, "Status")

        mock_text_widget.configure.assert_called()
        call_kwargs = mock_text_widget.configure.call_args[1]
        assert call_kwargs.get('state') == 'normal'

    def test_updates_status_manager(self, streaming_mixin, mock_app, mock_text_widget):
        """Test that status manager is updated."""
        streaming_mixin._start_streaming_display(mock_text_widget, "Generating...")

        mock_app.status_manager.progress.assert_called_once_with("Generating...")

    def test_handles_exception(self, streaming_mixin, mock_text_widget):
        """Test that exceptions are handled gracefully."""
        mock_text_widget.configure.side_effect = Exception("Error")

        # Should not raise
        streaming_mixin._start_streaming_display(mock_text_widget, "Status")


class TestFinishStreamingDisplay:
    """Tests for _finish_streaming_display method."""

    def test_schedules_on_main_thread(self, streaming_mixin, mock_app, mock_text_widget):
        """Test that finish is scheduled via app.after."""
        streaming_mixin._finish_streaming_display(mock_text_widget, "Done")

        assert mock_app.after.called

    def test_adds_edit_separator(self, streaming_mixin, mock_text_widget):
        """Test that edit separator is added for undo history."""
        streaming_mixin._finish_streaming_display(mock_text_widget, "Done")

        mock_text_widget.edit_separator.assert_called_once()

    def test_stops_progress_bar(self, streaming_mixin, mock_app, mock_text_widget):
        """Test that progress bar is stopped."""
        streaming_mixin._finish_streaming_display(mock_text_widget, "Done")

        mock_app.progress_bar.stop.assert_called_once()
        mock_app.progress_bar.pack_forget.assert_called_once()

    def test_reenables_button_when_provided(self, streaming_mixin, mock_app, mock_text_widget):
        """Test that button is re-enabled when provided."""
        mock_button = Mock()

        streaming_mixin._finish_streaming_display(mock_text_widget, "Done", button=mock_button)

        mock_button.config.assert_called()

    def test_updates_status_success(self, streaming_mixin, mock_app, mock_text_widget):
        """Test that success status is shown."""
        streaming_mixin._finish_streaming_display(mock_text_widget, "Operation complete")

        mock_app.status_manager.success.assert_called_once_with("Operation complete")

    def test_handles_no_button(self, streaming_mixin, mock_app, mock_text_widget):
        """Test that None button is handled."""
        # Should not raise
        streaming_mixin._finish_streaming_display(mock_text_widget, "Done", button=None)

    def test_handles_exception(self, streaming_mixin, mock_text_widget):
        """Test that exceptions are handled."""
        mock_text_widget.edit_separator.side_effect = Exception("Error")

        # Should not raise
        streaming_mixin._finish_streaming_display(mock_text_widget, "Done")


class TestUpdateTextWidgetContent:
    """Tests for _update_text_widget_content method."""

    def test_enables_widget(self, streaming_mixin, mock_text_widget):
        """Test that widget is enabled for editing."""
        streaming_mixin._update_text_widget_content(mock_text_widget, "Content")

        mock_text_widget.configure.assert_called()
        call_kwargs = mock_text_widget.configure.call_args[1]
        assert call_kwargs.get('state') == 'normal'

    def test_clears_existing_content(self, streaming_mixin, mock_text_widget):
        """Test that existing content is cleared."""
        streaming_mixin._update_text_widget_content(mock_text_widget, "New")

        mock_text_widget.delete.assert_called_once_with('1.0', 'end')

    def test_inserts_new_content(self, streaming_mixin, mock_text_widget):
        """Test that new content is inserted."""
        streaming_mixin._update_text_widget_content(mock_text_widget, "New content")

        mock_text_widget.insert.assert_called_once_with('1.0', 'New content')

    def test_scrolls_to_top(self, streaming_mixin, mock_text_widget):
        """Test that widget scrolls to top after update."""
        streaming_mixin._update_text_widget_content(mock_text_widget, "Content")

        mock_text_widget.see.assert_called_once_with('1.0')

    def test_adds_edit_separator(self, streaming_mixin, mock_text_widget):
        """Test that edit separator is added."""
        streaming_mixin._update_text_widget_content(mock_text_widget, "Content")

        mock_text_widget.edit_separator.assert_called_once()

    def test_forces_update(self, streaming_mixin, mock_text_widget):
        """Test that widget refresh is forced."""
        streaming_mixin._update_text_widget_content(mock_text_widget, "Content")

        mock_text_widget.update_idletasks.assert_called_once()

    def test_handles_exception(self, streaming_mixin, mock_text_widget):
        """Test that exceptions are handled."""
        mock_text_widget.insert.side_effect = Exception("Error")

        # Should not raise
        streaming_mixin._update_text_widget_content(mock_text_widget, "Content")


class TestUpdateAnalysisPanel:
    """Tests for _update_analysis_panel method."""

    def test_handles_none_widget(self, streaming_mixin):
        """Test that None widget is handled."""
        # Should not raise
        streaming_mixin._update_analysis_panel(None, "Content")

    def test_enables_widget_for_update(self, streaming_mixin, mock_text_widget):
        """Test that widget is enabled for update."""
        streaming_mixin._update_analysis_panel(mock_text_widget, "Content")

        mock_text_widget.config.assert_called()

    def test_clears_content(self, streaming_mixin, mock_text_widget):
        """Test that existing content is cleared."""
        streaming_mixin._update_analysis_panel(mock_text_widget, "New")

        mock_text_widget.delete.assert_called_once_with('1.0', 'end')

    def test_inserts_content(self, streaming_mixin, mock_text_widget):
        """Test that content is inserted."""
        streaming_mixin._update_analysis_panel(mock_text_widget, "Panel content")

        mock_text_widget.insert.assert_called_once_with('1.0', 'Panel content')

    def test_disables_widget_after_update(self, streaming_mixin, mock_text_widget):
        """Test that widget is disabled after update."""
        streaming_mixin._update_analysis_panel(mock_text_widget, "Content")

        # Last config call should disable
        config_calls = mock_text_widget.config.call_args_list
        assert config_calls[-1][1].get('state') == 'disabled'

    def test_handles_exception(self, streaming_mixin, mock_text_widget):
        """Test that exceptions are handled."""
        mock_text_widget.insert.side_effect = Exception("Error")

        # Should not raise
        streaming_mixin._update_analysis_panel(mock_text_widget, "Content")


class TestThreadSafety:
    """Tests for thread safety of streaming operations."""

    def test_chunk_append_from_different_thread(self, streaming_mixin, mock_app, mock_text_widget):
        """Test that chunk can be appended from different thread."""
        results = []

        def append_chunk():
            streaming_mixin._append_streaming_chunk(mock_text_widget, "chunk")
            results.append(True)

        thread = threading.Thread(target=append_chunk)
        thread.start()
        thread.join()

        assert len(results) == 1
        assert mock_app.after.called

    def test_concurrent_chunk_appends(self, streaming_mixin, mock_app, mock_text_widget):
        """Test concurrent chunk appends."""
        call_count = [0]

        def mock_after(delay, fn):
            call_count[0] += 1
            fn()

        mock_app.after.side_effect = mock_after

        threads = []
        for i in range(10):
            t = threading.Thread(
                target=lambda: streaming_mixin._append_streaming_chunk(
                    mock_text_widget, f"chunk{i}"
                )
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert call_count[0] == 10

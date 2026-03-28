"""Tests for utils.cleanup_utils — clear_all_content and clear_content_except_context.

All Tkinter widgets are mocked so these tests run headless.
"""

import pytest
from unittest.mock import MagicMock, patch, call
import tkinter as tk


def make_widget():
    """Return a mock that acts like a Tkinter Text widget."""
    w = MagicMock()
    return w


def make_app(**extra_attrs):
    """Build a minimal fake MedicalDictationApp with text widgets."""
    app = MagicMock()
    app.transcript_text = make_widget()
    app.soap_text = make_widget()
    app.referral_text = make_widget()
    app.letter_text = make_widget()
    app.context_text = make_widget()

    # Default: no chat_text, no ui, no audio_state_manager
    del app.chat_text  # ensure hasattr returns False by default
    del app.ui
    del app.audio_state_manager
    del app.current_recording_id
    del app._pending_medication_analysis
    del app._pending_differential_analysis

    for attr, val in extra_attrs.items():
        setattr(app, attr, val)

    return app


class TestClearAllContent:
    def _call(self, app):
        from utils.cleanup_utils import clear_all_content
        clear_all_content(app)

    def test_clears_core_text_widgets(self):
        app = make_app()
        self._call(app)
        app.transcript_text.delete.assert_called_with("1.0", tk.END)
        app.soap_text.delete.assert_called_with("1.0", tk.END)
        app.referral_text.delete.assert_called_with("1.0", tk.END)
        app.letter_text.delete.assert_called_with("1.0", tk.END)
        app.context_text.delete.assert_called_with("1.0", tk.END)

    def test_calls_edit_reset_on_widgets(self):
        app = make_app()
        self._call(app)
        app.transcript_text.edit_reset.assert_called_once()
        app.soap_text.edit_reset.assert_called_once()

    def test_clears_chat_text_when_present(self):
        chat = make_widget()
        app = make_app(chat_text=chat)
        self._call(app)
        chat.delete.assert_called_with("1.0", tk.END)

    def test_no_chat_text_does_not_raise(self):
        app = make_app()
        self._call(app)  # Should not raise

    def test_clears_audio_via_state_manager(self):
        asm = MagicMock()
        app = make_app(audio_state_manager=asm)
        self._call(app)
        asm.clear_all.assert_called_once()

    def test_no_audio_state_manager_does_not_raise(self):
        app = make_app()
        self._call(app)  # Should not raise

    def test_resets_current_recording_id(self):
        app = make_app(current_recording_id=42)
        self._call(app)
        assert app.current_recording_id is None

    def test_clears_pending_medication_analysis(self):
        app = make_app(_pending_medication_analysis={"some": "data"})
        self._call(app)
        assert app._pending_medication_analysis is None

    def test_clears_pending_differential_analysis(self):
        app = make_app(_pending_differential_analysis={"some": "data"})
        self._call(app)
        assert app._pending_differential_analysis is None

    def test_calls_update_status(self):
        app = make_app()
        app.update_status = MagicMock()
        self._call(app)
        app.update_status.assert_called_once()

    def test_no_update_status_does_not_raise(self):
        app = make_app()
        del app.update_status
        self._call(app)  # Should not raise

    def test_clears_analysis_widgets_when_ui_present(self):
        med_widget = MagicMock()
        diff_widget = MagicMock()

        ui = MagicMock()
        ui.components = {
            "medication_analysis_text": med_widget,
            "differential_analysis_text": diff_widget,
        }
        app = make_app(ui=ui)
        self._call(app)

        med_widget.config.assert_any_call(state="normal")
        med_widget.delete.assert_called_with("1.0", tk.END)
        med_widget.config.assert_called_with(state="disabled")

    def test_analysis_widget_tcl_error_is_swallowed(self):
        bad_widget = MagicMock()
        bad_widget.config.side_effect = [None, tk.TclError("destroyed")]

        ui = MagicMock()
        ui.components = {"medication_analysis_text": bad_widget, "differential_analysis_text": None}
        app = make_app(ui=ui)
        self._call(app)  # Should not raise

    def test_none_widget_skipped_gracefully(self):
        ui = MagicMock()
        ui.components = {
            "medication_analysis_text": None,
            "differential_analysis_text": None,
        }
        app = make_app(ui=ui)
        self._call(app)  # Should not raise


class TestClearContentExceptContext:
    def _call(self, app):
        from utils.cleanup_utils import clear_content_except_context
        clear_content_except_context(app)

    def test_clears_non_context_widgets(self):
        app = make_app()
        self._call(app)
        app.transcript_text.delete.assert_called_with("1.0", tk.END)
        app.soap_text.delete.assert_called_with("1.0", tk.END)
        app.referral_text.delete.assert_called_with("1.0", tk.END)
        app.letter_text.delete.assert_called_with("1.0", tk.END)

    def test_does_not_clear_context_text(self):
        app = make_app()
        self._call(app)
        app.context_text.delete.assert_not_called()

    def test_clears_chat_text_when_present(self):
        chat = make_widget()
        app = make_app(chat_text=chat)
        self._call(app)
        chat.delete.assert_called_with("1.0", tk.END)

    def test_no_chat_text_does_not_raise(self):
        app = make_app()
        self._call(app)

    def test_clears_audio_via_state_manager(self):
        asm = MagicMock()
        app = make_app(audio_state_manager=asm)
        self._call(app)
        asm.clear_all.assert_called_once()

    def test_no_audio_state_manager_does_not_raise(self):
        app = make_app()
        self._call(app)

    def test_resets_current_recording_id(self):
        app = make_app(current_recording_id=99)
        self._call(app)
        assert app.current_recording_id is None

    def test_clears_pending_analyses(self):
        app = make_app(
            _pending_medication_analysis={"x": 1},
            _pending_differential_analysis={"y": 2},
        )
        self._call(app)
        assert app._pending_medication_analysis is None
        assert app._pending_differential_analysis is None

    def test_calls_update_status(self):
        app = make_app()
        app.update_status = MagicMock()
        self._call(app)
        app.update_status.assert_called_once()
        # Status message should mention context preserved
        call_args = app.update_status.call_args[0]
        assert any("context" in str(a).lower() for a in call_args)

    def test_no_update_status_does_not_raise(self):
        app = make_app()
        del app.update_status
        self._call(app)

    def test_edit_reset_called_on_non_context_widgets(self):
        app = make_app()
        self._call(app)
        app.transcript_text.edit_reset.assert_called_once()
        app.soap_text.edit_reset.assert_called_once()
        app.referral_text.edit_reset.assert_called_once()
        app.letter_text.edit_reset.assert_called_once()

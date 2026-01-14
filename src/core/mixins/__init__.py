"""
Mixins Package

Provides mixin classes for MedicalDictationApp to organize functionality.
"""

from core.mixins.app_dialog_mixin import AppDialogMixin
from core.mixins.app_ui_layout_mixin import AppUiLayoutMixin
from core.mixins.app_recording_mixin import AppRecordingMixin

__all__ = [
    "AppDialogMixin",
    "AppUiLayoutMixin",
    "AppRecordingMixin"
]

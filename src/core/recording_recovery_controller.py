"""
Recording Recovery Controller Module

DEPRECATED: This module has been consolidated into core.controllers.recording_controller.
Import from there instead:

    from core.controllers.recording_controller import RecordingController

This file is maintained for backward compatibility only.
"""

import warnings
import logging

logger = logging.getLogger(__name__)

# Re-export RecordingController as RecordingRecoveryController for backward compatibility
from core.controllers.recording_controller import RecordingController as RecordingRecoveryController

# Issue deprecation warning when this module is imported directly
warnings.warn(
    "recording_recovery_controller is deprecated. "
    "Import RecordingController from core.controllers.recording_controller instead.",
    DeprecationWarning,
    stacklevel=2
)

logger.warning("DEPRECATED: recording_recovery_controller.py - use core.controllers.recording_controller instead")

__all__ = ["RecordingRecoveryController"]

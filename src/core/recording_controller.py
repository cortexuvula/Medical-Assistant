"""
Recording Controller Module

DEPRECATED: This module has been consolidated into core.controllers.recording_controller.
Import from there instead:

    from core.controllers.recording_controller import RecordingController

This file is maintained for backward compatibility only.
"""

import warnings

from utils.structured_logging import get_logger

logger = get_logger(__name__)

# Re-export RecordingController for backward compatibility
from core.controllers.recording_controller import RecordingController

# Issue deprecation warning when this module is imported directly
warnings.warn(
    "core.recording_controller is deprecated. "
    "Import RecordingController from core.controllers.recording_controller instead.",
    DeprecationWarning,
    stacklevel=2
)

logger.warning("DEPRECATED: recording_controller.py - use core.controllers.recording_controller instead")

__all__ = ["RecordingController"]

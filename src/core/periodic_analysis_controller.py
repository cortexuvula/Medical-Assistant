"""
Periodic Analysis Controller Module

DEPRECATED: This module has been consolidated into core.controllers.recording_controller.
Import from there instead:

    from core.controllers.recording_controller import RecordingController

This file is maintained for backward compatibility only.
"""

import warnings
import logging

logger = logging.getLogger(__name__)

# Re-export RecordingController as PeriodicAnalysisController for backward compatibility
from core.controllers.recording_controller import RecordingController as PeriodicAnalysisController

# Issue deprecation warning when this module is imported directly
warnings.warn(
    "periodic_analysis_controller is deprecated. "
    "Import RecordingController from core.controllers.recording_controller instead.",
    DeprecationWarning,
    stacklevel=2
)

logger.warning("DEPRECATED: periodic_analysis_controller.py - use core.controllers.recording_controller instead")

__all__ = ["PeriodicAnalysisController"]

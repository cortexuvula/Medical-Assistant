"""
Microphone Controller Module

DEPRECATED: This module has been consolidated into core.controllers.config_controller.
Import from there instead:

    from core.controllers.config_controller import ConfigController

This file is maintained for backward compatibility only.
"""

import warnings

from utils.structured_logging import get_logger

logger = get_logger(__name__)

# Re-export ConfigController as MicrophoneController for backward compatibility
from core.controllers.config_controller import ConfigController as MicrophoneController

# Issue deprecation warning when this module is imported directly
warnings.warn(
    "microphone_controller is deprecated. "
    "Import ConfigController from core.controllers.config_controller instead.",
    DeprecationWarning,
    stacklevel=2
)

logger.warning("DEPRECATED: microphone_controller.py - use core.controllers.config_controller instead")

__all__ = ["MicrophoneController"]

"""
Window State Controller Module

DEPRECATED: This module has been consolidated into core.controllers.window_controller.
Import from there instead:

    from core.controllers.window_controller import WindowController

This file is maintained for backward compatibility only.
"""

import warnings

from utils.structured_logging import get_logger

logger = get_logger(__name__)

# Re-export WindowController as WindowStateController for backward compatibility
from core.controllers.window_controller import WindowController as WindowStateController

# Issue deprecation warning when this module is imported directly
warnings.warn(
    "window_state_controller is deprecated. "
    "Import WindowController from core.controllers.window_controller instead.",
    DeprecationWarning,
    stacklevel=2
)

logger.warning("DEPRECATED: window_state_controller.py - use core.controllers.window_controller instead")

__all__ = ["WindowStateController"]

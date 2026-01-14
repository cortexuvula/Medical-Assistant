"""
Navigation Controller for Medical Assistant

DEPRECATED: This module has been consolidated into core.controllers.window_controller.
Import from there instead:

    from core.controllers.window_controller import WindowController

This file is maintained for backward compatibility only.
"""

import warnings
import logging

logger = logging.getLogger(__name__)

# Re-export WindowController as NavigationController for backward compatibility
from core.controllers.window_controller import WindowController as NavigationController

# Issue deprecation warning when this module is imported directly
warnings.warn(
    "navigation_controller is deprecated. "
    "Import WindowController from core.controllers.window_controller instead.",
    DeprecationWarning,
    stacklevel=2
)

logger.warning("DEPRECATED: navigation_controller.py - use core.controllers.window_controller instead")

__all__ = ["NavigationController"]

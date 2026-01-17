"""
Logs Viewer Controller Module

DEPRECATED: This module has been consolidated into core.controllers.window_controller.
Import from there instead:

    from core.controllers.window_controller import WindowController

This file is maintained for backward compatibility only.
"""

import warnings

from utils.structured_logging import get_logger

logger = get_logger(__name__)

# Re-export WindowController as LogsViewerController for backward compatibility
from core.controllers.window_controller import WindowController as LogsViewerController

# Issue deprecation warning when this module is imported directly
warnings.warn(
    "logs_viewer_controller is deprecated. "
    "Import WindowController from core.controllers.window_controller instead.",
    DeprecationWarning,
    stacklevel=2
)

logger.warning("DEPRECATED: logs_viewer_controller.py - use core.controllers.window_controller instead")

__all__ = ["LogsViewerController"]

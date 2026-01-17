"""
Keyboard Shortcuts Controller Module

DEPRECATED: This module has been consolidated into core.controllers.persistence_controller.
Import from there instead:

    from core.controllers.persistence_controller import PersistenceController

This file is maintained for backward compatibility only.
"""

import warnings

from utils.structured_logging import get_logger

logger = get_logger(__name__)

# Re-export PersistenceController as KeyboardShortcutsController for backward compatibility
from core.controllers.persistence_controller import PersistenceController as KeyboardShortcutsController

# Issue deprecation warning when this module is imported directly
warnings.warn(
    "keyboard_shortcuts_controller is deprecated. "
    "Import PersistenceController from core.controllers.persistence_controller instead.",
    DeprecationWarning,
    stacklevel=2
)

logger.warning("DEPRECATED: keyboard_shortcuts_controller.py - use core.controllers.persistence_controller instead")

__all__ = ["KeyboardShortcutsController"]

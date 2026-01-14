"""
Auto-Save Controller Module

DEPRECATED: This module has been consolidated into core.controllers.persistence_controller.
Import from there instead:

    from core.controllers.persistence_controller import PersistenceController

This file is maintained for backward compatibility only.
"""

import warnings
import logging

logger = logging.getLogger(__name__)

# Re-export PersistenceController as AutoSaveController for backward compatibility
from core.controllers.persistence_controller import PersistenceController as AutoSaveController

# Issue deprecation warning when this module is imported directly
warnings.warn(
    "autosave_controller is deprecated. "
    "Import PersistenceController from core.controllers.persistence_controller instead.",
    DeprecationWarning,
    stacklevel=2
)

logger.warning("DEPRECATED: autosave_controller.py - use core.controllers.persistence_controller instead")

__all__ = ["AutoSaveController"]

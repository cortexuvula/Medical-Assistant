"""
Queue Processing Controller Module

DEPRECATED: This module has been consolidated into core.controllers.processing_controller.
Import from there instead:

    from core.controllers.processing_controller import ProcessingController

This file is maintained for backward compatibility only.
"""

import warnings
import logging

logger = logging.getLogger(__name__)

# Re-export ProcessingController as QueueProcessingController for backward compatibility
from core.controllers.processing_controller import ProcessingController as QueueProcessingController

# Issue deprecation warning when this module is imported directly
warnings.warn(
    "queue_processing_controller is deprecated. "
    "Import ProcessingController from core.controllers.processing_controller instead.",
    DeprecationWarning,
    stacklevel=2
)

logger.warning("DEPRECATED: queue_processing_controller.py - use core.controllers.processing_controller instead")

__all__ = ["QueueProcessingController"]

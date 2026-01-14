"""
Provider Configuration Controller Module

DEPRECATED: This module has been consolidated into core.controllers.config_controller.
Import from there instead:

    from core.controllers.config_controller import ConfigController

This file is maintained for backward compatibility only.
"""

import warnings
import logging

logger = logging.getLogger(__name__)

# Re-export ConfigController as ProviderConfigController for backward compatibility
from core.controllers.config_controller import ConfigController as ProviderConfigController

# Issue deprecation warning when this module is imported directly
warnings.warn(
    "provider_config_controller is deprecated. "
    "Import ConfigController from core.controllers.config_controller instead.",
    DeprecationWarning,
    stacklevel=2
)

logger.warning("DEPRECATED: provider_config_controller.py - use core.controllers.config_controller instead")

__all__ = ["ProviderConfigController"]

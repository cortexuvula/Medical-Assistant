"""
Setup module for Medical Assistant initialization.

This module provides specialized setup classes that break down the
initialization logic from AppInitializer into focused components.

Each setup class handles a specific aspect of initialization:
- ThreadingSetup: Executors and thread pools
- SecuritySetup: API keys and encryption
- DatabaseSetup: Connection pools and migrations
- AudioSetup: Audio handlers and devices
- UISetup: Window configuration and widgets

Usage:
    from core.setup import SetupOrchestrator

    orchestrator = SetupOrchestrator(app)
    orchestrator.initialize_all()
"""

from .base import BaseSetup
from .threading_setup import ThreadingSetup
from .security_setup import SecuritySetup
from .database_setup import DatabaseSetup
from .orchestrator import SetupOrchestrator

__all__ = [
    'BaseSetup',
    'ThreadingSetup',
    'SecuritySetup',
    'DatabaseSetup',
    'SetupOrchestrator',
]

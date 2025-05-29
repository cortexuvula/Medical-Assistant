"""
Runtime hook for Windows to fix asyncio issues with PyInstaller
"""
import sys
import os

# Fix for asyncio TypeError in Python 3.11+ on Windows
if sys.platform == 'win32':
    # Patch asyncio to handle the issue with function() argument 'code' must be code, not str
    import asyncio
    import asyncio.windows_events
    import asyncio.windows_utils
    
    # The issue is related to how PyInstaller handles certain Windows-specific asyncio internals
    # This hook ensures proper initialization of asyncio on Windows
    if hasattr(asyncio, '_windows_utils'):
        asyncio._windows_utils = asyncio.windows_utils
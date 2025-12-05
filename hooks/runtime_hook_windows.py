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

# Fix for ttkbootstrap LabelFrame/Labelframe compatibility
# Some versions of ttkbootstrap use Labelframe (lowercase 'f') instead of LabelFrame
try:
    import ttkbootstrap as ttk
    if not hasattr(ttk, 'LabelFrame') and hasattr(ttk, 'Labelframe'):
        ttk.LabelFrame = ttk.Labelframe
    elif not hasattr(ttk, 'Labelframe') and hasattr(ttk, 'LabelFrame'):
        ttk.Labelframe = ttk.LabelFrame
except ImportError:
    pass
"""
Runtime hook for Windows to fix asyncio issues with PyInstaller
"""
import sys
import os

# Add src directory to path for internal module imports
# This is needed because the internal modules (managers, utils, etc.) are in src/
if hasattr(sys, '_MEIPASS'):
    # Add the _MEIPASS directory itself first
    if sys._MEIPASS not in sys.path:
        sys.path.insert(0, sys._MEIPASS)

    # Add src directory for internal package imports (managers, rag, utils, etc.)
    src_path = os.path.join(sys._MEIPASS, 'src')
    if os.path.exists(src_path) and src_path not in sys.path:
        sys.path.insert(0, src_path)

    # Try to pre-import psycopg to ensure binary extensions are loaded early
    try:
        import psycopg
    except ImportError as e:
        # Log import failure but don't crash - RAG will handle gracefully
        print(f"Runtime hook: psycopg import failed: {e}", file=sys.stderr)

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

# Fix for ttkbootstrap widget name compatibility
# Some versions of ttkbootstrap use different casing (e.g., Labelframe vs LabelFrame)
# This creates aliases for all common widget name variations
try:
    import ttkbootstrap as ttk

    # Widget name mappings: (CamelCase, lowercase_variant)
    widget_aliases = [
        ('LabelFrame', 'Labelframe'),
        ('PanedWindow', 'Panedwindow'),
        ('Checkbutton', 'Checkbutton'),  # Usually consistent but check anyway
        ('Radiobutton', 'Radiobutton'),
        ('Spinbox', 'Spinbox'),
        ('Scrollbar', 'Scrollbar'),
    ]

    for camel_case, lower_case in widget_aliases:
        # If CamelCase doesn't exist but lowercase does, create alias
        if not hasattr(ttk, camel_case) and hasattr(ttk, lower_case):
            setattr(ttk, camel_case, getattr(ttk, lower_case))
        # If lowercase doesn't exist but CamelCase does, create alias
        elif not hasattr(ttk, lower_case) and hasattr(ttk, camel_case):
            setattr(ttk, lower_case, getattr(ttk, camel_case))

except ImportError:
    pass
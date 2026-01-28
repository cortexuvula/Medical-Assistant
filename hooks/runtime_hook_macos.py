"""
Runtime hook for macOS.

Sets up Python path for internal module imports and pre-imports heavy modules.

NOTE: Do NOT call NSApplication.sharedApplication() here! Doing so before Tkinter
initializes causes a crash because Tkinter expects to create/configure the
NSApplication itself. The dock icon is set AFTER Tkinter init in app_initializer.py.
"""
import os
import sys
import platform

if platform.system() == 'Darwin' and hasattr(sys, 'frozen'):
    # Add src directory to path for internal module imports
    if hasattr(sys, '_MEIPASS'):
        if sys._MEIPASS not in sys.path:
            sys.path.insert(0, sys._MEIPASS)
        src_path = os.path.join(sys._MEIPASS, 'src')
        if os.path.exists(src_path) and src_path not in sys.path:
            sys.path.insert(0, src_path)

    # Try to pre-import psycopg for RAG functionality
    try:
        import psycopg
    except ImportError as e:
        print(f"Runtime hook: psycopg import failed: {e}", file=sys.stderr)

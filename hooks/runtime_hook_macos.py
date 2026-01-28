"""
Runtime hook for macOS to fix double dock icon issue.

This hook runs BEFORE the main application code, setting the dock icon
using PyObjC's AppKit before Tkinter can create its own dock representation
with the default Python rocket icon.
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

    # Set dock icon BEFORE Tkinter initializes
    try:
        from AppKit import NSApplication, NSImage

        # Get the application instance
        app = NSApplication.sharedApplication()

        # Find the icon in the bundle's Resources folder
        # PyInstaller places resources in Contents/Resources for .app bundles
        bundle_path = os.path.dirname(os.path.dirname(sys._MEIPASS))
        icon_path = os.path.join(bundle_path, 'Resources', 'icon.icns')

        # Fallback: check in _MEIPASS directly (in case of different bundle structure)
        if not os.path.exists(icon_path):
            icon_path = os.path.join(sys._MEIPASS, 'icon.icns')

        # Another fallback: check parent directory of _MEIPASS
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(sys._MEIPASS), 'icon.icns')

        if os.path.exists(icon_path):
            icon = NSImage.alloc().initWithContentsOfFile_(icon_path)
            if icon:
                app.setApplicationIconImage_(icon)
                print(f"Runtime hook: Set dock icon from {icon_path}")
            else:
                print(f"Runtime hook: Failed to load icon from {icon_path}", file=sys.stderr)
        else:
            print(f"Runtime hook: icon.icns not found at expected paths", file=sys.stderr)

    except ImportError as e:
        # PyObjC not available - this is expected in development
        print(f"Runtime hook: PyObjC not available: {e}", file=sys.stderr)
    except Exception as e:
        # Don't crash the app if icon setting fails
        print(f"Runtime hook: Failed to set dock icon: {e}", file=sys.stderr)

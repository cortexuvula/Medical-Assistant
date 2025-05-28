"""
Runtime hook for Linux to fix library conflicts with system FFmpeg
"""
import os
import sys
import platform

if platform.system() == 'Linux' and hasattr(sys, 'frozen'):
    # Remove PyInstaller's temporary directory from LD_LIBRARY_PATH
    # This prevents conflicts with system libraries needed by FFmpeg
    if 'LD_LIBRARY_PATH' in os.environ:
        paths = os.environ['LD_LIBRARY_PATH'].split(':')
        # Filter out PyInstaller's temp directory (contains _MEI)
        filtered_paths = [p for p in paths if '_MEI' not in p]
        if filtered_paths:
            os.environ['LD_LIBRARY_PATH'] = ':'.join(filtered_paths)
        else:
            # If no paths left, remove the variable entirely
            del os.environ['LD_LIBRARY_PATH']
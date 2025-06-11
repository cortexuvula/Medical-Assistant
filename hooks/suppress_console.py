"""
Monkey patch to suppress console windows when pydub calls FFmpeg on Windows.
This should be imported early in the application to prevent window flashing.
"""
import os
import sys
import subprocess
from pydub.utils import which

# Only apply this patch on Windows
if os.name == 'nt':
    # Store the original Popen
    _original_popen = subprocess.Popen
    
    def _patched_popen(*args, **kwargs):
        """Patched Popen that adds CREATE_NO_WINDOW flag on Windows."""
        # Check if this is likely an FFmpeg call from pydub
        if args and len(args) > 0:
            cmd = args[0]
            if isinstance(cmd, list) and len(cmd) > 0:
                # Check if the command contains ffmpeg or ffprobe
                if any('ffmpeg' in str(arg).lower() or 'ffprobe' in str(arg).lower() for arg in cmd):
                    # Add CREATE_NO_WINDOW flag to prevent console window
                    if sys.platform == 'win32':
                        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        
        return _original_popen(*args, **kwargs)
    
    # Apply the monkey patch
    subprocess.Popen = _patched_popen
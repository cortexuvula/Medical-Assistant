"""
FFmpeg utilities for bundled FFmpeg support
"""
import os
import sys
import platform
import subprocess
from pathlib import Path

from utils.structured_logging import get_logger

logger = get_logger(__name__)

def get_ffmpeg_path():
    """Get the path to FFmpeg executable, preferring bundled version if available."""
    
    # For Linux, always use system ffmpeg to avoid library dependency issues
    if platform.system() == 'Linux':
        logger.info("Using system FFmpeg on Linux")
        return 'ffmpeg'
    
    # Check if we're running as a PyInstaller bundle
    if getattr(sys, 'frozen', False):
        # We're running as a bundle
        bundle_dir = sys._MEIPASS
        system = platform.system().lower()
        
        if system == 'windows':
            ffmpeg_exe = 'ffmpeg.exe'
        else:
            ffmpeg_exe = 'ffmpeg'
            
        bundled_ffmpeg = os.path.join(bundle_dir, 'ffmpeg', ffmpeg_exe)
        
        if os.path.exists(bundled_ffmpeg):
            logger.info(f"Using bundled FFmpeg: {bundled_ffmpeg}")
            return bundled_ffmpeg
        else:
            logger.warning(f"Bundled FFmpeg not found at: {bundled_ffmpeg}")
    
    # Fallback to system FFmpeg
    return 'ffmpeg'

def get_ffprobe_path():
    """Get the path to FFprobe executable, preferring bundled version if available."""
    
    # For Linux, always use system ffprobe to avoid library dependency issues
    if platform.system() == 'Linux':
        logger.info("Using system FFprobe on Linux")
        return 'ffprobe'
    
    # Check if we're running as a PyInstaller bundle
    if getattr(sys, 'frozen', False):
        # We're running as a bundle
        bundle_dir = sys._MEIPASS
        system = platform.system().lower()
        
        if system == 'windows':
            ffprobe_exe = 'ffprobe.exe'
        else:
            ffprobe_exe = 'ffprobe'
            
        bundled_ffprobe = os.path.join(bundle_dir, 'ffmpeg', ffprobe_exe)
        
        if os.path.exists(bundled_ffprobe):
            logger.info(f"Using bundled FFprobe: {bundled_ffprobe}")
            return bundled_ffprobe
        else:
            logger.warning(f"Bundled FFprobe not found at: {bundled_ffprobe}")
    
    # Fallback to system FFprobe
    return 'ffprobe'

def configure_pydub():
    """Configure pydub to use bundled FFmpeg if available."""
    import subprocess
    from pydub.utils import which
    
    ffmpeg_path = get_ffmpeg_path()
    ffprobe_path = get_ffprobe_path()
    
    # Set pydub to use our paths
    from pydub import AudioSegment
    AudioSegment.converter = ffmpeg_path
    AudioSegment.ffmpeg = ffmpeg_path
    AudioSegment.ffprobe = ffprobe_path
    
    # On Windows, configure pydub to suppress console windows
    if platform.system() == 'Windows':
        # Monkey patch pydub's subprocess calls to use CREATE_NO_WINDOW
        import pydub.utils
        original_popen = subprocess.Popen
        
        def no_window_popen(*args, **kwargs):
            if platform.system() == 'Windows':
                # Ensure creationflags is set for Windows
                if 'creationflags' not in kwargs:
                    kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                else:
                    kwargs['creationflags'] |= subprocess.CREATE_NO_WINDOW
                
                # Also set startupinfo to hide the window
                if 'startupinfo' not in kwargs:
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    si.wShowWindow = subprocess.SW_HIDE
                    kwargs['startupinfo'] = si
            return original_popen(*args, **kwargs)
        
        # Replace both pydub's Popen and the global subprocess.Popen
        pydub.utils.Popen = no_window_popen
        subprocess.Popen = no_window_popen
        logger.debug("Configured pydub and subprocess to suppress console windows on Windows")
    
    logger.info(f"Configured pydub with FFmpeg: {ffmpeg_path}")
    
    # Pre-initialize pydub by creating a tiny silent segment
    # This forces pydub to check FFmpeg availability at startup
    # preventing window flicker on first actual use
    try:
        # Create a 1ms silent audio segment
        silent = AudioSegment.silent(duration=1)
        logger.debug("Pre-initialized pydub with silent segment")
    except Exception as e:
        logger.warning(f"Could not pre-initialize pydub: {e}")
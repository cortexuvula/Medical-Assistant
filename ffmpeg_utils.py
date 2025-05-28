"""
FFmpeg utilities for bundled FFmpeg support
"""
import os
import sys
import platform
import logging
from pathlib import Path

def get_ffmpeg_path():
    """Get the path to FFmpeg executable, preferring bundled version if available."""
    
    # For Linux, always use system ffmpeg to avoid library dependency issues
    if platform.system() == 'Linux':
        logging.info("Using system FFmpeg on Linux")
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
            logging.info(f"Using bundled FFmpeg: {bundled_ffmpeg}")
            return bundled_ffmpeg
        else:
            logging.warning(f"Bundled FFmpeg not found at: {bundled_ffmpeg}")
    
    # Fallback to system FFmpeg
    return 'ffmpeg'

def get_ffprobe_path():
    """Get the path to FFprobe executable, preferring bundled version if available."""
    
    # For Linux, always use system ffprobe to avoid library dependency issues
    if platform.system() == 'Linux':
        logging.info("Using system FFprobe on Linux")
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
            logging.info(f"Using bundled FFprobe: {bundled_ffprobe}")
            return bundled_ffprobe
        else:
            logging.warning(f"Bundled FFprobe not found at: {bundled_ffprobe}")
    
    # Fallback to system FFprobe
    return 'ffprobe'

def configure_pydub():
    """Configure pydub to use bundled FFmpeg if available."""
    from pydub.utils import which
    
    ffmpeg_path = get_ffmpeg_path()
    ffprobe_path = get_ffprobe_path()
    
    # Set pydub to use our paths
    from pydub import AudioSegment
    AudioSegment.converter = ffmpeg_path
    AudioSegment.ffmpeg = ffmpeg_path
    AudioSegment.ffprobe = ffprobe_path
    
    logging.info(f"Configured pydub with FFmpeg: {ffmpeg_path}")
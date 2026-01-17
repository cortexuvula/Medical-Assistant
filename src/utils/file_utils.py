"""
File utilities for the Medical Dictation application.

This module provides utilities for safe file operations, including
temporary file management with automatic cleanup.
"""

import os
import tempfile
from contextlib import contextmanager
from typing import Generator, Optional

from utils.structured_logging import get_logger

logger = get_logger(__name__)


@contextmanager
def temp_audio_file(suffix: str = '.wav', prefix: str = 'medical_audio_') -> Generator[str, None, None]:
    """Context manager for creating temporary audio files with automatic cleanup.

    Creates a temporary file that is automatically deleted when the context exits,
    even if an exception occurs. This prevents temp file accumulation that can
    cause disk space issues in long-running sessions.

    Args:
        suffix: File extension for the temp file (default: '.wav')
        prefix: Prefix for the temp filename (default: 'medical_audio_')

    Yields:
        str: Path to the temporary file

    Example:
        with temp_audio_file() as temp_path:
            audio_segment.export(temp_path, format='wav')
            transcription = transcribe(temp_path)
        # File is automatically deleted here

    Note:
        The file is created but closed, allowing other processes to write to it.
        On Windows, this is important because some tools require exclusive access.
    """
    fd = None
    path = None
    try:
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        os.close(fd)  # Close fd so other processes can use the file
        fd = None  # Mark as closed
        yield path
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError as e:
                logger.warning(f"Failed to delete temp file {path}: {e}")


@contextmanager
def temp_file(suffix: str = '', prefix: str = 'medical_temp_') -> Generator[str, None, None]:
    """Context manager for creating general temporary files with automatic cleanup.

    Similar to temp_audio_file but for non-audio temporary files.

    Args:
        suffix: File extension for the temp file
        prefix: Prefix for the temp filename

    Yields:
        str: Path to the temporary file
    """
    fd = None
    path = None
    try:
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        os.close(fd)
        fd = None
        yield path
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError as e:
                logger.warning(f"Failed to delete temp file {path}: {e}")


@contextmanager
def temp_directory(prefix: str = 'medical_temp_') -> Generator[str, None, None]:
    """Context manager for creating temporary directories with automatic cleanup.

    Creates a temporary directory that is automatically deleted (including all
    contents) when the context exits.

    Args:
        prefix: Prefix for the temp directory name

    Yields:
        str: Path to the temporary directory
    """
    import shutil
    path = None
    try:
        path = tempfile.mkdtemp(prefix=prefix)
        yield path
    finally:
        if path and os.path.exists(path):
            try:
                shutil.rmtree(path)
            except OSError as e:
                logger.warning(f"Failed to delete temp directory {path}: {e}")


def safe_delete_file(file_path: str, log_errors: bool = True) -> bool:
    """Safely delete a file, handling errors gracefully.

    Args:
        file_path: Path to the file to delete
        log_errors: Whether to log errors (default: True)

    Returns:
        bool: True if file was deleted or didn't exist, False on error
    """
    if not file_path:
        return True

    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        return True
    except OSError as e:
        if log_errors:
            logger.warning(f"Failed to delete file {file_path}: {e}")
        return False


def ensure_directory_exists(directory_path: str) -> bool:
    """Ensure a directory exists, creating it if necessary.

    Args:
        directory_path: Path to the directory

    Returns:
        bool: True if directory exists or was created, False on error
    """
    try:
        os.makedirs(directory_path, exist_ok=True)
        return True
    except OSError as e:
        logger.error(f"Failed to create directory {directory_path}: {e}")
        return False


def get_safe_filename(filename: str, max_length: int = 255) -> str:
    """Convert a string to a safe filename by removing/replacing unsafe characters.

    Args:
        filename: The original filename
        max_length: Maximum length for the filename (default: 255)

    Returns:
        str: A safe filename string
    """
    # Characters not allowed in filenames on various platforms
    unsafe_chars = '<>:"/\\|?*\x00'

    # Replace unsafe characters with underscores
    safe_name = ''.join(c if c not in unsafe_chars else '_' for c in filename)

    # Truncate if too long (preserving extension if present)
    if len(safe_name) > max_length:
        name, ext = os.path.splitext(safe_name)
        max_name_length = max_length - len(ext)
        safe_name = name[:max_name_length] + ext

    return safe_name

"""
Safe JSON Utilities Module

Provides wrapper functions for JSON operations with proper error handling,
logging, and default value support to prevent crashes from malformed JSON.

Usage:
    from utils.json_utils import safe_json_load, safe_json_dump, safe_json_loads

    # Safe file loading with default
    data = safe_json_load("config.json", default={})

    # Safe string parsing with default
    obj = safe_json_loads(json_string, default=[])

    # Safe file writing with error handling
    success = safe_json_dump(data, "output.json")
"""

import json
from pathlib import Path
from typing import Any, Optional, Union

from utils.structured_logging import get_logger

logger = get_logger(__name__)


def safe_json_loads(
    json_string: str,
    default: Any = None,
    log_errors: bool = True
) -> Any:
    """Safely parse a JSON string with error handling.

    Args:
        json_string: The JSON string to parse
        default: Value to return if parsing fails (default: None)
        log_errors: Whether to log parsing errors (default: True)

    Returns:
        Parsed JSON object or default value if parsing fails

    Example:
        >>> data = safe_json_loads('{"key": "value"}', default={})
        >>> data = safe_json_loads('invalid json', default=[])  # Returns []
    """
    if not json_string:
        return default

    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        if log_errors:
            # Truncate long strings for logging
            preview = json_string[:100] + "..." if len(json_string) > 100 else json_string
            logger.warning(f"JSON parse error: {e.msg} at position {e.pos}. Input preview: {preview!r}")
        return default
    except (TypeError, ValueError) as e:
        if log_errors:
            logger.warning(f"JSON parse error: {e}")
        return default


def safe_json_load(
    file_path: Union[str, Path],
    default: Any = None,
    encoding: str = "utf-8",
    log_errors: bool = True
) -> Any:
    """Safely load JSON from a file with error handling.

    Args:
        file_path: Path to the JSON file
        default: Value to return if loading fails (default: None)
        encoding: File encoding (default: utf-8)
        log_errors: Whether to log errors (default: True)

    Returns:
        Parsed JSON object or default value if loading fails

    Example:
        >>> config = safe_json_load("settings.json", default={"theme": "dark"})
    """
    file_path = Path(file_path)

    if not file_path.exists():
        if log_errors:
            logger.debug(f"JSON file not found: {file_path}")
        return default

    try:
        with open(file_path, "r", encoding=encoding) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        if log_errors:
            logger.warning(f"JSON parse error in {file_path}: {e.msg} at line {e.lineno}")
        return default
    except (OSError, IOError) as e:
        if log_errors:
            logger.warning(f"Error reading JSON file {file_path}: {e}")
        return default
    except Exception as e:
        if log_errors:
            logger.error(f"Unexpected error loading JSON from {file_path}: {e}")
        return default


def safe_json_dump(
    data: Any,
    file_path: Union[str, Path],
    indent: int = 2,
    encoding: str = "utf-8",
    ensure_ascii: bool = False,
    log_errors: bool = True
) -> bool:
    """Safely write data to a JSON file with error handling.

    Args:
        data: Data to serialize to JSON
        file_path: Path to write the JSON file
        indent: Indentation level for pretty printing (default: 2)
        encoding: File encoding (default: utf-8)
        ensure_ascii: Escape non-ASCII characters (default: False)
        log_errors: Whether to log errors (default: True)

    Returns:
        True if write succeeded, False otherwise

    Example:
        >>> success = safe_json_dump({"key": "value"}, "output.json")
    """
    file_path = Path(file_path)

    try:
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding=encoding) as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
        return True
    except (TypeError, ValueError) as e:
        if log_errors:
            logger.error(f"JSON serialization error for {file_path}: {e}")
        return False
    except (OSError, IOError) as e:
        if log_errors:
            logger.error(f"Error writing JSON file {file_path}: {e}")
        return False
    except Exception as e:
        if log_errors:
            logger.error(f"Unexpected error writing JSON to {file_path}: {e}")
        return False


def safe_json_dumps(
    data: Any,
    default: str = "{}",
    indent: Optional[int] = None,
    ensure_ascii: bool = False,
    log_errors: bool = True
) -> str:
    """Safely serialize data to a JSON string with error handling.

    Args:
        data: Data to serialize to JSON
        default: String to return if serialization fails (default: "{}")
        indent: Indentation level for pretty printing (default: None)
        ensure_ascii: Escape non-ASCII characters (default: False)
        log_errors: Whether to log errors (default: True)

    Returns:
        JSON string or default value if serialization fails

    Example:
        >>> json_str = safe_json_dumps({"key": "value"})
        >>> json_str = safe_json_dumps(circular_ref, default="null")
    """
    try:
        return json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
    except (TypeError, ValueError) as e:
        if log_errors:
            logger.warning(f"JSON serialization error: {e}")
        return default
    except Exception as e:
        if log_errors:
            logger.error(f"Unexpected JSON serialization error: {e}")
        return default

"""
Sentry Error Monitoring Configuration

Initializes Sentry SDK with PHI (Protected Health Information) scrubbing
to ensure no patient data leaves the machine via error reports.

Uses the same SENSITIVE_FIELDS list from structured_logging.py as the
single source of truth for what constitutes sensitive data.
"""

import os

from utils.structured_logging import get_logger

logger = get_logger(__name__)


def _scrub_data(data: dict) -> dict:
    """Recursively scrub sensitive fields from a dictionary.

    Args:
        data: Dictionary that may contain PHI or credentials.

    Returns:
        Scrubbed copy of the dictionary.
    """
    from utils.structured_logging import SENSITIVE_FIELDS

    if not isinstance(data, dict):
        return data

    scrubbed = {}
    for key, value in data.items():
        if key.lower() in SENSITIVE_FIELDS:
            scrubbed[key] = "[Filtered]"
        elif isinstance(value, dict):
            scrubbed[key] = _scrub_data(value)
        elif isinstance(value, list):
            scrubbed[key] = [
                _scrub_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        elif isinstance(value, str) and len(value) > 500:
            # Truncate long strings that could contain clinical text
            scrubbed[key] = value[:200] + "...[truncated]"
        else:
            scrubbed[key] = value
    return scrubbed


def _before_send(event, hint):
    """Scrub PHI from Sentry events before they leave the machine.

    This callback fires for every event (errors, messages) before
    transmission to Sentry servers. It walks exception frames, breadcrumbs,
    and extra context to redact any sensitive fields.
    """
    # Scrub local variables from exception stack frames
    if "exception" in event:
        for exception_entry in event["exception"].get("values", []):
            stacktrace = exception_entry.get("stacktrace")
            if stacktrace:
                for frame in stacktrace.get("frames", []):
                    if frame.get("vars"):
                        frame["vars"] = _scrub_data(frame["vars"])

    # Scrub breadcrumb data (recent actions/logs that provide context)
    if "breadcrumbs" in event:
        for breadcrumb in event["breadcrumbs"].get("values", []):
            if breadcrumb.get("data"):
                breadcrumb["data"] = _scrub_data(breadcrumb["data"])
            # Scrub message content that might contain clinical text
            msg = breadcrumb.get("message", "")
            if isinstance(msg, str) and len(msg) > 500:
                breadcrumb["message"] = msg[:200] + "...[truncated]"

    # Scrub extra context
    if "extra" in event:
        event["extra"] = _scrub_data(event["extra"])

    # Scrub tags
    if "tags" in event:
        event["tags"] = _scrub_data(event["tags"])

    # Scrub user context (should be minimal with send_default_pii=False)
    if "user" in event:
        event["user"] = _scrub_data(event["user"])

    return event


def _before_send_transaction(event, hint):
    """Scrub PHI from performance transaction events."""
    if "tags" in event:
        event["tags"] = _scrub_data(event["tags"])
    if "extra" in event:
        event["extra"] = _scrub_data(event["extra"])
    return event


def init_sentry() -> bool:
    """Initialize Sentry SDK if DSN is configured.

    Reads SENTRY_DSN from environment variables. If not set, Sentry is
    silently disabled — the app runs normally without monitoring.

    Returns:
        True if Sentry was initialized, False otherwise.
    """
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        logger.debug("SENTRY_DSN not set — Sentry monitoring disabled")
        return False

    try:
        import sentry_sdk

        environment = os.environ.get("MEDICAL_ASSISTANT_ENV", "production")

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,

            # PHI protection: do NOT send PII (IPs, cookies, headers)
            send_default_pii=False,

            # Scrub PHI from all events before transmission
            before_send=_before_send,
            before_send_transaction=_before_send_transaction,

            # Sample rates — adjust as needed
            traces_sample_rate=0.2,  # 20% of transactions for performance monitoring
            profiles_sample_rate=0.1,  # 10% of profiled transactions

            # Attach stack local variables for debugging (scrubbed by before_send)
            include_local_variables=True,

            # Release tracking — use git SHA if available
            release=_get_release_version(),

            # Enable threading integration for background task monitoring
            enable_tracing=True,
        )

        logger.info("Sentry initialized", environment=environment)
        return True

    except ImportError:
        logger.debug("sentry-sdk not installed — monitoring disabled")
        return False
    except Exception as e:
        logger.warning(f"Sentry initialization failed: {e}")
        return False


def _get_release_version() -> str:
    """Get release version for Sentry tagging.

    Tries git SHA first, falls back to a static version string.
    """
    # Try git SHA
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            sha = result.stdout.strip()
            return f"medical-assistant@{sha}"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return "medical-assistant@unknown"

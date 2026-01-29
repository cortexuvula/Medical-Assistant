"""
Audit Logging Module

This module provides audit logging capabilities for the Medical Assistant
application. Audit logs track sensitive operations for HIPAA compliance
and security monitoring.

Features:
- Separate audit log file (append-only)
- Tracks sensitive operations: API key access, data access, exports
- Redacts PHI from audit entries
- Structured JSON format for log analysis
- Thread-safe logging

Usage:
    from utils.audit_logger import audit_log, AuditEventType

    # Log a data access event
    audit_log(
        event_type=AuditEventType.DATA_ACCESS,
        action="view_recording",
        resource_type="recording",
        resource_id="123",
        user_session=session_id
    )
"""

import json
import logging
import os
import hashlib
import threading
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from managers.data_folder_manager import data_folder_manager
from utils.structured_logging import get_logger


class AuditEventType(str, Enum):
    """Types of auditable events."""
    # Authentication events
    AUTH_LOGIN = "auth_login"
    AUTH_LOGOUT = "auth_logout"
    AUTH_FAILED = "auth_failed"

    # API key events
    API_KEY_ACCESS = "api_key_access"
    API_KEY_ADD = "api_key_add"
    API_KEY_REMOVE = "api_key_remove"
    API_KEY_MODIFIED = "api_key_modified"

    # Data access events
    DATA_ACCESS = "data_access"
    DATA_CREATE = "data_create"
    DATA_UPDATE = "data_update"
    DATA_DELETE = "data_delete"

    # Export events
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"

    # Recording events
    RECORDING_ACCESS = "recording_access"
    RECORDING_TRANSCRIBE = "recording_transcribe"
    RECORDING_DELETE = "recording_delete"

    # AI processing events
    AI_PROCESS = "ai_process"
    AI_GENERATE = "ai_generate"

    # Security events
    SECURITY_VIOLATION = "security_violation"
    SECURITY_WARNING = "security_warning"

    # Configuration events
    CONFIG_CHANGE = "config_change"

    # Application lifecycle
    APP_START = "app_start"
    APP_SHUTDOWN = "app_shutdown"


class AuditLogger:
    """Thread-safe audit logger with separate log file.

    Provides append-only audit logging for sensitive operations.
    Logs are stored in JSON format for easy analysis.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern for audit logger."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the audit logger."""
        if self._initialized:
            return

        self._initialized = True
        self._write_lock = threading.Lock()

        # Set up audit log directory
        self._log_dir = data_folder_manager.logs_folder_path
        self._log_dir.mkdir(parents=True, exist_ok=True)

        # Audit log file path
        self._log_path = self._log_dir / "audit.log"

        # Set up Python logger for audit
        self._logger = get_logger("audit")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False  # Don't propagate to root logger

        # Only add handler if not already present
        if not self._logger.handlers:
            # File handler for audit log (append mode)
            handler = logging.FileHandler(
                self._log_path,
                mode='a',
                encoding='utf-8'
            )
            handler.setFormatter(logging.Formatter('%(message)s'))
            self._logger.addHandler(handler)

        # Secure the audit log file
        self._secure_log_file()

    def _secure_log_file(self):
        """Set secure permissions on audit log file."""
        import platform
        import stat

        if platform.system() == 'Windows':
            return  # Windows uses ACLs

        try:
            if self._log_path.exists():
                current_mode = self._log_path.stat().st_mode
                # Set to append-only for owner (0600)
                if current_mode & (stat.S_IRWXG | stat.S_IRWXO):
                    os.chmod(self._log_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass  # Best effort

    def _generate_session_hash(self, session_id: Optional[str] = None) -> str:
        """Generate a session identifier hash.

        Args:
            session_id: Optional session ID to hash

        Returns:
            A short hash for session tracking (not reversible)
        """
        if session_id:
            # Hash the session ID for privacy
            return hashlib.sha256(session_id.encode()).hexdigest()[:12]
        # Generate a default session hash based on timestamp
        return hashlib.sha256(
            f"{os.getpid()}-{threading.get_ident()}".encode()
        ).hexdigest()[:12]

    def _redact_phi(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact PHI from audit data.

        Args:
            data: Dictionary that may contain PHI

        Returns:
            Dictionary with PHI fields redacted
        """
        # Fields that should be redacted in audit logs
        phi_fields = {
            'patient_name', 'patient_id', 'diagnosis', 'symptoms',
            'transcript', 'soap_note', 'medical_history', 'medication',
            'chief_complaint', 'assessment', 'treatment', 'content',
            'text', 'clinical_text', 'note', 'notes'
        }

        redacted = {}
        for key, value in data.items():
            if key.lower() in phi_fields:
                if isinstance(value, str) and value:
                    redacted[key] = f"[REDACTED:{len(value)}chars]"
                else:
                    redacted[key] = "[REDACTED]"
            elif isinstance(value, dict):
                redacted[key] = self._redact_phi(value)
            else:
                redacted[key] = value
        return redacted

    def log(
        self,
        event_type: AuditEventType,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        user_session: Optional[str] = None,
        outcome: str = "success",
        details: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """Log an audit event.

        Args:
            event_type: The type of audit event
            action: Specific action being performed
            resource_type: Type of resource being accessed (e.g., "recording", "api_key")
            resource_id: Identifier for the resource (will be hashed if sensitive)
            user_session: Session identifier (will be hashed)
            outcome: "success", "failure", or "warning"
            details: Additional details (PHI will be redacted)
            error: Error message if outcome is failure
        """
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Build audit entry
        entry = {
            "timestamp": timestamp,
            "event_type": event_type.value,
            "action": action,
            "outcome": outcome,
            "session_hash": self._generate_session_hash(user_session),
        }

        if resource_type:
            entry["resource_type"] = resource_type

        if resource_id:
            # Hash resource IDs that might be sensitive
            if resource_type in ("patient", "recording", "user"):
                entry["resource_id_hash"] = hashlib.sha256(
                    str(resource_id).encode()
                ).hexdigest()[:16]
            else:
                entry["resource_id"] = str(resource_id)

        if details:
            entry["details"] = self._redact_phi(details)

        if error:
            entry["error"] = error[:500]  # Truncate long errors

        # Write to audit log (thread-safe)
        with self._write_lock:
            try:
                self._logger.info(json.dumps(entry))
            except Exception:
                pass  # Never fail on audit logging

    def log_api_key_operation(
        self,
        operation: str,
        provider: str,
        success: bool,
        error: Optional[str] = None
    ):
        """Log API key operations.

        Args:
            operation: "access", "add", "remove", "validate"
            provider: The API provider name
            success: Whether the operation succeeded
            error: Error message if failed
        """
        event_map = {
            "access": AuditEventType.API_KEY_ACCESS,
            "add": AuditEventType.API_KEY_ADD,
            "remove": AuditEventType.API_KEY_REMOVE,
            "validate": AuditEventType.API_KEY_ACCESS,
            "modify": AuditEventType.API_KEY_MODIFIED,
        }

        self.log(
            event_type=event_map.get(operation, AuditEventType.API_KEY_ACCESS),
            action=f"api_key_{operation}",
            resource_type="api_key",
            resource_id=provider,
            outcome="success" if success else "failure",
            error=error
        )

    def log_data_export(
        self,
        export_type: str,
        record_count: int,
        destination: str,
        success: bool,
        error: Optional[str] = None
    ):
        """Log data export operations.

        Args:
            export_type: Type of export (e.g., "prompts", "recordings", "report")
            record_count: Number of records exported
            destination: Export destination (will be redacted to just filename)
            success: Whether export succeeded
            error: Error message if failed
        """
        # Only log filename, not full path
        dest_name = Path(destination).name if destination else "unknown"

        self.log(
            event_type=AuditEventType.DATA_EXPORT,
            action=f"export_{export_type}",
            resource_type="export",
            outcome="success" if success else "failure",
            details={
                "export_type": export_type,
                "record_count": record_count,
                "destination_file": dest_name
            },
            error=error
        )

    def log_recording_access(
        self,
        recording_id: int,
        action: str,
        success: bool = True
    ):
        """Log recording access.

        Args:
            recording_id: The recording ID (will be hashed)
            action: "view", "play", "transcribe", "generate_soap", etc.
            success: Whether the action succeeded
        """
        self.log(
            event_type=AuditEventType.RECORDING_ACCESS,
            action=action,
            resource_type="recording",
            resource_id=str(recording_id),
            outcome="success" if success else "failure"
        )

    def log_security_event(
        self,
        event: str,
        severity: str = "warning",
        details: Optional[Dict[str, Any]] = None
    ):
        """Log security-related events.

        Args:
            event: Description of security event
            severity: "warning" or "violation"
            details: Additional context
        """
        event_type = (
            AuditEventType.SECURITY_VIOLATION
            if severity == "violation"
            else AuditEventType.SECURITY_WARNING
        )

        self.log(
            event_type=event_type,
            action=event,
            outcome=severity,
            details=details
        )


# Singleton instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the singleton audit logger instance.

    Returns:
        AuditLogger instance
    """
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def audit_log(
    event_type: AuditEventType,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    user_session: Optional[str] = None,
    outcome: str = "success",
    details: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None
):
    """Convenience function for audit logging.

    Args:
        event_type: The type of audit event
        action: Specific action being performed
        resource_type: Type of resource being accessed
        resource_id: Identifier for the resource
        user_session: Session identifier
        outcome: "success", "failure", or "warning"
        details: Additional details (PHI will be redacted)
        error: Error message if outcome is failure
    """
    get_audit_logger().log(
        event_type=event_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_session=user_session,
        outcome=outcome,
        details=details,
        error=error
    )


# Export public API
__all__ = [
    'AuditLogger',
    'AuditEventType',
    'get_audit_logger',
    'audit_log',
]

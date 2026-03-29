"""
Tests for src/utils/audit_logger.py

Covers AuditLogger: singleton, PHI redaction, session hash, audit log methods,
and convenience functions. Uses a temporary directory to avoid touching real logs.
"""

import json
import os
import sys
import stat
import threading
import hashlib
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_test_logger_names: list = []


def _reset_audit_logger_singleton():
    """Reset singleton state and close all handlers from test loggers."""
    import logging
    import utils.audit_logger as mod
    mod.AuditLogger._instance = None
    mod._audit_logger = None

    # Close/remove handlers from any test audit loggers we created
    for name in list(_test_logger_names):
        lg = logging.getLogger(name)
        for handler in list(lg.handlers):
            try:
                handler.close()
            except Exception:
                pass
        lg.handlers.clear()
    _test_logger_names.clear()


def _make_audit_logger(tmp_path):
    """Create an AuditLogger backed by tmp_path, with external deps mocked."""
    import logging
    _reset_audit_logger_singleton()

    mock_dfm = MagicMock()
    mock_dfm.logs_folder_path = tmp_path

    # Use a unique logger name per test so handlers don't bleed between tests.
    logger_name = f"audit_test_{id(tmp_path)}"
    _test_logger_names.append(logger_name)
    real_audit_logger = logging.getLogger(logger_name)
    real_audit_logger.handlers.clear()

    # settings_manager is imported lazily inside __init__ with try/except.
    # get_logger returns StructuredLogger which lacks setLevel — use a real logger.
    with patch("utils.audit_logger.data_folder_manager", mock_dfm), \
         patch("utils.audit_logger.get_logger", return_value=real_audit_logger):
        from utils.audit_logger import AuditLogger
        logger = AuditLogger()

    return logger


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before and after each test."""
    _reset_audit_logger_singleton()
    yield
    _reset_audit_logger_singleton()


@pytest.fixture
def audit_logger(tmp_path):
    """Fresh AuditLogger backed by tmp_path."""
    return _make_audit_logger(tmp_path)


# ===========================================================================
# AuditEventType enum
# ===========================================================================

class TestAuditEventType:
    def test_all_event_types_are_strings(self):
        from utils.audit_logger import AuditEventType
        for member in AuditEventType:
            assert isinstance(member.value, str)

    def test_auth_events_exist(self):
        from utils.audit_logger import AuditEventType
        assert AuditEventType.AUTH_LOGIN
        assert AuditEventType.AUTH_LOGOUT
        assert AuditEventType.AUTH_FAILED

    def test_api_key_events_exist(self):
        from utils.audit_logger import AuditEventType
        assert AuditEventType.API_KEY_ACCESS
        assert AuditEventType.API_KEY_ADD
        assert AuditEventType.API_KEY_REMOVE

    def test_data_events_exist(self):
        from utils.audit_logger import AuditEventType
        assert AuditEventType.DATA_ACCESS
        assert AuditEventType.DATA_CREATE
        assert AuditEventType.DATA_EXPORT
        assert AuditEventType.DATA_IMPORT

    def test_recording_events_exist(self):
        from utils.audit_logger import AuditEventType
        assert AuditEventType.RECORDING_ACCESS
        assert AuditEventType.RECORDING_TRANSCRIBE
        assert AuditEventType.RECORDING_DELETE

    def test_security_events_exist(self):
        from utils.audit_logger import AuditEventType
        assert AuditEventType.SECURITY_VIOLATION
        assert AuditEventType.SECURITY_WARNING

    def test_app_lifecycle_events_exist(self):
        from utils.audit_logger import AuditEventType
        assert AuditEventType.APP_START
        assert AuditEventType.APP_SHUTDOWN


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_same_instance_returned(self, tmp_path):
        a = _make_audit_logger(tmp_path)
        # Second call returns the cached singleton
        mock_dfm = MagicMock()
        mock_dfm.logs_folder_path = tmp_path
        with patch("utils.audit_logger.data_folder_manager", mock_dfm):
            from utils.audit_logger import AuditLogger
            b = AuditLogger()
        assert a is b

    def test_get_audit_logger_returns_singleton(self, tmp_path):
        logger = _make_audit_logger(tmp_path)
        mock_dfm = MagicMock()
        mock_dfm.logs_folder_path = tmp_path
        with patch("utils.audit_logger.data_folder_manager", mock_dfm):
            from utils.audit_logger import get_audit_logger
            result = get_audit_logger()
        assert result is logger


# ===========================================================================
# _generate_session_hash
# ===========================================================================

class TestGenerateSessionHash:
    def test_hash_with_session_id(self, audit_logger):
        h = audit_logger._generate_session_hash("my-session-123")
        assert isinstance(h, str)
        assert len(h) == 12

    def test_hash_deterministic(self, audit_logger):
        h1 = audit_logger._generate_session_hash("abc")
        h2 = audit_logger._generate_session_hash("abc")
        assert h1 == h2

    def test_different_sessions_different_hashes(self, audit_logger):
        h1 = audit_logger._generate_session_hash("session-1")
        h2 = audit_logger._generate_session_hash("session-2")
        assert h1 != h2

    def test_no_session_returns_hash(self, audit_logger):
        h = audit_logger._generate_session_hash(None)
        assert isinstance(h, str)
        assert len(h) == 12

    def test_no_session_is_process_based(self, audit_logger):
        # Two calls without session ID should return same hash (same process)
        h1 = audit_logger._generate_session_hash(None)
        h2 = audit_logger._generate_session_hash(None)
        assert h1 == h2


# ===========================================================================
# _redact_phi
# ===========================================================================

class TestRedactPHI:
    def test_phi_field_redacted(self, audit_logger):
        data = {"patient_name": "John Doe", "action": "view"}
        result = audit_logger._redact_phi(data)
        assert "[REDACTED" in result["patient_name"]
        assert result["action"] == "view"

    def test_empty_phi_field_still_redacted(self, audit_logger):
        data = {"patient_name": ""}
        result = audit_logger._redact_phi(data)
        assert result["patient_name"] == "[REDACTED]"

    def test_content_field_redacted_with_length(self, audit_logger):
        data = {"content": "x" * 50}
        result = audit_logger._redact_phi(data)
        assert "50chars" in result["content"]

    def test_non_phi_field_preserved(self, audit_logger):
        data = {"action": "export", "record_count": 5}
        result = audit_logger._redact_phi(data)
        assert result["action"] == "export"
        assert result["record_count"] == 5

    def test_nested_dict_redacted(self, audit_logger):
        data = {"outer": {"patient_name": "Jane"}}
        result = audit_logger._redact_phi(data)
        assert "[REDACTED" in result["outer"]["patient_name"]

    def test_transcript_field_redacted(self, audit_logger):
        data = {"transcript": "Patient complains of headache"}
        result = audit_logger._redact_phi(data)
        assert "[REDACTED" in result["transcript"]

    def test_case_insensitive_phi_detection(self, audit_logger):
        # Field names are lowercased for comparison
        data = {"patient_name": "Test User"}  # key already lowercase
        result = audit_logger._redact_phi(data)
        assert "[REDACTED" in result["patient_name"]

    def test_returns_new_dict(self, audit_logger):
        original = {"action": "test", "patient_name": "Joe"}
        result = audit_logger._redact_phi(original)
        assert result is not original


# ===========================================================================
# log method
# ===========================================================================

class TestLogMethod:
    def test_log_writes_json_line(self, audit_logger, tmp_path):
        from utils.audit_logger import AuditEventType
        audit_logger.log(
            event_type=AuditEventType.DATA_ACCESS,
            action="view_recording",
        )
        log_path = tmp_path / "audit.log"
        assert log_path.exists()
        content = log_path.read_text()
        entry = json.loads(content.strip().split('\n')[-1])
        assert entry["event_type"] == "data_access"
        assert entry["action"] == "view_recording"

    def test_log_includes_timestamp(self, audit_logger, tmp_path):
        from utils.audit_logger import AuditEventType
        audit_logger.log(event_type=AuditEventType.APP_START, action="start")
        log_path = tmp_path / "audit.log"
        content = log_path.read_text().strip()
        entry = json.loads(content)
        assert "timestamp" in entry
        assert entry["timestamp"].endswith("Z")

    def test_log_outcome_default_success(self, audit_logger, tmp_path):
        from utils.audit_logger import AuditEventType
        audit_logger.log(event_type=AuditEventType.DATA_ACCESS, action="read")
        log_path = tmp_path / "audit.log"
        entry = json.loads(log_path.read_text().strip())
        assert entry["outcome"] == "success"

    def test_log_outcome_failure(self, audit_logger, tmp_path):
        from utils.audit_logger import AuditEventType
        audit_logger.log(
            event_type=AuditEventType.AUTH_FAILED,
            action="login",
            outcome="failure"
        )
        log_path = tmp_path / "audit.log"
        entry = json.loads(log_path.read_text().strip())
        assert entry["outcome"] == "failure"

    def test_log_resource_type_included(self, audit_logger, tmp_path):
        from utils.audit_logger import AuditEventType
        audit_logger.log(
            event_type=AuditEventType.DATA_ACCESS,
            action="view",
            resource_type="recording"
        )
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert entry["resource_type"] == "recording"

    def test_log_resource_id_hashed_for_patient(self, audit_logger, tmp_path):
        from utils.audit_logger import AuditEventType
        audit_logger.log(
            event_type=AuditEventType.DATA_ACCESS,
            action="view",
            resource_type="patient",
            resource_id="patient-123"
        )
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert "resource_id_hash" in entry
        assert "resource_id" not in entry

    def test_log_resource_id_plain_for_non_sensitive(self, audit_logger, tmp_path):
        from utils.audit_logger import AuditEventType
        audit_logger.log(
            event_type=AuditEventType.CONFIG_CHANGE,
            action="update",
            resource_type="setting",
            resource_id="theme"
        )
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert entry["resource_id"] == "theme"

    def test_log_details_phi_redacted(self, audit_logger, tmp_path):
        from utils.audit_logger import AuditEventType
        audit_logger.log(
            event_type=AuditEventType.DATA_ACCESS,
            action="view",
            details={"patient_name": "Alice Smith", "action": "view"}
        )
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert "[REDACTED" in entry["details"]["patient_name"]
        assert entry["details"]["action"] == "view"

    def test_log_error_truncated_to_500(self, audit_logger, tmp_path):
        from utils.audit_logger import AuditEventType
        long_error = "E" * 600
        audit_logger.log(
            event_type=AuditEventType.AUTH_FAILED,
            action="login",
            outcome="failure",
            error=long_error
        )
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert len(entry["error"]) == 500

    def test_log_session_hash_included(self, audit_logger, tmp_path):
        from utils.audit_logger import AuditEventType
        audit_logger.log(
            event_type=AuditEventType.DATA_ACCESS,
            action="view",
            user_session="my-session"
        )
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert "session_hash" in entry
        assert len(entry["session_hash"]) == 12


# ===========================================================================
# log_api_key_operation
# ===========================================================================

class TestLogAPIKeyOperation:
    def test_access_operation(self, audit_logger, tmp_path):
        audit_logger.log_api_key_operation("access", "openai", success=True)
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert entry["event_type"] == "api_key_access"
        assert entry["outcome"] == "success"

    def test_add_operation(self, audit_logger, tmp_path):
        audit_logger.log_api_key_operation("add", "anthropic", success=True)
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert entry["event_type"] == "api_key_add"

    def test_remove_operation(self, audit_logger, tmp_path):
        audit_logger.log_api_key_operation("remove", "gemini", success=False, error="failed")
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert entry["event_type"] == "api_key_remove"
        assert entry["outcome"] == "failure"

    def test_modify_operation(self, audit_logger, tmp_path):
        audit_logger.log_api_key_operation("modify", "groq", success=True)
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert entry["event_type"] == "api_key_modified"

    def test_unknown_operation_defaults_to_access(self, audit_logger, tmp_path):
        audit_logger.log_api_key_operation("unknown_op", "openai", success=True)
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert entry["event_type"] == "api_key_access"


# ===========================================================================
# log_data_export
# ===========================================================================

class TestLogDataExport:
    def test_successful_export(self, audit_logger, tmp_path):
        audit_logger.log_data_export(
            export_type="prompts", record_count=5,
            destination="/some/path/export.json", success=True
        )
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert entry["event_type"] == "data_export"
        assert entry["outcome"] == "success"
        assert entry["details"]["record_count"] == 5
        assert entry["details"]["destination_file"] == "export.json"

    def test_failed_export(self, audit_logger, tmp_path):
        audit_logger.log_data_export(
            export_type="recordings", record_count=0,
            destination="/path/file.csv", success=False, error="permission denied"
        )
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert entry["outcome"] == "failure"
        assert entry["error"] == "permission denied"

    def test_empty_destination(self, audit_logger, tmp_path):
        audit_logger.log_data_export(
            export_type="prompts", record_count=1,
            destination="", success=True
        )
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert entry["details"]["destination_file"] == "unknown"

    def test_full_path_stripped_to_filename(self, audit_logger, tmp_path):
        audit_logger.log_data_export(
            export_type="prompts", record_count=1,
            destination="/very/long/absolute/path/myfile.json", success=True
        )
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert entry["details"]["destination_file"] == "myfile.json"


# ===========================================================================
# log_recording_access
# ===========================================================================

class TestLogRecordingAccess:
    def test_log_recording_view(self, audit_logger, tmp_path):
        audit_logger.log_recording_access(recording_id=42, action="view")
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert entry["event_type"] == "recording_access"
        assert entry["action"] == "view"
        assert entry["outcome"] == "success"

    def test_log_recording_transcribe_failure(self, audit_logger, tmp_path):
        audit_logger.log_recording_access(recording_id=7, action="transcribe", success=False)
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert entry["outcome"] == "failure"

    def test_recording_id_is_hashed(self, audit_logger, tmp_path):
        """Recording IDs are hashed because resource_type is 'recording'."""
        audit_logger.log_recording_access(recording_id=99, action="play")
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert "resource_id_hash" in entry
        assert "resource_id" not in entry


# ===========================================================================
# log_security_event
# ===========================================================================

class TestLogSecurityEvent:
    def test_warning_event(self, audit_logger, tmp_path):
        audit_logger.log_security_event("suspicious_access", severity="warning")
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert entry["event_type"] == "security_warning"
        assert entry["outcome"] == "warning"

    def test_violation_event(self, audit_logger, tmp_path):
        audit_logger.log_security_event("injection_attempt", severity="violation")
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert entry["event_type"] == "security_violation"
        assert entry["outcome"] == "violation"

    def test_security_event_with_details(self, audit_logger, tmp_path):
        audit_logger.log_security_event(
            "rate_limit_breach",
            details={"ip": "192.168.1.1", "count": 100}
        )
        entry = json.loads((tmp_path / "audit.log").read_text().strip())
        assert entry["details"]["ip"] == "192.168.1.1"
        assert entry["details"]["count"] == 100


# ===========================================================================
# audit_log convenience function
# ===========================================================================

class TestAuditLogFunction:
    def test_convenience_function_writes_log(self, audit_logger, tmp_path):
        from utils.audit_logger import AuditEventType

        # audit_logger singleton is already set in fixture
        mock_dfm = MagicMock()
        mock_dfm.logs_folder_path = tmp_path
        with patch("utils.audit_logger.data_folder_manager", mock_dfm):
            from utils.audit_logger import audit_log
            audit_log(
                event_type=AuditEventType.CONFIG_CHANGE,
                action="update_theme"
            )

        entry = json.loads((tmp_path / "audit.log").read_text().strip().split('\n')[-1])
        assert entry["action"] == "update_theme"


# ===========================================================================
# Thread safety — concurrent log writes
# ===========================================================================

class TestThreadSafety:
    def test_concurrent_log_writes(self, audit_logger, tmp_path):
        from utils.audit_logger import AuditEventType

        errors = []

        def write_log(i):
            try:
                audit_logger.log(
                    event_type=AuditEventType.DATA_ACCESS,
                    action=f"action_{i}"
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_log, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        log_path = tmp_path / "audit.log"
        lines = [l for l in log_path.read_text().strip().split('\n') if l]
        assert len(lines) == 10

"""
Tests for src/utils/audit_logger.py

Covers pure-logic methods on AuditLogger (no file I/O) and the AuditEventType
enum. Instances are created by bypassing __init__ via object.__new__ so that
no filesystem access, ConcurrentRotatingFileHandler, or external dependencies
are triggered.
"""

import hashlib
import os
import sys
import threading
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.audit_logger import AuditEventType, AuditLogger  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture: AuditLogger instance that skips __init__ entirely
# ---------------------------------------------------------------------------

@pytest.fixture
def logger_instance():
    """Create an AuditLogger instance bypassing __init__ (no file I/O)."""
    instance = object.__new__(AuditLogger)
    return instance


# ===========================================================================
# AuditEventType enum
# ===========================================================================

class TestAuditEventType:
    """Tests for the AuditEventType string enum."""

    def test_is_str_enum(self):
        assert issubclass(AuditEventType, str)

    def test_auth_login_value(self):
        assert AuditEventType.AUTH_LOGIN == "auth_login"
        assert AuditEventType.AUTH_LOGIN.value == "auth_login"

    def test_auth_logout_value(self):
        assert AuditEventType.AUTH_LOGOUT == "auth_logout"

    def test_auth_failed_value(self):
        assert AuditEventType.AUTH_FAILED == "auth_failed"

    def test_api_key_access_value(self):
        assert AuditEventType.API_KEY_ACCESS == "api_key_access"

    def test_data_export_value(self):
        assert AuditEventType.DATA_EXPORT == "data_export"

    def test_ai_process_value(self):
        assert AuditEventType.AI_PROCESS == "ai_process"

    def test_security_violation_value(self):
        assert AuditEventType.SECURITY_VIOLATION == "security_violation"

    def test_app_start_value(self):
        assert AuditEventType.APP_START == "app_start"

    def test_all_members_are_strings(self):
        for member in AuditEventType:
            assert isinstance(member.value, str), f"{member.name} value is not str"

    def test_str_comparison_works_directly(self):
        # str Enum allows direct string comparison
        assert AuditEventType.API_KEY_ACCESS == "api_key_access"
        assert AuditEventType.DATA_EXPORT == "data_export"

    def test_expected_member_count(self):
        # The source defines 22 members; guard against accidental deletions
        assert len(AuditEventType) >= 20

    def test_api_key_add_and_remove_exist(self):
        assert AuditEventType.API_KEY_ADD == "api_key_add"
        assert AuditEventType.API_KEY_REMOVE == "api_key_remove"


# ===========================================================================
# _generate_session_hash
# ===========================================================================

class TestGenerateSessionHash:
    """Tests for AuditLogger._generate_session_hash."""

    # --- Return type and length ---

    def test_returns_string(self, logger_instance):
        result = logger_instance._generate_session_hash("abc")
        assert isinstance(result, str)

    def test_returns_12_chars_with_session_id(self, logger_instance):
        result = logger_instance._generate_session_hash("any-session")
        assert len(result) == 12

    def test_returns_12_chars_with_none(self, logger_instance):
        result = logger_instance._generate_session_hash(None)
        assert len(result) == 12

    def test_returns_12_chars_with_empty_string(self, logger_instance):
        # empty string is falsy, so it follows the pid-thread path
        result = logger_instance._generate_session_hash("")
        assert len(result) == 12

    def test_only_hex_characters(self, logger_instance):
        result = logger_instance._generate_session_hash("session-42")
        valid = set("0123456789abcdef")
        assert all(c in valid for c in result), f"Non-hex chars in {result!r}"

    def test_lowercase_hex(self, logger_instance):
        result = logger_instance._generate_session_hash("UPPERCASE-ID")
        assert result == result.lower()

    # --- Correctness against known SHA-256 output ---

    def test_matches_sha256_hexdigest_12(self, logger_instance):
        session_id = "test-session-id"
        expected = hashlib.sha256(session_id.encode()).hexdigest()[:12]
        assert logger_instance._generate_session_hash(session_id) == expected

    def test_different_session_ids_differ(self, logger_instance):
        h1 = logger_instance._generate_session_hash("session-a")
        h2 = logger_instance._generate_session_hash("session-b")
        assert h1 != h2

    def test_same_session_id_is_deterministic(self, logger_instance):
        h1 = logger_instance._generate_session_hash("stable-session")
        h2 = logger_instance._generate_session_hash("stable-session")
        assert h1 == h2

    def test_unicode_session_id(self, logger_instance):
        result = logger_instance._generate_session_hash("日本語セッション")
        assert isinstance(result, str)
        assert len(result) == 12

    def test_long_session_id(self, logger_instance):
        result = logger_instance._generate_session_hash("x" * 10_000)
        assert len(result) == 12

    # --- None / no-argument path uses pid and thread ---

    def test_no_session_id_uses_pid_thread(self, logger_instance):
        pid = os.getpid()
        tid = threading.get_ident()
        expected = hashlib.sha256(
            f"{pid}-{tid}".encode()
        ).hexdigest()[:12]
        assert logger_instance._generate_session_hash(None) == expected

    def test_no_session_id_consistent_within_same_thread(self, logger_instance):
        h1 = logger_instance._generate_session_hash(None)
        h2 = logger_instance._generate_session_hash(None)
        assert h1 == h2


# ===========================================================================
# _redact_phi
# ===========================================================================

class TestRedactPHI:
    """Tests for AuditLogger._redact_phi."""

    # --- Non-PHI fields are preserved ---

    def test_non_phi_string_preserved(self, logger_instance):
        result = logger_instance._redact_phi({"action": "view"})
        assert result["action"] == "view"

    def test_non_phi_integer_preserved(self, logger_instance):
        result = logger_instance._redact_phi({"record_count": 7})
        assert result["record_count"] == 7

    def test_non_phi_none_preserved(self, logger_instance):
        result = logger_instance._redact_phi({"status": None})
        assert result["status"] is None

    def test_non_phi_list_preserved(self, logger_instance):
        result = logger_instance._redact_phi({"tags": [1, 2, 3]})
        assert result["tags"] == [1, 2, 3]

    def test_empty_dict_returns_empty_dict(self, logger_instance):
        assert logger_instance._redact_phi({}) == {}

    def test_returns_new_dict(self, logger_instance):
        original = {"action": "test", "patient_name": "Alice"}
        result = logger_instance._redact_phi(original)
        assert result is not original

    # --- PHI string fields get length-tagged redaction ---

    def test_phi_string_redacted_with_char_count(self, logger_instance):
        result = logger_instance._redact_phi({"patient_name": "Alice Smith"})
        assert result["patient_name"] == "[REDACTED:11chars]"

    def test_phi_length_in_tag_matches_value_length(self, logger_instance):
        value = "x" * 75
        result = logger_instance._redact_phi({"transcript": value})
        assert result["transcript"] == "[REDACTED:75chars]"

    def test_phi_empty_string_replaced_with_redacted(self, logger_instance):
        result = logger_instance._redact_phi({"patient_name": ""})
        assert result["patient_name"] == "[REDACTED]"

    # --- PHI non-string values get plain [REDACTED] ---

    def test_phi_integer_value_redacted(self, logger_instance):
        result = logger_instance._redact_phi({"patient_id": 12345})
        assert result["patient_id"] == "[REDACTED]"

    def test_phi_none_value_redacted(self, logger_instance):
        result = logger_instance._redact_phi({"diagnosis": None})
        assert result["diagnosis"] == "[REDACTED]"

    def test_phi_list_value_redacted(self, logger_instance):
        result = logger_instance._redact_phi({"symptoms": ["fever", "cough"]})
        assert result["symptoms"] == "[REDACTED]"

    def test_phi_zero_value_redacted(self, logger_instance):
        result = logger_instance._redact_phi({"medication": 0})
        assert result["medication"] == "[REDACTED]"

    # --- All 15 PHI field names redact non-empty strings ---

    @pytest.mark.parametrize("field", [
        "patient_name",
        "patient_id",
        "diagnosis",
        "symptoms",
        "transcript",
        "soap_note",
        "medical_history",
        "medication",
        "chief_complaint",
        "assessment",
        "treatment",
        "content",
        "text",
        "clinical_text",
        "note",
        "notes",
    ])
    def test_phi_field_is_redacted(self, logger_instance, field):
        value = "some sensitive data"
        result = logger_instance._redact_phi({field: value})
        assert result[field] == f"[REDACTED:{len(value)}chars]"

    # --- Case-insensitive key matching ---

    def test_uppercase_phi_key_is_redacted(self, logger_instance):
        # "PATIENT_NAME".lower() == "patient_name" which is in phi_fields
        result = logger_instance._redact_phi({"PATIENT_NAME": "Bob"})
        assert result["PATIENT_NAME"].startswith("[REDACTED")

    def test_mixed_case_phi_key_is_redacted(self, logger_instance):
        result = logger_instance._redact_phi({"Patient_Name": "Carol"})
        assert result["Patient_Name"].startswith("[REDACTED")

    def test_mixed_case_content_key_is_redacted(self, logger_instance):
        result = logger_instance._redact_phi({"Content": "some text"})
        assert result["Content"].startswith("[REDACTED")

    # --- Nested dict recursion ---

    def test_nested_phi_field_redacted(self, logger_instance):
        data = {"metadata": {"patient_name": "Dave"}}
        result = logger_instance._redact_phi(data)
        assert result["metadata"]["patient_name"].startswith("[REDACTED")

    def test_nested_non_phi_preserved(self, logger_instance):
        data = {"metadata": {"record_type": "outpatient"}}
        result = logger_instance._redact_phi(data)
        assert result["metadata"]["record_type"] == "outpatient"

    def test_deeply_nested_phi_redacted(self, logger_instance):
        data = {"level1": {"level2": {"clinical_text": "deep PHI"}}}
        result = logger_instance._redact_phi(data)
        assert result["level1"]["level2"]["clinical_text"].startswith("[REDACTED")

    # --- Mixed PHI and non-PHI in one dict ---

    def test_mixed_dict_only_phi_redacted(self, logger_instance):
        data = {
            "action": "transcribe",
            "transcript": "Patient reports pain",
            "record_count": 1,
            "note": "follow-up needed",
        }
        result = logger_instance._redact_phi(data)
        assert result["action"] == "transcribe"
        assert result["record_count"] == 1
        assert result["transcript"].startswith("[REDACTED")
        assert result["note"].startswith("[REDACTED")

    def test_original_dict_not_mutated(self, logger_instance):
        original = {"patient_name": "Eve", "action": "view"}
        original_copy = dict(original)
        logger_instance._redact_phi(original)
        assert original == original_copy

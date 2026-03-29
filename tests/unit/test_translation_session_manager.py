"""
Tests for src/managers/translation_session_manager.py

Covers TranslationSessionManager (singleton, start_session, end_session,
add_entry, add_patient_entry, add_doctor_entry, get_session,
get_sessions_for_recording, get_recent_sessions, delete_session,
export_session) and get_translation_session_manager singleton accessor.
All database calls are mocked via get_db_manager.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from models.translation_session import Speaker, TranslationEntry, TranslationSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cursor(fetchone_val=None, fetchall_val=None):
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone_val
    cursor.fetchall.return_value = fetchall_val or []
    return cursor


def _make_conn(cursor=None):
    if cursor is None:
        cursor = _make_cursor()
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


def _make_db_manager(conn=None):
    """Return (db_manager_mock, conn_mock)."""
    if conn is None:
        conn = _make_conn()
    db_manager = MagicMock()
    # Wire up the context manager protocol
    db_manager.get_connection.return_value.__enter__.return_value = conn
    db_manager.get_connection.return_value.__exit__.return_value = False
    return db_manager, conn


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton state before and after every test."""
    import managers.translation_session_manager as mod
    mod.TranslationSessionManager._instance = None
    mod._session_manager = None
    yield
    mod.TranslationSessionManager._instance = None
    mod._session_manager = None


def _make_manager(db_manager=None):
    """Create a TranslationSessionManager with a mocked db_manager.

    Returns (manager, db_manager_mock).
    """
    if db_manager is None:
        db_manager, _ = _make_db_manager()
    with patch("managers.translation_session_manager.get_db_manager", return_value=db_manager):
        from managers.translation_session_manager import TranslationSessionManager
        mgr = TranslationSessionManager()
    return mgr, db_manager


def _make_entry(speaker=Speaker.PATIENT):
    return TranslationEntry.create(
        speaker=speaker,
        original_text="Hello",
        original_language="en",
        translated_text="Hola",
        target_language="es"
    )


# ===========================================================================
# Init / Singleton
# ===========================================================================

class TestTranslationSessionManagerInit:
    def test_current_session_is_none(self):
        mgr, _ = _make_manager()
        assert mgr.current_session is None

    def test_db_manager_set(self):
        db, _ = _make_db_manager()
        mgr, _ = _make_manager(db)
        assert mgr.db_manager is db

    def test_singleton_returns_same_instance(self):
        db, _ = _make_db_manager()
        with patch("managers.translation_session_manager.get_db_manager", return_value=db):
            from managers.translation_session_manager import TranslationSessionManager
            mgr1 = TranslationSessionManager()
            mgr2 = TranslationSessionManager()
        assert mgr1 is mgr2


# ===========================================================================
# start_session
# ===========================================================================

class TestStartSession:
    def test_returns_translation_session(self):
        mgr, _ = _make_manager()
        session = mgr.start_session("es", "en")
        assert isinstance(session, TranslationSession)

    def test_sets_current_session(self):
        mgr, _ = _make_manager()
        session = mgr.start_session("es", "en")
        assert mgr.current_session is session

    def test_patient_language_set(self):
        mgr, _ = _make_manager()
        session = mgr.start_session("fr", "en")
        assert session.patient_language == "fr"

    def test_doctor_language_set(self):
        mgr, _ = _make_manager()
        session = mgr.start_session("es", "de")
        assert session.doctor_language == "de"

    def test_patient_name_passed(self):
        mgr, _ = _make_manager()
        session = mgr.start_session("es", "en", patient_name="John Doe")
        assert session.patient_name == "John Doe"

    def test_recording_id_passed(self):
        mgr, _ = _make_manager()
        session = mgr.start_session("es", "en", recording_id=42)
        assert session.recording_id == 42

    def test_ends_existing_session_before_starting(self):
        mgr, _ = _make_manager()
        session1 = mgr.start_session("es", "en")
        mgr.start_session("fr", "en")
        assert session1.ended_at is not None

    def test_previous_current_session_cleared(self):
        mgr, _ = _make_manager()
        mgr.start_session("es", "en")
        session2 = mgr.start_session("fr", "en")
        assert mgr.current_session is session2

    def test_calls_db_get_connection(self):
        db, _ = _make_db_manager()
        mgr, _ = _make_manager(db)
        mgr.start_session("es", "en")
        db.get_connection.assert_called()


# ===========================================================================
# end_session
# ===========================================================================

class TestEndSession:
    def test_returns_none_when_no_active_session(self):
        mgr, _ = _make_manager()
        result = mgr.end_session()
        assert result is None

    def test_returns_ended_session(self):
        mgr, _ = _make_manager()
        session = mgr.start_session("es", "en")
        result = mgr.end_session()
        assert result is session

    def test_sets_ended_at_on_session(self):
        mgr, _ = _make_manager()
        mgr.start_session("es", "en")
        ended = mgr.end_session()
        assert ended.ended_at is not None

    def test_clears_current_session(self):
        mgr, _ = _make_manager()
        mgr.start_session("es", "en")
        mgr.end_session()
        assert mgr.current_session is None

    def test_double_end_returns_none(self):
        mgr, _ = _make_manager()
        mgr.start_session("es", "en")
        mgr.end_session()
        assert mgr.end_session() is None


# ===========================================================================
# add_entry
# ===========================================================================

class TestAddEntry:
    def test_raises_when_no_active_session(self):
        mgr, _ = _make_manager()
        with pytest.raises(RuntimeError):
            mgr.add_entry(_make_entry())

    def test_appends_entry_to_current_session(self):
        mgr, _ = _make_manager()
        mgr.start_session("es", "en")
        entry = _make_entry()
        mgr.add_entry(entry)
        assert entry in mgr.current_session.entries

    def test_entry_count_increments(self):
        mgr, _ = _make_manager()
        mgr.start_session("es", "en")
        mgr.add_entry(_make_entry())
        mgr.add_entry(_make_entry())
        assert mgr.current_session.entry_count == 2

    def test_calls_db_get_connection_for_save(self):
        db, _ = _make_db_manager()
        mgr, _ = _make_manager(db)
        mgr.start_session("es", "en")
        count_before = db.get_connection.call_count
        mgr.add_entry(_make_entry())
        assert db.get_connection.call_count > count_before


# ===========================================================================
# add_patient_entry
# ===========================================================================

class TestAddPatientEntry:
    def test_returns_translation_entry(self):
        mgr, _ = _make_manager()
        mgr.start_session("es", "en")
        entry = mgr.add_patient_entry("Hello", "en", "Hola", "es")
        assert isinstance(entry, TranslationEntry)

    def test_speaker_is_patient(self):
        mgr, _ = _make_manager()
        mgr.start_session("es", "en")
        entry = mgr.add_patient_entry("Hello", "en", "Hola", "es")
        assert entry.speaker == Speaker.PATIENT

    def test_llm_refined_text_passed(self):
        mgr, _ = _make_manager()
        mgr.start_session("es", "en")
        entry = mgr.add_patient_entry("Hello", "en", "Hola", "es", llm_refined_text="Hola!")
        assert entry.llm_refined_text == "Hola!"

    def test_duration_seconds_passed(self):
        mgr, _ = _make_manager()
        mgr.start_session("es", "en")
        entry = mgr.add_patient_entry("Hello", "en", "Hola", "es", duration_seconds=2.5)
        assert entry.duration_seconds == 2.5

    def test_entry_added_to_current_session(self):
        mgr, _ = _make_manager()
        mgr.start_session("es", "en")
        entry = mgr.add_patient_entry("Hello", "en", "Hola", "es")
        assert entry in mgr.current_session.entries


# ===========================================================================
# add_doctor_entry
# ===========================================================================

class TestAddDoctorEntry:
    def test_returns_translation_entry(self):
        mgr, _ = _make_manager()
        mgr.start_session("es", "en")
        entry = mgr.add_doctor_entry("Good morning", "en", "Buenos días", "es")
        assert isinstance(entry, TranslationEntry)

    def test_speaker_is_doctor(self):
        mgr, _ = _make_manager()
        mgr.start_session("es", "en")
        entry = mgr.add_doctor_entry("Good morning", "en", "Buenos días", "es")
        assert entry.speaker == Speaker.DOCTOR

    def test_llm_refined_text_passed(self):
        mgr, _ = _make_manager()
        mgr.start_session("es", "en")
        entry = mgr.add_doctor_entry("Good morning", "en", "Buenos días", "es",
                                     llm_refined_text="Buenos días!")
        assert entry.llm_refined_text == "Buenos días!"


# ===========================================================================
# get_session
# ===========================================================================

class TestGetSession:
    def test_returns_none_when_not_found(self):
        mgr, _ = _make_manager()
        # Default cursor: fetchone returns None
        result = mgr.get_session("nonexistent-id")
        assert result is None

    def test_returns_session_when_found(self):
        cursor = _make_cursor(
            fetchone_val=("sess-1", "es", "en", None, None, None,
                          "2024-01-01T10:00:00", None),
            fetchall_val=[]
        )
        db, _ = _make_db_manager(_make_conn(cursor))
        mgr, _ = _make_manager(db)
        result = mgr.get_session("sess-1")
        assert isinstance(result, TranslationSession)

    def test_returns_correct_session_id(self):
        cursor = _make_cursor(
            fetchone_val=("sess-abc", "fr", "en", "Jane", 1, None,
                          "2024-06-15T08:30:00", None),
            fetchall_val=[]
        )
        db, _ = _make_db_manager(_make_conn(cursor))
        mgr, _ = _make_manager(db)
        result = mgr.get_session("sess-abc")
        assert result.session_id == "sess-abc"

    def test_parses_entries_from_rows(self):
        cursor = _make_cursor(
            fetchone_val=("sess-1", "es", "en", None, None, None,
                          "2024-01-01T10:00:00", None),
            fetchall_val=[
                ("entry-1", "patient", "2024-01-01T10:00:01", "Hello",
                 "en", "Hola", "es", None, None)
            ]
        )
        db, _ = _make_db_manager(_make_conn(cursor))
        mgr, _ = _make_manager(db)
        result = mgr.get_session("sess-1")
        assert len(result.entries) == 1
        assert result.entries[0].id == "entry-1"

    def test_returns_none_on_exception(self):
        db, _ = _make_db_manager()
        db.get_connection.side_effect = RuntimeError("DB error")
        mgr, _ = _make_manager()
        mgr.db_manager = db
        result = mgr.get_session("any-id")
        assert result is None

    def test_parses_ended_at_when_present(self):
        cursor = _make_cursor(
            fetchone_val=("sess-1", "es", "en", None, None, None,
                          "2024-01-01T10:00:00", "2024-01-01T10:30:00"),
            fetchall_val=[]
        )
        db, _ = _make_db_manager(_make_conn(cursor))
        mgr, _ = _make_manager(db)
        result = mgr.get_session("sess-1")
        assert result.ended_at is not None


# ===========================================================================
# get_sessions_for_recording
# ===========================================================================

class TestGetSessionsForRecording:
    def test_returns_empty_list_when_none(self):
        mgr, _ = _make_manager()
        result = mgr.get_sessions_for_recording(1)
        assert result == []

    def test_returns_list_type(self):
        mgr, _ = _make_manager()
        result = mgr.get_sessions_for_recording(1)
        assert isinstance(result, list)

    def test_returns_empty_on_exception(self):
        db, _ = _make_db_manager()
        db.get_connection.side_effect = RuntimeError("DB error")
        mgr, _ = _make_manager()
        mgr.db_manager = db
        result = mgr.get_sessions_for_recording(1)
        assert result == []


# ===========================================================================
# get_recent_sessions
# ===========================================================================

class TestGetRecentSessions:
    def test_returns_empty_list_when_none(self):
        mgr, _ = _make_manager()
        result = mgr.get_recent_sessions()
        assert result == []

    def test_returns_list_type(self):
        mgr, _ = _make_manager()
        result = mgr.get_recent_sessions()
        assert isinstance(result, list)

    def test_passes_limit_to_db(self):
        db, conn = _make_db_manager()
        mgr, _ = _make_manager(db)
        mgr.get_recent_sessions(limit=5)
        cursor = conn.cursor.return_value
        all_params = [
            c.args[1] for c in cursor.execute.call_args_list
            if len(c.args) > 1
        ]
        assert any(5 in p for p in all_params)

    def test_default_limit_is_10(self):
        db, conn = _make_db_manager()
        mgr, _ = _make_manager(db)
        mgr.get_recent_sessions()
        cursor = conn.cursor.return_value
        all_params = [
            c.args[1] for c in cursor.execute.call_args_list
            if len(c.args) > 1
        ]
        assert any(10 in p for p in all_params)

    def test_returns_empty_on_exception(self):
        db, _ = _make_db_manager()
        db.get_connection.side_effect = RuntimeError("DB error")
        mgr, _ = _make_manager()
        mgr.db_manager = db
        result = mgr.get_recent_sessions()
        assert result == []


# ===========================================================================
# delete_session
# ===========================================================================

class TestDeleteSession:
    def test_returns_true_on_success(self):
        mgr, _ = _make_manager()
        result = mgr.delete_session("sess-1")
        assert result is True

    def test_executes_delete_statements(self):
        db, conn = _make_db_manager()
        mgr, _ = _make_manager(db)
        mgr.delete_session("sess-1")
        cursor = conn.cursor.return_value
        # DELETE from translation_entries + DELETE from translation_sessions
        assert cursor.execute.call_count >= 2

    def test_returns_false_on_exception(self):
        db, _ = _make_db_manager()
        db.get_connection.side_effect = RuntimeError("DB error")
        mgr, _ = _make_manager()
        mgr.db_manager = db
        result = mgr.delete_session("sess-1")
        assert result is False

    def test_calls_commit(self):
        db, conn = _make_db_manager()
        mgr, _ = _make_manager(db)
        mgr.delete_session("sess-1")
        conn.commit.assert_called()


# ===========================================================================
# export_session
# ===========================================================================

class TestExportSession:
    def test_returns_none_when_session_not_found(self):
        mgr, _ = _make_manager()
        # Default cursor returns None for fetchone → get_session returns None
        result = mgr.export_session("nonexistent")
        assert result is None

    def test_returns_string_for_txt_format(self):
        mgr, _ = _make_manager()
        session = TranslationSession.create("es", "en")
        with patch.object(mgr, "get_session", return_value=session):
            result = mgr.export_session(session.session_id)
        assert isinstance(result, str)

    def test_txt_contains_session_id(self):
        mgr, _ = _make_manager()
        session = TranslationSession.create("es", "en")
        with patch.object(mgr, "get_session", return_value=session):
            result = mgr.export_session(session.session_id, format="txt")
        assert session.session_id in result

    def test_returns_valid_json_when_format_json(self):
        import json
        mgr, _ = _make_manager()
        session = TranslationSession.create("es", "en")
        with patch.object(mgr, "get_session", return_value=session):
            result = mgr.export_session(session.session_id, format="json")
        data = json.loads(result)
        assert "session_id" in data

    def test_unknown_format_defaults_to_txt(self):
        mgr, _ = _make_manager()
        session = TranslationSession.create("es", "en")
        with patch.object(mgr, "get_session", return_value=session):
            result = mgr.export_session(session.session_id, format="xml")
        # Falls to else branch → to_transcript()
        assert session.session_id in result


# ===========================================================================
# get_translation_session_manager singleton accessor
# ===========================================================================

class TestGetTranslationSessionManager:
    def test_returns_manager_instance(self):
        import managers.translation_session_manager as mod
        mod.TranslationSessionManager._instance = None
        mod._session_manager = None

        db, _ = _make_db_manager()
        with patch("managers.translation_session_manager.get_db_manager", return_value=db):
            from managers.translation_session_manager import (
                get_translation_session_manager, TranslationSessionManager
            )
            mgr = get_translation_session_manager()
        assert isinstance(mgr, TranslationSessionManager)
        mod._session_manager = None

    def test_returns_same_instance_on_repeated_calls(self):
        import managers.translation_session_manager as mod
        mod.TranslationSessionManager._instance = None
        mod._session_manager = None

        db, _ = _make_db_manager()
        with patch("managers.translation_session_manager.get_db_manager", return_value=db):
            from managers.translation_session_manager import get_translation_session_manager
            m1 = get_translation_session_manager()
            m2 = get_translation_session_manager()
        assert m1 is m2
        mod._session_manager = None

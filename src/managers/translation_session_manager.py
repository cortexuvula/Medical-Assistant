"""
Translation Session Manager

Manages persistence and retrieval of translation sessions,
providing a singleton interface for session tracking across the application.
"""

import threading
from typing import List, Optional
from datetime import datetime
from utils.structured_logging import get_logger

from database.db_pool import get_db_manager
from models.translation_session import TranslationSession, TranslationEntry, Speaker

logger = get_logger(__name__)


class TranslationSessionManager:
    """Manages translation session persistence and retrieval.

    Singleton manager that handles creating, updating, and retrieving
    translation sessions from the database.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.db_manager = get_db_manager()
        self.current_session: Optional[TranslationSession] = None
        # Using module-level logger

    def start_session(
        self,
        patient_language: str,
        doctor_language: str,
        patient_name: Optional[str] = None,
        recording_id: Optional[int] = None
    ) -> TranslationSession:
        """Start a new translation session.

        Args:
            patient_language: Language code for patient
            doctor_language: Language code for doctor
            patient_name: Optional patient name
            recording_id: Optional link to a recording

        Returns:
            New TranslationSession instance
        """
        # End any existing session
        if self.current_session:
            self.end_session()

        # Create new session
        self.current_session = TranslationSession.create(
            patient_language=patient_language,
            doctor_language=doctor_language,
            patient_name=patient_name,
            recording_id=recording_id
        )

        # Persist to database
        self._save_session(self.current_session)

        logger.info(f"Started translation session {self.current_session.session_id}")
        return self.current_session

    def end_session(self) -> Optional[TranslationSession]:
        """End the current session.

        Returns:
            The ended session, or None if no session was active
        """
        if not self.current_session:
            return None

        self.current_session.end_session()
        self._update_session_ended(self.current_session)

        ended_session = self.current_session
        self.current_session = None

        logger.info(f"Ended translation session {ended_session.session_id}")
        return ended_session

    def add_entry(self, entry: TranslationEntry) -> None:
        """Add an entry to the current session.

        Args:
            entry: TranslationEntry to add

        Raises:
            RuntimeError: If no session is active
        """
        if not self.current_session:
            raise RuntimeError("No active translation session")

        self.current_session.add_entry(entry)
        self._save_entry(entry, self.current_session.session_id)

        logger.debug(f"Added entry {entry.id} to session {self.current_session.session_id}")

    def add_patient_entry(
        self,
        original_text: str,
        original_language: str,
        translated_text: str,
        target_language: str,
        llm_refined_text: Optional[str] = None,
        duration_seconds: Optional[float] = None
    ) -> TranslationEntry:
        """Convenience method to add a patient entry.

        Args:
            original_text: Patient's original speech
            original_language: Language code of original
            translated_text: Translated text for doctor
            target_language: Language code of translation
            llm_refined_text: Optional LLM-refined translation
            duration_seconds: Optional duration of speech

        Returns:
            The created TranslationEntry
        """
        entry = TranslationEntry.create(
            speaker=Speaker.PATIENT,
            original_text=original_text,
            original_language=original_language,
            translated_text=translated_text,
            target_language=target_language,
            llm_refined_text=llm_refined_text,
            duration_seconds=duration_seconds
        )
        self.add_entry(entry)
        return entry

    def add_doctor_entry(
        self,
        original_text: str,
        original_language: str,
        translated_text: str,
        target_language: str,
        llm_refined_text: Optional[str] = None
    ) -> TranslationEntry:
        """Convenience method to add a doctor entry.

        Args:
            original_text: Doctor's original text
            original_language: Language code of original
            translated_text: Translated text for patient
            target_language: Language code of translation
            llm_refined_text: Optional LLM-refined translation

        Returns:
            The created TranslationEntry
        """
        entry = TranslationEntry.create(
            speaker=Speaker.DOCTOR,
            original_text=original_text,
            original_language=original_language,
            translated_text=translated_text,
            target_language=target_language,
            llm_refined_text=llm_refined_text
        )
        self.add_entry(entry)
        return entry

    def get_session(self, session_id: str) -> Optional[TranslationSession]:
        """Retrieve a session by ID.

        Args:
            session_id: Session UUID to retrieve

        Returns:
            TranslationSession if found, None otherwise
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get session
                cursor.execute("""
                    SELECT session_id, patient_language, doctor_language,
                           patient_name, recording_id, notes, created_at, ended_at
                    FROM translation_sessions
                    WHERE session_id = ?
                """, (session_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                session = TranslationSession(
                    session_id=row[0],
                    patient_language=row[1],
                    doctor_language=row[2],
                    patient_name=row[3],
                    recording_id=row[4],
                    notes=row[5],
                    created_at=datetime.fromisoformat(row[6]) if row[6] else datetime.now(),
                    ended_at=datetime.fromisoformat(row[7]) if row[7] else None
                )

                # Get entries
                cursor.execute("""
                    SELECT entry_id, speaker, timestamp, original_text,
                           original_language, translated_text, target_language,
                           llm_refined_text, duration_seconds
                    FROM translation_entries
                    WHERE session_id = ?
                    ORDER BY timestamp ASC
                """, (session_id,))

                for entry_row in cursor.fetchall():
                    entry = TranslationEntry(
                        id=entry_row[0],
                        speaker=Speaker(entry_row[1]),
                        timestamp=datetime.fromisoformat(entry_row[2]),
                        original_text=entry_row[3],
                        original_language=entry_row[4],
                        translated_text=entry_row[5],
                        target_language=entry_row[6],
                        llm_refined_text=entry_row[7],
                        duration_seconds=entry_row[8]
                    )
                    session.entries.append(entry)

                return session

        except Exception as e:
            logger.error(f"Error retrieving session {session_id}: {e}")
            return None

    def get_sessions_for_recording(self, recording_id: int) -> List[TranslationSession]:
        """Get all translation sessions for a recording.

        Args:
            recording_id: Recording ID to search for

        Returns:
            List of TranslationSession objects
        """
        sessions = []
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT session_id FROM translation_sessions
                    WHERE recording_id = ?
                    ORDER BY created_at DESC
                """, (recording_id,))

                for row in cursor.fetchall():
                    session = self.get_session(row[0])
                    if session:
                        sessions.append(session)

        except Exception as e:
            logger.error(f"Error retrieving sessions for recording {recording_id}: {e}")

        return sessions

    def get_recent_sessions(self, limit: int = 10) -> List[TranslationSession]:
        """Get the most recent translation sessions.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of TranslationSession objects
        """
        sessions = []
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT session_id FROM translation_sessions
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))

                for row in cursor.fetchall():
                    session = self.get_session(row[0])
                    if session:
                        sessions.append(session)

        except Exception as e:
            logger.error(f"Error retrieving recent sessions: {e}")

        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its entries.

        Args:
            session_id: Session UUID to delete

        Returns:
            True if deleted, False otherwise
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Delete entries first (cascade should handle this, but be explicit)
                cursor.execute("""
                    DELETE FROM translation_entries WHERE session_id = ?
                """, (session_id,))

                # Delete session
                cursor.execute("""
                    DELETE FROM translation_sessions WHERE session_id = ?
                """, (session_id,))

                conn.commit()
                logger.info(f"Deleted translation session {session_id}")
                return True

        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            return False

    def export_session(self, session_id: str, format: str = "txt") -> Optional[str]:
        """Export a session to the specified format.

        Args:
            session_id: Session UUID to export
            format: Export format ("txt", "json")

        Returns:
            Exported content string, or None if session not found
        """
        session = self.get_session(session_id)
        if not session:
            return None

        if format == "json":
            return session.to_json()
        else:  # Default to txt
            return session.to_transcript()

    def _save_session(self, session: TranslationSession) -> None:
        """Save a session to the database."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO translation_sessions
                    (session_id, recording_id, patient_language, doctor_language,
                     patient_name, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    session.session_id,
                    session.recording_id,
                    session.patient_language,
                    session.doctor_language,
                    session.patient_name,
                    session.notes,
                    session.created_at.isoformat()
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving session: {e}")

    def _save_entry(self, entry: TranslationEntry, session_id: str) -> None:
        """Save an entry to the database."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO translation_entries
                    (session_id, entry_id, speaker, timestamp, original_text,
                     original_language, translated_text, target_language,
                     llm_refined_text, duration_seconds)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    entry.id,
                    entry.speaker.value,
                    entry.timestamp.isoformat(),
                    entry.original_text,
                    entry.original_language,
                    entry.translated_text,
                    entry.target_language,
                    entry.llm_refined_text,
                    entry.duration_seconds
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving entry: {e}")

    def _update_session_ended(self, session: TranslationSession) -> None:
        """Update session ended timestamp."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE translation_sessions
                    SET ended_at = ?
                    WHERE session_id = ?
                """, (
                    session.ended_at.isoformat() if session.ended_at else None,
                    session.session_id
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating session ended: {e}")


# Singleton accessor
_session_manager: Optional[TranslationSessionManager] = None
_manager_lock = threading.Lock()


def get_translation_session_manager() -> TranslationSessionManager:
    """Get the global translation session manager.

    Returns:
        TranslationSessionManager singleton instance
    """
    global _session_manager
    if _session_manager is None:
        with _manager_lock:
            if _session_manager is None:
                _session_manager = TranslationSessionManager()
    return _session_manager

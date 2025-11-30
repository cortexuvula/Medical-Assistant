"""
Database Manager Module

Handles all database operations for recordings, letters, and other data.
Provides a clean interface for database interactions.
"""

import logging
import os
from datetime import datetime as dt
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from database.database import Database
from pydub import AudioSegment
from managers.data_folder_manager import data_folder_manager


class DatabaseManager:
    """Manages database operations for the application."""

    def __init__(self, db_path: str = None):
        """Initialize database manager.

        Args:
            db_path: Path to the database file
        """
        self.db_path = db_path if db_path else str(data_folder_manager.database_file_path)
        self._db = Database(self.db_path)
        self._ensure_database_exists()

    def _ensure_database_exists(self) -> None:
        """Ensure database exists and is properly initialized."""
        try:
            # Database class initializes tables via create_tables()
            self._db.create_tables()
        except Exception as e:
            logging.error(f"Failed to initialize database: {e}")

    def save_soap_recording(self, recording_data: Dict[str, Any]) -> Optional[int]:
        """Save SOAP recording to database.

        Args:
            recording_data: Dictionary containing:
                - transcript: Text transcript
                - audio_path: Path to audio file
                - duration: Recording duration in seconds
                - soap_note: Generated SOAP note (optional)
                - metadata: Additional metadata (optional)

        Returns:
            Optional[int]: Recording ID or None if failed
        """
        try:
            # Prepare data
            transcript = recording_data.get("transcript", "")
            audio_path = recording_data.get("audio_path", "")
            duration = recording_data.get("duration", 0)
            soap_note = recording_data.get("soap_note", "")
            metadata = recording_data.get("metadata", {})

            # Add timestamp to metadata
            metadata["saved_at"] = dt.now().isoformat()

            # Save to database using the Database class method
            recording_id = self._db.add_recording(
                filename=audio_path,
                transcript=transcript,
                soap_note=soap_note
            )

            logging.info(f"SOAP recording saved to database with ID: {recording_id}")
            return recording_id

        except Exception as e:
            logging.error(f"Failed to save SOAP recording: {e}")
            return None

    def save_letter(self, letter_data: Dict[str, Any]) -> Optional[int]:
        """Save letter to database.

        Args:
            letter_data: Dictionary containing:
                - type: Letter type (referral, general, etc.)
                - content: Letter content
                - source_text: Original source text
                - metadata: Additional metadata (optional)

        Returns:
            Optional[int]: Letter ID or None if failed
        """
        try:
            # Prepare data
            letter_type = letter_data.get("type", "general")
            content = letter_data.get("content", "")
            source_text = letter_data.get("source_text", "")
            metadata = letter_data.get("metadata", {})

            # Add timestamp to metadata
            metadata["created_at"] = dt.now().isoformat()
            metadata["letter_type"] = letter_type

            # Save to database using the Database class method
            letter_id = self._db.add_recording(
                filename="",  # No audio file for letters
                transcript=source_text,
                letter=content  # Store letter content in letter field
            )

            logging.info(f"Letter saved to database with ID: {letter_id}")
            return letter_id

        except Exception as e:
            logging.error(f"Failed to save letter: {e}")
            return None

    def get_recordings(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get recordings from database.

        Args:
            limit: Maximum number of recordings to retrieve
            offset: Number of recordings to skip

        Returns:
            List of recording dictionaries
        """
        try:
            # Use the Database class method which returns dictionaries
            recordings = self._db.get_all_recordings()

            # Apply offset and limit
            return recordings[offset:offset + limit]

        except Exception as e:
            logging.error(f"Failed to get recordings: {e}")
            return []

    def get_recording_by_id(self, recording_id: int) -> Optional[Dict[str, Any]]:
        """Get specific recording by ID.

        Args:
            recording_id: Recording ID

        Returns:
            Optional[Dict[str, Any]]: Recording data or None if not found
        """
        try:
            # Use the Database class method which returns a dictionary
            return self._db.get_recording(recording_id)

        except Exception as e:
            logging.error(f"Failed to get recording {recording_id}: {e}")
            return None

    def update_recording(self, recording_id: int, updates: Dict[str, Any]) -> bool:
        """Update recording in database.

        Args:
            recording_id: Recording ID
            updates: Dictionary of fields to update

        Returns:
            bool: True if updated successfully
        """
        try:
            # Use the Database class method
            result = self._db.update_recording(recording_id, **updates)

            if result:
                logging.info(f"Recording {recording_id} updated successfully")
            return result

        except Exception as e:
            logging.error(f"Failed to update recording {recording_id}: {e}")
            return False

    def delete_recording(self, recording_id: int) -> bool:
        """Delete recording from database.

        Args:
            recording_id: Recording ID

        Returns:
            bool: True if deleted successfully
        """
        try:
            # Get recording to check for audio file
            recording = self.get_recording_by_id(recording_id)

            if recording:
                # Delete from database using the Database class method
                result = self._db.delete_recording(recording_id)

                if result:
                    # Delete audio file if exists
                    audio_path = recording.get("filename", "")
                    if audio_path and os.path.exists(audio_path):
                        try:
                            os.remove(audio_path)
                            logging.info(f"Deleted audio file: {audio_path}")
                        except Exception as e:
                            logging.warning(f"Failed to delete audio file: {e}")

                    logging.info(f"Recording {recording_id} deleted successfully")
                    return True

            return False

        except Exception as e:
            logging.error(f"Failed to delete recording {recording_id}: {e}")
            return False

    def search_recordings(self, query: str, search_type: str = "all") -> List[Dict[str, Any]]:
        """Search recordings in database.

        Args:
            query: Search query
            search_type: Type of search (all, transcript, soap_note)

        Returns:
            List of matching recordings
        """
        try:
            # Use the Database class method for searching
            # The Database.search_recordings method already handles all fields
            return self._db.search_recordings(query)

        except Exception as e:
            logging.error(f"Failed to search recordings: {e}")
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics.

        Returns:
            Dictionary with statistics
        """
        try:
            with self._db.connection() as (conn, cursor):
                # Total recordings
                cursor.execute("SELECT COUNT(*) FROM recordings")
                total_recordings = cursor.fetchone()[0]

                # Total duration
                cursor.execute("SELECT SUM(duration) FROM recordings")
                result = cursor.fetchone()[0]
                total_duration = result if result else 0

                # Recordings with SOAP notes
                cursor.execute("SELECT COUNT(*) FROM recordings WHERE soap_note != '' AND soap_note IS NOT NULL")
                soap_count = cursor.fetchone()[0]

                # Latest recording date
                cursor.execute("SELECT MAX(timestamp) FROM recordings")
                latest_date = cursor.fetchone()[0]

                return {
                    "total_recordings": total_recordings,
                    "total_duration_seconds": total_duration,
                    "total_duration_hours": round(total_duration / 3600, 2) if total_duration else 0,
                    "soap_notes_count": soap_count,
                    "latest_recording_date": latest_date
                }

        except Exception as e:
            logging.error(f"Failed to get statistics: {e}")
            return {
                "total_recordings": 0,
                "total_duration_seconds": 0,
                "total_duration_hours": 0,
                "soap_notes_count": 0,
                "latest_recording_date": None
            }

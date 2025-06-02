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

from database import Database
from pydub import AudioSegment


class DatabaseManager:
    """Manages database operations for the application."""
    
    def __init__(self, db_path: str = "database.db"):
        """Initialize database manager.
        
        Args:
            db_path: Path to the database file
        """
        self.db_path = db_path
        self._ensure_database_exists()
        
    def _ensure_database_exists(self) -> None:
        """Ensure database exists and is properly initialized."""
        try:
            db = Database(self.db_path)
            # Database class initializes tables in __init__, no need to close
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
            db = Database(self.db_path)
            
            # Prepare data
            transcript = recording_data.get("transcript", "")
            audio_path = recording_data.get("audio_path", "")
            duration = recording_data.get("duration", 0)
            soap_note = recording_data.get("soap_note", "")
            metadata = recording_data.get("metadata", {})
            
            # Add timestamp to metadata
            metadata["saved_at"] = dt.now().isoformat()
            
            # Save to database
            recording_id = db.add_recording(
                transcript=transcript,
                audio_path=audio_path,
                duration=duration,
                soap_note=soap_note,
                metadata=metadata
            )
            
            # Database class doesn't have close method
            
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
            db = Database(self.db_path)
            
            # Prepare data
            letter_type = letter_data.get("type", "general")
            content = letter_data.get("content", "")
            source_text = letter_data.get("source_text", "")
            metadata = letter_data.get("metadata", {})
            
            # Add timestamp to metadata
            metadata["created_at"] = dt.now().isoformat()
            metadata["letter_type"] = letter_type
            
            # Save to database (using recording table for now)
            letter_id = db.add_recording(
                transcript=source_text,
                audio_path="",  # No audio for letters
                duration=0,
                soap_note=content,
                metadata=metadata
            )
            
            # Database class doesn't have close method
            
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
            db = Database(self.db_path)
            recordings = db.get_recordings(limit=limit, offset=offset)
            # Database class doesn't have close method
            
            # Convert to list of dictionaries
            result = []
            for recording in recordings:
                result.append({
                    "id": recording[0],
                    "transcript": recording[1],
                    "audio_path": recording[2],
                    "created_at": recording[3],
                    "duration": recording[4],
                    "soap_note": recording[5],
                    "metadata": recording[6] if len(recording) > 6 else {}
                })
                
            return result
            
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
            db = Database(self.db_path)
            recording = db.get_recording(recording_id)
            # Database class doesn't have close method
            
            if recording:
                return {
                    "id": recording[0],
                    "transcript": recording[1],
                    "audio_path": recording[2],
                    "created_at": recording[3],
                    "duration": recording[4],
                    "soap_note": recording[5],
                    "metadata": recording[6] if len(recording) > 6 else {}
                }
                
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
            db = Database(self.db_path)
            
            # Build update query based on provided fields
            if "soap_note" in updates:
                db.cursor.execute(
                    "UPDATE recordings SET soap_note = ? WHERE id = ?",
                    (updates["soap_note"], recording_id)
                )
                
            if "metadata" in updates:
                db.cursor.execute(
                    "UPDATE recordings SET metadata = ? WHERE id = ?",
                    (updates["metadata"], recording_id)
                )
                
            db.conn.commit()
            # Database class doesn't have close method
            
            logging.info(f"Recording {recording_id} updated successfully")
            return True
            
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
            db = Database(self.db_path)
            
            # Get recording to check for audio file
            recording = self.get_recording_by_id(recording_id)
            
            if recording:
                # Delete from database
                db.cursor.execute("DELETE FROM recordings WHERE id = ?", (recording_id,))
                db.conn.commit()
                
                # Delete audio file if exists
                audio_path = recording.get("audio_path", "")
                if audio_path and os.path.exists(audio_path):
                    try:
                        os.remove(audio_path)
                        logging.info(f"Deleted audio file: {audio_path}")
                    except Exception as e:
                        logging.warning(f"Failed to delete audio file: {e}")
                        
            # Database class doesn't have close method
            
            logging.info(f"Recording {recording_id} deleted successfully")
            return True
            
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
            db = Database(self.db_path)
            
            # Build search query based on type
            if search_type == "transcript":
                sql = "SELECT * FROM recordings WHERE transcript LIKE ? ORDER BY created_at DESC"
            elif search_type == "soap_note":
                sql = "SELECT * FROM recordings WHERE soap_note LIKE ? ORDER BY created_at DESC"
            else:  # all
                sql = "SELECT * FROM recordings WHERE transcript LIKE ? OR soap_note LIKE ? ORDER BY created_at DESC"
                
            # Execute search
            search_pattern = f"%{query}%"
            
            if search_type == "all":
                db.cursor.execute(sql, (search_pattern, search_pattern))
            else:
                db.cursor.execute(sql, (search_pattern,))
                
            recordings = db.cursor.fetchall()
            # Database class doesn't have close method
            
            # Convert to list of dictionaries
            result = []
            for recording in recordings:
                result.append({
                    "id": recording[0],
                    "transcript": recording[1],
                    "audio_path": recording[2],
                    "created_at": recording[3],
                    "duration": recording[4],
                    "soap_note": recording[5],
                    "metadata": recording[6] if len(recording) > 6 else {}
                })
                
            return result
            
        except Exception as e:
            logging.error(f"Failed to search recordings: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics.
        
        Returns:
            Dictionary with statistics
        """
        try:
            db = Database(self.db_path)
            
            # Total recordings
            db.cursor.execute("SELECT COUNT(*) FROM recordings")
            total_recordings = db.cursor.fetchone()[0]
            
            # Total duration
            db.cursor.execute("SELECT SUM(duration) FROM recordings")
            total_duration = db.cursor.fetchone()[0] or 0
            
            # Recordings with SOAP notes
            db.cursor.execute("SELECT COUNT(*) FROM recordings WHERE soap_note != ''")
            soap_count = db.cursor.fetchone()[0]
            
            # Latest recording date
            db.cursor.execute("SELECT MAX(created_at) FROM recordings")
            latest_date = db.cursor.fetchone()[0]
            
            # Database class doesn't have close method
            
            return {
                "total_recordings": total_recordings,
                "total_duration_seconds": total_duration,
                "total_duration_hours": round(total_duration / 3600, 2),
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
"""
Improved database module with connection pooling, context managers, and better search.
"""

import sqlite3
import datetime
import json
import logging
from typing import Optional, Dict, List, Any, Union, Tuple
from contextlib import contextmanager

from database.db_pool import get_db_manager
from database.db_migrations import get_migration_manager
from utils.exceptions import DatabaseError


class ImprovedDatabase:
    """Improved database interface with connection pooling and better features."""
    
    def __init__(self):
        """Initialize database with connection pool."""
        self.logger = logging.getLogger(__name__)
        self.db_manager = get_db_manager()
        self._ensure_migrations()
    
    def _ensure_migrations(self):
        """Ensure all migrations are applied."""
        migration_manager = get_migration_manager()
        current_version = migration_manager.get_current_version()
        pending = migration_manager.get_pending_migrations()
        
        if pending:
            self.logger.info(f"Found {len(pending)} pending migrations")
            try:
                migration_manager.migrate()
            except DatabaseError as e:
                self.logger.error(f"Failed to apply migrations: {e}")
                raise
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions.
        
        Usage:
            with db.transaction():
                db.add_recording(...)
                db.update_recording(...)
        """
        with self.db_manager.transaction() as conn:
            # Store connection for use in methods
            self._current_conn = conn
            try:
                yield self
            finally:
                self._current_conn = None
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get current connection or a new one from pool."""
        if hasattr(self, '_current_conn') and self._current_conn:
            return self._current_conn
        # This will raise an error - transactions should be used
        raise DatabaseError("Database operations must be performed within a transaction context")
    
    def add_recording(
        self,
        filename: str,
        transcript: Optional[str] = None,
        soap_note: Optional[str] = None,
        referral: Optional[str] = None,
        letter: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        file_size_bytes: Optional[int] = None,
        stt_provider: Optional[str] = None,
        ai_provider: Optional[str] = None,
        tags: Optional[List[str]] = None,
        patient_id: Optional[int] = None
    ) -> int:
        """Add a new recording to the database.
        
        Args:
            filename: Path to the recording file
            transcript: Text transcript of the recording
            soap_note: Generated SOAP note
            referral: Generated referral
            letter: Generated letter
            duration_seconds: Recording duration
            file_size_bytes: File size in bytes
            stt_provider: STT provider used
            ai_provider: AI provider used
            tags: List of tags
            patient_id: Associated patient ID
            
        Returns:
            ID of the new recording
            
        Raises:
            DatabaseError: If operation fails
        """
        try:
            # Serialize tags as JSON
            tags_json = json.dumps(tags) if tags else None
            
            query = """
            INSERT INTO recordings (
                filename, transcript, soap_note, referral, letter,
                timestamp, duration_seconds, file_size_bytes,
                stt_provider, ai_provider, tags, patient_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            params = (
                filename, transcript, soap_note, referral, letter,
                datetime.datetime.now(), duration_seconds, file_size_bytes,
                stt_provider, ai_provider, tags_json, patient_id
            )
            
            cursor = self.db_manager.execute(query, params)
            return cursor.lastrowid
            
        except Exception as e:
            raise DatabaseError(f"Failed to add recording: {e}")
    
    def update_recording(self, recording_id: int, **kwargs: Any) -> bool:
        """Update a recording in the database.
        
        Args:
            recording_id: ID of the recording to update
            **kwargs: Fields to update
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            DatabaseError: If operation fails
        """
        allowed_fields = [
            'filename', 'transcript', 'soap_note', 'referral', 'letter',
            'duration_seconds', 'file_size_bytes', 'stt_provider',
            'ai_provider', 'tags', 'patient_id'
        ]
        
        # Validate field names
        update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not update_fields:
            return False
        
        try:
            # Handle tags serialization
            if 'tags' in update_fields and update_fields['tags'] is not None:
                update_fields['tags'] = json.dumps(update_fields['tags'])
            
            # Build query
            set_clause = ", ".join([f"{field} = ?" for field in update_fields.keys()])
            query = f"UPDATE recordings SET {set_clause} WHERE id = ?"
            
            params = list(update_fields.values()) + [recording_id]
            
            cursor = self.db_manager.execute(query, params)
            return cursor.rowcount > 0
            
        except Exception as e:
            raise DatabaseError(f"Failed to update recording: {e}")
    
    def delete_recording(self, recording_id: int) -> bool:
        """Delete a recording from the database.
        
        Args:
            recording_id: ID of the recording to delete
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            DatabaseError: If operation fails
        """
        try:
            cursor = self.db_manager.execute(
                "DELETE FROM recordings WHERE id = ?",
                (recording_id,)
            )
            return cursor.rowcount > 0
        except Exception as e:
            raise DatabaseError(f"Failed to delete recording: {e}")
    
    def get_recording(self, recording_id: int) -> Optional[Dict[str, Any]]:
        """Get a recording by ID.
        
        Args:
            recording_id: ID of the recording
            
        Returns:
            Recording dict or None if not found
        """
        row = self.db_manager.fetchone(
            "SELECT * FROM recordings WHERE id = ?",
            (recording_id,)
        )
        
        if row:
            return self._row_to_dict(row)
        return None
    
    def get_all_recordings(self) -> List[Dict[str, Any]]:
        """Get all recordings ordered by timestamp."""
        rows = self.db_manager.fetchall(
            "SELECT * FROM recordings ORDER BY timestamp DESC"
        )
        return [self._row_to_dict(row) for row in rows]
    
    def search_recordings(
        self,
        search_term: str,
        use_fts: bool = True
    ) -> List[Dict[str, Any]]:
        """Search for recordings containing the search term.
        
        Args:
            search_term: Text to search for
            use_fts: Use full-text search if available
            
        Returns:
            List of matching recordings
        """
        try:
            if use_fts and self._has_fts():
                # Use full-text search
                query = """
                SELECT r.* FROM recordings r
                JOIN recordings_fts fts ON r.id = fts.rowid
                WHERE recordings_fts MATCH ?
                ORDER BY rank
                """
                # Escape special FTS characters
                escaped_term = search_term.replace('"', '""')
                rows = self.db_manager.fetchall(query, (f'"{escaped_term}"',))
            else:
                # Fallback to LIKE search
                query = """
                SELECT * FROM recordings 
                WHERE filename LIKE ? 
                   OR transcript LIKE ? 
                   OR soap_note LIKE ? 
                   OR referral LIKE ? 
                   OR letter LIKE ? 
                ORDER BY timestamp DESC
                """
                search_pattern = f"%{search_term}%"
                params = (search_pattern,) * 5
                rows = self.db_manager.fetchall(query, params)
            
            return [self._row_to_dict(row) for row in rows]
            
        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            # Fallback to basic search on error
            return self.search_recordings(search_term, use_fts=False)
    
    def search_by_tags(self, tags: List[str]) -> List[Dict[str, Any]]:
        """Search for recordings by tags.
        
        Args:
            tags: List of tags to search for
            
        Returns:
            List of recordings containing any of the tags
        """
        if not tags:
            return []
        
        # Build query for JSON array search
        tag_conditions = []
        params = []
        
        for tag in tags:
            tag_conditions.append("tags LIKE ?")
            params.append(f'%"{tag}"%')
        
        query = f"""
        SELECT * FROM recordings 
        WHERE {' OR '.join(tag_conditions)}
        ORDER BY timestamp DESC
        """
        
        rows = self.db_manager.fetchall(query, tuple(params))
        return [self._row_to_dict(row) for row in rows]
    
    def get_recordings_by_date_range(
        self,
        start_date: Union[str, datetime.datetime],
        end_date: Union[str, datetime.datetime]
    ) -> List[Dict[str, Any]]:
        """Get recordings created within a date range.
        
        Args:
            start_date: Start date (datetime or ISO string)
            end_date: End date (datetime or ISO string)
            
        Returns:
            List of recordings within the date range
        """
        if isinstance(start_date, str):
            start_date = datetime.datetime.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = datetime.datetime.fromisoformat(end_date)
        
        # Make end date inclusive
        end_date = end_date + datetime.timedelta(days=1)
        
        rows = self.db_manager.fetchall(
            """
            SELECT * FROM recordings 
            WHERE timestamp >= ? AND timestamp < ? 
            ORDER BY timestamp DESC
            """,
            (start_date.isoformat(), end_date.isoformat())
        )
        
        return [self._row_to_dict(row) for row in rows]
    
    def get_recordings_by_patient(self, patient_id: int) -> List[Dict[str, Any]]:
        """Get all recordings for a patient.
        
        Args:
            patient_id: Patient ID
            
        Returns:
            List of recordings for the patient
        """
        rows = self.db_manager.fetchall(
            "SELECT * FROM recordings WHERE patient_id = ? ORDER BY timestamp DESC",
            (patient_id,)
        )
        return [self._row_to_dict(row) for row in rows]
    
    def get_recording_stats(self) -> Dict[str, Any]:
        """Get statistics about recordings.
        
        Returns:
            Dictionary with statistics
        """
        stats = {}
        
        # Total recordings
        result = self.db_manager.fetchone("SELECT COUNT(*) FROM recordings")
        stats['total_recordings'] = result[0] if result else 0
        
        # Total duration
        result = self.db_manager.fetchone(
            "SELECT SUM(duration_seconds) FROM recordings WHERE duration_seconds IS NOT NULL"
        )
        stats['total_duration_seconds'] = result[0] if result and result[0] else 0
        
        # Total file size
        result = self.db_manager.fetchone(
            "SELECT SUM(file_size_bytes) FROM recordings WHERE file_size_bytes IS NOT NULL"
        )
        stats['total_file_size_bytes'] = result[0] if result and result[0] else 0
        
        # Recordings by provider
        rows = self.db_manager.fetchall(
            """
            SELECT stt_provider, COUNT(*) as count 
            FROM recordings 
            WHERE stt_provider IS NOT NULL 
            GROUP BY stt_provider
            """
        )
        stats['by_stt_provider'] = {row[0]: row[1] for row in rows}
        
        # Recordings by AI provider
        rows = self.db_manager.fetchall(
            """
            SELECT ai_provider, COUNT(*) as count 
            FROM recordings 
            WHERE ai_provider IS NOT NULL 
            GROUP BY ai_provider
            """
        )
        stats['by_ai_provider'] = {row[0]: row[1] for row in rows}
        
        return stats
    
    def _has_fts(self) -> bool:
        """Check if full-text search is available."""
        try:
            self.db_manager.execute("SELECT 1 FROM recordings_fts LIMIT 1")
            return True
        except:
            return False
    
    def _row_to_dict(self, row: tuple) -> Dict[str, Any]:
        """Convert a database row to a dictionary."""
        columns = [
            'id', 'filename', 'transcript', 'soap_note', 'referral', 'letter',
            'timestamp', 'duration_seconds', 'file_size_bytes', 'stt_provider',
            'ai_provider', 'tags', 'patient_id'
        ]
        
        # Handle different column counts for backward compatibility
        if len(row) < len(columns):
            # Pad with None for missing columns
            row = row + (None,) * (len(columns) - len(row))
        
        result = dict(zip(columns, row))
        
        # Deserialize tags
        if result.get('tags'):
            try:
                result['tags'] = json.loads(result['tags'])
            except:
                result['tags'] = []
        
        return result
    
    def optimize(self):
        """Optimize the database."""
        self.db_manager.execute("PRAGMA optimize")
        self.db_manager.execute("VACUUM")
        self.logger.info("Database optimized")


# Create a compatibility layer for the old Database class
class Database(ImprovedDatabase):
    """Backward-compatible database class."""
    
    def __init__(self, db_path: str = "database.db"):
        """Initialize with backward compatibility."""
        # Note: db_path is ignored, path comes from config
        super().__init__()
        self.db_path = db_path
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """Legacy connect method - no-op with connection pool."""
        pass
    
    def disconnect(self):
        """Legacy disconnect method - no-op with connection pool."""
        pass
    
    def create_tables(self):
        """Legacy create tables - handled by migrations."""
        pass
    
    # Override methods to use transaction context
    def add_recording(self, *args, **kwargs):
        """Add recording with transaction."""
        with self.transaction():
            return super().add_recording(*args, **kwargs)
    
    def update_recording(self, *args, **kwargs):
        """Update recording with transaction."""
        with self.transaction():
            return super().update_recording(*args, **kwargs)
    
    def delete_recording(self, *args, **kwargs):
        """Delete recording with transaction."""
        with self.transaction():
            return super().delete_recording(*args, **kwargs)
"""
Database Analysis Mixin

Provides analysis results operations for the Database class.
"""

import json
from typing import Optional, Dict, List, Any

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class AnalysisMixin:
    """Mixin providing analysis results operations."""

    def save_analysis_result(
        self,
        analysis_type: str,
        result_text: str,
        recording_id: Optional[int] = None,
        analysis_subtype: Optional[str] = None,
        result_json: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        patient_context: Optional[Dict[str, Any]] = None,
        source_type: Optional[str] = None,
        source_text: Optional[str] = None
    ) -> Optional[int]:
        """
        Save a medical analysis result to the database.

        Parameters:
        - analysis_type: Type of analysis ('medication', 'diagnostic', 'workflow')
        - result_text: The analysis result text
        - recording_id: Optional link to a recording
        - analysis_subtype: Subtype (e.g., 'comprehensive', 'interactions')
        - result_json: Optional structured JSON result
        - metadata: Optional metadata (model, counts, etc.)
        - patient_context: Optional patient context used
        - source_type: Source of analysis ('transcript', 'soap', 'custom')
        - source_text: The input text that was analyzed

        Returns:
        - ID of the created analysis result, or None on failure
        """
        with self.connection() as (conn, cursor):
            cursor.execute("""
                INSERT INTO analysis_results (
                    recording_id, analysis_type, analysis_subtype,
                    result_text, result_json, metadata_json,
                    patient_context_json, source_type, source_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                recording_id,
                analysis_type,
                analysis_subtype,
                result_text,
                json.dumps(result_json) if result_json else None,
                json.dumps(metadata) if metadata else None,
                json.dumps(patient_context) if patient_context else None,
                source_type,
                source_text
            ))
            return cursor.lastrowid

    def get_analysis_result(self, analysis_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single analysis result by ID.

        Parameters:
        - analysis_id: The analysis result ID

        Returns:
        - Analysis result dictionary or None if not found
        """
        with self.connection() as (conn, cursor):
            cursor.execute("""
                SELECT id, recording_id, analysis_type, analysis_subtype,
                       result_text, result_json, metadata_json,
                       patient_context_json, source_type, source_text,
                       created_at, updated_at
                FROM analysis_results
                WHERE id = ?
            """, (analysis_id,))

            row = cursor.fetchone()
            if row:
                return self._parse_analysis_row(row)
            return None

    def get_analysis_results_for_recording(
        self,
        recording_id: int,
        analysis_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all analysis results for a recording.

        Parameters:
        - recording_id: The recording ID
        - analysis_type: Optional filter by analysis type

        Returns:
        - List of analysis result dictionaries
        """
        with self.connection() as (conn, cursor):
            if analysis_type:
                cursor.execute("""
                    SELECT id, recording_id, analysis_type, analysis_subtype,
                           result_text, result_json, metadata_json,
                           patient_context_json, source_type, source_text,
                           created_at, updated_at
                    FROM analysis_results
                    WHERE recording_id = ? AND analysis_type = ?
                    ORDER BY created_at DESC
                """, (recording_id, analysis_type))
            else:
                cursor.execute("""
                    SELECT id, recording_id, analysis_type, analysis_subtype,
                           result_text, result_json, metadata_json,
                           patient_context_json, source_type, source_text,
                           created_at, updated_at
                    FROM analysis_results
                    WHERE recording_id = ?
                    ORDER BY created_at DESC
                """, (recording_id,))

            rows = cursor.fetchall()
            return [self._parse_analysis_row(row) for row in rows]

    def get_recent_analysis_results(
        self,
        analysis_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get recent analysis results.

        Parameters:
        - analysis_type: Optional filter by analysis type
        - limit: Maximum number of results to return

        Returns:
        - List of analysis result dictionaries
        """
        with self.connection() as (conn, cursor):
            if analysis_type:
                cursor.execute("""
                    SELECT id, recording_id, analysis_type, analysis_subtype,
                           result_text, result_json, metadata_json,
                           patient_context_json, source_type, source_text,
                           created_at, updated_at
                    FROM analysis_results
                    WHERE analysis_type = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (analysis_type, limit))
            else:
                cursor.execute("""
                    SELECT id, recording_id, analysis_type, analysis_subtype,
                           result_text, result_json, metadata_json,
                           patient_context_json, source_type, source_text,
                           created_at, updated_at
                    FROM analysis_results
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))

            rows = cursor.fetchall()
            return [self._parse_analysis_row(row) for row in rows]

    def delete_analysis_result(self, analysis_id: int) -> bool:
        """
        Delete an analysis result.

        Parameters:
        - analysis_id: The analysis result ID

        Returns:
        - True if deleted, False if not found
        """
        with self.connection() as (conn, cursor):
            cursor.execute("DELETE FROM analysis_results WHERE id = ?", (analysis_id,))
            return cursor.rowcount > 0

    def _parse_analysis_row(self, row: tuple) -> Dict[str, Any]:
        """
        Parse an analysis result database row into a dictionary.

        Parameters:
        - row: Database row tuple

        Returns:
        - Parsed dictionary with JSON fields decoded
        """
        columns = (
            'id', 'recording_id', 'analysis_type', 'analysis_subtype',
            'result_text', 'result_json', 'metadata_json',
            'patient_context_json', 'source_type', 'source_text',
            'created_at', 'updated_at'
        )
        result = dict(zip(columns, row))

        # Parse JSON fields
        for json_field in ('result_json', 'metadata_json', 'patient_context_json'):
            if result.get(json_field):
                try:
                    result[json_field] = json.loads(result[json_field])
                except (json.JSONDecodeError, TypeError):
                    pass  # Keep as string if parsing fails

        return result

    def save_analysis_with_version(
        self,
        analysis_type: str,
        result_text: str,
        recording_id: Optional[int] = None,
        analysis_subtype: Optional[str] = None,
        result_json: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        patient_context: Optional[Dict[str, Any]] = None,
        source_type: Optional[str] = None,
        source_text: Optional[str] = None,
        patient_identifier: Optional[str] = None,
        parent_analysis_id: Optional[int] = None
    ) -> Optional[int]:
        """
        Save an analysis result with version tracking.

        This extends save_analysis_result to support:
        - patient_identifier: Group analyses for same patient
        - parent_analysis_id: Link to previous version of this analysis
        - Automatic version numbering

        Parameters:
        - All parameters from save_analysis_result
        - patient_identifier: Unique patient identifier for grouping
        - parent_analysis_id: ID of previous analysis version

        Returns:
        - ID of the created analysis result, or None on failure
        """
        with self.connection() as (conn, cursor):
            # Determine version number
            version = 1
            if parent_analysis_id:
                cursor.execute(
                    "SELECT version FROM analysis_results WHERE id = ?",
                    (parent_analysis_id,)
                )
                row = cursor.fetchone()
                if row and row[0]:
                    version = row[0] + 1

            cursor.execute("""
                INSERT INTO analysis_results (
                    recording_id, analysis_type, analysis_subtype,
                    result_text, result_json, metadata_json,
                    patient_context_json, source_type, source_text,
                    version, parent_analysis_id, patient_identifier
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                recording_id,
                analysis_type,
                analysis_subtype,
                result_text,
                json.dumps(result_json) if result_json else None,
                json.dumps(metadata) if metadata else None,
                json.dumps(patient_context) if patient_context else None,
                source_type,
                source_text,
                version,
                parent_analysis_id,
                patient_identifier
            ))
            return cursor.lastrowid

    def get_analysis_versions(self, analysis_id: int) -> List[Dict[str, Any]]:
        """
        Get all versions of an analysis (version history).

        This traces back through parent_analysis_id links to find
        all previous versions of an analysis.

        Parameters:
        - analysis_id: Starting analysis ID

        Returns:
        - List of analysis versions, newest first
        """
        versions = []
        current_id = analysis_id

        with self.connection() as (conn, cursor):
            while current_id:
                cursor.execute("""
                    SELECT id, recording_id, analysis_type, analysis_subtype,
                           result_text, result_json, metadata_json,
                           patient_context_json, source_type, source_text,
                           created_at, updated_at, version, parent_analysis_id,
                           patient_identifier
                    FROM analysis_results
                    WHERE id = ?
                """, (current_id,))

                row = cursor.fetchone()
                if row:
                    result = self._parse_analysis_row_extended(row)
                    versions.append(result)
                    current_id = result.get('parent_analysis_id')
                else:
                    break

        return versions

    def get_patient_analyses(
        self,
        patient_identifier: str,
        analysis_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all analyses for a patient.

        Parameters:
        - patient_identifier: The patient identifier
        - analysis_type: Optional filter by analysis type

        Returns:
        - List of analyses for the patient, newest first
        """
        with self.connection() as (conn, cursor):
            if analysis_type:
                cursor.execute("""
                    SELECT id, recording_id, analysis_type, analysis_subtype,
                           result_text, result_json, metadata_json,
                           patient_context_json, source_type, source_text,
                           created_at, updated_at, version, parent_analysis_id,
                           patient_identifier
                    FROM analysis_results
                    WHERE patient_identifier = ? AND analysis_type = ?
                    ORDER BY created_at DESC
                """, (patient_identifier, analysis_type))
            else:
                cursor.execute("""
                    SELECT id, recording_id, analysis_type, analysis_subtype,
                           result_text, result_json, metadata_json,
                           patient_context_json, source_type, source_text,
                           created_at, updated_at, version, parent_analysis_id,
                           patient_identifier
                    FROM analysis_results
                    WHERE patient_identifier = ?
                    ORDER BY created_at DESC
                """, (patient_identifier,))

            rows = cursor.fetchall()
            return [self._parse_analysis_row_extended(row) for row in rows]

    def get_child_analyses(self, analysis_id: int) -> List[Dict[str, Any]]:
        """
        Get analyses that are newer versions of this one.

        Parameters:
        - analysis_id: The parent analysis ID

        Returns:
        - List of child analyses
        """
        with self.connection() as (conn, cursor):
            cursor.execute("""
                SELECT id, recording_id, analysis_type, analysis_subtype,
                       result_text, result_json, metadata_json,
                       patient_context_json, source_type, source_text,
                       created_at, updated_at, version, parent_analysis_id,
                       patient_identifier
                FROM analysis_results
                WHERE parent_analysis_id = ?
                ORDER BY created_at DESC
            """, (analysis_id,))

            rows = cursor.fetchall()
            return [self._parse_analysis_row_extended(row) for row in rows]

    def _parse_analysis_row_extended(self, row: tuple) -> Dict[str, Any]:
        """
        Parse an extended analysis result row with version fields.

        Parameters:
        - row: Database row tuple with version fields

        Returns:
        - Parsed dictionary with JSON fields decoded
        """
        columns = (
            'id', 'recording_id', 'analysis_type', 'analysis_subtype',
            'result_text', 'result_json', 'metadata_json',
            'patient_context_json', 'source_type', 'source_text',
            'created_at', 'updated_at', 'version', 'parent_analysis_id',
            'patient_identifier'
        )
        result = dict(zip(columns, row))

        # Parse JSON fields
        for json_field in ('result_json', 'metadata_json', 'patient_context_json'):
            if result.get(json_field):
                try:
                    result[json_field] = json.loads(result[json_field])
                except (json.JSONDecodeError, TypeError):
                    pass  # Keep as string if parsing fails

        return result


__all__ = ["AnalysisMixin"]

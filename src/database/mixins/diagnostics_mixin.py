"""
Database Diagnostics Mixin

Provides differential diagnosis and investigation operations for the Database class.
"""

import json
import logging
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class DiagnosticsMixin:
    """Mixin providing diagnostic-related database operations."""

    def get_structured_differentials(
        self,
        analysis_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get structured differential diagnoses for an analysis.

        Parameters:
        - analysis_id: The analysis result ID

        Returns:
        - List of differential diagnosis dictionaries
        """
        with self.connection() as (conn, cursor):
            cursor.execute("""
                SELECT id, analysis_id, rank, diagnosis_name, icd10_code, icd9_code,
                       confidence_score, confidence_level, reasoning,
                       supporting_findings, against_findings, is_red_flag, created_at
                FROM differential_diagnoses
                WHERE analysis_id = ?
                ORDER BY rank ASC
            """, (analysis_id,))

            rows = cursor.fetchall()
            results = []
            for row in rows:
                diff = {
                    'id': row[0],
                    'analysis_id': row[1],
                    'rank': row[2],
                    'diagnosis_name': row[3],
                    'icd10_code': row[4],
                    'icd9_code': row[5],
                    'confidence_score': row[6],
                    'confidence_level': row[7],
                    'reasoning': row[8],
                    'supporting_findings': json.loads(row[9]) if row[9] else [],
                    'against_findings': json.loads(row[10]) if row[10] else [],
                    'is_red_flag': bool(row[11]),
                    'created_at': row[12]
                }
                results.append(diff)
            return results

    def get_recommended_investigations(
        self,
        analysis_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get recommended investigations for an analysis.

        Parameters:
        - analysis_id: The analysis result ID

        Returns:
        - List of investigation dictionaries
        """
        with self.connection() as (conn, cursor):
            cursor.execute("""
                SELECT id, analysis_id, investigation_name, investigation_type,
                       priority, rationale, target_diagnoses, status,
                       ordered_at, completed_at, result_summary, created_at
                FROM recommended_investigations
                WHERE analysis_id = ?
                ORDER BY
                    CASE priority
                        WHEN 'urgent' THEN 1
                        WHEN 'routine' THEN 2
                        WHEN 'optional' THEN 3
                        ELSE 4
                    END
            """, (analysis_id,))

            rows = cursor.fetchall()
            results = []
            for row in rows:
                inv = {
                    'id': row[0],
                    'analysis_id': row[1],
                    'investigation_name': row[2],
                    'investigation_type': row[3],
                    'priority': row[4],
                    'rationale': row[5],
                    'target_diagnoses': json.loads(row[6]) if row[6] else [],
                    'status': row[7],
                    'ordered_at': row[8],
                    'completed_at': row[9],
                    'result_summary': row[10],
                    'created_at': row[11]
                }
                results.append(inv)
            return results

    def update_investigation_status(
        self,
        investigation_id: int,
        status: str,
        result_summary: Optional[str] = None
    ) -> bool:
        """
        Update the status of an investigation.

        Parameters:
        - investigation_id: The investigation ID
        - status: New status ('pending', 'ordered', 'completed', 'cancelled')
        - result_summary: Optional result summary for completed investigations

        Returns:
        - True if updated, False if not found
        """
        with self.connection() as (conn, cursor):
            if status == 'ordered':
                cursor.execute("""
                    UPDATE recommended_investigations
                    SET status = ?, ordered_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, investigation_id))
            elif status == 'completed':
                cursor.execute("""
                    UPDATE recommended_investigations
                    SET status = ?, completed_at = CURRENT_TIMESTAMP, result_summary = ?
                    WHERE id = ?
                """, (status, result_summary, investigation_id))
            else:
                cursor.execute("""
                    UPDATE recommended_investigations
                    SET status = ?
                    WHERE id = ?
                """, (status, investigation_id))

            return cursor.rowcount > 0


__all__ = ["DiagnosticsMixin"]

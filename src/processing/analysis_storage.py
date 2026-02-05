"""
Analysis Storage Module

Helper class for storing and retrieving medication and differential diagnosis analyses.
"""

from typing import Optional, Dict, List, Any
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class AnalysisStorage:
    """Helper class for managing analysis results in the database."""

    # Analysis type constants
    TYPE_MEDICATION = "medication"
    TYPE_DIFFERENTIAL = "differential"
    TYPE_COMPLIANCE = "compliance"

    def __init__(self, db=None):
        """Initialize the analysis storage helper.

        Args:
            db: Database instance. If None, uses the default database.
        """
        self._db = db

    @property
    def db(self):
        """Get the database instance."""
        if self._db is None:
            from database.database import Database
            self._db = Database()
        return self._db

    def save_medication_analysis(
        self,
        result_text: str,
        recording_id: Optional[int] = None,
        result_json: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        patient_context: Optional[Dict[str, Any]] = None,
        source_type: Optional[str] = None,
        source_text: Optional[str] = None,
        analysis_subtype: str = "comprehensive"
    ) -> Optional[int]:
        """Save a medication analysis result to the database.

        Args:
            result_text: The medication analysis result text
            recording_id: Optional link to a recording
            result_json: Optional structured JSON result
            metadata: Optional metadata (medication count, interaction count, etc.)
            patient_context: Optional patient context used for the analysis
            source_type: Source of analysis ('transcript', 'soap', 'custom')
            source_text: The input text that was analyzed
            analysis_subtype: Subtype of analysis (e.g., 'comprehensive', 'interactions')

        Returns:
            ID of the created analysis result, or None on failure
        """
        try:
            analysis_id = self.db.save_analysis_result(
                analysis_type=self.TYPE_MEDICATION,
                result_text=result_text,
                recording_id=recording_id,
                analysis_subtype=analysis_subtype,
                result_json=result_json,
                metadata=metadata,
                patient_context=patient_context,
                source_type=source_type,
                source_text=source_text
            )
            logger.info(f"Saved medication analysis (id={analysis_id}) for recording_id={recording_id}")
            return analysis_id
        except Exception as e:
            logger.error(f"Failed to save medication analysis: {e}")
            return None

    def save_differential_diagnosis(
        self,
        result_text: str,
        recording_id: Optional[int] = None,
        result_json: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        patient_context: Optional[Dict[str, Any]] = None,
        source_type: Optional[str] = None,
        source_text: Optional[str] = None,
        analysis_subtype: str = "comprehensive"
    ) -> Optional[int]:
        """Save a differential diagnosis result to the database.

        Args:
            result_text: The differential diagnosis result text
            recording_id: Optional link to a recording
            result_json: Optional structured JSON result
            metadata: Optional metadata (differential count, has_red_flags, etc.)
            patient_context: Optional patient context used for the analysis
            source_type: Source of analysis ('transcript', 'soap', 'custom')
            source_text: The input text that was analyzed
            analysis_subtype: Subtype of analysis (e.g., 'comprehensive', 'focused')

        Returns:
            ID of the created analysis result, or None on failure
        """
        try:
            analysis_id = self.db.save_analysis_result(
                analysis_type=self.TYPE_DIFFERENTIAL,
                result_text=result_text,
                recording_id=recording_id,
                analysis_subtype=analysis_subtype,
                result_json=result_json,
                metadata=metadata,
                patient_context=patient_context,
                source_type=source_type,
                source_text=source_text
            )
            logger.info(f"Saved differential diagnosis (id={analysis_id}) for recording_id={recording_id}")
            return analysis_id
        except Exception as e:
            logger.error(f"Failed to save differential diagnosis: {e}")
            return None

    def save_compliance_analysis(
        self,
        result_text: str,
        recording_id: Optional[int] = None,
        result_json: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        patient_context: Optional[Dict[str, Any]] = None,
        source_type: Optional[str] = None,
        source_text: Optional[str] = None,
        analysis_subtype: str = "guidelines"
    ) -> Optional[int]:
        """Save a compliance analysis result to the database.

        Args:
            result_text: The compliance analysis result text
            recording_id: Optional link to a recording
            result_json: Optional structured JSON result
            metadata: Optional metadata (overall_score, gap_count, etc.)
            patient_context: Optional patient context used for the analysis
            source_type: Source of analysis ('transcript', 'soap', 'custom')
            source_text: The input text that was analyzed
            analysis_subtype: Subtype of analysis (e.g., 'guidelines')

        Returns:
            ID of the created analysis result, or None on failure
        """
        try:
            analysis_id = self.db.save_analysis_result(
                analysis_type=self.TYPE_COMPLIANCE,
                result_text=result_text,
                recording_id=recording_id,
                analysis_subtype=analysis_subtype,
                result_json=result_json,
                metadata=metadata,
                patient_context=patient_context,
                source_type=source_type,
                source_text=source_text
            )
            logger.info(f"Saved compliance analysis (id={analysis_id}) for recording_id={recording_id}")
            return analysis_id
        except Exception as e:
            logger.error(f"Failed to save compliance analysis: {e}")
            return None

    def get_analyses_for_recording(
        self,
        recording_id: int
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Get all analyses for a recording, organized by type.

        Args:
            recording_id: The recording ID

        Returns:
            Dictionary with 'medication', 'differential', and 'compliance' keys,
            each containing the most recent analysis of that type, or None if not found.
        """
        result = {
            "medication": None,
            "differential": None,
            "compliance": None
        }

        try:
            # Get medication analysis (most recent)
            medication_analyses = self.db.get_analysis_results_for_recording(
                recording_id=recording_id,
                analysis_type=self.TYPE_MEDICATION
            )
            if medication_analyses:
                result["medication"] = medication_analyses[0]  # Most recent

            # Get differential diagnosis (most recent)
            differential_analyses = self.db.get_analysis_results_for_recording(
                recording_id=recording_id,
                analysis_type=self.TYPE_DIFFERENTIAL
            )
            if differential_analyses:
                result["differential"] = differential_analyses[0]  # Most recent

            # Get compliance analysis (most recent)
            compliance_analyses = self.db.get_analysis_results_for_recording(
                recording_id=recording_id,
                analysis_type=self.TYPE_COMPLIANCE
            )
            if compliance_analyses:
                result["compliance"] = compliance_analyses[0]  # Most recent

            return result

        except Exception as e:
            logger.error(f"Failed to get analyses for recording {recording_id}: {e}")
            return result

    def get_medication_analysis(
        self,
        recording_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent medication analysis for a recording.

        Args:
            recording_id: The recording ID

        Returns:
            The most recent medication analysis or None
        """
        try:
            analyses = self.db.get_analysis_results_for_recording(
                recording_id=recording_id,
                analysis_type=self.TYPE_MEDICATION
            )
            return analyses[0] if analyses else None
        except Exception as e:
            logger.error(f"Failed to get medication analysis for recording {recording_id}: {e}")
            return None

    def get_differential_diagnosis(
        self,
        recording_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent differential diagnosis for a recording.

        Args:
            recording_id: The recording ID

        Returns:
            The most recent differential diagnosis or None
        """
        try:
            analyses = self.db.get_analysis_results_for_recording(
                recording_id=recording_id,
                analysis_type=self.TYPE_DIFFERENTIAL
            )
            return analyses[0] if analyses else None
        except Exception as e:
            logger.error(f"Failed to get differential diagnosis for recording {recording_id}: {e}")
            return None

    def has_medication_analysis(self, recording_id: int) -> bool:
        """Check if a recording has a medication analysis.

        Args:
            recording_id: The recording ID

        Returns:
            True if medication analysis exists, False otherwise
        """
        return self.get_medication_analysis(recording_id) is not None

    def has_differential_diagnosis(self, recording_id: int) -> bool:
        """Check if a recording has a differential diagnosis.

        Args:
            recording_id: The recording ID

        Returns:
            True if differential diagnosis exists, False otherwise
        """
        return self.get_differential_diagnosis(recording_id) is not None

    def get_compliance_analysis(
        self,
        recording_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent compliance analysis for a recording.

        Args:
            recording_id: The recording ID

        Returns:
            The most recent compliance analysis or None
        """
        try:
            analyses = self.db.get_analysis_results_for_recording(
                recording_id=recording_id,
                analysis_type=self.TYPE_COMPLIANCE
            )
            return analyses[0] if analyses else None
        except Exception as e:
            logger.error(f"Failed to get compliance analysis for recording {recording_id}: {e}")
            return None

    def has_compliance_analysis(self, recording_id: int) -> bool:
        """Check if a recording has a compliance analysis.

        Args:
            recording_id: The recording ID

        Returns:
            True if compliance analysis exists, False otherwise
        """
        return self.get_compliance_analysis(recording_id) is not None

    def get_recent_medication_analyses(
        self,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent medication analyses across all recordings.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of medication analyses, newest first
        """
        try:
            return self.db.get_recent_analysis_results(
                analysis_type=self.TYPE_MEDICATION,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Failed to get recent medication analyses: {e}")
            return []

    def get_recent_differential_diagnoses(
        self,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent differential diagnoses across all recordings.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of differential diagnoses, newest first
        """
        try:
            return self.db.get_recent_analysis_results(
                analysis_type=self.TYPE_DIFFERENTIAL,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Failed to get recent differential diagnoses: {e}")
            return []


# Singleton instance
_analysis_storage: Optional[AnalysisStorage] = None


def get_analysis_storage() -> AnalysisStorage:
    """Get the singleton AnalysisStorage instance.

    Returns:
        AnalysisStorage instance
    """
    global _analysis_storage
    if _analysis_storage is None:
        _analysis_storage = AnalysisStorage()
    return _analysis_storage


__all__ = ["AnalysisStorage", "get_analysis_storage"]

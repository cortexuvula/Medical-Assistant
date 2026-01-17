"""
Diagnostic Results Database Module

Provides database save/load functionality for diagnostic results.
"""

import json
from tkinter import messagebox
from typing import Dict, List, Optional, TYPE_CHECKING
from utils.structured_logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    import tkinter as tk
    from database.database import Database


class DatabaseMixin:
    """Mixin for database operations on diagnostic results."""

    parent: "tk.Tk"
    dialog: Optional["tk.Toplevel"]
    analysis_text: str
    source: str
    metadata: Dict
    recording_id: Optional[int]
    source_text: str
    _db: Optional["Database"]

    def _get_database(self) -> "Database":
        """Get or create database connection."""
        if self._db is None:
            from database.database import Database
            self._db = Database()
        return self._db

    def _save_to_database(self):
        """Save the diagnostic analysis to the database, including structured data."""
        try:
            db = self._get_database()

            # Parse structured data from analysis
            parsed_data = self._parse_diagnostic_analysis(self.analysis_text)

            # Prepare metadata dict with ICD validation results if available
            metadata_dict = dict(self.metadata) if self.metadata else {}

            # Pre-compute differential_count for efficient history display
            # This avoids re-parsing the full result_text when loading history
            structured_diffs = self.metadata.get('structured_differentials', []) if self.metadata else []
            metadata_dict['differential_count'] = len(structured_diffs) if structured_diffs else self._count_differentials_from_text(self.analysis_text)

            # Save to database
            analysis_id = db.save_analysis_result(
                analysis_type="diagnostic",
                result_text=self.analysis_text,
                recording_id=self.recording_id,
                analysis_subtype="differential",
                result_json=parsed_data,  # Pass dict, not JSON string
                metadata=metadata_dict if metadata_dict else None,
                patient_context=None,  # Diagnostic doesn't have patient context yet
                source_type=self.source,
                source_text=self.source_text[:5000] if self.source_text else None
            )

            if analysis_id:
                saved_items = {'differentials': 0, 'investigations': 0, 'pearls': 0}

                # Save structured differentials if available in metadata
                structured_diffs = self.metadata.get('structured_differentials', [])
                if structured_diffs:
                    saved_items['differentials'] = self._save_structured_differentials(
                        db, analysis_id, structured_diffs
                    )

                # Save structured investigations
                structured_invs = self.metadata.get('structured_investigations', [])
                if structured_invs:
                    saved_items['investigations'] = self._save_structured_investigations(
                        db, analysis_id, structured_invs
                    )

                # Save clinical pearls
                structured_pearls = self.metadata.get('structured_clinical_pearls', [])
                if structured_pearls:
                    saved_items['pearls'] = self._save_clinical_pearls(
                        db, analysis_id, structured_pearls
                    )

                # Save extracted clinical data
                extracted_data = self.metadata.get('extracted_clinical_data')
                if extracted_data:
                    self._save_extracted_clinical_data(db, analysis_id, extracted_data)

                # Build info message
                info_parts = [f"Diagnostic analysis saved (ID: {analysis_id})"]
                if self.recording_id:
                    info_parts.append(f"Linked to recording #{self.recording_id}")
                diff_count = self.metadata.get('differential_count', 0)
                if diff_count:
                    info_parts.append(f"Contains {diff_count} differential diagnoses")
                if saved_items['differentials'] > 0:
                    info_parts.append(f"Saved {saved_items['differentials']} structured differentials")
                if saved_items['investigations'] > 0:
                    info_parts.append(f"Saved {saved_items['investigations']} investigations")

                messagebox.showinfo(
                    "Saved",
                    "\n".join(info_parts),
                    parent=self.dialog if self.dialog else self.parent
                )
            else:
                messagebox.showerror(
                    "Save Failed",
                    "Failed to save analysis to database.",
                    parent=self.dialog if self.dialog else self.parent
                )

        except Exception as e:
            logger.error(f"Error saving to database: {str(e)}")
            messagebox.showerror(
                "Save Error",
                f"Failed to save to database: {str(e)}",
                parent=self.dialog if self.dialog else self.parent
            )

    def _save_structured_differentials(
        self, db: "Database", analysis_id: int, differentials: List[Dict]
    ) -> int:
        """Save structured differential diagnoses to database.

        Args:
            db: Database connection
            analysis_id: ID of the parent analysis
            differentials: List of structured differential dictionaries

        Returns:
            Number of differentials saved
        """
        saved_count = 0
        try:
            conn = db._get_connection()
            for diff in differentials:
                conn.execute(
                    """
                    INSERT INTO differential_diagnoses (
                        analysis_id, rank, diagnosis_name, icd10_code, icd9_code,
                        confidence_score, confidence_level, reasoning,
                        supporting_findings, against_findings, is_red_flag
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        analysis_id,
                        diff.get('rank', 0),
                        diff.get('diagnosis_name', ''),
                        diff.get('icd10_code'),
                        diff.get('icd9_code'),
                        diff.get('confidence_score'),
                        diff.get('confidence_level'),
                        diff.get('reasoning', ''),
                        json.dumps(diff.get('supporting_findings', [])),
                        json.dumps(diff.get('against_findings', [])),
                        diff.get('is_red_flag', False)
                    )
                )
                saved_count += 1
            conn.commit()
        except Exception as e:
            logger.warning(f"Error saving structured differentials: {e}")
        return saved_count

    def _save_structured_investigations(
        self, db: "Database", analysis_id: int, investigations: List[Dict]
    ) -> int:
        """Save recommended investigations to database.

        Args:
            db: Database connection
            analysis_id: ID of the parent analysis
            investigations: List of investigation dictionaries

        Returns:
            Number of investigations saved
        """
        saved_count = 0
        try:
            conn = db._get_connection()
            for inv in investigations:
                conn.execute(
                    """
                    INSERT INTO recommended_investigations (
                        analysis_id, investigation_name, investigation_type,
                        priority, rationale, status
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        analysis_id,
                        inv.get('investigation_name', ''),
                        inv.get('investigation_type', 'other'),
                        inv.get('priority', 'routine'),
                        inv.get('rationale', ''),
                        inv.get('status', 'pending')
                    )
                )
                saved_count += 1
            conn.commit()
        except Exception as e:
            logger.warning(f"Error saving investigations: {e}")
        return saved_count

    def _save_clinical_pearls(
        self, db: "Database", analysis_id: int, pearls: List[Dict]
    ) -> int:
        """Save clinical pearls to database.

        Args:
            db: Database connection
            analysis_id: ID of the parent analysis
            pearls: List of clinical pearl dictionaries

        Returns:
            Number of pearls saved
        """
        saved_count = 0
        try:
            conn = db._get_connection()
            for pearl in pearls:
                conn.execute(
                    """
                    INSERT INTO clinical_pearls (
                        analysis_id, pearl_text, category
                    ) VALUES (?, ?, ?)
                    """,
                    (
                        analysis_id,
                        pearl.get('pearl_text', ''),
                        pearl.get('category', 'diagnostic')
                    )
                )
                saved_count += 1
            conn.commit()
        except Exception as e:
            logger.warning(f"Error saving clinical pearls: {e}")
        return saved_count

    def _save_extracted_clinical_data(
        self, db: "Database", analysis_id: int, extracted_data: Dict
    ):
        """Save extracted clinical data to database.

        Args:
            db: Database connection
            analysis_id: ID of the parent analysis
            extracted_data: Dictionary of extracted clinical data
        """
        try:
            conn = db._get_connection()
            for data_type, data in extracted_data.items():
                if data:  # Only save non-empty data
                    conn.execute(
                        """
                        INSERT INTO extracted_clinical_data (
                            analysis_id, data_type, data_json
                        ) VALUES (?, ?, ?)
                        """,
                        (analysis_id, data_type, json.dumps(data))
                    )
            conn.commit()
        except Exception as e:
            logger.warning(f"Error saving extracted clinical data: {e}")


__all__ = ["DatabaseMixin"]

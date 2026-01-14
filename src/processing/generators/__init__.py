"""
Document Generators Package

Provides document generation functionality through composable mixins.
The main DocumentGenerators class combines all generation capabilities.

Usage:
    from processing.generators import DocumentGenerators

    generators = DocumentGenerators(app)
    generators.create_soap_note()
    generators.create_referral()
    generators.create_letter()
    generators.create_diagnostic_analysis()
    generators.analyze_medications()
    generators.extract_clinical_data()
    generators.manage_workflow()
"""

from typing import TYPE_CHECKING, List, Dict, Any, Callable

from processing.generators.base import StreamingMixin
from processing.generators.soap import SOAPGeneratorMixin
from processing.generators.letter import LetterGeneratorMixin
from processing.generators.referral import ReferralGeneratorMixin
from processing.generators.diagnostic import DiagnosticGeneratorMixin
from processing.generators.medication import MedicationGeneratorMixin
from processing.generators.extraction import DataExtractionGeneratorMixin
from processing.generators.workflow import WorkflowGeneratorMixin

if TYPE_CHECKING:
    from core.app import MedicalAssistantApp


class DocumentGenerators(
    StreamingMixin,
    SOAPGeneratorMixin,
    LetterGeneratorMixin,
    ReferralGeneratorMixin,
    DiagnosticGeneratorMixin,
    MedicationGeneratorMixin,
    DataExtractionGeneratorMixin,
    WorkflowGeneratorMixin
):
    """Manages medical document generation functionality.

    This class combines all document generation capabilities through mixins:
    - SOAP note generation
    - Letter generation
    - Referral generation
    - Diagnostic analysis
    - Medication analysis
    - Clinical data extraction
    - Workflow management

    Batch processing methods are delegated to BatchProcessor.
    """

    def __init__(self, parent_app: "MedicalAssistantApp"):
        """Initialize the document generators.

        Args:
            parent_app: The main application instance
        """
        self.app = parent_app
        self._batch_processor = None

    @property
    def batch_processor(self):
        """Get or create the batch processor instance."""
        if self._batch_processor is None:
            from processing.batch_processor import BatchProcessor
            self._batch_processor = BatchProcessor(self.app)
        return self._batch_processor

    def process_batch_recordings(self, recording_ids: List[int], options: Dict[str, Any],
                                 on_complete: Callable = None, on_progress: Callable = None) -> None:
        """Process multiple recordings in batch. Delegates to BatchProcessor."""
        self.batch_processor.process_batch_recordings(recording_ids, options, on_complete, on_progress)

    def process_batch_files(self, file_paths: List[str], options: Dict[str, Any],
                            on_complete: Callable = None, on_progress: Callable = None) -> None:
        """Process multiple audio files in batch. Delegates to BatchProcessor."""
        self.batch_processor.process_batch_files(file_paths, options, on_complete, on_progress)


__all__ = [
    "DocumentGenerators",
    # Mixins for direct access if needed
    "StreamingMixin",
    "SOAPGeneratorMixin",
    "LetterGeneratorMixin",
    "ReferralGeneratorMixin",
    "DiagnosticGeneratorMixin",
    "MedicationGeneratorMixin",
    "DataExtractionGeneratorMixin",
    "WorkflowGeneratorMixin",
]

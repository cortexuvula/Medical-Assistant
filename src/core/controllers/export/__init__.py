"""
Export Handlers Package

Provides document export functionality extracted from ProcessingController.
"""

from core.controllers.export.document_constants import DOCUMENT_TYPES, TAB_DOCUMENT_MAP
from core.controllers.export.export_helpers import (
    get_active_document_info,
    get_export_file_path,
    get_text_widgets,
    create_fhir_config
)
from core.controllers.export.pdf_exporter_handler import PDFExporterHandler
from core.controllers.export.word_exporter_handler import WordExporterHandler
from core.controllers.export.fhir_exporter_handler import FHIRExporterHandler

__all__ = [
    "DOCUMENT_TYPES",
    "TAB_DOCUMENT_MAP",
    "get_active_document_info",
    "get_export_file_path",
    "get_text_widgets",
    "create_fhir_config",
    "PDFExporterHandler",
    "WordExporterHandler",
    "FHIRExporterHandler"
]

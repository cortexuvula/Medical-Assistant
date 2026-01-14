"""
Export Helpers

Common helper functions for document export operations.
Eliminates duplicated boilerplate across export methods.
"""

import tkinter as tk
from tkinter import filedialog
from datetime import datetime
from typing import TYPE_CHECKING, List, Tuple, Optional, Dict, Any

from settings import settings_manager
from core.controllers.export.document_constants import (
    DOCUMENT_TYPES,
    get_document_display_name,
    get_document_type_for_tab
)

if TYPE_CHECKING:
    from core.app import MedicalDictationApp


def get_text_widgets(app: 'MedicalDictationApp') -> List[tk.Widget]:
    """Get list of text widgets in tab order.

    Args:
        app: Reference to the main application

    Returns:
        List of text widgets matching tab order
    """
    return [
        app.transcript_text,
        app.soap_text,
        app.referral_text,
        app.letter_text,
        app.chat_text
    ]


def get_active_document_info(app: 'MedicalDictationApp') -> Tuple[Optional[str], Optional[str], int]:
    """Get information about the currently active document.

    Args:
        app: Reference to the main application

    Returns:
        Tuple of (document_type, content, tab_index) or (None, None, -1) if invalid
    """
    selected_tab = app.notebook.index('current')

    if selected_tab >= len(DOCUMENT_TYPES):
        return None, None, -1

    doc_type = get_document_type_for_tab(selected_tab)
    text_widgets = get_text_widgets(app)
    content = text_widgets[selected_tab].get("1.0", tk.END).strip()

    return doc_type, content, selected_tab


def get_export_file_path(
    doc_type: str,
    extension: str = ".pdf",
    title: str = None,
    filetypes: List[Tuple[str, str]] = None
) -> Optional[str]:
    """Show save file dialog and return selected path.

    Args:
        doc_type: Document type for default filename
        extension: File extension (default: .pdf)
        title: Dialog title (auto-generated if None)
        filetypes: List of (description, pattern) tuples

    Returns:
        Selected file path or None if cancelled
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    display_name = get_document_display_name(doc_type)

    default_filename = f"{doc_type}_{timestamp}{extension}"

    if title is None:
        title = f"Export {display_name} as {extension.upper().strip('.')}"

    if filetypes is None:
        ext_upper = extension.upper().strip('.')
        filetypes = [(f"{ext_upper} files", f"*{extension}"), ("All files", "*.*")]

    file_path = filedialog.asksaveasfilename(
        defaultextension=extension,
        filetypes=filetypes,
        initialfile=default_filename,
        title=title
    )

    return file_path if file_path else None


def create_fhir_config() -> 'FHIRExportConfig':
    """Create a FHIR export configuration from current settings.

    Returns:
        Configured FHIRExportConfig instance
    """
    from exporters.fhir_config import FHIRExportConfig

    clinic_name = settings_manager.get("clinic_name", "")
    doctor_name = settings_manager.get("doctor_name", "")

    return FHIRExportConfig(
        organization_name=clinic_name,
        practitioner_name=doctor_name,
        include_patient=False,
        include_practitioner=bool(doctor_name),
        include_organization=bool(clinic_name)
    )


def validate_export_content(doc_type: str, content: str) -> Tuple[bool, str]:
    """Validate that content exists for export.

    Args:
        doc_type: Document type being exported
        content: Document content

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not content:
        display_name = get_document_display_name(doc_type)
        return False, f"No {display_name.lower()} content to export."
    return True, ""


def prepare_export_content(doc_type: str, content: str) -> Dict[str, Any]:
    """Prepare content dictionary for export handlers.

    Args:
        doc_type: Document type
        content: Raw document content

    Returns:
        Dictionary with standardized export content
    """
    display_name = get_document_display_name(doc_type)

    return {
        "document_type": doc_type,
        "content": content,
        "title": display_name,
        "timestamp": datetime.now().isoformat()
    }


__all__ = [
    "get_text_widgets",
    "get_active_document_info",
    "get_export_file_path",
    "create_fhir_config",
    "validate_export_content",
    "prepare_export_content"
]

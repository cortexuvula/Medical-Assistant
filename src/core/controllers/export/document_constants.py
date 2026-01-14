"""
Document Constants

Centralized constants for document types and tab mappings.
Eliminates the repeated doc_types list throughout the codebase.
"""

from typing import List, Dict

# Document types in tab order
DOCUMENT_TYPES: List[str] = ['transcript', 'soap_note', 'referral', 'letter', 'chat']

# Map tab index to document type
TAB_DOCUMENT_MAP: Dict[int, str] = {
    0: 'transcript',
    1: 'soap_note',
    2: 'referral',
    3: 'letter',
    4: 'chat'
}

# Human-readable document names
DOCUMENT_DISPLAY_NAMES: Dict[str, str] = {
    'transcript': 'Transcript',
    'soap_note': 'SOAP Note',
    'referral': 'Referral',
    'letter': 'Letter',
    'chat': 'Chat'
}

# Document types that support SOAP-style structured export
SOAP_EXPORT_TYPES = {'soap_note'}

# Document types that use referral/letter style formatting
CORRESPONDENCE_TYPES = {'referral', 'letter'}


def get_document_display_name(doc_type: str) -> str:
    """Get human-readable display name for a document type.

    Args:
        doc_type: Internal document type identifier

    Returns:
        Human-readable display name
    """
    return DOCUMENT_DISPLAY_NAMES.get(doc_type, doc_type.replace('_', ' ').title())


def get_document_type_for_tab(tab_index: int) -> str:
    """Get document type for a given tab index.

    Args:
        tab_index: Index of the selected notebook tab

    Returns:
        Document type string or 'unknown' if invalid
    """
    return TAB_DOCUMENT_MAP.get(tab_index, 'unknown')


__all__ = [
    "DOCUMENT_TYPES",
    "TAB_DOCUMENT_MAP",
    "DOCUMENT_DISPLAY_NAMES",
    "SOAP_EXPORT_TYPES",
    "CORRESPONDENCE_TYPES",
    "get_document_display_name",
    "get_document_type_for_tab"
]

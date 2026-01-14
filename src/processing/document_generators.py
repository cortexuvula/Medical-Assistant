"""
Document Generators Module

Handles the generation of medical documents including SOAP notes, referrals,
letters, and diagnostic analyses from transcripts using AI processing.

This module has been refactored into the generators/ package for better
maintainability. This file re-exports the main class for backward compatibility.

For new code, prefer importing directly from the package:
    from processing.generators import DocumentGenerators

Batch processing functionality is in processing/batch_processor.py.
"""

# Re-export DocumentGenerators for backward compatibility
from processing.generators import DocumentGenerators

__all__ = ["DocumentGenerators"]

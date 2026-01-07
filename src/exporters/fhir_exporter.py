"""
FHIR Exporter Module

Exports clinical documents in FHIR R4 format for import into EHR/EMR systems.
Supports SOAP notes, referrals, and other clinical documents.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union

from exporters.base_exporter import BaseExporter
from exporters.fhir_config import FHIRExportConfig
from exporters.fhir_resources import FHIRResourceBuilder

logger = logging.getLogger(__name__)


class FHIRExporter(BaseExporter):
    """FHIR R4 document exporter.

    Exports clinical documents as FHIR resources for healthcare
    interoperability with EHR/EMR systems.
    """

    def __init__(self, config: Optional[FHIRExportConfig] = None):
        """Initialize the FHIR exporter.

        Args:
            config: Optional FHIR export configuration
        """
        super().__init__()
        self.config = config or FHIRExportConfig()
        self.resource_builder = FHIRResourceBuilder(self.config)

    def export(
        self,
        content: Dict[str, Any],
        output_path: Path
    ) -> bool:
        """Export content to a FHIR JSON file.

        Args:
            content: Dictionary containing the document content.
                Expected keys:
                - soap_data: Dict with SOAP sections OR content key
                - patient_info: Optional patient information
                - practitioner_info: Optional practitioner information
                - organization_info: Optional organization information
                - title: Optional document title
                - export_type: "bundle" (default) or "document_reference"

        Returns:
            True if export was successful, False otherwise.
        """
        try:
            # Ensure directory exists
            if not self._ensure_directory(output_path):
                return False

            # Generate FHIR JSON
            fhir_json = self.export_to_string(content)

            # Write to file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(fhir_json)

            logger.info(f"FHIR document exported to: {output_path}")
            return True

        except Exception as e:
            self._last_error = f"Failed to export FHIR document: {str(e)}"
            logger.error(self._last_error, exc_info=True)
            return False

    def export_to_string(self, content: Dict[str, Any]) -> str:
        """Export content as FHIR JSON string.

        Args:
            content: Dictionary containing the document content.

        Returns:
            FHIR JSON string
        """
        export_type = content.get("export_type", "bundle")

        if export_type == "document_reference":
            return self._export_as_document_reference(content)
        else:
            return self._export_as_bundle(content)

    def _export_as_bundle(self, content: Dict[str, Any]) -> str:
        """Export as FHIR Bundle with Composition.

        Args:
            content: Document content dictionary

        Returns:
            FHIR Bundle JSON string
        """
        # Extract content components
        soap_data = content.get("soap_data", {})

        # If soap_data is a string, convert to dict with content key
        if isinstance(soap_data, str):
            soap_data = {"content": soap_data}

        patient_info = content.get("patient_info")
        practitioner_info = content.get("practitioner_info")
        organization_info = content.get("organization_info")
        title = content.get("title", "SOAP Note")

        # Create FHIR Bundle
        bundle = self.resource_builder.create_soap_bundle(
            soap_data=soap_data,
            patient_info=patient_info,
            practitioner_info=practitioner_info,
            organization_info=organization_info,
            title=title
        )

        # Convert to JSON
        return bundle.model_dump_json(indent=2, exclude_none=True)

    def _export_as_document_reference(self, content: Dict[str, Any]) -> str:
        """Export as simple FHIR DocumentReference.

        Args:
            content: Document content dictionary

        Returns:
            FHIR DocumentReference JSON string
        """
        # Extract content
        soap_data = content.get("soap_data", {})

        # Get plain text content
        if isinstance(soap_data, str):
            text_content = soap_data
        elif "content" in soap_data:
            text_content = soap_data["content"]
        else:
            # Combine sections into text
            sections = []
            for section in ["subjective", "objective", "assessment", "plan"]:
                if section in soap_data and soap_data[section]:
                    sections.append(f"{section.upper()}:\n{soap_data[section]}")
            text_content = "\n\n".join(sections)

        title = content.get("title", "Clinical Document")
        document_type = content.get("document_type", "soap_note")

        # Create DocumentReference
        doc_ref = self.resource_builder.create_document_reference(
            content=text_content,
            document_type=document_type,
            title=title,
            patient_ref=None,  # Could add patient reference
            practitioner_ref=None  # Could add practitioner reference
        )

        return doc_ref.model_dump_json(indent=2, exclude_none=True)

    def export_soap_note(
        self,
        soap_text: str,
        title: str = "SOAP Note",
        patient_info: Optional[Dict[str, Any]] = None,
        practitioner_info: Optional[Dict[str, Any]] = None,
        organization_info: Optional[Dict[str, Any]] = None,
        output_path: Optional[Path] = None,
        as_document_reference: bool = False
    ) -> Union[str, bool]:
        """Export a SOAP note as FHIR.

        Convenience method for exporting SOAP notes.

        Args:
            soap_text: Full SOAP note text
            title: Document title
            patient_info: Optional patient information
            practitioner_info: Optional practitioner information
            organization_info: Optional organization information
            output_path: Optional path to save file (returns JSON string if None)
            as_document_reference: If True, export as simple DocumentReference

        Returns:
            FHIR JSON string if no output_path, True/False if saving to file
        """
        content = {
            "soap_data": soap_text,
            "title": title,
            "patient_info": patient_info,
            "practitioner_info": practitioner_info,
            "organization_info": organization_info,
            "export_type": "document_reference" if as_document_reference else "bundle"
        }

        if output_path:
            return self.export(content, output_path)
        else:
            return self.export_to_string(content)

    def export_referral(
        self,
        referral_text: str,
        title: str = "Referral Letter",
        output_path: Optional[Path] = None
    ) -> Union[str, bool]:
        """Export a referral letter as FHIR.

        Args:
            referral_text: Referral letter text
            title: Document title
            output_path: Optional path to save file

        Returns:
            FHIR JSON string if no output_path, True/False if saving to file
        """
        content = {
            "soap_data": referral_text,
            "title": title,
            "document_type": "referral",
            "export_type": "document_reference"
        }

        if output_path:
            return self.export(content, output_path)
        else:
            return self.export_to_string(content)

    def export_letter(
        self,
        letter_text: str,
        title: str = "Medical Letter",
        output_path: Optional[Path] = None
    ) -> Union[str, bool]:
        """Export a medical letter as FHIR.

        Args:
            letter_text: Letter text
            title: Document title
            output_path: Optional path to save file

        Returns:
            FHIR JSON string if no output_path, True/False if saving to file
        """
        content = {
            "soap_data": letter_text,
            "title": title,
            "document_type": "letter",
            "export_type": "document_reference"
        }

        if output_path:
            return self.export(content, output_path)
        else:
            return self.export_to_string(content)

    def copy_soap_to_clipboard(
        self,
        soap_text: str,
        title: str = "SOAP Note",
        as_document_reference: bool = False
    ) -> bool:
        """Copy SOAP note as FHIR JSON to clipboard.

        Args:
            soap_text: Full SOAP note text
            title: Document title
            as_document_reference: If True, export as simple DocumentReference

        Returns:
            True if successful, False otherwise
        """
        content = {
            "soap_data": soap_text,
            "title": title,
            "export_type": "document_reference" if as_document_reference else "bundle"
        }

        return self.export_to_clipboard(content)


def get_fhir_exporter(config: Optional[FHIRExportConfig] = None) -> FHIRExporter:
    """Get a FHIR exporter instance.

    Factory function for creating FHIR exporter with optional config.

    Args:
        config: Optional FHIR export configuration

    Returns:
        FHIRExporter instance
    """
    return FHIRExporter(config)

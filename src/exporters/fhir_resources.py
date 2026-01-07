"""
FHIR Resource Builders Module

Creates FHIR R4 resources for clinical documents including
Composition, DocumentReference, Bundle, Patient, Practitioner, and Organization.
"""

import logging
import uuid
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from html import escape as html_escape

from fhir.resources.composition import Composition, CompositionSection
from fhir.resources.documentreference import DocumentReference, DocumentReferenceContent
from fhir.resources.bundle import Bundle, BundleEntry
from fhir.resources.patient import Patient
from fhir.resources.practitioner import Practitioner
from fhir.resources.organization import Organization
from fhir.resources.narrative import Narrative
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.identifier import Identifier
from fhir.resources.humanname import HumanName
from fhir.resources.attachment import Attachment
from fhir.resources.reference import Reference

from exporters.fhir_config import (
    FHIRExportConfig,
    FHIR_SYSTEMS,
    get_section_code,
    get_document_type_code,
    normalize_section_name,
    generate_resource_id,
    SECTION_TITLE_PATTERNS,
)

logger = logging.getLogger(__name__)


class FHIRResourceBuilder:
    """Builder class for creating FHIR R4 resources.

    Provides methods to create various FHIR resources from clinical data
    for export to EHR/EMR systems.
    """

    def __init__(self, config: Optional[FHIRExportConfig] = None):
        """Initialize the resource builder.

        Args:
            config: Optional FHIR export configuration
        """
        self.config = config or FHIRExportConfig()
        self._resource_index = 0

    def _next_id(self, resource_type: str) -> str:
        """Generate next unique resource ID."""
        self._resource_index += 1
        return generate_resource_id(resource_type, self._resource_index)

    def _create_narrative(self, text: str, status: str = "generated") -> Narrative:
        """Create a FHIR Narrative element with HTML div.

        Args:
            text: Plain text content
            status: Narrative status (generated, extensions, additional, empty)

        Returns:
            FHIR Narrative resource
        """
        # Convert plain text to simple HTML div
        escaped_text = html_escape(text)
        # Convert newlines to <br/> for better formatting
        html_text = escaped_text.replace("\n", "<br/>")
        div = f'<div xmlns="http://www.w3.org/1999/xhtml">{html_text}</div>'

        return Narrative(status=status, div=div)

    def _create_codeable_concept(
        self,
        code: str,
        display: str,
        system: str
    ) -> CodeableConcept:
        """Create a FHIR CodeableConcept.

        Args:
            code: Code value
            display: Human-readable display text
            system: Code system URL

        Returns:
            FHIR CodeableConcept
        """
        coding = Coding(code=code, display=display, system=system)
        return CodeableConcept(coding=[coding], text=display)

    def create_patient(
        self,
        patient_info: Optional[Dict[str, Any]] = None
    ) -> Patient:
        """Create a FHIR Patient resource.

        Args:
            patient_info: Optional patient information dict with keys:
                - name: Patient name (string)
                - id: Patient identifier
                - dob: Date of birth (YYYY-MM-DD)
                - gender: male/female/other/unknown

        Returns:
            FHIR Patient resource
        """
        patient_info = patient_info or {}

        patient_id = self._next_id("patient")

        # Build name
        name_parts = []
        if patient_info.get("name"):
            name_str = patient_info["name"]
            parts = name_str.split()
            given = parts[:-1] if len(parts) > 1 else parts
            family = parts[-1] if len(parts) > 1 else ""
            name_parts.append(HumanName(
                use="official",
                family=family,
                given=given if given else None
            ))

        # Build identifiers
        identifiers = []
        if patient_info.get("id"):
            identifiers.append(Identifier(
                use="usual",
                value=patient_info["id"]
            ))

        patient = Patient(
            id=patient_id,
            identifier=identifiers if identifiers else None,
            name=name_parts if name_parts else None,
            gender=patient_info.get("gender"),
            birthDate=patient_info.get("dob")
        )

        return patient

    def create_practitioner(
        self,
        practitioner_info: Optional[Dict[str, Any]] = None
    ) -> Practitioner:
        """Create a FHIR Practitioner resource.

        Args:
            practitioner_info: Optional practitioner information dict with keys:
                - name: Practitioner name
                - id: Practitioner identifier
                - qualification: Credentials/title

        Returns:
            FHIR Practitioner resource
        """
        practitioner_info = practitioner_info or {}

        # Use config values as defaults
        name = practitioner_info.get("name") or self.config.practitioner_name
        pract_id = practitioner_info.get("id") or self.config.practitioner_id

        resource_id = self._next_id("practitioner")

        # Build name
        name_parts = []
        if name:
            parts = name.split()
            given = parts[:-1] if len(parts) > 1 else parts
            family = parts[-1] if len(parts) > 1 else ""
            name_parts.append(HumanName(
                use="official",
                family=family,
                given=given if given else None,
                suffix=[practitioner_info.get("qualification")] if practitioner_info.get("qualification") else None
            ))

        # Build identifiers
        identifiers = []
        if pract_id:
            identifiers.append(Identifier(
                use="official",
                value=pract_id
            ))

        practitioner = Practitioner(
            id=resource_id,
            identifier=identifiers if identifiers else None,
            name=name_parts if name_parts else None
        )

        return practitioner

    def create_organization(
        self,
        organization_info: Optional[Dict[str, Any]] = None
    ) -> Organization:
        """Create a FHIR Organization resource.

        Args:
            organization_info: Optional organization information dict with keys:
                - name: Organization name
                - id: Organization identifier

        Returns:
            FHIR Organization resource
        """
        organization_info = organization_info or {}

        # Use config values as defaults
        name = organization_info.get("name") or self.config.organization_name
        org_id = organization_info.get("id") or self.config.organization_id

        resource_id = self._next_id("organization")

        # Build identifiers
        identifiers = []
        if org_id:
            identifiers.append(Identifier(
                use="official",
                value=org_id
            ))

        organization = Organization(
            id=resource_id,
            identifier=identifiers if identifiers else None,
            name=name if name else None
        )

        return organization

    def create_composition_section(
        self,
        title: str,
        content: str,
        section_type: str = "assessment"
    ) -> CompositionSection:
        """Create a FHIR Composition section.

        Args:
            title: Section title (e.g., "Subjective", "Objective")
            content: Section text content
            section_type: Type of section for LOINC coding

        Returns:
            FHIR CompositionSection
        """
        # Get LOINC code for this section type
        code_info = get_section_code(section_type)

        section = CompositionSection(
            title=title,
            code=self._create_codeable_concept(
                code_info["code"],
                code_info["display"],
                code_info["system"]
            ),
            text=self._create_narrative(content)
        )

        return section

    def parse_soap_sections(self, soap_text: str) -> Dict[str, str]:
        """Parse SOAP note text into sections.

        Args:
            soap_text: Full SOAP note text

        Returns:
            Dictionary with keys: subjective, objective, assessment, plan
        """
        sections = {
            "subjective": "",
            "objective": "",
            "assessment": "",
            "plan": ""
        }

        # Split by common section headers
        current_section = None
        current_content = []

        lines = soap_text.split("\n")

        for line in lines:
            line_lower = line.lower().strip()

            # Check if this line is a section header
            found_section = None
            for section_name, patterns in SECTION_TITLE_PATTERNS.items():
                for pattern in patterns:
                    # Check for exact match or pattern at start of line
                    if line_lower == pattern or line_lower.startswith(pattern + ":") or line_lower.startswith(pattern + " "):
                        found_section = section_name
                        break
                if found_section:
                    break

            if found_section:
                # Save previous section content
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = found_section
                current_content = []
                # Check if there's content after the header on same line
                for pattern in SECTION_TITLE_PATTERNS[found_section]:
                    if line_lower.startswith(pattern + ":"):
                        remainder = line[len(pattern)+1:].strip()
                        if remainder:
                            current_content.append(remainder)
                        break
                    elif line_lower.startswith(pattern + " "):
                        remainder = line[len(pattern)+1:].strip()
                        if remainder:
                            current_content.append(remainder)
                        break
            elif current_section:
                current_content.append(line)

        # Save last section
        if current_section and current_content:
            sections[current_section] = "\n".join(current_content).strip()

        # If no sections found, put everything in subjective
        if not any(sections.values()):
            sections["subjective"] = soap_text

        return sections

    def create_composition(
        self,
        soap_data: Dict[str, str],
        title: str = "SOAP Note",
        document_type: str = "soap_note",
        patient_ref: Optional[str] = None,
        practitioner_ref: Optional[str] = None
    ) -> Composition:
        """Create a FHIR Composition resource for a SOAP note.

        Args:
            soap_data: Dictionary with SOAP sections (subjective, objective, assessment, plan)
                      OR a single "content" key with full SOAP text to parse
            title: Document title
            document_type: Type of document for LOINC coding
            patient_ref: Optional reference to Patient resource
            practitioner_ref: Optional reference to Practitioner resource

        Returns:
            FHIR Composition resource
        """
        resource_id = self._next_id("composition")

        # Parse sections if full content provided
        if "content" in soap_data and len(soap_data) == 1:
            soap_data = self.parse_soap_sections(soap_data["content"])

        # Get document type code
        type_code = get_document_type_code(document_type)

        # Build sections
        sections = []
        section_order = ["subjective", "objective", "assessment", "plan"]

        for section_name in section_order:
            content = soap_data.get(section_name, "")
            if content:
                sections.append(self.create_composition_section(
                    title=section_name.title(),
                    content=content,
                    section_type=section_name
                ))

        # Build author reference
        author_refs = []
        if practitioner_ref:
            author_refs.append(Reference(reference=practitioner_ref))

        # Build subject reference
        subject_ref = None
        if patient_ref:
            subject_ref = Reference(reference=patient_ref)

        composition = Composition(
            id=resource_id,
            status="final",
            type=self._create_codeable_concept(
                type_code["code"],
                type_code["display"],
                type_code["system"]
            ),
            date=datetime.now(timezone.utc).isoformat(),
            title=title,
            section=sections if sections else None,
            author=author_refs if author_refs else None,
            subject=subject_ref
        )

        return composition

    def create_document_reference(
        self,
        content: str,
        document_type: str = "soap_note",
        title: str = "Clinical Document",
        patient_ref: Optional[str] = None,
        practitioner_ref: Optional[str] = None
    ) -> DocumentReference:
        """Create a FHIR DocumentReference resource.

        A simpler alternative to Composition for document export.

        Args:
            content: Document content (plain text)
            document_type: Type of document for LOINC coding
            title: Document title
            patient_ref: Optional reference to Patient resource
            practitioner_ref: Optional reference to Practitioner resource

        Returns:
            FHIR DocumentReference resource
        """
        import base64

        resource_id = self._next_id("documentreference")

        # Get document type code
        type_code = get_document_type_code(document_type)

        # Encode content as base64
        content_bytes = content.encode("utf-8")
        content_b64 = base64.b64encode(content_bytes).decode("ascii")

        # Create attachment
        attachment = Attachment(
            contentType="text/plain",
            data=content_b64,
            title=title
        )

        # Create content element
        doc_content = DocumentReferenceContent(attachment=attachment)

        # Build author reference
        author_refs = []
        if practitioner_ref:
            author_refs.append(Reference(reference=practitioner_ref))

        # Build subject reference
        subject_ref = None
        if patient_ref:
            subject_ref = Reference(reference=patient_ref)

        doc_ref = DocumentReference(
            id=resource_id,
            status="current",
            type=self._create_codeable_concept(
                type_code["code"],
                type_code["display"],
                type_code["system"]
            ),
            date=datetime.now(timezone.utc).isoformat(),
            description=title,
            content=[doc_content],
            author=author_refs if author_refs else None,
            subject=subject_ref
        )

        return doc_ref

    def create_bundle(
        self,
        resources: List[Any],
        bundle_type: str = "document"
    ) -> Bundle:
        """Create a FHIR Bundle containing multiple resources.

        Args:
            resources: List of FHIR resources to include
            bundle_type: Bundle type (document, collection, transaction, etc.)

        Returns:
            FHIR Bundle resource
        """
        bundle_id = self._next_id("bundle")

        entries = []
        for resource in resources:
            # Create fullUrl using urn:uuid format
            full_url = f"urn:uuid:{resource.id}"
            entry = BundleEntry(
                fullUrl=full_url,
                resource=resource
            )
            entries.append(entry)

        bundle = Bundle(
            id=bundle_id,
            type=bundle_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            entry=entries if entries else None
        )

        return bundle

    def create_soap_bundle(
        self,
        soap_data: Dict[str, str],
        patient_info: Optional[Dict[str, Any]] = None,
        practitioner_info: Optional[Dict[str, Any]] = None,
        organization_info: Optional[Dict[str, Any]] = None,
        title: str = "SOAP Note"
    ) -> Bundle:
        """Create a complete FHIR Bundle for a SOAP note.

        This is the main entry point for creating a full FHIR document
        that can be imported into EHR/EMR systems.

        Args:
            soap_data: Dictionary with SOAP sections or "content" key
            patient_info: Optional patient information
            practitioner_info: Optional practitioner information
            organization_info: Optional organization information
            title: Document title

        Returns:
            FHIR Bundle containing all resources
        """
        resources = []
        patient_ref = None
        practitioner_ref = None

        # Create Patient only if actual patient info is provided
        # (empty patient resources cause validation issues)
        if patient_info:
            patient = self.create_patient(patient_info)
            resources.append(patient)
            patient_ref = f"urn:uuid:{patient.id}"

        # Create Practitioner if info provided or config says to include
        if practitioner_info or (self.config.include_practitioner and self.config.practitioner_name):
            practitioner = self.create_practitioner(practitioner_info)
            resources.append(practitioner)
            practitioner_ref = f"urn:uuid:{practitioner.id}"

        # Create Organization if info provided or config says to include
        if organization_info or (self.config.include_organization and self.config.organization_name):
            organization = self.create_organization(organization_info)
            resources.append(organization)

        # Create Composition (main document)
        composition = self.create_composition(
            soap_data=soap_data,
            title=title,
            document_type="soap_note",
            patient_ref=patient_ref,
            practitioner_ref=practitioner_ref
        )
        # Insert Composition at beginning (required for document bundle)
        resources.insert(0, composition)

        return self.create_bundle(resources, bundle_type="document")

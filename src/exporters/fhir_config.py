"""
FHIR Configuration Module

Contains FHIR R4 constants, LOINC codes, and configuration for healthcare
interoperability exports.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from datetime import datetime


@dataclass
class FHIRExportConfig:
    """Configuration for FHIR exports.

    Attributes:
        fhir_version: FHIR version to use (R4 recommended)
        organization_name: Name of the healthcare organization
        organization_id: Unique identifier for the organization
        practitioner_name: Name of the practitioner/author
        practitioner_id: Unique identifier for the practitioner
        include_patient: Whether to include Patient resource
        include_practitioner: Whether to include Practitioner resource
        include_organization: Whether to include Organization resource
    """
    fhir_version: str = "R4"
    organization_name: str = ""
    organization_id: str = ""
    practitioner_name: str = ""
    practitioner_id: str = ""
    include_patient: bool = True
    include_practitioner: bool = True
    include_organization: bool = True


# FHIR System URLs
FHIR_SYSTEMS = {
    "loinc": "http://loinc.org",
    "snomed": "http://snomed.info/sct",
    "icd9": "http://hl7.org/fhir/sid/icd-9-cm",
    "icd10": "http://hl7.org/fhir/sid/icd-10-cm",
    "document_type": "http://loinc.org",
    "composition_status": "http://hl7.org/fhir/composition-status",
}

# LOINC codes for document types
DOCUMENT_TYPE_CODES = {
    "soap_note": {
        "code": "34108-1",
        "display": "Outpatient Note",
        "system": FHIR_SYSTEMS["loinc"]
    },
    "referral": {
        "code": "57133-1",
        "display": "Referral note",
        "system": FHIR_SYSTEMS["loinc"]
    },
    "letter": {
        "code": "68610-2",
        "display": "Letter",
        "system": FHIR_SYSTEMS["loinc"]
    },
    "transcript": {
        "code": "11488-4",
        "display": "Consultation note",
        "system": FHIR_SYSTEMS["loinc"]
    },
    "progress_note": {
        "code": "11506-3",
        "display": "Progress note",
        "system": FHIR_SYSTEMS["loinc"]
    },
}

# LOINC codes for SOAP note sections
SOAP_SECTION_CODES = {
    "subjective": {
        "code": "10154-3",
        "display": "Chief complaint Narrative - Reported",
        "system": FHIR_SYSTEMS["loinc"]
    },
    "history_of_present_illness": {
        "code": "10164-2",
        "display": "History of present illness Narrative",
        "system": FHIR_SYSTEMS["loinc"]
    },
    "objective": {
        "code": "29545-1",
        "display": "Physical findings Narrative",
        "system": FHIR_SYSTEMS["loinc"]
    },
    "vital_signs": {
        "code": "8716-3",
        "display": "Vital signs",
        "system": FHIR_SYSTEMS["loinc"]
    },
    "assessment": {
        "code": "51848-0",
        "display": "Evaluation note",
        "system": FHIR_SYSTEMS["loinc"]
    },
    "plan": {
        "code": "18776-5",
        "display": "Plan of care note",
        "system": FHIR_SYSTEMS["loinc"]
    },
    "medications": {
        "code": "10160-0",
        "display": "History of Medication use Narrative",
        "system": FHIR_SYSTEMS["loinc"]
    },
    "allergies": {
        "code": "48765-2",
        "display": "Allergies and adverse reactions Document",
        "system": FHIR_SYSTEMS["loinc"]
    },
    "synopsis": {
        "code": "77401-8",
        "display": "Clinical summary Document",
        "system": FHIR_SYSTEMS["loinc"]
    },
}

# Section title variations to match during parsing
SECTION_TITLE_PATTERNS = {
    "subjective": [
        "subjective", "s:", "s.", "chief complaint", "cc:", "cc.",
        "history of present illness", "hpi", "history"
    ],
    "objective": [
        "objective", "o:", "o.", "physical exam", "pe:", "pe.",
        "examination", "physical findings", "vitals"
    ],
    "assessment": [
        "assessment", "a:", "a.", "impression", "diagnoses",
        "diagnosis", "clinical impression", "assessment and plan"
    ],
    "plan": [
        "plan", "p:", "p.", "treatment plan", "recommendations",
        "management", "follow-up", "follow up"
    ],
}


def get_section_code(section_name: str) -> Dict[str, str]:
    """Get LOINC code information for a SOAP section.

    Args:
        section_name: Name of the section (subjective, objective, assessment, plan)

    Returns:
        Dictionary with code, display, and system keys
    """
    normalized = section_name.lower().strip()
    return SOAP_SECTION_CODES.get(normalized, SOAP_SECTION_CODES["assessment"])


def get_document_type_code(doc_type: str) -> Dict[str, str]:
    """Get LOINC code information for a document type.

    Args:
        doc_type: Type of document (soap_note, referral, letter, etc.)

    Returns:
        Dictionary with code, display, and system keys
    """
    normalized = doc_type.lower().strip().replace(" ", "_")
    return DOCUMENT_TYPE_CODES.get(normalized, DOCUMENT_TYPE_CODES["soap_note"])


def normalize_section_name(title: str) -> Optional[str]:
    """Normalize a section title to a standard SOAP section name.

    Args:
        title: Section title to normalize

    Returns:
        Normalized section name (subjective, objective, assessment, plan)
        or None if not recognized
    """
    title_lower = title.lower().strip()

    for section, patterns in SECTION_TITLE_PATTERNS.items():
        for pattern in patterns:
            if pattern in title_lower:
                return section

    return None


def generate_resource_id(resource_type: str, index: int = 0) -> str:
    """Generate a unique resource ID.

    Args:
        resource_type: Type of FHIR resource
        index: Optional index for multiple resources of same type

    Returns:
        Unique resource ID string
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{resource_type.lower()}-{timestamp}-{index:03d}"

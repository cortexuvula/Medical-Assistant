"""
SOAP QA - Medication comparison between transcript and SOAP note.

Compares medications extracted from the original transcript against
medications found in the generated SOAP note. Flags medications present
in the transcript but missing from the SOAP note as potential omissions.
"""

from typing import List, Set

from utils.structured_logging import get_logger

logger = get_logger(__name__)


def compare_medications(transcript: str, soap_note: str) -> List[str]:
    """Compare medications in transcript vs SOAP note, returning warnings.

    Uses the existing MedicalNERExtractor to extract medication entities
    from both texts, then flags medications present in the transcript
    but absent from the SOAP note.

    Args:
        transcript: The original transcript text
        soap_note: The generated SOAP note text

    Returns:
        List of warning strings for medications in transcript but not in SOAP.
        Returns empty list on any failure (never raises).
    """
    if not transcript or not soap_note:
        return []

    try:
        from rag.medical_ner import get_medical_ner_extractor

        extractor = get_medical_ner_extractor()

        # Extract medications from both texts
        transcript_entities = extractor._extract_medications(transcript)
        soap_entities = extractor._extract_medications(soap_note)

        # Build normalized name sets
        transcript_meds: Set[str] = set()
        transcript_med_text: dict = {}  # normalized -> original text for display
        for entity in transcript_entities:
            name = (entity.normalized_name or entity.text).lower()
            transcript_meds.add(name)
            if name not in transcript_med_text:
                transcript_med_text[name] = entity.text

        soap_meds: Set[str] = set()
        for entity in soap_entities:
            name = (entity.normalized_name or entity.text).lower()
            soap_meds.add(name)

        # Find medications in transcript but not in SOAP (by normalized name)
        missing = transcript_meds - soap_meds

        # Substring fallback: check if the normalized name appears
        # anywhere in the raw SOAP text (catches "lisinopril 20mg daily"
        # matching "lisinopril" even if NER didn't extract it separately)
        soap_lower = soap_note.lower()
        still_missing = set()
        for med in missing:
            if med in soap_lower:
                continue
            orig_text = transcript_med_text.get(med, med)
            if orig_text.lower() in soap_lower:
                continue
            still_missing.add(med)

        # Build warning strings
        warnings = []
        for med in sorted(still_missing):
            orig = transcript_med_text.get(med, med)
            if orig.lower() != med:
                warnings.append(
                    f'"{orig}" ({med}) mentioned in transcript '
                    f'but not found in SOAP note'
                )
            else:
                warnings.append(
                    f'"{med}" mentioned in transcript '
                    f'but not found in SOAP note'
                )

        if warnings:
            logger.info(f"SOAP QA: {len(warnings)} medication omission(s) detected")
        else:
            logger.debug("SOAP QA: No medication omissions detected")

        return warnings

    except Exception as e:
        logger.error(f"SOAP QA comparison failed: {e}", exc_info=True)
        return []

"""
Diagnostic Results Parser Module

Provides analysis text parsing functionality.
"""

import re
from typing import Dict, List, Any
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class ParserMixin:
    """Mixin for parsing diagnostic analysis text."""

    analysis_text: str

    def _parse_diagnostic_analysis(self, analysis_text: str) -> Dict:
        """Parse diagnostic analysis text into structured data.

        Args:
            analysis_text: The raw analysis text

        Returns:
            Dictionary with structured diagnostic data
        """
        data = {
            "clinical_findings": "",
            "differentials": [],
            "red_flags": [],
            "investigations": [],
            "clinical_pearls": []
        }

        # Split into sections
        lines = analysis_text.split('\n')
        current_section = None
        current_content = []

        for line in lines:
            line = line.strip()

            # Check for section headers
            if "CLINICAL SUMMARY:" in line:
                if current_section and current_content:
                    self._save_section_data(data, current_section, current_content)
                current_section = "clinical_findings"
                current_content = []
            elif "DIFFERENTIAL DIAGNOSES:" in line:
                if current_section and current_content:
                    self._save_section_data(data, current_section, current_content)
                current_section = "differentials"
                current_content = []
            elif "RED FLAGS:" in line:
                if current_section and current_content:
                    self._save_section_data(data, current_section, current_content)
                current_section = "red_flags"
                current_content = []
            elif "RECOMMENDED INVESTIGATIONS:" in line:
                if current_section and current_content:
                    self._save_section_data(data, current_section, current_content)
                current_section = "investigations"
                current_content = []
            elif "CLINICAL PEARLS:" in line:
                if current_section and current_content:
                    self._save_section_data(data, current_section, current_content)
                current_section = "clinical_pearls"
                current_content = []
            elif line and current_section:
                current_content.append(line)

        # Save last section
        if current_section and current_content:
            self._save_section_data(data, current_section, current_content)

        return data

    def _save_section_data(self, data: Dict, section: str, content: List[str]):
        """Save parsed section data to the data dictionary.

        Args:
            data: Data dictionary to update
            section: Section name
            content: List of content lines
        """
        if section == "clinical_findings":
            data["clinical_findings"] = "\n".join(content)
        elif section == "differentials":
            # Parse differentials with their details
            for line in content:
                if line and (line[0].isdigit() or line.startswith("-")):
                    # Extract diagnosis name and ICD codes (both ICD-10 and ICD-9)
                    # ICD-10 pattern: letter + 2 digits + optional decimal
                    # ICD-9 pattern: 3 digits + decimal
                    icd10_match = re.search(r'\(([A-Z]\d{2}(?:\.\d{1,2})?)\)', line)
                    icd9_match = re.search(r'\((\d{3}\.\d{1,2})\)', line)

                    icd10_code = icd10_match.group(1) if icd10_match else ""
                    icd9_code = icd9_match.group(1) if icd9_match else ""

                    # Extract confidence level
                    confidence_match = re.search(r'\[(HIGH|MEDIUM|LOW)\]', line, re.IGNORECASE)
                    confidence = confidence_match.group(1).upper() if confidence_match else ""

                    # Extract diagnosis name (before any ICD codes or confidence markers)
                    diag_line = line
                    for pattern in [r'\([A-Z]\d{2}(?:\.\d{1,2})?\)', r'\(\d{3}\.\d{1,2}\)', r'\[(HIGH|MEDIUM|LOW)\]']:
                        diag_line = re.sub(pattern, '', diag_line, flags=re.IGNORECASE)
                    diagnosis = diag_line.strip(" -0123456789.:")

                    data["differentials"].append({
                        "diagnosis": diagnosis,
                        "icd10_code": icd10_code,
                        "icd9_code": icd9_code,
                        "icd_code": icd10_code or icd9_code,  # Backward compatibility
                        "confidence": confidence,
                        "probability": confidence,  # Alias for confidence
                        "evidence": [],
                        "tests": []
                    })
        elif section == "red_flags":
            data["red_flags"] = [line.strip("- ") for line in content if line.strip()]
        elif section == "investigations":
            data["investigations"] = [line.strip("- ") for line in content if line.strip()]
        elif section == "clinical_pearls":
            data["clinical_pearls"] = [line.strip("- ") for line in content if line.strip()]

    def _extract_red_flags_from_text(self, analysis: str) -> List[str]:
        """Extract red flags from analysis text.

        Args:
            analysis: The analysis text

        Returns:
            List of red flag strings
        """
        red_flags = []
        if 'RED FLAGS:' not in analysis:
            return red_flags

        try:
            red_section = analysis.split('RED FLAGS:')[1]
            # Find the end of the section
            for end_marker in ['RECOMMENDED INVESTIGATIONS:', 'CLINICAL PEARLS:',
                               'MEDICATION CONSIDERATIONS:', '\n\n\n']:
                if end_marker in red_section:
                    red_section = red_section.split(end_marker)[0]
                    break

            # Parse each line
            for line in red_section.split('\n'):
                line = line.strip()
                if line and line not in ['None', '-', 'N/A', '']:
                    # Remove bullet points and numbers
                    cleaned = re.sub(r'^[\d\.\-\•\*]+\s*', '', line).strip()
                    if cleaned and len(cleaned) > 3:
                        red_flags.append(cleaned)
        except Exception as e:
            logger.warning(f"Error extracting red flags: {e}")

        return red_flags

    def _extract_investigations_from_text(self, analysis: str) -> List[Dict[str, Any]]:
        """Extract recommended investigations from analysis text.

        Args:
            analysis: The analysis text

        Returns:
            List of investigation dictionaries
        """
        investigations = []
        if 'RECOMMENDED INVESTIGATIONS:' not in analysis:
            return investigations

        try:
            inv_section = analysis.split('RECOMMENDED INVESTIGATIONS:')[1]
            # Find the end of the section
            for end_marker in ['CLINICAL PEARLS:', 'MEDICATION CONSIDERATIONS:', '\n\n\n']:
                if end_marker in inv_section:
                    inv_section = inv_section.split(end_marker)[0]
                    break

            # Parse each line
            for line in inv_section.split('\n'):
                line = line.strip()
                # Skip empty lines and common non-content markers
                if not line or line in ['None', '-', 'N/A', '', 'o', 'O', '', '*']:
                    continue

                # Remove bullet points, numbers, and common list markers
                # Extended pattern: digits, dots, dashes, bullets, asterisks, 'o'/'O' as bullets
                cleaned = re.sub(r'^[\d\.\-\•\*oO]+[\.\)\:\s]*', '', line).strip()

                # Skip if cleaned text is empty, too short, or just punctuation/whitespace
                if not cleaned or len(cleaned) < 5:
                    continue

                # Skip lines that are just markers or don't contain alphabetic content
                if not any(c.isalpha() for c in cleaned):
                    continue

                # Determine priority based on keywords
                priority = 'routine'
                if any(kw in cleaned.lower() for kw in ['urgent', 'stat', 'immediately', 'emergent']):
                    priority = 'urgent'
                elif any(kw in cleaned.lower() for kw in ['priority', 'soon', 'within 24']):
                    priority = 'high'

                investigations.append({
                    'investigation_name': cleaned,
                    'priority': priority,
                    'status': 'pending',
                    'rationale': ''
                })
        except Exception as e:
            logger.warning(f"Error extracting investigations: {e}")

        return investigations

    def _extract_icd_codes(self) -> Dict[str, List[str]]:
        """Extract all ICD codes from the analysis text.

        Returns:
            Dictionary with 'icd10' and 'icd9' lists of codes
        """
        # ICD-10 pattern: letter + 2 digits + optional decimal (e.g., J18.9, K21.0)
        icd10_pattern = r'\b[A-Z]\d{2}(?:\.\d{1,2})?\b'
        # ICD-9 pattern: 3 digits + decimal (e.g., 486.0, 530.81)
        icd9_pattern = r'\b\d{3}\.\d{1,2}\b'

        icd10_codes = list(set(re.findall(icd10_pattern, self.analysis_text)))
        icd9_codes = list(set(re.findall(icd9_pattern, self.analysis_text)))

        return {
            'icd10': sorted(icd10_codes),
            'icd9': sorted(icd9_codes)
        }

    def _count_differentials_from_text(self, result_text: str) -> int:
        """Count differential diagnoses from result text.

        This is a fallback when structured_differentials is not available.
        Matches the counting logic used in diagnostic_history_dialog.py.
        """
        if not result_text or 'DIFFERENTIAL DIAGNOSES:' not in result_text:
            return 0

        try:
            diff_section = result_text.split('DIFFERENTIAL DIAGNOSES:')[1]
            # Find the end of the section
            for end_marker in ['RED FLAGS:', 'RECOMMENDED INVESTIGATIONS:', 'CLINICAL PEARLS:', 'MEDICATION CONSIDERATIONS:']:
                if end_marker in diff_section:
                    diff_section = diff_section.split(end_marker)[0]
                    break
            # Count numbered or bulleted items
            numbered = re.findall(r'^\s*\d+\.', diff_section, re.MULTILINE)
            bulleted = re.findall(r'^\s*[-]', diff_section, re.MULTILINE)
            return len(numbered) or len(bulleted) or 0
        except Exception:
            return 0


__all__ = ["ParserMixin"]

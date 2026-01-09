"""
Diagnostic agent for analyzing symptoms and suggesting differential diagnoses.

Supports both ICD-9 and ICD-10 diagnostic codes with validation.
"""

import logging
from typing import Optional, List, Dict, Any, TYPE_CHECKING
import re

from .base import BaseAgent
from .models import AgentConfig, AgentTask, AgentResponse

# Import ICD validator
try:
    from utils.icd_validator import (
        ICDValidator, ICDValidationResult, ICDCodeSystem,
        extract_icd_codes, get_validator
    )
    ICD_VALIDATION_AVAILABLE = True
except ImportError:
    ICD_VALIDATION_AVAILABLE = False
    logger.warning("ICD validator not available, code validation will be skipped")

if TYPE_CHECKING:
    from .ai_caller import AICallerProtocol


logger = logging.getLogger(__name__)


class DiagnosticAgent(BaseAgent):
    """Agent specialized in diagnostic analysis and differential diagnosis generation."""
    
    # Default configuration for diagnostic agent
    DEFAULT_CONFIG = AgentConfig(
        name="DiagnosticAgent",
        description="Analyzes clinical findings and suggests differential diagnoses with ICD code validation",
        system_prompt="""You are a medical diagnostic assistant with expertise in differential diagnosis.

Your role is to:
1. Analyze symptoms, signs, and clinical findings
2. Generate a comprehensive differential diagnosis list with ICD codes
3. Rank diagnoses by likelihood based on the clinical presentation
4. Suggest appropriate investigations to narrow the differential
5. Highlight any red flags or concerning features

Guidelines:
- Always provide multiple diagnostic possibilities
- Include BOTH ICD-10 and ICD-9 codes for each differential diagnosis
  - ICD-10 format: Letter + 2 digits + optional decimal (e.g., J06.9, E11.65)
  - ICD-9 format: 3 digits + optional decimal (e.g., 346.10, 250.00)
- Consider common conditions before rare ones (think horses, not zebras)
- Include both benign and serious conditions when appropriate
- Never provide definitive diagnoses - only suggestions for clinical consideration
- Always recommend appropriate follow-up and investigations
- Flag any emergency conditions that need immediate attention

Format your response as:
1. CLINICAL SUMMARY: Brief overview of key findings
2. DIFFERENTIAL DIAGNOSES: Listed by likelihood with ICD codes and brief reasoning
   Example: 1. Migraine without aura (ICD-10: G43.009, ICD-9: 346.10) - Classic presentation with family history
3. RED FLAGS: Any concerning features requiring urgent attention
4. RECOMMENDED INVESTIGATIONS: Tests to help narrow the differential
5. CLINICAL PEARLS: Key points to remember for this presentation""",
        model="gpt-4",
        temperature=0.1,  # Lower temperature for more consistent diagnostic reasoning
        max_tokens=600
    )
    
    def __init__(self, config: Optional[AgentConfig] = None, ai_caller: Optional['AICallerProtocol'] = None):
        """
        Initialize the diagnostic agent.

        Args:
            config: Optional custom configuration. Uses default if not provided.
            ai_caller: Optional AI caller for dependency injection.
        """
        super().__init__(config or self.DEFAULT_CONFIG, ai_caller=ai_caller)
        
    def execute(self, task: AgentTask) -> AgentResponse:
        """
        Analyze clinical findings and generate differential diagnoses.

        Args:
            task: Task containing clinical findings in input_data['clinical_findings']
                 or input_data['soap_note']

        Returns:
            AgentResponse with diagnostic analysis including validated ICD codes
        """
        try:
            # Extract clinical findings from task
            clinical_findings = task.input_data.get('clinical_findings', '')
            soap_note = task.input_data.get('soap_note', '')

            if not clinical_findings and not soap_note:
                return AgentResponse(
                    result="",
                    success=False,
                    error="No clinical findings or SOAP note provided"
                )

            # Use SOAP note if clinical findings not directly provided
            if not clinical_findings:
                clinical_findings = self._extract_clinical_findings(soap_note)

            # Build the diagnostic prompt
            prompt = self._build_diagnostic_prompt(clinical_findings, task.context)

            # Call AI for diagnostic analysis
            analysis = self._call_ai(prompt)

            # Structure the diagnostic response
            structured_analysis = self._structure_diagnostic_response(analysis)

            # Extract and validate ICD codes
            icd_validation_results = self._validate_icd_codes(structured_analysis)

            # Extract key information for metadata
            differential_count = len(self._extract_diagnoses(structured_analysis))
            has_red_flags = "RED FLAGS:" in structured_analysis and \
                           len(structured_analysis.split("RED FLAGS:")[1].split("\n")[0].strip()) > 0

            # Add validation warnings to the analysis if needed
            validation_warnings = self._get_validation_warnings(icd_validation_results)
            if validation_warnings:
                structured_analysis = self._append_validation_warnings(
                    structured_analysis, validation_warnings
                )

            # Create response
            response = AgentResponse(
                result=structured_analysis,
                thoughts=f"Generated {differential_count} differential diagnoses based on clinical findings",
                success=True,
                metadata={
                    'differential_count': differential_count,
                    'has_red_flags': has_red_flags,
                    'model_used': self.config.model,
                    'clinical_findings_length': len(clinical_findings),
                    'icd_codes_found': len(icd_validation_results),
                    'icd_codes_valid': sum(1 for r in icd_validation_results if r.get('is_valid', False)),
                    'icd_codes_invalid': sum(1 for r in icd_validation_results if not r.get('is_valid', True)),
                    'icd_validation_results': icd_validation_results
                }
            )

            # Add to history
            self.add_to_history(task, response)

            return response

        except Exception as e:
            logger.error(f"Error in diagnostic analysis: {e}")
            return AgentResponse(
                result="",
                success=False,
                error=str(e)
            )

    def _validate_icd_codes(self, analysis: str) -> List[Dict[str, Any]]:
        """
        Extract and validate ICD codes from the analysis.

        Args:
            analysis: The diagnostic analysis text

        Returns:
            List of validation result dictionaries
        """
        if not ICD_VALIDATION_AVAILABLE:
            return []

        validation_results = []
        validator = get_validator()

        # Extract ICD codes from the text
        codes = extract_icd_codes(analysis)

        for code in codes:
            result = validator.validate(code)
            validation_results.append({
                'code': result.code,
                'is_valid': result.is_valid,
                'code_system': result.code_system.value if result.code_system else 'Unknown',
                'description': result.description,
                'warning': result.warning
            })

        return validation_results

    def _get_validation_warnings(self, validation_results: List[Dict[str, Any]]) -> List[str]:
        """
        Extract validation warnings from results.

        Args:
            validation_results: List of validation result dictionaries

        Returns:
            List of warning messages for invalid or unknown codes
        """
        warnings = []

        for result in validation_results:
            if not result.get('is_valid', True):
                warnings.append(f"Invalid ICD code format: {result['code']}")
            elif result.get('warning'):
                # Code has valid format but not in known database
                warnings.append(f"Unverified code {result['code']}: {result['warning']}")

        return warnings

    def _append_validation_warnings(self, analysis: str, warnings: List[str]) -> str:
        """
        Append ICD validation warnings to the analysis.

        Args:
            analysis: Original analysis text
            warnings: List of warning messages

        Returns:
            Analysis with appended warnings section
        """
        if not warnings:
            return analysis

        warning_section = "\n\nICD CODE VALIDATION NOTES:\n"
        warning_section += "\n".join(f"- {w}" for w in warnings)
        warning_section += "\n\nPlease verify any unrecognized codes with official ICD references."

        return analysis + warning_section
    
    def _extract_clinical_findings(self, soap_note: str) -> str:
        """Extract relevant clinical findings from a SOAP note."""
        # Extract key sections from SOAP note
        findings = []
        soap_upper = soap_note.upper()
        
        # Extract subjective findings
        if "SUBJECTIVE:" in soap_upper:
            start_idx = soap_note.upper().find("SUBJECTIVE:") + len("SUBJECTIVE:")
            # Find the end (start of next section or end of string)
            end_idx = len(soap_note)
            for next_section in ["OBJECTIVE:", "ASSESSMENT:", "PLAN:"]:
                next_idx = soap_upper.find(next_section, start_idx)
                if next_idx != -1 and next_idx < end_idx:
                    end_idx = next_idx
            subjective = soap_note[start_idx:end_idx].strip()
            if subjective:
                findings.append(f"Patient Complaints: {subjective}")
        
        # Extract objective findings
        if "OBJECTIVE:" in soap_upper:
            start_idx = soap_note.upper().find("OBJECTIVE:") + len("OBJECTIVE:")
            # Find the end (start of next section or end of string)
            end_idx = len(soap_note)
            for next_section in ["ASSESSMENT:", "PLAN:"]:
                next_idx = soap_upper.find(next_section, start_idx)
                if next_idx != -1 and next_idx < end_idx:
                    end_idx = next_idx
            objective = soap_note[start_idx:end_idx].strip()
            if objective:
                findings.append(f"Examination Findings: {objective}")
        
        # Extract current assessment if available
        if "ASSESSMENT:" in soap_upper:
            start_idx = soap_note.upper().find("ASSESSMENT:") + len("ASSESSMENT:")
            # Find the end (start of next section or end of string)
            end_idx = len(soap_note)
            next_idx = soap_upper.find("PLAN:", start_idx)
            if next_idx != -1:
                end_idx = next_idx
            assessment = soap_note[start_idx:end_idx].strip()
            if assessment:
                findings.append(f"Current Assessment: {assessment}")
        
        return "\n\n".join(findings)
    
    def _build_diagnostic_prompt(self, clinical_findings: str, context: Optional[str] = None) -> str:
        """Build the prompt for diagnostic analysis."""
        prompt_parts = []
        
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")
        
        prompt_parts.append("Please analyze the following clinical findings and provide a comprehensive diagnostic assessment:\n")
        prompt_parts.append(f"Clinical Findings:\n{clinical_findings}\n")
        prompt_parts.append("\nProvide your diagnostic analysis following the specified format.")
        
        return "\n".join(prompt_parts)
    
    def _structure_diagnostic_response(self, analysis: str) -> str:
        """Ensure the diagnostic response follows the expected structure."""
        # Check if response already has the expected structure
        required_sections = ["CLINICAL SUMMARY:", "DIFFERENTIAL DIAGNOSES:", 
                           "RED FLAGS:", "RECOMMENDED INVESTIGATIONS:", "CLINICAL PEARLS:"]
        
        has_all_sections = all(section in analysis for section in required_sections)
        
        if has_all_sections:
            return analysis
        
        # If not properly structured, attempt to reformat
        logger.warning("Diagnostic response not properly structured, attempting to reformat")
        
        # This is a fallback - ideally the AI should format correctly
        formatted = "DIAGNOSTIC ANALYSIS\n" + "=" * 20 + "\n\n"
        formatted += analysis
        
        return formatted
    
    def _extract_diagnoses(self, analysis: str) -> List[str]:
        """
        Extract list of differential diagnoses from the analysis.

        Handles both ICD-9 and ICD-10 code formats.
        """
        diagnoses = []

        if "DIFFERENTIAL DIAGNOSES:" in analysis:
            diff_section = analysis.split("DIFFERENTIAL DIAGNOSES:")[1]
            # Find end of differential section
            for end_marker in ["RED FLAGS:", "RECOMMENDED INVESTIGATIONS:", "CLINICAL PEARLS:"]:
                if end_marker in diff_section:
                    diff_section = diff_section.split(end_marker)[0]
                    break

            # Look for numbered or bulleted items
            lines = diff_section.strip().split("\n")
            for line in lines:
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-") or line.startswith("•")):
                    # Extract ICD codes - support both formats
                    # Pattern 1: (ICD-10: X00.0, ICD-9: 000.0)
                    # Pattern 2: (X00.0) or (000.0)
                    icd10_pattern = r'ICD-10:\s*([A-Z]\d{2}(?:\.\d{1,4})?)'
                    icd9_pattern = r'ICD-9:\s*(\d{3}(?:\.\d{1,2})?)'
                    simple_icd10 = r'\(([A-Z]\d{2}(?:\.\d{1,4})?)\)'
                    simple_icd9 = r'\((\d{3}(?:\.\d{1,2})?)\)'

                    icd10_match = re.search(icd10_pattern, line, re.IGNORECASE)
                    icd9_match = re.search(icd9_pattern, line, re.IGNORECASE)

                    # Extract diagnosis name (before the first parenthesis or code indicator)
                    diagnosis = line
                    # Remove leading numbers and bullets
                    diagnosis = re.sub(r'^[\d\.\-\•\*\s]+', '', diagnosis).strip()
                    # Remove ICD code portions
                    diagnosis = re.sub(r'\(ICD-10:[^)]+\)', '', diagnosis, flags=re.IGNORECASE)
                    diagnosis = re.sub(r'\(ICD-9:[^)]+\)', '', diagnosis, flags=re.IGNORECASE)
                    diagnosis = re.sub(r'\([A-Z]\d{2}(?:\.\d{1,4})?\)', '', diagnosis, flags=re.IGNORECASE)
                    diagnosis = re.sub(r'\(\d{3}(?:\.\d{1,2})?\)', '', diagnosis)
                    # Clean up trailing dashes or spaces
                    diagnosis = diagnosis.strip(' -–—:')

                    if diagnosis:
                        # Build diagnosis string with codes
                        codes = []
                        if icd10_match:
                            codes.append(f"ICD-10: {icd10_match.group(1)}")
                        else:
                            # Try simple pattern
                            simple_match = re.search(simple_icd10, line, re.IGNORECASE)
                            if simple_match:
                                codes.append(f"ICD-10: {simple_match.group(1)}")

                        if icd9_match:
                            codes.append(f"ICD-9: {icd9_match.group(1)}")
                        else:
                            # Try simple pattern
                            simple_match = re.search(simple_icd9, line)
                            if simple_match:
                                codes.append(f"ICD-9: {simple_match.group(1)}")

                        if codes:
                            diagnoses.append(f"{diagnosis} ({', '.join(codes)})")
                        else:
                            diagnoses.append(diagnosis)

        return diagnoses
    
    def analyze_symptoms(self, symptoms: List[str], patient_info: Optional[Dict] = None) -> AgentResponse:
        """
        Convenience method to analyze a list of symptoms.
        
        Args:
            symptoms: List of symptoms to analyze
            patient_info: Optional patient information (age, gender, PMH, etc.)
            
        Returns:
            AgentResponse with diagnostic analysis
        """
        # Format symptoms and patient info into clinical findings
        clinical_findings = "Presenting Symptoms:\n"
        clinical_findings += "\n".join(f"- {symptom}" for symptom in symptoms)
        
        if patient_info:
            clinical_findings += "\n\nPatient Information:\n"
            for key, value in patient_info.items():
                clinical_findings += f"- {key.replace('_', ' ').title()}: {value}\n"
        
        task = AgentTask(
            task_description="Analyze symptoms and generate differential diagnoses",
            input_data={"clinical_findings": clinical_findings}
        )
        
        return self.execute(task)
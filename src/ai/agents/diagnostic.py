"""
Diagnostic agent for analyzing symptoms and suggesting differential diagnoses.

Supports both ICD-9 and ICD-10 diagnostic codes with validation.
Enhanced with:
- Numeric confidence scoring (0-100%)
- DataExtractionAgent integration for structured data
- Expanded patient context handling
- Structured differential output
"""

import logging
from typing import Optional, List, Dict, Any, TYPE_CHECKING
import re
import json

from .base import BaseAgent
from .models import AgentConfig, AgentTask, AgentResponse

# Try to import medication agent for cross-reference
try:
    from .medication import MedicationAgent
    MEDICATION_AGENT_AVAILABLE = True
except ImportError:
    MEDICATION_AGENT_AVAILABLE = False

# Try to import data extraction agent
try:
    from .data_extraction import DataExtractionAgent
    DATA_EXTRACTION_AVAILABLE = True
except ImportError:
    DATA_EXTRACTION_AVAILABLE = False

# Import ICD validator
try:
    from utils.icd_validator import (
        ICDValidator, ICDValidationResult, ICDCodeSystem,
        extract_icd_codes, get_validator
    )
    ICD_VALIDATION_AVAILABLE = True
except ImportError:
    ICD_VALIDATION_AVAILABLE = False

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
3. Rank diagnoses by likelihood with NUMERIC CONFIDENCE SCORES (0-100%)
4. Suggest appropriate investigations to narrow the differential
5. Highlight any red flags or concerning features

Guidelines:
- Always provide multiple diagnostic possibilities (aim for 5-10)
- Include BOTH ICD-10 and ICD-9 codes for each differential diagnosis
  - ICD-10 format: Letter + 2 digits + optional decimal (e.g., J06.9, E11.65)
  - ICD-9 format: 3 digits + optional decimal (e.g., 346.10, 250.00)
- ALWAYS include a numeric confidence score (0-100%) for each diagnosis
  - HIGH confidence: 70-100% (strong supporting evidence)
  - MEDIUM confidence: 40-69% (moderate support, needs investigation)
  - LOW confidence: 0-39% (possible but less likely)
- Consider common conditions before rare ones (think horses, not zebras)
- Include both benign and serious conditions when appropriate
- Never provide definitive diagnoses - only suggestions for clinical consideration
- Always recommend appropriate follow-up and investigations
- Flag any emergency conditions that need immediate attention

Format your response as:
1. CLINICAL SUMMARY: Brief overview of key findings

2. DIFFERENTIAL DIAGNOSES: Listed by likelihood with confidence scores, ICD codes, and reasoning
   Format each diagnosis as:
   [Rank]. [Diagnosis Name] - [Confidence]% (ICD-10: [code], ICD-9: [code])
   - Supporting: [key supporting findings]
   - Against: [findings that argue against this diagnosis]
   - Next steps: [specific tests to confirm/exclude]

   Example:
   1. Migraine without aura - 75% (ICD-10: G43.009, ICD-9: 346.10)
   - Supporting: Unilateral throbbing headache, photophobia, family history
   - Against: No prior episodes documented
   - Next steps: Headache diary, consider MRI if atypical features

3. RED FLAGS: Any concerning features requiring urgent attention (mark with ⚠️)

4. RECOMMENDED INVESTIGATIONS: Tests to help narrow the differential
   - List as: [Test] - [Priority: Urgent/Routine/Optional] - [Rationale]

5. CLINICAL PEARLS: Key points to remember for this presentation""",
        model="gpt-4",
        temperature=0.1,  # Lower temperature for more consistent diagnostic reasoning
        max_tokens=1200  # Increased for more detailed structured output
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
                 or input_data['soap_note'], plus optional patient_context and specialty

        Returns:
            AgentResponse with diagnostic analysis including validated ICD codes
        """
        try:
            # Extract clinical findings from task
            clinical_findings = task.input_data.get('clinical_findings', '')
            soap_note = task.input_data.get('soap_note', '')
            patient_context = task.input_data.get('patient_context', {})
            specialty = task.input_data.get('specialty', 'general')
            enable_medication_crossref = task.input_data.get('enable_medication_crossref', True)

            if not clinical_findings and not soap_note:
                return AgentResponse(
                    result="",
                    success=False,
                    error="No clinical findings or SOAP note provided"
                )

            # Use SOAP note if clinical findings not directly provided
            if not clinical_findings:
                clinical_findings = self._extract_clinical_findings(soap_note)

            # Build enhanced clinical findings with patient context
            enhanced_findings = self._enhance_findings_with_context(
                clinical_findings, patient_context
            )

            # Build the diagnostic prompt with specialty focus
            prompt = self._build_diagnostic_prompt(
                enhanced_findings, task.context, specialty
            )

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

            # Add medication cross-reference if enabled and medications present
            medication_section = None
            if enable_medication_crossref:
                medication_section = self._get_medication_considerations(
                    clinical_findings, patient_context, enable_medication_crossref
                )
                if medication_section:
                    structured_analysis = self._append_medication_considerations(
                        structured_analysis, medication_section
                    )

            # Extract structured data from the analysis
            structured_data = self.get_structured_analysis(structured_analysis)
            structured_differentials = structured_data.get('differentials', [])

            # Run DataExtractionAgent if available
            enable_data_extraction = task.input_data.get('enable_data_extraction', True)
            extracted_clinical_data = None
            if enable_data_extraction:
                extracted_clinical_data = self._run_data_extraction(
                    clinical_findings, task.context
                )

            # Calculate average confidence score
            confidence_scores = [d.get('confidence_score', 0.5) for d in structured_differentials]
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5

            # Create response with enhanced metadata
            response = AgentResponse(
                result=structured_analysis,
                thoughts=f"Generated {differential_count} differential diagnoses based on clinical findings with {specialty} focus (avg confidence: {avg_confidence*100:.0f}%)",
                success=True,
                metadata={
                    'differential_count': differential_count,
                    'has_red_flags': has_red_flags,
                    'model_used': self.config.model,
                    'clinical_findings_length': len(clinical_findings),
                    'specialty': specialty,
                    'has_patient_context': bool(patient_context),
                    'patient_age': patient_context.get('age') if patient_context else None,
                    'patient_sex': patient_context.get('sex') if patient_context else None,
                    'icd_codes_found': len(icd_validation_results),
                    'icd_codes_valid': sum(1 for r in icd_validation_results if r.get('is_valid', False)),
                    'icd_codes_invalid': sum(1 for r in icd_validation_results if not r.get('is_valid', True)),
                    'icd_validation_results': icd_validation_results,
                    'medication_crossref_enabled': enable_medication_crossref,
                    'medication_crossref_included': medication_section is not None,
                    # New structured data
                    'structured_differentials': structured_differentials,
                    'structured_investigations': structured_data.get('investigations', []),
                    'structured_clinical_pearls': structured_data.get('clinical_pearls', []),
                    'red_flags_list': structured_data.get('red_flags', []),
                    'clinical_summary': structured_data.get('clinical_summary', ''),
                    'average_confidence': avg_confidence,
                    'extracted_clinical_data': extracted_clinical_data,
                    'data_extraction_performed': extracted_clinical_data is not None
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
    
    def _enhance_findings_with_context(
        self, clinical_findings: str, patient_context: Optional[Dict] = None
    ) -> str:
        """
        Enhance clinical findings with patient context information.

        Args:
            clinical_findings: The original clinical findings
            patient_context: Optional patient context dictionary

        Returns:
            Enhanced clinical findings string
        """
        if not patient_context:
            return clinical_findings

        context_parts = []

        # Build patient demographics
        demo_parts = []
        if 'age' in patient_context:
            demo_parts.append(f"{patient_context['age']}-year-old")
        if 'sex' in patient_context:
            demo_parts.append(patient_context['sex'].lower())
        if patient_context.get('pregnant'):
            demo_parts.append("pregnant")

        if demo_parts:
            context_parts.append(f"Patient: {' '.join(demo_parts)}")

        # Add medical history
        if 'past_medical_history' in patient_context:
            context_parts.append(f"Past Medical History: {patient_context['past_medical_history']}")

        # Add surgical history
        if 'past_surgical_history' in patient_context:
            context_parts.append(f"Past Surgical History: {patient_context['past_surgical_history']}")

        # Add family history
        if 'family_history' in patient_context:
            context_parts.append(f"Family History: {patient_context['family_history']}")

        # Add social history
        if 'social_history' in patient_context:
            context_parts.append(f"Social History: {patient_context['social_history']}")

        # Add current medications
        if 'current_medications' in patient_context:
            context_parts.append(f"Current Medications: {patient_context['current_medications']}")

        # Add allergies
        if 'allergies' in patient_context:
            context_parts.append(f"Allergies: {patient_context['allergies']}")

        # Add review of systems
        if 'review_of_systems' in patient_context:
            context_parts.append(f"Review of Systems: {patient_context['review_of_systems']}")

        if context_parts:
            return "PATIENT INFORMATION:\n" + "\n".join(context_parts) + "\n\n" + clinical_findings

        return clinical_findings

    def _build_diagnostic_prompt(
        self,
        clinical_findings: str,
        context: Optional[str] = None,
        specialty: str = "general"
    ) -> str:
        """
        Build the prompt for diagnostic analysis with specialty focus.

        Args:
            clinical_findings: The clinical findings to analyze
            context: Optional additional context
            specialty: The specialty focus for the analysis

        Returns:
            Formatted prompt string
        """
        prompt_parts = []

        # Add specialty-specific instructions
        specialty_instructions = self._get_specialty_instructions(specialty)
        if specialty_instructions:
            prompt_parts.append(f"SPECIALTY FOCUS: {specialty_instructions}\n")

        if context:
            prompt_parts.append(f"Additional Context:\n{context}\n")

        prompt_parts.append("Please analyze the following clinical findings and provide a comprehensive diagnostic assessment:\n")
        prompt_parts.append(f"Clinical Findings:\n{clinical_findings}\n")
        prompt_parts.append("\nProvide your diagnostic analysis following the specified format. Include confidence levels (HIGH >70%, MEDIUM 40-70%, LOW <40%) for each differential diagnosis.")

        return "\n".join(prompt_parts)

    def _get_specialty_instructions(self, specialty: str) -> str:
        """
        Get specialty-specific instructions for the diagnostic analysis.

        Args:
            specialty: The specialty focus

        Returns:
            Specialty-specific instruction string
        """
        specialty_map = {
            "general": "Apply a broad primary care perspective. Consider common conditions first (horses, not zebras). Include conditions from multiple organ systems.",
            "emergency": "PRIORITIZE LIFE-THREATENING CONDITIONS. Focus on red flags and time-sensitive diagnoses. Rank conditions by urgency, not just likelihood. Consider 'must-not-miss' diagnoses.",
            "internal": "Consider multisystem involvement and complex medical conditions. Account for comorbidities and their interactions. Consider atypical presentations.",
            "pediatric": "Apply age-appropriate differentials. Consider developmental milestones and congenital conditions. Account for age-specific vital sign normals and presentations.",
            "cardiology": "Focus on cardiovascular causes including structural, electrical, and vascular conditions. Consider cardiac risk stratification. Include relevant cardiac biomarkers in investigations.",
            "pulmonology": "Focus on respiratory and pulmonary conditions. Consider obstructive vs restrictive patterns. Include relevant pulmonary function tests and imaging.",
            "gi": "Focus on gastrointestinal and hepatobiliary conditions. Consider upper vs lower GI localization. Include relevant endoscopic and imaging studies.",
            "neurology": "Focus on neurological causes including structural, vascular, demyelinating, and functional. Consider localization (central vs peripheral). Include relevant imaging and electrophysiology.",
            "psychiatry": "Consider psychiatric and biopsychosocial factors. Rule out organic causes of psychiatric symptoms. Include relevant screening tools and assessments.",
            "orthopedic": "Focus on musculoskeletal and orthopedic conditions. Consider mechanical vs inflammatory causes. Include relevant imaging and orthopedic examinations.",
            "oncology": "Consider malignancy in the differential. Look for paraneoplastic syndromes. Include relevant tumor markers and imaging for staging.",
            "geriatric": "Consider age-related conditions and atypical presentations in elderly. Account for polypharmacy and drug interactions. Consider functional status and goals of care.",
        }

        return specialty_map.get(specialty, specialty_map["general"])
    
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

    def _get_medication_considerations(
        self,
        clinical_findings: str,
        patient_context: Optional[Dict] = None,
        enable_cross_reference: bool = True
    ) -> Optional[str]:
        """
        Analyze medications for diagnostic considerations.

        Uses the medication agent to identify drug-induced conditions,
        interactions, and medication-related concerns relevant to the
        differential diagnosis.

        Args:
            clinical_findings: The clinical findings text
            patient_context: Optional patient context with current_medications
            enable_cross_reference: Whether to enable medication cross-reference

        Returns:
            Medication considerations section text, or None if not applicable
        """
        if not enable_cross_reference or not MEDICATION_AGENT_AVAILABLE:
            return None

        # Check if there are medications to analyze
        medications_to_analyze = None

        # First check patient context for current medications
        if patient_context and patient_context.get('current_medications'):
            medications_to_analyze = patient_context['current_medications']

        # Also check clinical findings for medication mentions
        medication_patterns = [
            r'\b(taking|on|uses?|prescribed)\s+([a-zA-Z]+(?:,\s*[a-zA-Z]+)*)',
            r'\b(metformin|lisinopril|omeprazole|atorvastatin|amlodipine|metoprolol|'
            r'losartan|levothyroxine|gabapentin|sertraline|fluoxetine|citalopram|'
            r'escitalopram|duloxetine|venlafaxine|bupropion|trazodone|amitriptyline|'
            r'hydrochlorothiazide|furosemide|warfarin|aspirin|clopidogrel|insulin|'
            r'prednisone|montelukast|albuterol|fluticasone|pantoprazole)\b',
        ]

        found_meds_in_text = []
        for pattern in medication_patterns:
            matches = re.findall(pattern, clinical_findings, re.IGNORECASE)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        found_meds_in_text.extend(match)
                    else:
                        found_meds_in_text.append(match)

        if found_meds_in_text and not medications_to_analyze:
            medications_to_analyze = ", ".join(set(found_meds_in_text))

        if not medications_to_analyze:
            return None

        try:
            # Create medication agent instance
            med_agent = MedicationAgent(ai_caller=self._ai_caller)

            # Create task for medication analysis focused on diagnostic relevance
            med_task = AgentTask(
                task_description="Analyze medications for diagnostic considerations",
                input_data={
                    "clinical_text": clinical_findings,
                    "medications": medications_to_analyze,
                    "analysis_type": "diagnostic_relevance"
                },
                context="Focus on: 1) Drug-induced conditions that could explain symptoms, "
                        "2) Drug interactions affecting differential, "
                        "3) Medications that may mask or modify symptoms"
            )

            # Execute medication analysis
            med_response = med_agent.execute(med_task)

            if med_response.success and med_response.result:
                # Format as medication considerations section
                considerations = [
                    "\nMEDICATION CONSIDERATIONS:",
                    "-" * 30,
                    ""
                ]

                # Extract key points from medication analysis
                med_result = med_response.result

                # Look for drug-induced conditions
                if "drug-induced" in med_result.lower() or "medication-induced" in med_result.lower():
                    considerations.append("⚠ Potential drug-induced conditions identified")
                    considerations.append("")

                # Look for significant interactions
                if "major" in med_result.lower() or "contraindicated" in med_result.lower():
                    considerations.append("⚠ Significant drug interactions present")
                    considerations.append("")

                # Add the full medication analysis summary
                # Take first 500 chars to keep it concise
                summary = med_result[:500] if len(med_result) > 500 else med_result
                considerations.append(summary)

                if len(med_result) > 500:
                    considerations.append("\n[... Additional details available in full medication analysis]")

                return "\n".join(considerations)

        except Exception as e:
            logger.warning(f"Medication cross-reference failed: {e}")
            return None

        return None

    def _append_medication_considerations(
        self, analysis: str, medication_section: Optional[str]
    ) -> str:
        """
        Append medication considerations to the diagnostic analysis.

        Args:
            analysis: The original analysis text
            medication_section: The medication considerations section

        Returns:
            Analysis with appended medication section
        """
        if not medication_section:
            return analysis

        # Insert before CLINICAL PEARLS if present, otherwise append at end
        if "CLINICAL PEARLS:" in analysis:
            parts = analysis.split("CLINICAL PEARLS:")
            return parts[0] + medication_section + "\n\nCLINICAL PEARLS:" + parts[1]
        else:
            return analysis + "\n" + medication_section

    def _extract_structured_differentials(self, analysis: str) -> List[Dict[str, Any]]:
        """
        Extract structured differential diagnoses with confidence scores from analysis text.

        Args:
            analysis: The diagnostic analysis text

        Returns:
            List of structured differential diagnosis dictionaries
        """
        differentials = []

        if "DIFFERENTIAL DIAGNOSES:" not in analysis:
            return differentials

        diff_section = analysis.split("DIFFERENTIAL DIAGNOSES:")[1]
        # Find end of differential section
        for end_marker in ["RED FLAGS:", "RECOMMENDED INVESTIGATIONS:", "CLINICAL PEARLS:", "MEDICATION CONSIDERATIONS:"]:
            if end_marker in diff_section:
                diff_section = diff_section.split(end_marker)[0]
                break

        lines = diff_section.strip().split("\n")
        current_diff = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this is a new diagnosis line (starts with number)
            rank_match = re.match(r'^(\d+)\.\s*(.+)', line)
            if rank_match:
                # Save previous differential if exists
                if current_diff:
                    differentials.append(current_diff)

                rank = int(rank_match.group(1))
                rest = rank_match.group(2)

                # Extract confidence score - look for patterns like "75%", "- 75%", etc.
                confidence_match = re.search(r'[-–]\s*(\d+(?:\.\d+)?)\s*%', rest)
                confidence_score = float(confidence_match.group(1)) / 100 if confidence_match else None

                # Determine confidence level
                if confidence_score is not None:
                    if confidence_score >= 0.7:
                        confidence_level = 'high'
                    elif confidence_score >= 0.4:
                        confidence_level = 'medium'
                    else:
                        confidence_level = 'low'
                else:
                    # Try to extract from text
                    if 'high' in rest.lower():
                        confidence_level = 'high'
                        confidence_score = 0.75
                    elif 'medium' in rest.lower() or 'moderate' in rest.lower():
                        confidence_level = 'medium'
                        confidence_score = 0.55
                    elif 'low' in rest.lower():
                        confidence_level = 'low'
                        confidence_score = 0.25
                    else:
                        confidence_level = 'medium'
                        confidence_score = 0.5

                # Extract ICD codes
                icd10_match = re.search(r'ICD-10:\s*([A-Z]\d{2}(?:\.\d{1,4})?)', rest, re.IGNORECASE)
                icd9_match = re.search(r'ICD-9:\s*(\d{3}(?:\.\d{1,2})?)', rest, re.IGNORECASE)

                # Extract diagnosis name (before confidence/ICD codes)
                diagnosis_name = rest
                # Remove confidence score
                diagnosis_name = re.sub(r'[-–]\s*\d+(?:\.\d+)?\s*%', '', diagnosis_name)
                # Remove ICD codes
                diagnosis_name = re.sub(r'\(ICD-10:[^)]+\)', '', diagnosis_name, flags=re.IGNORECASE)
                diagnosis_name = re.sub(r'\(ICD-9:[^)]+\)', '', diagnosis_name, flags=re.IGNORECASE)
                diagnosis_name = re.sub(r'\([A-Z]\d{2}(?:\.\d{1,4})?,?\s*\d{3}(?:\.\d{1,2})?\)', '', diagnosis_name)
                diagnosis_name = diagnosis_name.strip(' -–—:(),')

                current_diff = {
                    'rank': rank,
                    'diagnosis_name': diagnosis_name,
                    'icd10_code': icd10_match.group(1) if icd10_match else None,
                    'icd9_code': icd9_match.group(1) if icd9_match else None,
                    'confidence_score': confidence_score,
                    'confidence_level': confidence_level,
                    'reasoning': '',
                    'supporting_findings': [],
                    'against_findings': [],
                    'next_steps': [],
                    'is_red_flag': '⚠' in rest or 'urgent' in rest.lower() or 'emergent' in rest.lower()
                }

            elif current_diff and line.startswith('-'):
                # This is a sub-item for the current differential
                content = line[1:].strip()
                content_lower = content.lower()

                if content_lower.startswith('supporting:'):
                    findings = content.split(':', 1)[1].strip()
                    current_diff['supporting_findings'] = [f.strip() for f in findings.split(',')]
                elif content_lower.startswith('against:'):
                    findings = content.split(':', 1)[1].strip()
                    current_diff['against_findings'] = [f.strip() for f in findings.split(',')]
                elif content_lower.startswith('next steps:') or content_lower.startswith('next step:'):
                    steps = content.split(':', 1)[1].strip()
                    current_diff['next_steps'] = [s.strip() for s in steps.split(',')]
                else:
                    # Add to reasoning
                    if current_diff['reasoning']:
                        current_diff['reasoning'] += ' ' + content
                    else:
                        current_diff['reasoning'] = content

        # Don't forget the last differential
        if current_diff:
            differentials.append(current_diff)

        return differentials

    def _extract_investigations(self, analysis: str) -> List[Dict[str, Any]]:
        """
        Extract recommended investigations from analysis text.

        Args:
            analysis: The diagnostic analysis text

        Returns:
            List of structured investigation dictionaries
        """
        investigations = []

        if "RECOMMENDED INVESTIGATIONS:" not in analysis:
            return investigations

        inv_section = analysis.split("RECOMMENDED INVESTIGATIONS:")[1]
        # Find end of section
        for end_marker in ["CLINICAL PEARLS:", "MEDICATION CONSIDERATIONS:", "ICD CODE VALIDATION"]:
            if end_marker in inv_section:
                inv_section = inv_section.split(end_marker)[0]
                break

        lines = inv_section.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line or not (line.startswith('-') or line.startswith('•') or line[0].isdigit()):
                continue

            # Remove leading markers
            content = re.sub(r'^[-•\d.]+\s*', '', line).strip()

            # Try to extract priority
            priority = 'routine'
            priority_match = re.search(r'(urgent|routine|optional)', content.lower())
            if priority_match:
                priority = priority_match.group(1)

            # Try to extract type
            inv_type = 'other'
            if any(term in content.lower() for term in ['blood', 'cbc', 'cmp', 'bmp', 'lft', 'tsh', 'a1c', 'lipid']):
                inv_type = 'lab'
            elif any(term in content.lower() for term in ['x-ray', 'xray', 'ct', 'mri', 'ultrasound', 'echo', 'scan']):
                inv_type = 'imaging'
            elif any(term in content.lower() for term in ['biopsy', 'endoscopy', 'colonoscopy', 'scope']):
                inv_type = 'procedure'
            elif any(term in content.lower() for term in ['refer', 'consult']):
                inv_type = 'referral'

            # Extract rationale if present (after dash or hyphen)
            parts = re.split(r'\s*[-–]\s*', content)
            name = parts[0].strip()
            rationale = parts[-1].strip() if len(parts) > 1 else ''

            investigations.append({
                'investigation_name': name,
                'investigation_type': inv_type,
                'priority': priority,
                'rationale': rationale,
                'status': 'pending'
            })

        return investigations

    def _extract_clinical_pearls(self, analysis: str) -> List[Dict[str, str]]:
        """
        Extract clinical pearls from analysis text.

        Args:
            analysis: The diagnostic analysis text

        Returns:
            List of clinical pearl dictionaries
        """
        pearls = []

        if "CLINICAL PEARLS:" not in analysis:
            return pearls

        pearl_section = analysis.split("CLINICAL PEARLS:")[1]
        # Find end of section
        for end_marker in ["ICD CODE VALIDATION", "MEDICATION CONSIDERATIONS:"]:
            if end_marker in pearl_section:
                pearl_section = pearl_section.split(end_marker)[0]
                break

        lines = pearl_section.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line or not (line.startswith('-') or line.startswith('•') or line[0].isdigit()):
                continue

            # Remove leading markers
            content = re.sub(r'^[-•\d.]+\s*', '', line).strip()
            if content:
                pearls.append({
                    'pearl_text': content,
                    'category': 'diagnostic'  # Could be enhanced to detect category
                })

        return pearls

    def _run_data_extraction(
        self,
        clinical_findings: str,
        context: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Run DataExtractionAgent on clinical findings to extract structured data.

        Args:
            clinical_findings: The clinical text to extract from
            context: Optional additional context

        Returns:
            Dictionary of extracted data, or None if extraction failed
        """
        if not DATA_EXTRACTION_AVAILABLE:
            logger.info("DataExtractionAgent not available, skipping structured extraction")
            return None

        try:
            # Create data extraction agent
            extraction_agent = DataExtractionAgent(ai_caller=self._ai_caller)

            # Create task for comprehensive extraction
            extraction_task = AgentTask(
                task_description="Extract structured clinical data for diagnostic analysis",
                input_data={
                    "clinical_text": clinical_findings,
                    "extraction_type": "comprehensive",
                    "output_format": "json"
                },
                context=context or "Focus on vital signs, labs, medications, and any existing diagnoses"
            )

            # Execute extraction
            response = extraction_agent.execute(extraction_task)

            if response.success and response.metadata:
                return response.metadata.get('parsed_data', {})

        except Exception as e:
            logger.warning(f"Data extraction failed: {e}")

        return None

    def get_structured_analysis(self, analysis_text: str) -> Dict[str, Any]:
        """
        Parse a diagnostic analysis into fully structured data.

        This method extracts all components of the analysis into structured
        format suitable for database storage.

        Args:
            analysis_text: The full diagnostic analysis text

        Returns:
            Dictionary with structured components:
            - differentials: List of structured differential diagnoses
            - investigations: List of recommended investigations
            - clinical_pearls: List of clinical pearls
            - red_flags: List of red flag findings
            - clinical_summary: The clinical summary text
        """
        result = {
            'differentials': self._extract_structured_differentials(analysis_text),
            'investigations': self._extract_investigations(analysis_text),
            'clinical_pearls': self._extract_clinical_pearls(analysis_text),
            'red_flags': [],
            'clinical_summary': ''
        }

        # Extract clinical summary
        if "CLINICAL SUMMARY:" in analysis_text:
            summary_section = analysis_text.split("CLINICAL SUMMARY:")[1]
            for end_marker in ["DIFFERENTIAL DIAGNOSES:", "RED FLAGS:"]:
                if end_marker in summary_section:
                    summary_section = summary_section.split(end_marker)[0]
                    break
            result['clinical_summary'] = summary_section.strip()

        # Extract red flags
        if "RED FLAGS:" in analysis_text:
            rf_section = analysis_text.split("RED FLAGS:")[1]
            for end_marker in ["RECOMMENDED INVESTIGATIONS:", "CLINICAL PEARLS:", "MEDICATION"]:
                if end_marker in rf_section:
                    rf_section = rf_section.split(end_marker)[0]
                    break

            for line in rf_section.strip().split("\n"):
                line = line.strip()
                if line and (line.startswith('-') or line.startswith('•') or line.startswith('⚠')):
                    content = re.sub(r'^[-•⚠\s]+', '', line).strip()
                    if content and content.lower() not in ['none', 'n/a', 'nil']:
                        result['red_flags'].append(content)

        return result
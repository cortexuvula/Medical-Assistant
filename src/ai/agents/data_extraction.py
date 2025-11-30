"""
Data extraction agent for extracting structured clinical data from unstructured text.
"""

import logging
import re
import json
from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING
from datetime import datetime

from .base import BaseAgent
from .models import AgentConfig, AgentTask, AgentResponse, ToolCall

if TYPE_CHECKING:
    from .ai_caller import AICallerProtocol


logger = logging.getLogger(__name__)


class DataExtractionAgent(BaseAgent):
    """Agent specialized in extracting structured clinical data from medical text."""
    
    # Default configuration for data extraction agent
    DEFAULT_CONFIG = AgentConfig(
        name="DataExtractionAgent",
        description="Extracts structured clinical data from unstructured medical text",
        system_prompt="""You are a clinical data extraction specialist with expertise in identifying and extracting structured medical information from unstructured text.

Your role is to:
1. Extract vital signs with values and units (BP, HR, Temp, RR, O2 sat, etc.)
2. Extract laboratory values with results, units, and reference ranges when available
3. Extract medications with dosages, routes, and frequencies
4. Extract diagnoses with appropriate ICD-9 or ICD-10 codes
5. Extract procedures and interventions with dates when available
6. Organize extracted data in a structured, consistent format

Guidelines:
- Be precise and accurate - only extract explicitly stated information
- Include units for all measurements (e.g., mmHg, bpm, °F, mg/dL)
- Use standard medical abbreviations appropriately
- For diagnoses, provide both the description and ICD code when possible
- For medications, include generic names, brand names if mentioned, dosage, route, and frequency
- Flag abnormal values when reference ranges are known
- Maintain temporal relationships when dates/times are mentioned
- If information is ambiguous or unclear, note it as such
- Organize data by categories for easy review

Output Format:
Provide extracted data in the following structure:
1. VITAL SIGNS
   - Include timestamp if available
   - List each vital with value and units

2. LABORATORY VALUES
   - Group by test category (e.g., CBC, Chemistry, etc.)
   - Include result, units, reference range, and flag if abnormal

3. MEDICATIONS
   - List each medication with full details
   - Note if current, discontinued, or new

4. DIAGNOSES
   - Primary diagnoses first
   - Include ICD codes in parentheses

5. PROCEDURES
   - Include dates if mentioned
   - Note if planned, completed, or pending""",
        model="gpt-3.5-turbo",
        temperature=0.0,  # Zero temperature for consistent extraction
        max_tokens=500  # Increased for comprehensive extraction
    )
    
    def __init__(self, config: Optional[AgentConfig] = None, ai_caller: Optional['AICallerProtocol'] = None):
        """
        Initialize the data extraction agent.

        Args:
            config: Optional custom configuration. Uses default if not provided.
            ai_caller: Optional AI caller for dependency injection.
        """
        super().__init__(config or self.DEFAULT_CONFIG, ai_caller=ai_caller)
        
    def execute(self, task: AgentTask) -> AgentResponse:
        """
        Execute data extraction tasks.
        
        Args:
            task: Task containing clinical text to extract data from
            
        Returns:
            AgentResponse with extracted structured data
        """
        try:
            # Determine extraction type from task
            extraction_type = self._determine_extraction_type(task)
            
            if extraction_type == "vitals":
                return self._extract_vital_signs(task)
            elif extraction_type == "labs":
                return self._extract_lab_values(task)
            elif extraction_type == "medications":
                return self._extract_medications(task)
            elif extraction_type == "diagnoses":
                return self._extract_diagnoses(task)
            elif extraction_type == "procedures":
                return self._extract_procedures(task)
            elif extraction_type == "comprehensive":
                return self._extract_all_data(task)
            else:
                # Default to comprehensive extraction
                return self._extract_all_data(task)
                
        except Exception as e:
            logger.error(f"Error in data extraction: {e}")
            return AgentResponse(
                result="",
                success=False,
                error=str(e)
            )
    
    def _determine_extraction_type(self, task: AgentTask) -> str:
        """Determine the type of extraction from the task description."""
        task_desc = task.task_description.lower()
        extraction_type = task.input_data.get('extraction_type', '').lower()
        
        # Check explicit extraction type first
        if extraction_type:
            return extraction_type
        
        # Infer from task description
        if "vital" in task_desc:
            return "vitals"
        elif "lab" in task_desc or "laboratory" in task_desc:
            return "labs"
        elif "medication" in task_desc or "drug" in task_desc:
            return "medications"
        elif "diagnos" in task_desc or "icd" in task_desc:
            return "diagnoses"
        elif "procedure" in task_desc:
            return "procedures"
        else:
            return "comprehensive"
    
    def _extract_all_data(self, task: AgentTask) -> AgentResponse:
        """Extract all types of clinical data comprehensively."""
        clinical_text = self._get_clinical_text(task)
        
        if not clinical_text:
            return AgentResponse(
                result="",
                success=False,
                error="No clinical text provided for data extraction"
            )
        
        output_format = task.input_data.get('output_format', 'structured_text')
        
        prompt = self._build_comprehensive_extraction_prompt(clinical_text, task.context)
        
        # Call AI to extract data
        extracted_data = self._call_ai(prompt)
        
        # Parse the extracted data
        parsed_data = self._parse_comprehensive_extraction(extracted_data)
        
        # Format output based on requested format
        if output_format == 'json':
            result = json.dumps(parsed_data, indent=2)
        elif output_format == 'csv':
            result = self._format_as_csv(parsed_data)
        else:
            result = extracted_data  # Already in structured text format
        
        # Count extracted items
        counts = self._count_extracted_items(parsed_data)
        
        # Create response
        response = AgentResponse(
            result=result,
            thoughts=f"Extracted {counts['total']} clinical data points",
            success=True,
            metadata={
                'extraction_type': 'comprehensive',
                'output_format': output_format,
                'counts': counts,
                'parsed_data': parsed_data,
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _extract_vital_signs(self, task: AgentTask) -> AgentResponse:
        """Extract vital signs from clinical text."""
        clinical_text = self._get_clinical_text(task)
        
        if not clinical_text:
            return AgentResponse(
                result="",
                success=False,
                error="No clinical text provided for vital signs extraction"
            )
        
        prompt = self._build_vitals_extraction_prompt(clinical_text, task.context)
        
        # Call AI to extract vitals
        extracted_vitals = self._call_ai(prompt)
        
        # Parse vital signs
        vitals_data = self._parse_vital_signs(extracted_vitals)
        
        # Create response
        response = AgentResponse(
            result=extracted_vitals,
            thoughts=f"Extracted {len(vitals_data)} vital signs",
            success=True,
            metadata={
                'extraction_type': 'vitals',
                'vital_count': len(vitals_data),
                'vitals': vitals_data,
                'has_abnormal': any(v.get('abnormal', False) for v in vitals_data),
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _extract_lab_values(self, task: AgentTask) -> AgentResponse:
        """Extract laboratory values from clinical text."""
        clinical_text = self._get_clinical_text(task)
        
        if not clinical_text:
            return AgentResponse(
                result="",
                success=False,
                error="No clinical text provided for lab values extraction"
            )
        
        prompt = self._build_labs_extraction_prompt(clinical_text, task.context)
        
        # Call AI to extract labs
        extracted_labs = self._call_ai(prompt)
        
        # Parse lab values
        labs_data = self._parse_lab_values(extracted_labs)
        
        # Simulate tool call for lab reference lookup
        tool_calls = [
            ToolCall(
                tool_name="lookup_lab_references",
                arguments={"lab_tests": [lab['test'] for lab in labs_data]}
            )
        ]
        
        # Create response
        response = AgentResponse(
            result=extracted_labs,
            thoughts=f"Extracted {len(labs_data)} laboratory values",
            tool_calls=tool_calls,
            success=True,
            metadata={
                'extraction_type': 'labs',
                'lab_count': len(labs_data),
                'labs': labs_data,
                'has_abnormal': any(lab.get('abnormal', False) for lab in labs_data),
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _extract_medications(self, task: AgentTask) -> AgentResponse:
        """Extract medications from clinical text."""
        clinical_text = self._get_clinical_text(task)
        
        if not clinical_text:
            return AgentResponse(
                result="",
                success=False,
                error="No clinical text provided for medication extraction"
            )
        
        prompt = self._build_medications_extraction_prompt(clinical_text, task.context)
        
        # Call AI to extract medications
        extracted_meds = self._call_ai(prompt)
        
        # Parse medications
        meds_data = self._parse_medications(extracted_meds)
        
        # Create response
        response = AgentResponse(
            result=extracted_meds,
            thoughts=f"Extracted {len(meds_data)} medications",
            success=True,
            metadata={
                'extraction_type': 'medications',
                'medication_count': len(meds_data),
                'medications': meds_data,
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _extract_diagnoses(self, task: AgentTask) -> AgentResponse:
        """Extract diagnoses with ICD codes from clinical text."""
        clinical_text = self._get_clinical_text(task)
        
        if not clinical_text:
            return AgentResponse(
                result="",
                success=False,
                error="No clinical text provided for diagnosis extraction"
            )
        
        prompt = self._build_diagnoses_extraction_prompt(clinical_text, task.context)
        
        # Call AI to extract diagnoses
        extracted_diagnoses = self._call_ai(prompt)
        
        # Parse diagnoses
        diagnoses_data = self._parse_diagnoses(extracted_diagnoses)
        
        # Create response
        response = AgentResponse(
            result=extracted_diagnoses,
            thoughts=f"Extracted {len(diagnoses_data)} diagnoses",
            success=True,
            metadata={
                'extraction_type': 'diagnoses',
                'diagnosis_count': len(diagnoses_data),
                'diagnoses': diagnoses_data,
                'has_primary': any(d.get('primary', False) for d in diagnoses_data),
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _extract_procedures(self, task: AgentTask) -> AgentResponse:
        """Extract procedures and interventions from clinical text."""
        clinical_text = self._get_clinical_text(task)
        
        if not clinical_text:
            return AgentResponse(
                result="",
                success=False,
                error="No clinical text provided for procedure extraction"
            )
        
        prompt = self._build_procedures_extraction_prompt(clinical_text, task.context)
        
        # Call AI to extract procedures
        extracted_procedures = self._call_ai(prompt)
        
        # Parse procedures
        procedures_data = self._parse_procedures(extracted_procedures)
        
        # Create response
        response = AgentResponse(
            result=extracted_procedures,
            thoughts=f"Extracted {len(procedures_data)} procedures",
            success=True,
            metadata={
                'extraction_type': 'procedures',
                'procedure_count': len(procedures_data),
                'procedures': procedures_data,
                'has_completed': any(p.get('status') == 'completed' for p in procedures_data),
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _get_clinical_text(self, task: AgentTask) -> str:
        """Get clinical text from various input sources."""
        # Check different input sources
        clinical_text = task.input_data.get('clinical_text', '')
        soap_note = task.input_data.get('soap_note', '')
        transcript = task.input_data.get('transcript', '')
        
        # Use the first available source
        return clinical_text or soap_note or transcript
    
    def _build_comprehensive_extraction_prompt(self, text: str, context: Optional[str] = None) -> str:
        """Build prompt for comprehensive data extraction."""
        prompt_parts = []
        
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")
        
        prompt_parts.append("Extract all structured clinical data from the following text.")
        prompt_parts.append("Organize the data into the following categories:\n")
        prompt_parts.append("1. VITAL SIGNS (with timestamps if available)")
        prompt_parts.append("2. LABORATORY VALUES (with units and reference ranges)")
        prompt_parts.append("3. MEDICATIONS (with dosages and frequencies)")
        prompt_parts.append("4. DIAGNOSES (with ICD codes)")
        prompt_parts.append("5. PROCEDURES (with dates if mentioned)\n")
        prompt_parts.append(f"Clinical Text:\n{text}\n")
        prompt_parts.append("Extracted Data:")
        
        return "\n".join(prompt_parts)
    
    def _build_vitals_extraction_prompt(self, text: str, context: Optional[str] = None) -> str:
        """Build prompt for vital signs extraction."""
        prompt_parts = []
        
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")
        
        prompt_parts.append("Extract all vital signs from the following clinical text.")
        prompt_parts.append("Include:")
        prompt_parts.append("- Blood pressure (systolic/diastolic)")
        prompt_parts.append("- Heart rate/pulse")
        prompt_parts.append("- Temperature")
        prompt_parts.append("- Respiratory rate")
        prompt_parts.append("- Oxygen saturation")
        prompt_parts.append("- Weight/Height/BMI")
        prompt_parts.append("- Pain score")
        prompt_parts.append("Include units and timestamps when available.\n")
        prompt_parts.append(f"Clinical Text:\n{text}\n")
        prompt_parts.append("Vital Signs:")
        
        return "\n".join(prompt_parts)
    
    def _build_labs_extraction_prompt(self, text: str, context: Optional[str] = None) -> str:
        """Build prompt for laboratory values extraction."""
        prompt_parts = []
        
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")
        
        prompt_parts.append("Extract all laboratory values from the following clinical text.")
        prompt_parts.append("For each lab value, include:")
        prompt_parts.append("- Test name")
        prompt_parts.append("- Result value")
        prompt_parts.append("- Units")
        prompt_parts.append("- Reference range (if mentioned)")
        prompt_parts.append("- Flag if abnormal (H/L)")
        prompt_parts.append("Group by test category (CBC, Chemistry, etc.) when possible.\n")
        prompt_parts.append(f"Clinical Text:\n{text}\n")
        prompt_parts.append("Laboratory Values:")
        
        return "\n".join(prompt_parts)
    
    def _build_medications_extraction_prompt(self, text: str, context: Optional[str] = None) -> str:
        """Build prompt for medications extraction."""
        prompt_parts = []
        
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")
        
        prompt_parts.append("Extract all medications from the following clinical text.")
        prompt_parts.append("For each medication, include:")
        prompt_parts.append("- Generic name")
        prompt_parts.append("- Brand name (if mentioned)")
        prompt_parts.append("- Dosage and strength")
        prompt_parts.append("- Route of administration")
        prompt_parts.append("- Frequency")
        prompt_parts.append("- Status (current/discontinued/new)")
        prompt_parts.append("- Indication (if mentioned)\n")
        prompt_parts.append(f"Clinical Text:\n{text}\n")
        prompt_parts.append("Medications:")
        
        return "\n".join(prompt_parts)
    
    def _build_diagnoses_extraction_prompt(self, text: str, context: Optional[str] = None) -> str:
        """Build prompt for diagnoses extraction."""
        prompt_parts = []
        
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")
        
        prompt_parts.append("Extract all diagnoses from the following clinical text.")
        prompt_parts.append("For each diagnosis, include:")
        prompt_parts.append("- Description")
        prompt_parts.append("- ICD-9 or ICD-10 code")
        prompt_parts.append("- Whether it's primary or secondary")
        prompt_parts.append("- Status (active/resolved/chronic)")
        prompt_parts.append("List primary diagnoses first.\n")
        prompt_parts.append(f"Clinical Text:\n{text}\n")
        prompt_parts.append("Diagnoses:")
        
        return "\n".join(prompt_parts)
    
    def _build_procedures_extraction_prompt(self, text: str, context: Optional[str] = None) -> str:
        """Build prompt for procedures extraction."""
        prompt_parts = []
        
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")
        
        prompt_parts.append("Extract all procedures and interventions from the following clinical text.")
        prompt_parts.append("For each procedure, include:")
        prompt_parts.append("- Procedure name")
        prompt_parts.append("- Date (if mentioned)")
        prompt_parts.append("- Status (completed/planned/pending)")
        prompt_parts.append("- Provider (if mentioned)")
        prompt_parts.append("- Location/facility (if mentioned)\n")
        prompt_parts.append(f"Clinical Text:\n{text}\n")
        prompt_parts.append("Procedures:")
        
        return "\n".join(prompt_parts)
    
    def _parse_comprehensive_extraction(self, extracted_text: str) -> Dict[str, Any]:
        """Parse comprehensively extracted data into structured format."""
        sections = {
            'vital_signs': [],
            'laboratory_values': [],
            'medications': [],
            'diagnoses': [],
            'procedures': []
        }
        
        current_section = None
        
        for line in extracted_text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Identify sections
            if 'VITAL SIGNS' in line:
                current_section = 'vital_signs'
            elif 'LABORATORY VALUES' in line:
                current_section = 'laboratory_values'
            elif 'MEDICATIONS' in line:
                current_section = 'medications'
            elif 'DIAGNOSES' in line:
                current_section = 'diagnoses'
            elif 'PROCEDURES' in line:
                current_section = 'procedures'
            elif current_section and line.startswith('-'):
                # Add item to current section
                sections[current_section].append(line[1:].strip())
        
        return sections
    
    def _parse_vital_signs(self, text: str) -> List[Dict[str, Any]]:
        """Parse vital signs from extracted text."""
        vitals = []
        
        # Common vital sign patterns
        patterns = {
            'blood_pressure': r'(\d+)/(\d+)\s*(?:mmHg|mm Hg)?',
            'heart_rate': r'(?:HR|Heart Rate|Pulse)[:\s]*(\d+)\s*(?:bpm|/min)?',
            'temperature': r'(?:Temp|Temperature)[:\s]*(\d+\.?\d*)\s*(?:°?[CF])?',
            'respiratory_rate': r'(?:RR|Resp|Respiratory Rate)[:\s]*(\d+)\s*(?:/min)?',
            'oxygen_saturation': r'(?:O2|SpO2|O2 Sat)[:\s]*(\d+)\s*%?',
            'weight': r'(?:Weight|Wt)[:\s]*(\d+\.?\d*)\s*(?:kg|lbs)?',
            'height': r'(?:Height|Ht)[:\s]*(\d+\.?\d*)\s*(?:cm|in)?'
        }
        
        for line in text.split('\n'):
            for vital_type, pattern in patterns.items():
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    vital_data = {
                        'type': vital_type,
                        'value': match.group(0),
                        'raw_text': line.strip()
                    }
                    vitals.append(vital_data)
        
        return vitals
    
    def _parse_lab_values(self, text: str) -> List[Dict[str, Any]]:
        """Parse laboratory values from extracted text."""
        labs = []
        
        # Look for common lab value patterns
        lab_pattern = r'([A-Za-z0-9\s]+):\s*(\d+\.?\d*)\s*([A-Za-z/%]+)?(?:\s*\((?:ref|normal|range)?[:\s]*([0-9.\-\s]+)\))?'
        
        for line in text.split('\n'):
            if '-' in line or ':' in line:
                match = re.search(lab_pattern, line)
                if match:
                    lab_data = {
                        'test': match.group(1).strip(),
                        'value': match.group(2),
                        'units': match.group(3) or '',
                        'reference': match.group(4) or '',
                        'raw_text': line.strip()
                    }
                    labs.append(lab_data)
        
        return labs
    
    def _parse_medications(self, text: str) -> List[Dict[str, str]]:
        """Parse medications from extracted text."""
        medications = []
        
        for line in text.split('\n'):
            line = line.strip()
            if line and ('-' in line or any(dose_term in line.lower() for dose_term in ['mg', 'ml', 'tablet', 'daily'])):
                # Simple medication extraction
                med_data = {
                    'raw_text': line,
                    'name': self._extract_medication_name(line),
                    'dosage': self._extract_dosage(line),
                    'frequency': self._extract_frequency(line)
                }
                if med_data['name']:
                    medications.append(med_data)
        
        return medications
    
    def _parse_diagnoses(self, text: str) -> List[Dict[str, str]]:
        """Parse diagnoses from extracted text."""
        diagnoses = []
        
        # ICD code pattern
        icd_pattern = r'\(([A-Z]\d{2}\.?\d*)\)'
        
        for line in text.split('\n'):
            line = line.strip()
            if line and ('-' in line or 'diagnos' in line.lower()):
                icd_match = re.search(icd_pattern, line)
                diag_data = {
                    'description': re.sub(icd_pattern, '', line).strip().strip('-').strip(),
                    'icd_code': icd_match.group(1) if icd_match else '',
                    'raw_text': line
                }
                if diag_data['description']:
                    diagnoses.append(diag_data)
        
        return diagnoses
    
    def _parse_procedures(self, text: str) -> List[Dict[str, str]]:
        """Parse procedures from extracted text."""
        procedures = []
        
        for line in text.split('\n'):
            line = line.strip()
            if line and ('-' in line or 'procedure' in line.lower()):
                # Extract date if present
                date_match = re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', line)
                proc_data = {
                    'name': line.strip('-').strip(),
                    'date': date_match.group(0) if date_match else '',
                    'status': self._determine_procedure_status(line),
                    'raw_text': line
                }
                procedures.append(proc_data)
        
        return procedures
    
    def _extract_medication_name(self, text: str) -> str:
        """Extract medication name from text."""
        # Remove dosage information to get name
        text = re.sub(r'\d+\.?\d*\s*mg', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\d+\.?\d*\s*ml', '', text, flags=re.IGNORECASE)
        # Get first few words as medication name
        words = text.split()[:3]
        return ' '.join(words).strip('-').strip()
    
    def _extract_dosage(self, text: str) -> str:
        """Extract dosage from medication text."""
        dosage_match = re.search(r'\d+\.?\d*\s*(?:mg|ml|mcg|g|unit)', text, re.IGNORECASE)
        return dosage_match.group(0) if dosage_match else ''
    
    def _extract_frequency(self, text: str) -> str:
        """Extract frequency from medication text."""
        freq_patterns = [
            r'(?:once|twice|three times|four times)\s*(?:a day|daily)',
            r'(?:q|every)\s*\d+\s*(?:hours?|hrs?)',
            r'(?:bid|tid|qid|qd|prn|hs)',
            r'(?:daily|weekly|monthly)'
        ]
        
        for pattern in freq_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        return ''
    
    def _determine_procedure_status(self, text: str) -> str:
        """Determine procedure status from text."""
        text_lower = text.lower()
        if any(word in text_lower for word in ['completed', 'done', 'performed']):
            return 'completed'
        elif any(word in text_lower for word in ['planned', 'scheduled', 'upcoming']):
            return 'planned'
        elif any(word in text_lower for word in ['pending', 'await']):
            return 'pending'
        return 'unknown'
    
    def _count_extracted_items(self, parsed_data: Dict[str, List]) -> Dict[str, int]:
        """Count extracted items by category."""
        counts = {
            'vital_signs': len(parsed_data.get('vital_signs', [])),
            'laboratory_values': len(parsed_data.get('laboratory_values', [])),
            'medications': len(parsed_data.get('medications', [])),
            'diagnoses': len(parsed_data.get('diagnoses', [])),
            'procedures': len(parsed_data.get('procedures', [])),
            'total': 0
        }
        counts['total'] = sum(counts.values()) - counts['total']
        return counts
    
    def _format_as_csv(self, parsed_data: Dict[str, List]) -> str:
        """Format extracted data as CSV."""
        csv_parts = []
        
        # Vital Signs CSV
        if parsed_data.get('vital_signs'):
            csv_parts.append("VITAL SIGNS")
            csv_parts.append("Type,Value,Notes")
            for vital in parsed_data['vital_signs']:
                csv_parts.append(f"{vital},{vital},{vital}")
        
        # Add other sections similarly...
        # This is a simplified version
        
        return '\n'.join(csv_parts)
    
    def extract_all_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Convenience method to extract all clinical data from text.
        
        Args:
            text: Clinical text to extract data from
            
        Returns:
            Dictionary of extracted data if successful, None otherwise
        """
        task = AgentTask(
            task_description="Extract all clinical data",
            input_data={"clinical_text": text}
        )
        
        response = self.execute(task)
        if response and response.success:
            return response.metadata.get('parsed_data', {})
        return None
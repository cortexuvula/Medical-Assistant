"""
Diagnostic agent for analyzing symptoms and suggesting differential diagnoses.
"""

import logging
from typing import Optional, List, Dict
import re

from .base import BaseAgent
from .models import AgentConfig, AgentTask, AgentResponse


logger = logging.getLogger(__name__)


class DiagnosticAgent(BaseAgent):
    """Agent specialized in diagnostic analysis and differential diagnosis generation."""
    
    # Default configuration for diagnostic agent
    DEFAULT_CONFIG = AgentConfig(
        name="DiagnosticAgent",
        description="Analyzes clinical findings and suggests differential diagnoses",
        system_prompt="""You are a medical diagnostic assistant with expertise in differential diagnosis.
        
Your role is to:
1. Analyze symptoms, signs, and clinical findings
2. Generate a comprehensive differential diagnosis list with ICD-9 codes
3. Rank diagnoses by likelihood based on the clinical presentation
4. Suggest appropriate investigations to narrow the differential
5. Highlight any red flags or concerning features

Guidelines:
- Always provide multiple diagnostic possibilities
- Include ICD-9 codes for each differential diagnosis (format: xxx.xx)
- Consider common conditions before rare ones (think horses, not zebras)
- Include both benign and serious conditions when appropriate
- Never provide definitive diagnoses - only suggestions for clinical consideration
- Always recommend appropriate follow-up and investigations
- Flag any emergency conditions that need immediate attention
- Use ONLY ICD-9 codes, not ICD-10 codes

Format your response as:
1. CLINICAL SUMMARY: Brief overview of key findings
2. DIFFERENTIAL DIAGNOSES: Listed by likelihood with ICD-9 codes and brief reasoning
   Example: 1. Migraine without aura (346.10) - Classic presentation with family history
3. RED FLAGS: Any concerning features requiring urgent attention
4. RECOMMENDED INVESTIGATIONS: Tests to help narrow the differential
5. CLINICAL PEARLS: Key points to remember for this presentation""",
        model="gpt-4",
        temperature=0.1,  # Lower temperature for more consistent diagnostic reasoning
        max_tokens=500
    )
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize the diagnostic agent.
        
        Args:
            config: Optional custom configuration. Uses default if not provided.
        """
        super().__init__(config or self.DEFAULT_CONFIG)
        
    def execute(self, task: AgentTask) -> AgentResponse:
        """
        Analyze clinical findings and generate differential diagnoses.
        
        Args:
            task: Task containing clinical findings in input_data['clinical_findings']
                 or input_data['soap_note']
            
        Returns:
            AgentResponse with diagnostic analysis
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
            
            # Extract key information for metadata
            differential_count = len(self._extract_diagnoses(structured_analysis))
            has_red_flags = "RED FLAGS:" in structured_analysis and \
                           len(structured_analysis.split("RED FLAGS:")[1].split("\n")[0].strip()) > 0
            
            # Create response
            response = AgentResponse(
                result=structured_analysis,
                thoughts=f"Generated {differential_count} differential diagnoses based on clinical findings",
                success=True,
                metadata={
                    'differential_count': differential_count,
                    'has_red_flags': has_red_flags,
                    'model_used': self.config.model,
                    'clinical_findings_length': len(clinical_findings)
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
        """Extract list of differential diagnoses from the analysis."""
        diagnoses = []
        
        if "DIFFERENTIAL DIAGNOSES:" in analysis:
            diff_section = analysis.split("DIFFERENTIAL DIAGNOSES:")[1].split("RED FLAGS:")[0]
            # Look for numbered or bulleted items
            lines = diff_section.strip().split("\n")
            for line in lines:
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-") or line.startswith("•")):
                    # Extract the diagnosis name and ICD-9 code
                    # Look for pattern like "Diagnosis name (xxx.xx)"
                    icd9_pattern = r'\((\d{3}\.\d{1,2})\)'
                    icd9_match = re.search(icd9_pattern, line)
                    
                    if icd9_match:
                        # Extract diagnosis name (everything before the ICD-9 code)
                        diagnosis_with_code = line[:icd9_match.start()].strip()
                        diagnosis = re.sub(r'^[\d\.\-\•\*\s]+', '', diagnosis_with_code).strip()
                        if diagnosis:
                            diagnoses.append(f"{diagnosis} ({icd9_match.group(1)})")
                    else:
                        # Fallback to original logic if no ICD-9 code found
                        diagnosis = re.split(r'[:\-–—]', line)[0].strip()
                        diagnosis = re.sub(r'^[\d\.\-\•\*\s]+', '', diagnosis).strip()
                        if diagnosis:
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
"""
Medication agent for analyzing medications, checking interactions, and managing prescriptions.
"""

import logging
import re
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from .base import BaseAgent
from .models import AgentConfig, AgentTask, AgentResponse, ToolCall

if TYPE_CHECKING:
    from .ai_caller import AICallerProtocol


logger = logging.getLogger(__name__)


class MedicationAgent(BaseAgent):
    """Agent specialized in medication management, interaction checking, and prescription generation."""
    
    # Default configuration for medication agent
    DEFAULT_CONFIG = AgentConfig(
        name="MedicationAgent",
        description="Manages medications, checks interactions, and generates prescriptions",
        system_prompt="""You are a clinical pharmacology specialist with expertise in medication management.
        
Your role is to:
1. Extract and analyze medication information from clinical text
2. Check for drug-drug interactions and contraindications
3. Validate appropriate dosing based on patient factors
4. Suggest alternative medications when needed
5. Generate properly formatted prescription information
6. Provide medication counseling points

Guidelines:
- Always prioritize patient safety
- Include both generic and brand names when relevant
- Specify exact dosing, frequency, route, and duration
- Flag any potentially dangerous interactions as HIGH PRIORITY
- Consider patient-specific factors (age, weight, renal/hepatic function)
- Include relevant warnings and precautions
- Never recommend medications without appropriate clinical context
- Always emphasize the importance of clinical judgment

Format medication information as:
1. MEDICATION NAME: Generic (Brand)
2. DOSE: Amount and units
3. ROUTE: How administered
4. FREQUENCY: How often
5. DURATION: Length of treatment
6. INDICATION: Reason for use
7. WARNINGS: Important safety information
8. INTERACTIONS: With current medications
9. MONITORING: Required follow-up

For interaction checks, categorize as:
- CONTRAINDICATED: Do not use together
- MAJOR: Serious interaction, use alternative if possible
- MODERATE: Use with caution, monitor closely
- MINOR: Minimal risk, monitor for effects""",
        model="gpt-4",
        temperature=0.2,  # Lower temperature for medication accuracy
        max_tokens=600
    )
    
    def __init__(self, config: Optional[AgentConfig] = None, ai_caller: Optional['AICallerProtocol'] = None):
        """
        Initialize the medication agent.

        Args:
            config: Optional custom configuration. Uses default if not provided.
            ai_caller: Optional AI caller for dependency injection.
        """
        super().__init__(config or self.DEFAULT_CONFIG, ai_caller=ai_caller)
        
    def execute(self, task: AgentTask) -> AgentResponse:
        """
        Execute medication-related tasks.
        
        Args:
            task: Task containing medication query or clinical text
            
        Returns:
            AgentResponse with medication analysis
        """
        try:
            # Determine task type from task description or input data
            task_type = self._determine_task_type(task)
            
            if task_type == "extract":
                return self._extract_medications(task)
            elif task_type == "check_interactions":
                return self._check_interactions(task)
            elif task_type == "generate_prescription":
                return self._generate_prescription(task)
            elif task_type == "validate_dosing":
                return self._validate_dosing(task)
            elif task_type == "suggest_alternatives":
                return self._suggest_alternatives(task)
            else:
                # Default comprehensive analysis
                return self._comprehensive_analysis(task)
                
        except Exception as e:
            logger.error(f"Error in medication analysis: {e}")
            return AgentResponse(
                result="",
                success=False,
                error=str(e)
            )
    
    def _determine_task_type(self, task: AgentTask) -> str:
        """Determine the type of medication task from the task description."""
        task_desc = task.task_description.lower()
        
        if "extract" in task_desc or "identify" in task_desc:
            return "extract"
        elif "interaction" in task_desc or "check interaction" in task_desc:
            return "check_interactions"
        elif "prescription" in task_desc or "prescribe" in task_desc:
            return "generate_prescription"
        elif "dosing" in task_desc or "dose" in task_desc:
            return "validate_dosing"
        elif "alternative" in task_desc or "substitute" in task_desc:
            return "suggest_alternatives"
        else:
            return "comprehensive"
    
    def _extract_medications(self, task: AgentTask) -> AgentResponse:
        """Extract medications from clinical text."""
        clinical_text = task.input_data.get('clinical_text', '')
        soap_note = task.input_data.get('soap_note', '')
        
        text_to_analyze = clinical_text or soap_note
        if not text_to_analyze:
            return AgentResponse(
                result="",
                success=False,
                error="No clinical text provided for medication extraction"
            )
        
        prompt = self._build_extraction_prompt(text_to_analyze, task.context)
        
        # Call AI to extract medications
        extracted = self._call_ai(prompt)
        
        # Parse the extracted medications
        medications = self._parse_medication_list(extracted)
        
        # Create response
        response = AgentResponse(
            result=extracted,
            thoughts=f"Extracted {len(medications)} medications from clinical text",
            success=True,
            metadata={
                'medication_count': len(medications),
                'medications': medications,
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _check_interactions(self, task: AgentTask) -> AgentResponse:
        """Check for drug-drug interactions."""
        medications = task.input_data.get('medications', [])
        
        if not medications or len(medications) < 2:
            return AgentResponse(
                result="At least two medications are required for interaction checking",
                success=False,
                error="Insufficient medications for interaction check"
            )
        
        prompt = self._build_interaction_prompt(medications, task.context)
        
        # Call AI to check interactions
        interaction_analysis = self._call_ai(prompt)
        
        # Parse interaction severity
        has_major_interaction = any(
            severity in interaction_analysis.upper() 
            for severity in ["CONTRAINDICATED", "MAJOR", "SERIOUS"]
        )
        
        # Simulate tool call for drug interaction database
        tool_calls = [
            ToolCall(
                tool_name="lookup_drug_interactions",
                arguments={"medications": medications}
            )
        ]
        
        # Create response
        response = AgentResponse(
            result=interaction_analysis,
            thoughts=f"Analyzed interactions between {len(medications)} medications",
            tool_calls=tool_calls,
            success=True,
            metadata={
                'medication_count': len(medications),
                'has_major_interaction': has_major_interaction,
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _generate_prescription(self, task: AgentTask) -> AgentResponse:
        """Generate prescription information."""
        medication_info = task.input_data.get('medication', {})
        patient_info = task.input_data.get('patient_info', {})
        indication = task.input_data.get('indication', '')
        
        if not medication_info:
            return AgentResponse(
                result="",
                success=False,
                error="No medication information provided for prescription"
            )
        
        prompt = self._build_prescription_prompt(medication_info, patient_info, indication, task.context)
        
        # Call AI to generate prescription
        prescription = self._call_ai(prompt)
        
        # Create response
        response = AgentResponse(
            result=prescription,
            thoughts="Generated prescription with appropriate dosing and instructions",
            success=True,
            metadata={
                'medication': medication_info.get('name', 'Unknown'),
                'has_patient_info': bool(patient_info),
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _validate_dosing(self, task: AgentTask) -> AgentResponse:
        """Validate medication dosing."""
        medication = task.input_data.get('medication', {})
        patient_factors = task.input_data.get('patient_factors', {})
        
        if not medication:
            return AgentResponse(
                result="",
                success=False,
                error="No medication information provided for dosing validation"
            )
        
        prompt = self._build_dosing_prompt(medication, patient_factors, task.context)
        
        # Call AI to validate dosing
        validation = self._call_ai(prompt)
        
        # Check if dosing is appropriate
        is_appropriate = "appropriate" in validation.lower() and "inappropriate" not in validation.lower()
        
        # Create response
        response = AgentResponse(
            result=validation,
            thoughts="Validated medication dosing based on patient factors",
            success=True,
            metadata={
                'medication': medication.get('name', 'Unknown'),
                'dose': medication.get('dose', 'Unknown'),
                'dosing_appropriate': is_appropriate,
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _suggest_alternatives(self, task: AgentTask) -> AgentResponse:
        """Suggest alternative medications."""
        current_medication = task.input_data.get('current_medication', {})
        reason_for_change = task.input_data.get('reason', '')
        patient_factors = task.input_data.get('patient_factors', {})
        
        if not current_medication:
            return AgentResponse(
                result="",
                success=False,
                error="No current medication provided for alternative suggestions"
            )
        
        prompt = self._build_alternatives_prompt(
            current_medication, reason_for_change, patient_factors, task.context
        )
        
        # Call AI to suggest alternatives
        alternatives = self._call_ai(prompt)
        
        # Parse alternative count
        alternative_count = len(re.findall(r'\d+\.', alternatives))
        
        # Create response
        response = AgentResponse(
            result=alternatives,
            thoughts=f"Suggested {alternative_count} alternative medications",
            success=True,
            metadata={
                'current_medication': current_medication.get('name', 'Unknown'),
                'reason_for_change': reason_for_change,
                'alternative_count': alternative_count,
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _comprehensive_analysis(self, task: AgentTask) -> AgentResponse:
        """Perform comprehensive medication analysis."""
        clinical_text = task.input_data.get('clinical_text', '')
        soap_note = task.input_data.get('soap_note', '')
        current_medications = task.input_data.get('current_medications', [])
        patient_context = task.input_data.get('patient_context', {})

        text_to_analyze = clinical_text or soap_note

        prompt = self._build_comprehensive_prompt(
            text_to_analyze, current_medications, task.context, patient_context
        )
        
        # Call AI for comprehensive analysis
        analysis = self._call_ai(prompt)

        # Create response
        response = AgentResponse(
            result=analysis,
            thoughts="Performed comprehensive medication analysis",
            success=True,
            metadata={
                'analysis_type': 'comprehensive',
                'has_current_medications': bool(current_medications),
                'has_patient_context': bool(patient_context),
                'patient_age': patient_context.get('age'),
                'patient_allergies': patient_context.get('allergies', []),
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _build_extraction_prompt(self, text: str, context: Optional[str] = None) -> str:
        """Build prompt for medication extraction."""
        prompt_parts = []
        
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")
        
        prompt_parts.append("Extract all medications mentioned in the following clinical text.")
        prompt_parts.append("For each medication, identify:")
        prompt_parts.append("- Generic and brand names")
        prompt_parts.append("- Dosage and strength")
        prompt_parts.append("- Route of administration")
        prompt_parts.append("- Frequency")
        prompt_parts.append("- Duration or status (ongoing, discontinued, etc.)")
        prompt_parts.append("- Indication if mentioned\n")
        prompt_parts.append(f"Clinical Text:\n{text}\n")
        prompt_parts.append("Extracted Medications:")
        
        return "\n".join(prompt_parts)
    
    def _build_interaction_prompt(self, medications: List[str], context: Optional[str] = None) -> str:
        """Build prompt for interaction checking."""
        prompt_parts = []
        
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")
        
        prompt_parts.append("Check for drug-drug interactions between the following medications:")
        for med in medications:
            prompt_parts.append(f"- {med}")
        
        prompt_parts.append("\nFor each interaction found, specify:")
        prompt_parts.append("- The medications involved")
        prompt_parts.append("- Severity (Contraindicated/Major/Moderate/Minor)")
        prompt_parts.append("- Clinical significance")
        prompt_parts.append("- Recommended action")
        prompt_parts.append("- Monitoring requirements\n")
        prompt_parts.append("Drug Interaction Analysis:")
        
        return "\n".join(prompt_parts)
    
    def _build_prescription_prompt(
        self, 
        medication: Dict[str, Any], 
        patient_info: Dict[str, Any],
        indication: str,
        context: Optional[str] = None
    ) -> str:
        """Build prompt for prescription generation."""
        prompt_parts = []
        
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")
        
        prompt_parts.append("Generate prescription information for:")
        prompt_parts.append(f"Medication: {medication.get('name', 'Unknown')}")
        
        if indication:
            prompt_parts.append(f"Indication: {indication}")
        
        if patient_info:
            prompt_parts.append("\nPatient Information:")
            for key, value in patient_info.items():
                prompt_parts.append(f"- {key}: {value}")
        
        prompt_parts.append("\nProvide complete prescription details including:")
        prompt_parts.append("- Exact dosing with units")
        prompt_parts.append("- Route of administration")
        prompt_parts.append("- Frequency and timing")
        prompt_parts.append("- Duration of treatment")
        prompt_parts.append("- Quantity to dispense")
        prompt_parts.append("- Number of refills")
        prompt_parts.append("- Important instructions")
        prompt_parts.append("- Warnings and precautions\n")
        prompt_parts.append("Prescription:")
        
        return "\n".join(prompt_parts)
    
    def _build_dosing_prompt(
        self, 
        medication: Dict[str, Any], 
        patient_factors: Dict[str, Any],
        context: Optional[str] = None
    ) -> str:
        """Build prompt for dosing validation."""
        prompt_parts = []
        
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")
        
        prompt_parts.append("Validate the following medication dosing:")
        prompt_parts.append(f"Medication: {medication.get('name', 'Unknown')}")
        prompt_parts.append(f"Dose: {medication.get('dose', 'Unknown')}")
        prompt_parts.append(f"Frequency: {medication.get('frequency', 'Unknown')}")
        
        if medication.get('indication'):
            prompt_parts.append(f"Indication: {medication.get('indication')}")
        
        if patient_factors:
            prompt_parts.append("\nPatient Factors:")
            for key, value in patient_factors.items():
                prompt_parts.append(f"- {key}: {value}")
        
        prompt_parts.append("\nAssess whether the dosing is:")
        prompt_parts.append("- Appropriate for the indication")
        prompt_parts.append("- Safe given patient factors")
        prompt_parts.append("- Within recommended ranges")
        prompt_parts.append("\nIf adjustments needed, provide specific recommendations.")
        prompt_parts.append("\nDosing Assessment:")
        
        return "\n".join(prompt_parts)
    
    def _build_alternatives_prompt(
        self,
        current_medication: Dict[str, Any],
        reason: str,
        patient_factors: Dict[str, Any],
        context: Optional[str] = None
    ) -> str:
        """Build prompt for alternative suggestions."""
        prompt_parts = []
        
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")
        
        prompt_parts.append("Suggest alternative medications for:")
        prompt_parts.append(f"Current Medication: {current_medication.get('name', 'Unknown')}")
        prompt_parts.append(f"Reason for Change: {reason}")
        
        if patient_factors:
            prompt_parts.append("\nPatient Factors:")
            for key, value in patient_factors.items():
                prompt_parts.append(f"- {key}: {value}")
        
        prompt_parts.append("\nProvide 3-5 suitable alternatives with:")
        prompt_parts.append("- Generic and brand names")
        prompt_parts.append("- Recommended dosing")
        prompt_parts.append("- Advantages over current medication")
        prompt_parts.append("- Potential disadvantages")
        prompt_parts.append("- Cost considerations if relevant")
        prompt_parts.append("- Switching instructions\n")
        prompt_parts.append("Alternative Medications:")
        
        return "\n".join(prompt_parts)
    
    def _format_patient_context(self, patient_context: Dict[str, Any]) -> str:
        """
        Format patient context for inclusion in prompts.

        Args:
            patient_context: Dictionary with patient factors

        Returns:
            Formatted string for prompt inclusion, or empty string if no context
        """
        if not patient_context:
            return ""

        parts = ["\nPATIENT FACTORS (IMPORTANT - Consider these in your analysis):"]

        if 'age' in patient_context:
            age = patient_context['age']
            parts.append(f"- Age: {age} years")
            if age < 12:
                parts.append("  ⚠️ PEDIATRIC patient - use pediatric dosing")
            elif age >= 65:
                parts.append("  ⚠️ GERIATRIC patient - consider reduced dosing, increased fall risk")

        if 'weight_kg' in patient_context:
            weight = patient_context['weight_kg']
            parts.append(f"- Weight: {weight} kg")
            if weight < 50:
                parts.append("  ⚠️ Low body weight - may need dose reduction")

        if 'egfr' in patient_context:
            egfr = patient_context['egfr']
            parts.append(f"- eGFR: {egfr} mL/min")
            if egfr < 30:
                parts.append("  ⚠️ SEVERE renal impairment (CKD Stage 4-5) - significant dose adjustments likely needed")
            elif egfr < 60:
                parts.append("  ⚠️ MODERATE renal impairment (CKD Stage 3) - dose adjustments may be needed")
            elif egfr < 90:
                parts.append("  Note: Mild renal impairment (CKD Stage 2)")

        if 'hepatic_function' in patient_context:
            hepatic = patient_context['hepatic_function']
            parts.append(f"- Hepatic function: {hepatic}")
            if 'Child-Pugh C' in hepatic:
                parts.append("  ⚠️ SEVERE hepatic impairment - many medications contraindicated")
            elif 'Child-Pugh B' in hepatic:
                parts.append("  ⚠️ MODERATE hepatic impairment - significant dose reductions needed")
            elif 'Child-Pugh A' in hepatic:
                parts.append("  Note: Mild hepatic impairment - monitor closely")

        if 'allergies' in patient_context and patient_context['allergies']:
            allergies = patient_context['allergies']
            parts.append(f"- Known allergies: {', '.join(allergies)}")
            parts.append("  ⚠️ CHECK for cross-reactivity with any recommended medications!")

        return "\n".join(parts)

    def _build_comprehensive_prompt(
        self,
        text: str,
        current_medications: List[str],
        context: Optional[str] = None,
        patient_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build prompt for comprehensive analysis."""
        prompt_parts = []

        if context:
            prompt_parts.append(f"Additional Context: {context}\n")

        # Add patient context prominently at the top
        if patient_context:
            patient_info = self._format_patient_context(patient_context)
            if patient_info:
                prompt_parts.append(patient_info)

        prompt_parts.append("\nPerform a comprehensive medication analysis for the following:")

        if text:
            prompt_parts.append(f"\nClinical Text:\n{text}")

        if current_medications:
            prompt_parts.append("\nCurrent Medications:")
            for med in current_medications:
                prompt_parts.append(f"- {med}")

        prompt_parts.append("\nProvide analysis including:")
        prompt_parts.append("1. All medications mentioned or implied")
        prompt_parts.append("2. Potential drug interactions")
        prompt_parts.append("3. Dosing appropriateness (ESPECIALLY given patient factors above)")
        prompt_parts.append("4. Missing medications for conditions mentioned")
        prompt_parts.append("5. Optimization opportunities")
        prompt_parts.append("6. Safety concerns (CHECK ALLERGIES if provided)")
        prompt_parts.append("7. Monitoring requirements")
        if patient_context and patient_context.get('egfr'):
            prompt_parts.append("8. Renal dose adjustments needed")
        if patient_context and patient_context.get('hepatic_function'):
            prompt_parts.append("9. Hepatic dose adjustments needed")
        prompt_parts.append("\nComprehensive Medication Analysis:")

        return "\n".join(prompt_parts)
    
    def _parse_medication_list(self, text: str) -> List[Dict[str, str]]:
        """Parse extracted medications into structured format."""
        medications = []
        
        # Simple parsing - in production, would use more sophisticated NLP
        lines = text.strip().split('\n')
        current_med = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_med:
                    medications.append(current_med)
                    current_med = {}
                continue
            
            # Look for medication patterns
            if line.startswith('-') or line[0].isdigit():
                if current_med:
                    medications.append(current_med)
                # Extract medication name
                med_name = re.sub(r'^[-\d\.\s]+', '', line).strip()
                current_med = {'name': med_name, 'raw': line}
            elif ':' in line:
                # Extract property
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                current_med[key] = value.strip()
        
        if current_med:
            medications.append(current_med)
        
        return medications
    
    def extract_medications_from_text(self, text: str) -> List[Dict[str, str]]:
        """
        Convenience method to extract medications from text.
        
        Args:
            text: Clinical text containing medication information
            
        Returns:
            List of dictionaries containing medication information
        """
        task = AgentTask(
            task_description="Extract all medications from clinical text",
            input_data={"clinical_text": text}
        )
        
        response = self.execute(task)
        if response and response.success:
            return response.metadata.get('medications', [])
        return []
    
    def check_drug_interactions(self, medications: List[str]) -> Optional[str]:
        """
        Convenience method to check drug interactions.
        
        Args:
            medications: List of medication names to check
            
        Returns:
            Interaction analysis text if successful, None otherwise
        """
        task = AgentTask(
            task_description="Check for drug-drug interactions",
            input_data={"medications": medications}
        )
        
        response = self.execute(task)
        if response and response.success:
            return response.result
        return None
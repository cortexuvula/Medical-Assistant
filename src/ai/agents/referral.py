"""
Referral agent for generating professional medical referral letters.
"""

import logging
import re
from typing import Optional, List, Dict, Any
from datetime import datetime

from .base import BaseAgent
from .models import AgentConfig, AgentTask, AgentResponse, ToolCall


logger = logging.getLogger(__name__)


class ReferralAgent(BaseAgent):
    """Agent specialized in generating professional medical referral letters."""
    
    # Default configuration for referral agent
    DEFAULT_CONFIG = AgentConfig(
        name="ReferralAgent",
        description="Generates professional medical referral letters",
        system_prompt="""You are a medical referral specialist with expertise in creating professional, comprehensive referral letters.

Your role is to:
1. Generate clear, concise referral letters that communicate essential patient information
2. Include relevant clinical history, current medications, and recent test results
3. Clearly state the reason for referral and specific questions to be addressed
4. Specify the appropriate urgency level based on clinical findings
5. Format letters professionally according to medical communication standards
6. Ensure all critical information is included for continuity of care

Guidelines:
- Use professional medical language appropriate for physician-to-physician communication
- Be concise but comprehensive - include all relevant information
- Clearly state the primary reason for referral in the opening paragraph
- Include pertinent positive and negative findings
- List current medications with dosages
- Mention recent relevant investigations and their results
- Specify any urgent concerns that require expedited attention
- End with specific questions or requests for the specialist
- Always include sender's contact information for follow-up

Format the referral letter with:
1. Date and recipient information
2. Patient demographics (name, DOB, MRN if available)
3. Opening paragraph with reason for referral
4. Clinical history and examination findings
5. Current medications
6. Recent investigations
7. Specific questions/requests
8. Urgency level
9. Sender's information and contact details""",
        model="gpt-4",
        temperature=0.3,  # Lower temperature for professional consistency
        max_tokens=500
    )
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize the referral agent.
        
        Args:
            config: Optional custom configuration. Uses default if not provided.
        """
        super().__init__(config or self.DEFAULT_CONFIG)
        
    def execute(self, task: AgentTask) -> AgentResponse:
        """
        Execute referral generation tasks.
        
        Args:
            task: Task containing clinical information and referral requirements
            
        Returns:
            AgentResponse with generated referral letter
        """
        try:
            # Determine referral type from task
            referral_type = self._determine_referral_type(task)
            
            if referral_type == "specialist":
                return self._generate_specialist_referral(task)
            elif referral_type == "urgent":
                return self._generate_urgent_referral(task)
            elif referral_type == "follow_up":
                return self._generate_followup_referral(task)
            elif referral_type == "diagnostic":
                return self._generate_diagnostic_referral(task)
            else:
                # Default standard referral
                return self._generate_standard_referral(task)
                
        except Exception as e:
            logger.error(f"Error generating referral: {e}")
            return AgentResponse(
                result="",
                success=False,
                error=str(e)
            )
    
    def _determine_referral_type(self, task: AgentTask) -> str:
        """Determine the type of referral from the task description."""
        task_desc = task.task_description.lower()
        
        if "urgent" in task_desc or "emergency" in task_desc:
            return "urgent"
        elif "specialist" in task_desc or "specialty" in task_desc:
            return "specialist"
        elif "follow" in task_desc or "follow-up" in task_desc:
            return "follow_up"
        elif "diagnostic" in task_desc or "investigation" in task_desc:
            return "diagnostic"
        else:
            return "standard"
    
    def _generate_standard_referral(self, task: AgentTask) -> AgentResponse:
        """Generate a standard referral letter."""
        soap_note = task.input_data.get('soap_note', '')
        transcript = task.input_data.get('transcript', '')
        conditions = task.input_data.get('conditions', '')
        
        # Use SOAP note if available, otherwise use transcript
        source_text = soap_note or transcript
        if not source_text:
            return AgentResponse(
                result="",
                success=False,
                error="No clinical information provided for referral generation"
            )
        
        prompt = self._build_standard_referral_prompt(source_text, conditions, task.context)
        
        # Call AI to generate referral
        referral_letter = self._call_ai(prompt)
        
        # Extract metadata
        urgency = self._extract_urgency(referral_letter)
        specialty = self._extract_specialty(referral_letter)
        
        # Create response
        response = AgentResponse(
            result=referral_letter,
            thoughts=f"Generated standard referral letter{f' for {conditions}' if conditions else ''}",
            success=True,
            metadata={
                'referral_type': 'standard',
                'urgency_level': urgency,
                'specialty': specialty,
                'has_conditions': bool(conditions),
                'source': 'soap_note' if soap_note else 'transcript',
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _generate_specialist_referral(self, task: AgentTask) -> AgentResponse:
        """Generate a specialist-specific referral."""
        specialty = task.input_data.get('specialty', '')
        clinical_info = task.input_data.get('clinical_info', '')
        specific_concerns = task.input_data.get('specific_concerns', '')
        
        if not clinical_info:
            return AgentResponse(
                result="",
                success=False,
                error="No clinical information provided for specialist referral"
            )
        
        prompt = self._build_specialist_referral_prompt(
            clinical_info, specialty, specific_concerns, task.context
        )
        
        # Call AI to generate referral
        referral_letter = self._call_ai(prompt)
        
        # Create response
        response = AgentResponse(
            result=referral_letter,
            thoughts=f"Generated specialist referral to {specialty or 'specialist'}",
            success=True,
            metadata={
                'referral_type': 'specialist',
                'specialty': specialty,
                'has_specific_concerns': bool(specific_concerns),
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _generate_urgent_referral(self, task: AgentTask) -> AgentResponse:
        """Generate an urgent referral letter."""
        clinical_info = task.input_data.get('clinical_info', '')
        red_flags = task.input_data.get('red_flags', [])
        
        if not clinical_info:
            return AgentResponse(
                result="",
                success=False,
                error="No clinical information provided for urgent referral"
            )
        
        prompt = self._build_urgent_referral_prompt(clinical_info, red_flags, task.context)
        
        # Call AI to generate referral
        referral_letter = self._call_ai(prompt)
        
        # Simulate tool call for urgent notification
        tool_calls = [
            ToolCall(
                tool_name="send_urgent_notification",
                arguments={"priority": "high", "red_flags": red_flags}
            )
        ]
        
        # Create response
        response = AgentResponse(
            result=referral_letter,
            thoughts="Generated URGENT referral letter with red flag indicators",
            tool_calls=tool_calls,
            success=True,
            metadata={
                'referral_type': 'urgent',
                'urgency_level': 'urgent',
                'red_flag_count': len(red_flags),
                'red_flags': red_flags,
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _generate_followup_referral(self, task: AgentTask) -> AgentResponse:
        """Generate a follow-up referral letter."""
        initial_referral = task.input_data.get('initial_referral', '')
        progress_notes = task.input_data.get('progress_notes', '')
        current_status = task.input_data.get('current_status', '')
        
        prompt = self._build_followup_referral_prompt(
            initial_referral, progress_notes, current_status, task.context
        )
        
        # Call AI to generate referral
        referral_letter = self._call_ai(prompt)
        
        # Create response
        response = AgentResponse(
            result=referral_letter,
            thoughts="Generated follow-up referral letter",
            success=True,
            metadata={
                'referral_type': 'follow_up',
                'has_initial_referral': bool(initial_referral),
                'has_progress_notes': bool(progress_notes),
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _generate_diagnostic_referral(self, task: AgentTask) -> AgentResponse:
        """Generate a referral for diagnostic procedures."""
        clinical_info = task.input_data.get('clinical_info', '')
        requested_tests = task.input_data.get('requested_tests', [])
        clinical_question = task.input_data.get('clinical_question', '')
        
        if not clinical_info:
            return AgentResponse(
                result="",
                success=False,
                error="No clinical information provided for diagnostic referral"
            )
        
        prompt = self._build_diagnostic_referral_prompt(
            clinical_info, requested_tests, clinical_question, task.context
        )
        
        # Call AI to generate referral
        referral_letter = self._call_ai(prompt)
        
        # Create response
        response = AgentResponse(
            result=referral_letter,
            thoughts=f"Generated diagnostic referral for {len(requested_tests)} tests",
            success=True,
            metadata={
                'referral_type': 'diagnostic',
                'test_count': len(requested_tests),
                'tests_requested': requested_tests,
                'has_clinical_question': bool(clinical_question),
                'model_used': self.config.model
            }
        )
        
        # Add to history
        self.add_to_history(task, response)
        
        return response
    
    def _build_standard_referral_prompt(self, source_text: str, conditions: str, context: Optional[str] = None) -> str:
        """Build prompt for standard referral."""
        prompt_parts = []
        
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")
        
        prompt_parts.append("Generate a professional referral letter based on the following clinical information.")
        
        if conditions:
            prompt_parts.append(f"Focus specifically on these conditions: {conditions}")
        
        prompt_parts.append(f"\nClinical Information:\n{source_text}\n")
        
        prompt_parts.append("Include in the referral letter:")
        prompt_parts.append("- Current date")
        prompt_parts.append("- Appropriate greeting to specialist colleague")
        prompt_parts.append("- Patient demographics")
        prompt_parts.append("- Clear reason for referral")
        prompt_parts.append("- Relevant clinical history")
        prompt_parts.append("- Physical examination findings")
        prompt_parts.append("- Current medications")
        prompt_parts.append("- Recent investigations and results")
        prompt_parts.append("- Specific questions or requests")
        prompt_parts.append("- Appropriate urgency level")
        prompt_parts.append("- Professional closing with sender information\n")
        prompt_parts.append("Referral Letter:")
        
        return "\n".join(prompt_parts)
    
    def _build_specialist_referral_prompt(
        self, 
        clinical_info: str, 
        specialty: str, 
        specific_concerns: str,
        context: Optional[str] = None
    ) -> str:
        """Build prompt for specialist referral."""
        prompt_parts = []
        
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")
        
        prompt_parts.append(f"Generate a professional referral letter to a {specialty} specialist.")
        
        if specific_concerns:
            prompt_parts.append(f"Specific concerns to address: {specific_concerns}")
        
        prompt_parts.append(f"\nClinical Information:\n{clinical_info}\n")
        
        prompt_parts.append(f"Tailor the referral specifically for {specialty} consultation, including:")
        prompt_parts.append(f"- Relevant history specific to {specialty}")
        prompt_parts.append(f"- Pertinent examination findings for {specialty}")
        prompt_parts.append(f"- Previous {specialty}-related treatments or consultations")
        prompt_parts.append(f"- Specific questions for the {specialty} specialist")
        prompt_parts.append("- Appropriate urgency based on clinical findings\n")
        prompt_parts.append("Specialist Referral Letter:")
        
        return "\n".join(prompt_parts)
    
    def _build_urgent_referral_prompt(
        self, 
        clinical_info: str, 
        red_flags: List[str],
        context: Optional[str] = None
    ) -> str:
        """Build prompt for urgent referral."""
        prompt_parts = []
        
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")
        
        prompt_parts.append("Generate an URGENT referral letter that requires immediate attention.")
        
        if red_flags:
            prompt_parts.append("Red flag symptoms/signs:")
            for flag in red_flags:
                prompt_parts.append(f"- {flag}")
        
        prompt_parts.append(f"\nClinical Information:\n{clinical_info}\n")
        
        prompt_parts.append("Create an urgent referral that:")
        prompt_parts.append("- Clearly states URGENT in the subject/header")
        prompt_parts.append("- Highlights red flag symptoms prominently")
        prompt_parts.append("- Provides concise but complete clinical summary")
        prompt_parts.append("- Specifies immediate actions needed")
        prompt_parts.append("- Includes direct contact information")
        prompt_parts.append("- Requests expedited appointment/assessment\n")
        prompt_parts.append("Urgent Referral Letter:")
        
        return "\n".join(prompt_parts)
    
    def _build_followup_referral_prompt(
        self,
        initial_referral: str,
        progress_notes: str,
        current_status: str,
        context: Optional[str] = None
    ) -> str:
        """Build prompt for follow-up referral."""
        prompt_parts = []
        
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")
        
        prompt_parts.append("Generate a follow-up referral letter.")
        
        if initial_referral:
            prompt_parts.append(f"Initial Referral Information:\n{initial_referral}\n")
        
        if progress_notes:
            prompt_parts.append(f"Progress Since Initial Referral:\n{progress_notes}\n")
        
        if current_status:
            prompt_parts.append(f"Current Status:\n{current_status}\n")
        
        prompt_parts.append("Create a follow-up referral that:")
        prompt_parts.append("- References the initial referral and date")
        prompt_parts.append("- Summarizes treatment/progress since last referral")
        prompt_parts.append("- Describes current status and concerns")
        prompt_parts.append("- Specifies reason for continued/renewed referral")
        prompt_parts.append("- Updates any changes in medications or conditions")
        prompt_parts.append("- Includes new questions or concerns\n")
        prompt_parts.append("Follow-up Referral Letter:")
        
        return "\n".join(prompt_parts)
    
    def _build_diagnostic_referral_prompt(
        self,
        clinical_info: str,
        requested_tests: List[str],
        clinical_question: str,
        context: Optional[str] = None
    ) -> str:
        """Build prompt for diagnostic referral."""
        prompt_parts = []
        
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")
        
        prompt_parts.append("Generate a referral letter for diagnostic procedures/investigations.")
        
        if clinical_question:
            prompt_parts.append(f"Clinical Question: {clinical_question}")
        
        if requested_tests:
            prompt_parts.append("Requested Investigations:")
            for test in requested_tests:
                prompt_parts.append(f"- {test}")
        
        prompt_parts.append(f"\nClinical Information:\n{clinical_info}\n")
        
        prompt_parts.append("Create a diagnostic referral that:")
        prompt_parts.append("- Clearly states the clinical question to be answered")
        prompt_parts.append("- Provides relevant clinical context for interpretation")
        prompt_parts.append("- Specifies exact tests/procedures requested")
        prompt_parts.append("- Includes pertinent positive and negative findings")
        prompt_parts.append("- Notes any contraindications or precautions")
        prompt_parts.append("- Indicates urgency of results needed\n")
        prompt_parts.append("Diagnostic Referral Letter:")
        
        return "\n".join(prompt_parts)
    
    def _extract_urgency(self, referral_text: str) -> str:
        """Extract urgency level from referral text."""
        text_lower = referral_text.lower()
        
        if any(word in text_lower for word in ["urgent", "emergency", "immediate", "stat"]):
            return "urgent"
        elif any(word in text_lower for word in ["soon", "expedite", "priority"]):
            return "high"
        elif any(word in text_lower for word in ["routine", "elective"]):
            return "routine"
        else:
            return "standard"
    
    def _extract_specialty(self, referral_text: str) -> Optional[str]:
        """Extract specialty from referral text."""
        # Common medical specialties
        specialties = [
            "cardiology", "neurology", "gastroenterology", "endocrinology",
            "rheumatology", "nephrology", "pulmonology", "hematology",
            "oncology", "psychiatry", "orthopedics", "dermatology",
            "ophthalmology", "otolaryngology", "urology", "gynecology",
            "radiology", "pathology", "anesthesiology", "emergency"
        ]
        
        text_lower = referral_text.lower()
        for specialty in specialties:
            if specialty in text_lower:
                return specialty.capitalize()
        
        return None
    
    def generate_referral_from_soap(self, soap_note: str, conditions: Optional[str] = None) -> Optional[str]:
        """
        Convenience method to generate a referral from a SOAP note.
        
        Args:
            soap_note: The SOAP note text
            conditions: Optional specific conditions to focus on
            
        Returns:
            Generated referral letter if successful, None otherwise
        """
        task = AgentTask(
            task_description="Generate referral letter from SOAP note",
            input_data={
                "soap_note": soap_note,
                "conditions": conditions or ""
            }
        )
        
        response = self.execute(task)
        if response and response.success:
            return response.result
        return None
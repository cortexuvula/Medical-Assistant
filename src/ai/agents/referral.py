"""
Referral agent for generating professional medical referral letters.

Supports multiple recipient types with tailored formatting:
- specialist: Consulting specialist referral
- gp_backreferral: Back-referral to referring GP
- hospital: Hospital/ER admission request
- diagnostic: Diagnostic services request
"""

import logging
import re
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from datetime import datetime
from enum import Enum

from .base import BaseAgent
from .models import AgentConfig, AgentTask, AgentResponse, ToolCall

if TYPE_CHECKING:
    from .ai_caller import AICallerProtocol


logger = logging.getLogger(__name__)


class ReferralRecipientType(Enum):
    """Types of referral recipients with different formatting needs."""
    SPECIALIST = "specialist"
    GP_BACKREFERRAL = "gp_backreferral"
    HOSPITAL = "hospital"
    DIAGNOSTIC = "diagnostic"


class UrgencyLevel(Enum):
    """Urgency levels for referrals."""
    ROUTINE = "routine"
    SOON = "soon"
    URGENT = "urgent"
    EMERGENCY = "emergency"


class ReferralAgent(BaseAgent):
    """Agent specialized in generating professional medical referral letters."""
    
    # Default configuration for referral agent
    DEFAULT_CONFIG = AgentConfig(
        name="ReferralAgent",
        description="Generates professional medical referral letters",
        system_prompt="""You are a medical referral specialist with expertise in creating professional, focused referral letters.

Your role is to:
1. Generate clear, concise referral letters focused ONLY on the specified condition(s)
2. EXCLUDE information about unrelated medical conditions or comorbidities
3. Include ONLY relevant clinical history, medications, and test results for the referral reason
4. Clearly state the reason for referral and specific questions to be addressed
5. Format letters professionally according to medical communication standards

CRITICAL RULE - CONDITION FILTERING:
When specific conditions are provided for the referral, you MUST:
- ONLY include information directly relevant to those conditions
- OMIT all other diagnoses, conditions, and comorbidities
- ONLY list medications relevant to the specified condition(s)
- ONLY mention investigations/results relevant to the specified condition(s)
- The receiving specialist does NOT need to know about unrelated health issues

Example: If referring for BPH to a urologist, do NOT include information about hypertension, diabetes, or other unrelated conditions unless they directly impact the urological assessment.

Guidelines:
- Use professional medical language appropriate for physician-to-physician communication
- Be focused and relevant - only include information pertinent to the referral reason
- Clearly state the primary reason for referral in the opening paragraph
- Include pertinent positive and negative findings for the specified condition(s)
- Only list medications relevant to the condition being referred
- Only mention investigations relevant to the referral reason
- End with specific questions or requests for the specialist

Format the referral letter with:
1. Date and recipient information
2. Patient demographics (name, DOB, contact)
3. Opening paragraph with specific reason for referral
4. Clinical history relevant to the referral condition ONLY
5. Examination findings relevant to the referral condition ONLY
6. Relevant medications (if applicable to the condition)
7. Relevant investigations (if applicable to the condition)
8. Specific questions/requests for the specialist
9. Urgency level
10. Sender's information and contact details""",
        model="gpt-4",
        temperature=0.3,  # Lower temperature for professional consistency
        max_tokens=1000  # Increased for comprehensive referral letters
    )
    
    def __init__(self, config: Optional[AgentConfig] = None, ai_caller: Optional['AICallerProtocol'] = None):
        """
        Initialize the referral agent.

        Args:
            config: Optional custom configuration. Uses default if not provided.
            ai_caller: Optional AI caller for dependency injection.
        """
        super().__init__(config or self.DEFAULT_CONFIG, ai_caller=ai_caller)
        
    def execute(self, task: AgentTask) -> AgentResponse:
        """
        Execute referral generation tasks.

        Args:
            task: Task containing clinical information and referral requirements

        Returns:
            AgentResponse with generated referral letter
        """
        try:
            # If we have soap_note or transcript in input, use the standard referral
            # which handles all the recipient-aware logic correctly
            has_new_style_input = (
                task.input_data.get('soap_note') or
                task.input_data.get('transcript') or
                task.input_data.get('recipient_type')
            )

            if has_new_style_input:
                # Use the comprehensive standard referral method
                return self._generate_standard_referral(task)

            # Legacy routing for backward compatibility with old-style input
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
        """Generate a standard referral letter.

        Supports enhanced recipient-aware generation when recipient_type is provided.

        Input data fields:
            - soap_note: SOAP note text (optional, preferred over transcript)
            - transcript: Transcript text (optional, fallback if no SOAP)
            - conditions: Conditions to focus on (optional)
            - recipient_type: Type of recipient - specialist, gp_backreferral, hospital, diagnostic (optional)
            - urgency: Urgency level - routine, soon, urgent, emergency (optional)
            - specialty: Target specialty (optional, can be auto-inferred)
            - recipient_details: Dict with name, facility, fax, etc. (optional)
        """
        soap_note = task.input_data.get('soap_note', '')
        transcript = task.input_data.get('transcript', '')
        conditions = task.input_data.get('conditions', '')
        recipient_type = task.input_data.get('recipient_type', 'specialist')
        input_urgency = task.input_data.get('urgency', 'routine')
        specialty = task.input_data.get('specialty', '')
        recipient_details = task.input_data.get('recipient_details', {})

        # Use SOAP note if available, otherwise use transcript
        source_text = soap_note or transcript
        if not source_text:
            return AgentResponse(
                result="",
                success=False,
                error="No clinical information provided for referral generation"
            )

        # Infer specialty from conditions if not provided
        inferred_specialty = specialty or self._infer_specialty_from_conditions(conditions)

        # Use recipient-aware prompt if recipient_type is provided
        if recipient_type and recipient_type != 'specialist':
            # Use the enhanced recipient-aware prompt builder
            prompt = self._build_recipient_aware_prompt(
                source_text=source_text,
                conditions=conditions,
                recipient_type=recipient_type,
                urgency=input_urgency,
                specialty=inferred_specialty,
                recipient_details=recipient_details,
                context=task.context
            )
        else:
            # Use standard specialist referral prompt
            prompt = self._build_standard_referral_prompt(
                source_text, conditions, task.context, inferred_specialty
            )

        # Call AI to generate referral
        referral_letter = self._call_ai(prompt)

        # Extract metadata - prefer provided values, fall back to extraction
        final_urgency = input_urgency if input_urgency != 'routine' else self._extract_urgency(referral_letter)
        final_specialty = inferred_specialty or self._extract_specialty(referral_letter)

        # Determine referral type label for metadata
        recipient_type_labels = {
            'specialist': 'specialist_consultation',
            'gp_backreferral': 'gp_back_referral',
            'hospital': 'hospital_admission',
            'diagnostic': 'diagnostic_request'
        }

        # Create response
        response = AgentResponse(
            result=referral_letter,
            thoughts=f"Generated {recipient_type} referral{f' for {conditions}' if conditions else ''}",
            success=True,
            metadata={
                'referral_type': recipient_type_labels.get(recipient_type, 'standard'),
                'recipient_type': recipient_type,
                'urgency_level': final_urgency,
                'specialty': final_specialty,
                'has_conditions': bool(conditions),
                'conditions': conditions,
                'source': 'soap_note' if soap_note else 'transcript',
                'recipient_name': recipient_details.get('name', ''),
                'recipient_facility': recipient_details.get('facility', ''),
                'model_used': self.config.model
            }
        )

        # Add to history
        self.add_to_history(task, response)

        return response
    
    def _generate_specialist_referral(self, task: AgentTask) -> AgentResponse:
        """Generate a specialist-specific referral."""
        specialty = task.input_data.get('specialty', '')
        # Support both old field name and new field names
        soap_note = task.input_data.get('soap_note', '')
        transcript = task.input_data.get('transcript', '')
        clinical_info = task.input_data.get('clinical_info', '') or soap_note or transcript
        specific_concerns = task.input_data.get('specific_concerns', '') or task.input_data.get('conditions', '')

        logger.debug(f"_generate_specialist_referral input_data keys: {list(task.input_data.keys())}")
        logger.debug(f"soap_note length: {len(soap_note)}, transcript length: {len(transcript)}, clinical_info length: {len(clinical_info)}")

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
        # Support both old field name and new field names
        soap_note = task.input_data.get('soap_note', '')
        transcript = task.input_data.get('transcript', '')
        clinical_info = task.input_data.get('clinical_info', '') or soap_note or transcript
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
        # Support both old field name and new field names
        soap_note = task.input_data.get('soap_note', '')
        transcript = task.input_data.get('transcript', '')
        clinical_info = task.input_data.get('clinical_info', '') or soap_note or transcript
        requested_tests = task.input_data.get('requested_tests', [])
        clinical_question = task.input_data.get('clinical_question', '') or task.input_data.get('conditions', '')

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
    
    def _build_standard_referral_prompt(
        self,
        source_text: str,
        conditions: str,
        context: Optional[str] = None,
        specialty: Optional[str] = None
    ) -> str:
        """Build prompt for standard referral."""
        prompt_parts = []

        if context:
            prompt_parts.append(f"Additional Context: {context}\n")

        # Include specialty in the opening if inferred
        if specialty:
            prompt_parts.append(f"Generate a professional referral letter to a {specialty} specialist based on the following clinical information.")
        else:
            prompt_parts.append("Generate a professional referral letter based on the following clinical information.")

        if conditions:
            # Strong filtering instructions for focused referral
            prompt_parts.append(f"\n**CRITICAL INSTRUCTION - CONDITION FOCUS:**")
            prompt_parts.append(f"This referral is ONLY for: {conditions}")
            if specialty:
                prompt_parts.append(f"The receiving specialist is a {specialty} specialist.")
            prompt_parts.append("You MUST:")
            prompt_parts.append("- ONLY include information directly relevant to the specified condition(s)")
            prompt_parts.append("- EXCLUDE any other medical conditions, diagnoses, or problems not related to the referral reason")
            prompt_parts.append("- ONLY include medications relevant to the specified condition(s)")
            prompt_parts.append("- ONLY include investigations/tests relevant to the specified condition(s)")
            prompt_parts.append("- DO NOT mention unrelated comorbidities or concurrent diagnoses")
            prompt_parts.append("- The specialist only needs information pertinent to their evaluation")
            prompt_parts.append("")

        prompt_parts.append(f"\nClinical Information (extract ONLY relevant details):\n{source_text}\n")

        prompt_parts.append("Include in the referral letter:")
        prompt_parts.append("- Current date")
        prompt_parts.append("- Appropriate greeting to specialist colleague")
        prompt_parts.append("- Patient demographics (name, DOB, contact)")
        prompt_parts.append("- Clear reason for referral (ONLY the specified condition)")
        if conditions:
            prompt_parts.append(f"- Clinical history ONLY related to: {conditions}")
            prompt_parts.append(f"- Physical examination findings ONLY related to: {conditions}")
            prompt_parts.append(f"- Medications ONLY if relevant to: {conditions}")
            prompt_parts.append(f"- Investigations ONLY related to: {conditions}")
        else:
            prompt_parts.append("- Relevant clinical history")
            prompt_parts.append("- Physical examination findings")
            prompt_parts.append("- Current medications")
            prompt_parts.append("- Recent investigations and results")
        prompt_parts.append("- Specific questions or requests for the specialist")
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

    def _infer_specialty_from_conditions(self, conditions: str) -> Optional[str]:
        """Infer the appropriate specialty based on condition keywords."""
        if not conditions:
            return None

        conditions_lower = conditions.lower()

        # Condition to specialty mapping
        specialty_mappings = {
            "urology": [
                "bph", "benign prostatic", "prostate", "urinary", "bladder",
                "kidney stone", "renal calculi", "hematuria", "incontinence",
                "erectile", "testicular", "scrotal", "uti", "pyelonephritis"
            ],
            "cardiology": [
                "hypertension", "heart", "cardiac", "arrhythmia", "afib",
                "atrial fibrillation", "chest pain", "angina", "heart failure",
                "chf", "coronary", "murmur", "palpitation", "bradycardia",
                "tachycardia", "valve", "cardiomyopathy"
            ],
            "gastroenterology": [
                "gerd", "reflux", "ibs", "crohn", "colitis", "hepatitis",
                "cirrhosis", "pancreatitis", "gallbladder", "dysphagia",
                "gi bleed", "hemorrhoid", "diverticulitis", "celiac"
            ],
            "neurology": [
                "headache", "migraine", "seizure", "epilepsy", "stroke",
                "parkinson", "tremor", "neuropathy", "multiple sclerosis",
                "dementia", "alzheimer", "vertigo", "tia"
            ],
            "endocrinology": [
                "diabetes", "thyroid", "hypothyroid", "hyperthyroid",
                "cushing", "addison", "pituitary", "adrenal", "osteoporosis",
                "pcos", "hormone"
            ],
            "pulmonology": [
                "asthma", "copd", "pneumonia", "pulmonary", "lung",
                "bronchitis", "sleep apnea", "osa", "shortness of breath",
                "dyspnea", "pleural", "interstitial"
            ],
            "rheumatology": [
                "arthritis", "rheumatoid", "lupus", "sle", "gout",
                "fibromyalgia", "scleroderma", "vasculitis", "sjogren"
            ],
            "orthopedics": [
                "fracture", "joint pain", "knee", "hip replacement",
                "rotator cuff", "back pain", "spine", "disc", "meniscus",
                "ligament", "acl", "osteoarthritis"
            ],
            "dermatology": [
                "rash", "eczema", "psoriasis", "skin cancer", "melanoma",
                "acne", "dermatitis", "skin lesion", "mole"
            ],
            "psychiatry": [
                "depression", "anxiety", "bipolar", "schizophrenia",
                "ptsd", "ocd", "adhd", "eating disorder", "substance"
            ],
            "ophthalmology": [
                "cataract", "glaucoma", "macular", "diabetic retinopathy",
                "vision loss", "eye"
            ],
            "otolaryngology": [
                "hearing loss", "tinnitus", "sinusitis", "tonsil",
                "sleep apnea", "deviated septum", "ear infection"
            ],
            "nephrology": [
                "chronic kidney", "ckd", "renal failure", "dialysis",
                "proteinuria", "glomerulonephritis"
            ],
            "hematology": [
                "anemia", "bleeding disorder", "leukemia", "lymphoma",
                "thrombocytopenia", "clotting"
            ],
            "oncology": [
                "cancer", "tumor", "malignancy", "chemotherapy",
                "radiation therapy", "metastasis"
            ]
        }

        for specialty, keywords in specialty_mappings.items():
            for keyword in keywords:
                if keyword in conditions_lower:
                    return specialty.capitalize()

        return None

    def _get_referral_recipient_guidance(self, recipient_type: str) -> Dict[str, Any]:
        """Get recipient-specific guidance for referral generation.

        Args:
            recipient_type: Type of recipient (specialist, gp_backreferral, hospital, diagnostic)

        Returns:
            Dictionary with focus, exclude, tone, and format guidance
        """
        guidance = {
            "specialist": {
                "focus": [
                    "Specific condition being referred",
                    "Relevant history only for the referred condition",
                    "Pertinent examination findings",
                    "Previous treatments tried",
                    "Specific questions for the specialist"
                ],
                "exclude": [
                    "Unrelated comorbidities",
                    "Social history unless directly relevant",
                    "Medications unrelated to the referred condition"
                ],
                "tone": "Professional physician-to-physician communication",
                "format": "Formal referral letter with demographics, clinical summary, and specific request",
                "opening": "Thank you for seeing this patient for evaluation and management of",
                "closing": "I would appreciate your expert opinion and recommendations regarding"
            },
            "gp_backreferral": {
                "focus": [
                    "Summary of treatment provided",
                    "Current clinical status",
                    "Ongoing management recommendations",
                    "Follow-up requirements and timeline",
                    "Red flags to watch for",
                    "When to re-refer"
                ],
                "exclude": [
                    "Detailed specialist workup unless relevant to GP management",
                    "Technical jargon that may be specialty-specific"
                ],
                "tone": "Collegial summary with clear handover",
                "format": "Consultation summary with management plan and contingencies",
                "opening": "Thank you for referring this patient. I am returning them to your care with the following summary",
                "closing": "Please do not hesitate to re-refer if"
            },
            "hospital": {
                "focus": [
                    "Admission criteria met",
                    "Acute clinical issues requiring inpatient care",
                    "Urgency level and reason",
                    "Immediate management needs",
                    "Key investigations and results"
                ],
                "exclude": [
                    "Routine chronic conditions unless relevant to admission",
                    "Extensive past history"
                ],
                "tone": "Concise and actionable",
                "format": "Admission request with clear reason, urgency, and immediate needs",
                "opening": "I am requesting admission for this patient due to",
                "closing": "Immediate priorities include"
            },
            "diagnostic": {
                "focus": [
                    "Clinical question to be answered",
                    "Relevant clinical findings supporting the request",
                    "Specific test or procedure requested",
                    "Urgency of results needed"
                ],
                "exclude": [
                    "Extensive history unless relevant to interpretation",
                    "Unrelated clinical information"
                ],
                "tone": "Request form style, clear and specific",
                "format": "Diagnostic request with clinical context for interpretation",
                "opening": "Please perform the following investigation(s)",
                "closing": "Clinical question: "
            }
        }
        return guidance.get(recipient_type, guidance["specialist"])

    def _build_recipient_aware_prompt(
        self,
        source_text: str,
        conditions: str,
        recipient_type: str,
        urgency: str,
        specialty: Optional[str] = None,
        recipient_details: Optional[Dict[str, str]] = None,
        context: Optional[str] = None
    ) -> str:
        """Build a referral prompt tailored to the recipient type.

        Args:
            source_text: The clinical source text (SOAP or transcript)
            conditions: Conditions to focus on
            recipient_type: Type of recipient (specialist, gp_backreferral, hospital, diagnostic)
            urgency: Urgency level (routine, soon, urgent, emergency)
            specialty: Target specialty (optional, for specialist referrals)
            recipient_details: Details about the recipient (name, facility, etc.)
            context: Additional context

        Returns:
            Formatted prompt string
        """
        guidance = self._get_referral_recipient_guidance(recipient_type)
        prompt_parts = []

        # Add context if provided
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")

        # Recipient details header
        if recipient_details:
            if recipient_details.get("name"):
                prompt_parts.append(f"Recipient: {recipient_details['name']}")
            if recipient_details.get("facility"):
                prompt_parts.append(f"Facility: {recipient_details['facility']}")
            prompt_parts.append("")

        # Type-specific opening
        if recipient_type == "specialist" and specialty:
            prompt_parts.append(f"Generate a professional referral letter to a {specialty} specialist.")
        elif recipient_type == "gp_backreferral":
            prompt_parts.append("Generate a back-referral letter to the referring GP/family physician.")
        elif recipient_type == "hospital":
            prompt_parts.append("Generate a hospital admission request letter.")
        elif recipient_type == "diagnostic":
            prompt_parts.append("Generate a diagnostic services request.")
        else:
            prompt_parts.append("Generate a professional referral letter.")

        # Urgency statement
        urgency_statements = {
            "routine": "This is a routine/elective referral.",
            "soon": "This referral requires attention within 2-4 weeks.",
            "urgent": "URGENT: This referral requires attention within 48-72 hours.",
            "emergency": "EMERGENCY: This patient requires immediate assessment today."
        }
        prompt_parts.append(urgency_statements.get(urgency, urgency_statements["routine"]))
        prompt_parts.append("")

        # Condition focus
        if conditions:
            prompt_parts.append(f"**CONDITION FOCUS:** This referral is specifically for: {conditions}")
            prompt_parts.append("")

        # Guidance-based instructions
        prompt_parts.append("**INCLUDE (focus on):**")
        for item in guidance["focus"]:
            prompt_parts.append(f"- {item}")
        prompt_parts.append("")

        prompt_parts.append("**EXCLUDE (do not include):**")
        for item in guidance["exclude"]:
            prompt_parts.append(f"- {item}")
        prompt_parts.append("")

        prompt_parts.append(f"**TONE:** {guidance['tone']}")
        prompt_parts.append(f"**FORMAT:** {guidance['format']}")
        prompt_parts.append("")

        # Source text
        prompt_parts.append("**Clinical Information:**")
        prompt_parts.append(source_text)
        prompt_parts.append("")

        # Format requirements
        prompt_parts.append("**Letter Structure:**")
        prompt_parts.append("- Current date")
        prompt_parts.append("- Recipient information (if provided)")
        prompt_parts.append("- Patient demographics (name, DOB)")
        prompt_parts.append(f"- Opening: {guidance['opening']}")
        prompt_parts.append("- Clinical summary (following the INCLUDE/EXCLUDE guidance)")
        prompt_parts.append(f"- Closing: {guidance['closing']}")
        prompt_parts.append("- Sender information")
        prompt_parts.append("")
        prompt_parts.append("Generate the referral letter:")

        return "\n".join(prompt_parts)

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
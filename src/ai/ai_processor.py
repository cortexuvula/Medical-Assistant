"""
AI Processor Module

Handles all AI-related text processing including refinement, improvement,
SOAP note generation, referral letters, and general letters.

Error Handling:
    - All public methods return OperationResult[T] for structured error handling
    - Use result.success to check if operation succeeded
    - Use result.value for the returned data on success
    - Use result.error for error message on failure
    - Use result.to_dict() for backward compatibility with legacy code
    - Methods use @handle_errors decorator for consistent error capture
    - APIError, TranscriptionError raised for unrecoverable provider failures

Logging:
    - Uses structured logging via get_logger(__name__)
    - Logs include operation context (provider, model, text_length)
    - API keys and sensitive data are redacted from logs

Usage:
    processor = AIProcessor()
    result = processor.refine_text("Raw transcript text")
    if result.success:
        refined = result.value["text"]
    else:
        handle_error(result.error)
"""

import os
from typing import Dict, Any, Optional
from utils.structured_logging import get_logger
from utils.security import get_security_manager
from settings.settings_manager import settings_manager
from ai.ai import (
    adjust_text_with_openai,
    improve_text_with_openai,
    create_soap_note_with_openai,
    get_possible_conditions
)
# Import prompts used for SOAP generation
from ai.prompts import SOAP_PROMPT_TEMPLATE, SOAP_SYSTEM_MESSAGE
from managers.agent_manager import agent_manager
from ai.agents.models import AgentTask, AgentType
from utils.error_handling import OperationResult, handle_errors, ErrorSeverity, sanitize_error_for_user
from utils.constants import (
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_OLLAMA, PROVIDER_GEMINI
)
from utils.validation import sanitize_prompt

logger = get_logger(__name__)


class AIProcessor:
    """Handles AI-powered text processing operations."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize AI processor.

        Args:
            api_key: OpenAI API key (uses security manager if not provided)
        """
        if api_key:
            self.api_key = api_key
        else:
            security_manager = get_security_manager()
            self.api_key = security_manager.get_api_key("openai")
        
    @handle_errors(ErrorSeverity.ERROR, error_message="Failed to refine text", return_type="result")
    def refine_text(self, text: str) -> OperationResult[Dict[str, str]]:
        """Refine text using AI.

        Args:
            text: Text to refine

        Returns:
            OperationResult containing refined text on success.
            Use result.to_dict() for backward compatibility.

        Note:
            Prompt customization available via Settings → Prompt Settings → Refine Prompt.
        """
        if not text.strip():
            return OperationResult.failure("No text to refine", error_code="EMPTY_INPUT")

        # Sanitize text to prevent prompt injection
        sanitized_text = sanitize_prompt(text)

        # Process text (reads prompt and temperature from SETTINGS internally)
        refined_text = adjust_text_with_openai(sanitized_text)

        logger.info("Text refined successfully")
        return OperationResult.success({"text": refined_text})
    
    @handle_errors(ErrorSeverity.ERROR, error_message="Failed to improve text", return_type="result")
    def improve_text(self, text: str) -> OperationResult[Dict[str, str]]:
        """Improve text using AI.

        Args:
            text: Text to improve

        Returns:
            OperationResult containing improved text on success.
            Use result.to_dict() for backward compatibility.

        Note:
            Prompt customization available via Settings → Prompt Settings → Improve Prompt.
        """
        if not text.strip():
            return OperationResult.failure("No text to improve", error_code="EMPTY_INPUT")

        # Sanitize text to prevent prompt injection
        sanitized_text = sanitize_prompt(text)

        # Process text (reads prompt and temperature from SETTINGS internally)
        improved_text = improve_text_with_openai(sanitized_text)

        logger.info("Text improved successfully")
        return OperationResult.success({"text": improved_text})
    
    @handle_errors(ErrorSeverity.ERROR, error_message="Failed to create SOAP note", return_type="result")
    def create_soap_note(self, transcript: str, context: str = "") -> OperationResult[Dict[str, str]]:
        """Create SOAP note from transcript.

        Args:
            transcript: Transcribed text
            context: Additional medical context

        Returns:
            OperationResult containing SOAP note on success.
            Use result.to_dict() for backward compatibility.
        """
        if not transcript.strip():
            return OperationResult.failure("No transcript provided", error_code="EMPTY_INPUT")

        # Sanitize transcript and context to prevent prompt injection
        sanitized_transcript = sanitize_prompt(transcript)
        sanitized_context = sanitize_prompt(context) if context else ""

        # Get SOAP prompt from settings or use default
        soap_config = settings_manager.get_soap_config()
        soap_prompt = soap_config.get("prompt", SOAP_PROMPT_TEMPLATE)

        # Include context if provided
        if sanitized_context:
            full_transcript = f"Previous medical information:\n{sanitized_context}\n\nCurrent transcript:\n{sanitized_transcript}"
        else:
            full_transcript = sanitized_transcript

        # Get temperature setting
        temperature = settings_manager.get_nested("soap_note.temperature", 0.2)

        # Generate SOAP note
        soap_note = create_soap_note_with_openai(
            full_transcript,
            soap_prompt,
            temperature=temperature
        )

        # Get possible conditions if enabled (non-critical, use inner try/except)
        possible_conditions = ""
        if settings_manager.get("include_possible_conditions", True):
            try:
                conditions = get_possible_conditions(soap_note)
                if conditions:
                    possible_conditions = f"\n\nPossible Conditions:\n{conditions}"
            except Exception as e:
                logger.warning("Failed to get possible conditions", error=str(e))

        full_soap_note = soap_note + possible_conditions

        logger.info("SOAP note created successfully")
        return OperationResult.success({"text": full_soap_note})
    
    @handle_errors(ErrorSeverity.ERROR, error_message="Failed to create referral letter", return_type="result")
    def create_referral_letter(self, text: str, letter_options: Dict[str, str]) -> OperationResult[Dict[str, str]]:
        """Create referral letter from text.

        Args:
            text: Source text for referral
            letter_options: Dictionary with letter configuration
                - referring_provider: Name of referring provider
                - patient_name: Patient name
                - specialty: Referral specialty
                - reason: Reason for referral

        Returns:
            OperationResult containing referral letter on success.
            Use result.to_dict() for backward compatibility.
        """
        if not text.strip():
            return OperationResult.failure("No text provided", error_code="EMPTY_INPUT")

        # Sanitize text to prevent prompt injection
        sanitized_text = sanitize_prompt(text)

        # Get referral prompt from settings or use default
        referral_config = settings_manager.get_model_config("referral")
        referral_prompt = referral_config.get(
            "prompt",
            "Create a professional referral letter based on the following information:"
        )

        # Build the referral context
        context_parts = [f"Source text:\n{sanitized_text}\n"]

        if letter_options.get("referring_provider"):
            context_parts.append(f"Referring Provider: {letter_options['referring_provider']}")
        if letter_options.get("patient_name"):
            context_parts.append(f"Patient: {letter_options['patient_name']}")
        if letter_options.get("specialty"):
            context_parts.append(f"Referral to: {letter_options['specialty']}")
        if letter_options.get("reason"):
            context_parts.append(f"Reason for referral: {letter_options['reason']}")

        full_context = "\n".join(context_parts)

        # Get temperature setting
        temperature = settings_manager.get_nested("referral.temperature", 0.3)

        # Generate referral letter
        referral_letter = adjust_text_with_openai(
            full_context,
            referral_prompt,
            temperature=temperature
        )

        logger.info("Referral letter created successfully")
        return OperationResult.success({"text": referral_letter})
    
    @handle_errors(ErrorSeverity.ERROR, error_message="Failed to create letter", return_type="result")
    def create_letter(self, text: str, letter_type: str, letter_options: Dict[str, str]) -> OperationResult[Dict[str, str]]:
        """Create a letter from text.

        Args:
            text: Source text for letter
            letter_type: Type of letter to create
            letter_options: Dictionary with letter configuration

        Returns:
            OperationResult containing letter on success.
            Use result.to_dict() for backward compatibility.
        """
        if not text.strip():
            return OperationResult.failure("No text provided", error_code="EMPTY_INPUT")

        # Sanitize text to prevent prompt injection
        sanitized_text = sanitize_prompt(text)

        # Get letter prompt based on type
        letter_prompt = settings_manager.get(
            f"{letter_type}_letter_prompt",
            f"Create a professional {letter_type} letter based on the following information:"
        )

        # Build the letter context
        context_parts = [f"Source text:\n{sanitized_text}\n"]

        # Add all provided options to context
        for key, value in letter_options.items():
            if value:
                # Convert key from snake_case to Title Case
                label = key.replace("_", " ").title()
                context_parts.append(f"{label}: {value}")

        full_context = "\n".join(context_parts)

        # Get temperature setting
        temperature = settings_manager.get("letter_temperature", 0.3)

        # Generate letter
        letter = adjust_text_with_openai(
            full_context,
            letter_prompt,
            temperature=temperature
        )

        logger.info("Letter created successfully", letter_type=letter_type)
        return OperationResult.success({"text": letter})
    
    @handle_errors(ErrorSeverity.WARNING, error_message="API key validation failed", return_type="bool")
    def validate_api_key(self) -> bool:
        """Validate the OpenAI API key.

        Returns:
            bool: True if API key is valid
        """
        if not self.api_key:
            return False

        # Test the API key with a minimal request using modern client pattern
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)
        client.models.list()
        return True
    
    @handle_errors(ErrorSeverity.ERROR, error_message="Failed to analyze medications", return_type="result")
    def analyze_medications(self, text: str, task_type: str = "extract",
                          additional_data: Optional[Dict[str, Any]] = None) -> OperationResult[Dict[str, Any]]:
        """Analyze medications using the medication agent.

        Args:
            text: Clinical text or SOAP note containing medication information
            task_type: Type of medication task ('extract', 'check_interactions',
                      'validate_dosing', 'suggest_alternatives', 'comprehensive')
            additional_data: Additional data for the task (medications list, patient info, etc.)

        Returns:
            OperationResult containing analysis result on success.
            Use result.to_dict() for backward compatibility.
        """
        # Check if medication agent is enabled
        if not agent_manager.is_agent_enabled(AgentType.MEDICATION):
            return OperationResult.failure(
                "Medication agent is not enabled. Please enable it in settings.",
                error_code="AGENT_DISABLED"
            )

        # Sanitize text to prevent prompt injection
        sanitized_text = sanitize_prompt(text) if text else ""

        # Prepare input data based on task type
        input_data = additional_data or {}

        if task_type == "extract":
            input_data["clinical_text"] = sanitized_text
            task_desc = "Extract medications from clinical text"
        elif task_type == "check_interactions":
            if "medications" not in input_data:
                return OperationResult.failure(
                    "Medications list required for interaction check",
                    error_code="MISSING_INPUT"
                )
            task_desc = "Check for drug-drug interactions"
        elif task_type == "validate_dosing":
            if "medication" not in input_data:
                return OperationResult.failure(
                    "Medication information required for dosing validation",
                    error_code="MISSING_INPUT"
                )
            task_desc = "Validate medication dosing"
        elif task_type == "suggest_alternatives":
            if "current_medication" not in input_data:
                return OperationResult.failure(
                    "Current medication required for alternative suggestions",
                    error_code="MISSING_INPUT"
                )
            task_desc = "Suggest alternative medications"
        else:  # comprehensive
            input_data["clinical_text"] = sanitized_text
            task_desc = "Perform comprehensive medication analysis"

        # Create task
        task = AgentTask(
            task_description=task_desc,
            input_data=input_data
        )

        # Execute task
        response = agent_manager.execute_agent_task(AgentType.MEDICATION, task)

        if response and response.success:
            logger.info("Medication task completed successfully", task_type=task_type)
            return OperationResult.success({
                "text": response.result,
                "metadata": response.metadata
            })
        else:
            error_msg = response.error if response else "Medication agent not available"
            logger.error("Medication task failed", task_type=task_type, error=error_msg)
            return OperationResult.failure(error_msg, error_code="MEDICATION_FAILED")
    
    def extract_medications_from_soap(self, soap_note: str) -> OperationResult[Dict[str, Any]]:
        """Extract medications from a SOAP note.

        Args:
            soap_note: SOAP note text

        Returns:
            OperationResult containing extracted medications on success.
        """
        return self.analyze_medications(soap_note, task_type="extract")

    def check_medication_interactions(self, medications: list) -> OperationResult[Dict[str, Any]]:
        """Check for drug interactions between medications.

        Args:
            medications: List of medication names

        Returns:
            OperationResult containing interaction analysis on success.
        """
        return self.analyze_medications(
            "",
            task_type="check_interactions",
            additional_data={"medications": medications}
        )

    def validate_medication_dosing(self, medication: Dict[str, str],
                                 patient_factors: Optional[Dict[str, Any]] = None) -> OperationResult[Dict[str, Any]]:
        """Validate medication dosing based on patient factors.

        Args:
            medication: Dict with medication name, dose, frequency
            patient_factors: Optional dict with age, weight, renal function, etc.

        Returns:
            OperationResult containing dosing validation on success.
        """
        return self.analyze_medications(
            "",
            task_type="validate_dosing",
            additional_data={
                "medication": medication,
                "patient_factors": patient_factors or {}
            }
        )
    
    def _get_specialty_instructions(self, specialty: str) -> str:
        """Get specialty-specific instructions for the diagnostic analysis.

        Args:
            specialty: The specialty focus (e.g., "general", "emergency", "cardiology")

        Returns:
            Specialty-specific instruction string to prepend to system message
        """
        specialty_map = {
            "general": "",  # No special instructions for general
            "emergency": (
                "SPECIALTY FOCUS: EMERGENCY MEDICINE\n"
                "PRIORITIZE LIFE-THREATENING CONDITIONS. Focus on red flags and time-sensitive diagnoses. "
                "Rank conditions by urgency, not just likelihood. Include 'must-not-miss' diagnoses prominently. "
                "Consider presentations that require immediate intervention or monitoring.\n\n"
            ),
            "internal": (
                "SPECIALTY FOCUS: INTERNAL MEDICINE\n"
                "Consider multisystem involvement and complex medical conditions. Account for comorbidities "
                "and their interactions. Consider atypical presentations of common conditions.\n\n"
            ),
            "pediatric": (
                "SPECIALTY FOCUS: PEDIATRICS\n"
                "Apply age-appropriate differentials. Consider developmental milestones and congenital conditions. "
                "Account for age-specific vital sign normals and presentations. Consider childhood-specific diseases.\n\n"
            ),
            "cardiology": (
                "SPECIALTY FOCUS: CARDIOLOGY\n"
                "Focus on cardiovascular causes including structural, electrical, and vascular conditions. "
                "Consider cardiac risk stratification. Include relevant cardiac biomarkers and ECG findings "
                "in investigations. Prioritize coronary and structural heart disease.\n\n"
            ),
            "pulmonology": (
                "SPECIALTY FOCUS: PULMONOLOGY\n"
                "Focus on respiratory and pulmonary conditions. Consider obstructive vs restrictive patterns. "
                "Include relevant pulmonary function tests and imaging. Consider infectious, inflammatory, "
                "and neoplastic causes.\n\n"
            ),
            "gi": (
                "SPECIALTY FOCUS: GASTROENTEROLOGY\n"
                "Focus on gastrointestinal and hepatobiliary conditions. Consider upper vs lower GI localization. "
                "Include relevant endoscopic and imaging studies. Consider functional vs organic causes.\n\n"
            ),
            "neurology": (
                "SPECIALTY FOCUS: NEUROLOGY\n"
                "Focus on neurological causes including structural, vascular, demyelinating, and functional. "
                "Consider localization (central vs peripheral, anatomical level). Include relevant imaging "
                "and electrophysiology studies.\n\n"
            ),
            "psychiatry": (
                "SPECIALTY FOCUS: PSYCHIATRY\n"
                "Consider psychiatric and biopsychosocial factors. Rule out organic causes of psychiatric symptoms. "
                "Include relevant screening tools and assessments. Consider substance use and medication effects.\n\n"
            ),
            "orthopedic": (
                "SPECIALTY FOCUS: ORTHOPEDICS\n"
                "Focus on musculoskeletal and orthopedic conditions. Consider mechanical vs inflammatory causes. "
                "Include relevant imaging and orthopedic examinations. Consider trauma, degenerative, and "
                "infectious etiologies.\n\n"
            ),
            "oncology": (
                "SPECIALTY FOCUS: ONCOLOGY\n"
                "Consider malignancy in the differential. Look for paraneoplastic syndromes. Include relevant "
                "tumor markers and imaging for staging. Consider both primary malignancies and metastatic disease.\n\n"
            ),
            "geriatric": (
                "SPECIALTY FOCUS: GERIATRICS\n"
                "Consider age-related conditions and atypical presentations in elderly patients. Account for "
                "polypharmacy and drug interactions. Consider functional status and goals of care. "
                "Be aware of presentations that may be subtle or masked.\n\n"
            ),
        }
        return specialty_map.get(specialty, "")

    @handle_errors(ErrorSeverity.ERROR, error_message="Failed to generate differential diagnosis", return_type="result")
    def generate_differential_diagnosis(self, transcript: str, specialty: str = None) -> OperationResult[Dict[str, str]]:
        """Generate differential diagnosis from transcript.

        Args:
            transcript: The medical transcript to analyze
            specialty: Optional clinical specialty focus (overrides settings if provided)

        Returns:
            OperationResult containing analysis on success.
            Use result.to_dict() for backward compatibility.
        """
        if not transcript.strip():
            return OperationResult.failure("No transcript to analyze", error_code="EMPTY_INPUT")

        # Sanitize transcript to prevent prompt injection
        sanitized_transcript = sanitize_prompt(transcript)

        # Force reload settings to get latest provider selection
        from settings.settings import load_settings
        current_settings = load_settings(force_refresh=True)

        # Get advanced analysis settings
        analysis_settings = current_settings.get("advanced_analysis", {})

        # Get prompt and system message from settings
        prompt_template = analysis_settings.get("prompt",
            "Create a 5 differential diagnosis list, possible investigations "
            "and treatment plan for the provided transcript:")

        # Create the full prompt with sanitized transcript
        prompt = f"{prompt_template}\n\n{sanitized_transcript}"

        # Get system message from settings
        system_message = analysis_settings.get("system_message",
            "You are a medical AI assistant helping to analyze patient consultations. "
            "Provide clear, structured differential diagnoses with relevant investigations "
            "and treatment recommendations. Format your response with clear sections for:\n"
            "1. Differential Diagnoses (list 5 with brief explanations)\n"
            "2. Recommended Investigations\n"
            "3. Treatment Plan"
        )

        # Get specialty from parameter or settings (parameter takes precedence)
        effective_specialty = specialty if specialty else analysis_settings.get("specialty", "general")

        # Inject specialty-specific instructions if applicable
        specialty_instructions = self._get_specialty_instructions(effective_specialty)
        if specialty_instructions:
            system_message = specialty_instructions + system_message
            logger.info("Applied specialty focus to differential diagnosis", specialty=effective_specialty)

        # Get temperature from settings
        temperature = analysis_settings.get("temperature", 0.3)

        # Generate analysis using call_ai directly since adjust_text_with_openai
        # doesn't support custom system messages or temperature
        from ai.ai import call_ai

        # Get the model based on AI provider
        # Use Advanced Analysis-specific provider if set, otherwise fall back to global
        analysis_provider = analysis_settings.get("provider", "")
        if analysis_provider:
            ai_provider = analysis_provider
            logger.info("Advanced Analysis using specific provider", provider=ai_provider)
        else:
            ai_provider = current_settings.get("ai_provider", "openai")
            logger.info("Advanced Analysis using global provider", provider=ai_provider)

        # Select the appropriate model based on provider
        if ai_provider == PROVIDER_OPENAI:
            model = analysis_settings.get("model", "gpt-4")
        elif ai_provider == PROVIDER_OLLAMA:
            model = analysis_settings.get("ollama_model", "")
            if not model:
                # Auto-detect from Ollama if no task-specific model configured
                from ai.providers.ollama_provider import _get_first_available_model
                from utils.http_client_manager import get_http_client_manager
                _session = get_http_client_manager().get_requests_session("ollama")
                _base = os.getenv("OLLAMA_API_URL", "http://localhost:11434").rstrip("/")
                model = _get_first_available_model(_session, _base) or "llama3"
        elif ai_provider == PROVIDER_ANTHROPIC:
            model = analysis_settings.get("anthropic_model", "claude-sonnet-4-20250514")
        elif ai_provider == PROVIDER_GEMINI:
            model = analysis_settings.get("gemini_model", "gemini-1.5-pro")
        else:
            # Fallback to OpenAI model
            model = analysis_settings.get("model", "gpt-4")

        # Get provider-specific temperature if available
        temp_key = f"{ai_provider}_temperature"
        if temp_key in analysis_settings:
            temperature = analysis_settings[temp_key]

        # Generate analysis - pass the provider to override global setting
        analysis = call_ai(model, system_message, prompt, temperature, provider=ai_provider)

        logger.info("Generated differential diagnosis successfully", provider=ai_provider, specialty=effective_specialty)
        # Extract text from AIResult
        analysis_text = analysis.text if hasattr(analysis, 'text') else str(analysis)
        return OperationResult.success({"text": analysis_text})
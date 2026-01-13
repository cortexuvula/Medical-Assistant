"""
AI Processor Module

Handles all AI-related text processing including refinement, improvement,
SOAP note generation, referral letters, and general letters.

All methods return OperationResult for consistent error handling.
Use result.to_dict() for backward compatibility with code expecting
{"success": bool, "text": str} or {"success": bool, "error": str}.
"""

import logging
from typing import Dict, Any, Optional, Tuple, Union
import openai
from settings.settings import SETTINGS
from ai.ai import (
    adjust_text_with_openai,
    improve_text_with_openai,
    create_soap_note_with_openai,
    get_possible_conditions
)
# Import individual prompts if needed
from ai.prompts import (
    REFINE_PROMPT, REFINE_SYSTEM_MESSAGE,
    IMPROVE_PROMPT, IMPROVE_SYSTEM_MESSAGE,
    SOAP_PROMPT_TEMPLATE, SOAP_SYSTEM_MESSAGE
)
from managers.agent_manager import agent_manager
from ai.agents.models import AgentTask, AgentType
from utils.error_handling import OperationResult, handle_errors, ErrorSeverity, sanitize_error_for_user
from utils.constants import (
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_OLLAMA, PROVIDER_GEMINI
)

logger = logging.getLogger(__name__)


class AIProcessor:
    """Handles AI-powered text processing operations."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize AI processor.
        
        Args:
            api_key: OpenAI API key (uses environment if not provided)
        """
        self.api_key = api_key or openai.api_key
        
    def refine_text(self, text: str, additional_context: str = "") -> OperationResult[Dict[str, str]]:
        """Refine text using AI.

        Args:
            text: Text to refine
            additional_context: Additional context for refinement

        Returns:
            OperationResult containing refined text on success.
            Use result.to_dict() for backward compatibility.
        """
        try:
            if not text.strip():
                return OperationResult.failure("No text to refine", error_code="EMPTY_INPUT")

            # Get refine prompt from settings or use default
            refine_settings = SETTINGS.get("refine_text", {})
            refine_prompt = refine_settings.get("prompt", REFINE_PROMPT)

            # Combine prompt with additional context if provided
            if additional_context:
                full_prompt = f"{refine_prompt}\n\nAdditional context: {additional_context}"
            else:
                full_prompt = refine_prompt

            # Process text (function reads temperature from SETTINGS internally)
            refined_text = adjust_text_with_openai(text)

            logger.info("Text refined successfully")
            return OperationResult.success({"text": refined_text})

        except Exception as e:
            logger.error(f"Failed to refine text: {e}")
            # SECURITY: Use sanitized error message to avoid exposing sensitive details
            return OperationResult.failure(sanitize_error_for_user(e), error_code="REFINE_FAILED", exception=e)
    
    def improve_text(self, text: str, additional_context: str = "") -> OperationResult[Dict[str, str]]:
        """Improve text using AI.

        Args:
            text: Text to improve
            additional_context: Additional context for improvement

        Returns:
            OperationResult containing improved text on success.
            Use result.to_dict() for backward compatibility.
        """
        try:
            if not text.strip():
                return OperationResult.failure("No text to improve", error_code="EMPTY_INPUT")

            # Get improve prompt from settings or use default
            improve_settings = SETTINGS.get("improve_text", {})
            improve_prompt = improve_settings.get("prompt", IMPROVE_PROMPT)

            # Combine prompt with additional context if provided
            if additional_context:
                full_prompt = f"{improve_prompt}\n\nAdditional context: {additional_context}"
            else:
                full_prompt = improve_prompt

            # Process text (function reads temperature from SETTINGS internally)
            improved_text = improve_text_with_openai(text)

            logger.info("Text improved successfully")
            return OperationResult.success({"text": improved_text})

        except Exception as e:
            logger.error(f"Failed to improve text: {e}")
            # SECURITY: Use sanitized error message to avoid exposing sensitive details
            return OperationResult.failure(sanitize_error_for_user(e), error_code="IMPROVE_FAILED", exception=e)
    
    def create_soap_note(self, transcript: str, context: str = "") -> OperationResult[Dict[str, str]]:
        """Create SOAP note from transcript.

        Args:
            transcript: Transcribed text
            context: Additional medical context

        Returns:
            OperationResult containing SOAP note on success.
            Use result.to_dict() for backward compatibility.
        """
        try:
            if not transcript.strip():
                return OperationResult.failure("No transcript provided", error_code="EMPTY_INPUT")

            # Get SOAP prompt from settings or use default
            soap_settings = SETTINGS.get("soap_note", {})
            soap_prompt = soap_settings.get("prompt", SOAP_PROMPT_TEMPLATE)

            # Include context if provided
            if context:
                full_transcript = f"Previous medical information:\n{context}\n\nCurrent transcript:\n{transcript}"
            else:
                full_transcript = transcript

            # Get temperature setting
            temperature = SETTINGS.get("soap_temperature", 0.2)

            # Generate SOAP note
            soap_note = create_soap_note_with_openai(
                full_transcript,
                soap_prompt,
                temperature=temperature
            )

            # Get possible conditions if enabled
            possible_conditions = ""
            if SETTINGS.get("include_possible_conditions", True):
                try:
                    conditions = get_possible_conditions(soap_note)
                    if conditions:
                        possible_conditions = f"\n\nPossible Conditions:\n{conditions}"
                except Exception as e:
                    logger.warning(f"Failed to get possible conditions: {e}")

            full_soap_note = soap_note + possible_conditions

            logger.info("SOAP note created successfully")
            return OperationResult.success({"text": full_soap_note})

        except Exception as e:
            logger.error(f"Failed to create SOAP note: {e}")
            # SECURITY: Use sanitized error message to avoid exposing sensitive details
            return OperationResult.failure(sanitize_error_for_user(e), error_code="SOAP_FAILED", exception=e)
    
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
        try:
            if not text.strip():
                return OperationResult.failure("No text provided", error_code="EMPTY_INPUT")

            # Get referral prompt from settings or use default
            referral_settings = SETTINGS.get("referral", {})
            referral_prompt = referral_settings.get(
                "prompt",
                "Create a professional referral letter based on the following information:"
            )

            # Build the referral context
            context_parts = [f"Source text:\n{text}\n"]

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
            temperature = SETTINGS.get("referral_temperature", 0.3)

            # Generate referral letter
            referral_letter = adjust_text_with_openai(
                full_context,
                referral_prompt,
                temperature=temperature
            )

            logger.info("Referral letter created successfully")
            return OperationResult.success({"text": referral_letter})

        except Exception as e:
            logger.error(f"Failed to create referral letter: {e}")
            # SECURITY: Use sanitized error message to avoid exposing sensitive details
            return OperationResult.failure(sanitize_error_for_user(e), error_code="REFERRAL_FAILED", exception=e)
    
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
        try:
            if not text.strip():
                return OperationResult.failure("No text provided", error_code="EMPTY_INPUT")

            # Get letter prompt based on type
            letter_prompt = SETTINGS.get(
                f"{letter_type}_letter_prompt",
                f"Create a professional {letter_type} letter based on the following information:"
            )

            # Build the letter context
            context_parts = [f"Source text:\n{text}\n"]

            # Add all provided options to context
            for key, value in letter_options.items():
                if value:
                    # Convert key from snake_case to Title Case
                    label = key.replace("_", " ").title()
                    context_parts.append(f"{label}: {value}")

            full_context = "\n".join(context_parts)

            # Get temperature setting
            temperature = SETTINGS.get("letter_temperature", 0.3)

            # Generate letter
            letter = adjust_text_with_openai(
                full_context,
                letter_prompt,
                temperature=temperature
            )

            logger.info(f"{letter_type} letter created successfully")
            return OperationResult.success({"text": letter})

        except Exception as e:
            logger.error(f"Failed to create {letter_type} letter: {e}")
            # SECURITY: Use sanitized error message to avoid exposing sensitive details
            return OperationResult.failure(sanitize_error_for_user(e), error_code="LETTER_FAILED", exception=e)
    
    def validate_api_key(self) -> bool:
        """Validate the OpenAI API key.
        
        Returns:
            bool: True if API key is valid
        """
        try:
            if not self.api_key:
                return False
                
            # Test the API key with a minimal request
            openai.api_key = self.api_key
            openai.Model.list()
            return True
            
        except Exception as e:
            logging.error(f"API key validation failed: {e}")
            return False
    
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
        try:
            # Check if medication agent is enabled
            if not agent_manager.is_agent_enabled(AgentType.MEDICATION):
                return OperationResult.failure(
                    "Medication agent is not enabled. Please enable it in settings.",
                    error_code="AGENT_DISABLED"
                )

            # Prepare input data based on task type
            input_data = additional_data or {}

            if task_type == "extract":
                input_data["clinical_text"] = text
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
                input_data["clinical_text"] = text
                task_desc = "Perform comprehensive medication analysis"

            # Create task
            task = AgentTask(
                task_description=task_desc,
                input_data=input_data
            )

            # Execute task
            response = agent_manager.execute_agent_task(AgentType.MEDICATION, task)

            if response and response.success:
                logger.info(f"Medication {task_type} completed successfully")
                return OperationResult.success({
                    "text": response.result,
                    "metadata": response.metadata
                })
            else:
                error_msg = response.error if response else "Medication agent not available"
                logger.error(f"Medication {task_type} failed: {error_msg}")
                return OperationResult.failure(error_msg, error_code="MEDICATION_FAILED")

        except Exception as e:
            logger.error(f"Failed to analyze medications: {e}")
            # SECURITY: Use sanitized error message to avoid exposing sensitive details
            return OperationResult.failure(sanitize_error_for_user(e), error_code="MEDICATION_FAILED", exception=e)
    
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
    
    def generate_differential_diagnosis(self, transcript: str) -> OperationResult[Dict[str, str]]:
        """Generate differential diagnosis from transcript.

        Args:
            transcript: The medical transcript to analyze

        Returns:
            OperationResult containing analysis on success.
            Use result.to_dict() for backward compatibility.
        """
        try:
            if not transcript.strip():
                return OperationResult.failure("No transcript to analyze", error_code="EMPTY_INPUT")

            # Force reload settings to get latest provider selection
            from settings.settings import load_settings
            current_settings = load_settings(force_refresh=True)

            # Get advanced analysis settings
            analysis_settings = current_settings.get("advanced_analysis", {})

            # Get prompt and system message from settings
            prompt_template = analysis_settings.get("prompt",
                "Create a 5 differential diagnosis list, possible investigations "
                "and treatment plan for the provided transcript:")

            # Create the full prompt
            prompt = f"{prompt_template}\n\n{transcript}"

            # Get system message from settings
            system_message = analysis_settings.get("system_message",
                "You are a medical AI assistant helping to analyze patient consultations. "
                "Provide clear, structured differential diagnoses with relevant investigations "
                "and treatment recommendations. Format your response with clear sections for:\n"
                "1. Differential Diagnoses (list 5 with brief explanations)\n"
                "2. Recommended Investigations\n"
                "3. Treatment Plan"
            )

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
                logger.info(f"Advanced Analysis using specific provider: {ai_provider}")
            else:
                ai_provider = current_settings.get("ai_provider", "openai")
                logger.info(f"Advanced Analysis using global provider: {ai_provider}")

            # Select the appropriate model based on provider
            if ai_provider == PROVIDER_OPENAI:
                model = analysis_settings.get("model", "gpt-4")
            elif ai_provider == PROVIDER_OLLAMA:
                model = analysis_settings.get("ollama_model", "llama3")
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

            logger.info(f"Generated differential diagnosis successfully using provider: {ai_provider}")
            return OperationResult.success({"text": analysis})

        except Exception as e:
            logger.error(f"Failed to generate differential diagnosis: {e}")
            # SECURITY: Use sanitized error message to avoid exposing sensitive details
            return OperationResult.failure(sanitize_error_for_user(e), error_code="DIAGNOSIS_FAILED", exception=e)
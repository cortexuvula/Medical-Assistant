"""
AI Processor Module

Handles all AI-related text processing including refinement, improvement,
SOAP note generation, referral letters, and general letters.
"""

import logging
from typing import Dict, Any, Optional, Tuple
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


class AIProcessor:
    """Handles AI-powered text processing operations."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize AI processor.
        
        Args:
            api_key: OpenAI API key (uses environment if not provided)
        """
        self.api_key = api_key or openai.api_key
        
    def refine_text(self, text: str, additional_context: str = "") -> Dict[str, Any]:
        """Refine text using AI.
        
        Args:
            text: Text to refine
            additional_context: Additional context for refinement
            
        Returns:
            Dict containing success status and refined text or error
        """
        try:
            if not text.strip():
                return {"success": False, "error": "No text to refine"}
                
            # Get refine prompt from settings or use default
            refine_settings = SETTINGS.get("refine_text", {})
            refine_prompt = refine_settings.get("prompt", REFINE_PROMPT)
            
            # Combine prompt with additional context if provided
            if additional_context:
                full_prompt = f"{refine_prompt}\n\nAdditional context: {additional_context}"
            else:
                full_prompt = refine_prompt
                
            # Get temperature setting
            temperature = SETTINGS.get("refine_temperature", 0.1)
            
            # Process text
            refined_text = adjust_text_with_openai(
                text,
                full_prompt,
                temperature=temperature
            )
            
            logging.info("Text refined successfully")
            return {"success": True, "text": refined_text}
            
        except Exception as e:
            logging.error(f"Failed to refine text: {e}")
            return {"success": False, "error": str(e)}
    
    def improve_text(self, text: str, additional_context: str = "") -> Dict[str, Any]:
        """Improve text using AI.
        
        Args:
            text: Text to improve
            additional_context: Additional context for improvement
            
        Returns:
            Dict containing success status and improved text or error
        """
        try:
            if not text.strip():
                return {"success": False, "error": "No text to improve"}
                
            # Get improve prompt from settings or use default
            improve_settings = SETTINGS.get("improve_text", {})
            improve_prompt = improve_settings.get("prompt", IMPROVE_PROMPT)
            
            # Combine prompt with additional context if provided
            if additional_context:
                full_prompt = f"{improve_prompt}\n\nAdditional context: {additional_context}"
            else:
                full_prompt = improve_prompt
                
            # Get temperature setting
            temperature = SETTINGS.get("improve_temperature", 0.3)
            
            # Process text
            improved_text = improve_text_with_openai(
                text,
                full_prompt,
                temperature=temperature
            )
            
            logging.info("Text improved successfully")
            return {"success": True, "text": improved_text}
            
        except Exception as e:
            logging.error(f"Failed to improve text: {e}")
            return {"success": False, "error": str(e)}
    
    def create_soap_note(self, transcript: str, context: str = "") -> Dict[str, Any]:
        """Create SOAP note from transcript.
        
        Args:
            transcript: Transcribed text
            context: Additional medical context
            
        Returns:
            Dict containing success status and SOAP note or error
        """
        try:
            if not transcript.strip():
                return {"success": False, "error": "No transcript provided"}
                
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
                    logging.warning(f"Failed to get possible conditions: {e}")
            
            full_soap_note = soap_note + possible_conditions
            
            logging.info("SOAP note created successfully")
            return {"success": True, "text": full_soap_note}
            
        except Exception as e:
            logging.error(f"Failed to create SOAP note: {e}")
            return {"success": False, "error": str(e)}
    
    def create_referral_letter(self, text: str, letter_options: Dict[str, str]) -> Dict[str, Any]:
        """Create referral letter from text.
        
        Args:
            text: Source text for referral
            letter_options: Dictionary with letter configuration
                - referring_provider: Name of referring provider
                - patient_name: Patient name
                - specialty: Referral specialty
                - reason: Reason for referral
                
        Returns:
            Dict containing success status and referral letter or error
        """
        try:
            if not text.strip():
                return {"success": False, "error": "No text provided"}
                
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
            
            logging.info("Referral letter created successfully")
            return {"success": True, "text": referral_letter}
            
        except Exception as e:
            logging.error(f"Failed to create referral letter: {e}")
            return {"success": False, "error": str(e)}
    
    def create_letter(self, text: str, letter_type: str, letter_options: Dict[str, str]) -> Dict[str, Any]:
        """Create a letter from text.
        
        Args:
            text: Source text for letter
            letter_type: Type of letter to create
            letter_options: Dictionary with letter configuration
                
        Returns:
            Dict containing success status and letter or error
        """
        try:
            if not text.strip():
                return {"success": False, "error": "No text provided"}
                
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
            
            logging.info(f"{letter_type} letter created successfully")
            return {"success": True, "text": letter}
            
        except Exception as e:
            logging.error(f"Failed to create {letter_type} letter: {e}")
            return {"success": False, "error": str(e)}
    
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
                          additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze medications using the medication agent.
        
        Args:
            text: Clinical text or SOAP note containing medication information
            task_type: Type of medication task ('extract', 'check_interactions', 
                      'validate_dosing', 'suggest_alternatives', 'comprehensive')
            additional_data: Additional data for the task (medications list, patient info, etc.)
            
        Returns:
            Dict containing success status and analysis result or error
        """
        try:
            # Check if medication agent is enabled
            if not agent_manager.is_agent_enabled(AgentType.MEDICATION):
                return {
                    "success": False, 
                    "error": "Medication agent is not enabled. Please enable it in settings."
                }
            
            # Prepare input data based on task type
            input_data = additional_data or {}
            
            if task_type == "extract":
                input_data["clinical_text"] = text
                task_desc = "Extract medications from clinical text"
            elif task_type == "check_interactions":
                if "medications" not in input_data:
                    return {"success": False, "error": "Medications list required for interaction check"}
                task_desc = "Check for drug-drug interactions"
            elif task_type == "validate_dosing":
                if "medication" not in input_data:
                    return {"success": False, "error": "Medication information required for dosing validation"}
                task_desc = "Validate medication dosing"
            elif task_type == "suggest_alternatives":
                if "current_medication" not in input_data:
                    return {"success": False, "error": "Current medication required for alternative suggestions"}
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
                logging.info(f"Medication {task_type} completed successfully")
                return {
                    "success": True,
                    "text": response.result,
                    "metadata": response.metadata
                }
            else:
                error_msg = response.error if response else "Medication agent not available"
                logging.error(f"Medication {task_type} failed: {error_msg}")
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            logging.error(f"Failed to analyze medications: {e}")
            return {"success": False, "error": str(e)}
    
    def extract_medications_from_soap(self, soap_note: str) -> Dict[str, Any]:
        """Extract medications from a SOAP note.
        
        Args:
            soap_note: SOAP note text
            
        Returns:
            Dict containing success status and extracted medications or error
        """
        return self.analyze_medications(soap_note, task_type="extract")
    
    def check_medication_interactions(self, medications: list) -> Dict[str, Any]:
        """Check for drug interactions between medications.
        
        Args:
            medications: List of medication names
            
        Returns:
            Dict containing success status and interaction analysis or error
        """
        return self.analyze_medications(
            "", 
            task_type="check_interactions",
            additional_data={"medications": medications}
        )
    
    def validate_medication_dosing(self, medication: Dict[str, str], 
                                 patient_factors: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate medication dosing based on patient factors.
        
        Args:
            medication: Dict with medication name, dose, frequency
            patient_factors: Optional dict with age, weight, renal function, etc.
            
        Returns:
            Dict containing success status and dosing validation or error
        """
        return self.analyze_medications(
            "",
            task_type="validate_dosing",
            additional_data={
                "medication": medication,
                "patient_factors": patient_factors or {}
            }
        )
    
    def generate_differential_diagnosis(self, transcript: str) -> Dict[str, Any]:
        """Generate differential diagnosis from transcript.
        
        Args:
            transcript: The medical transcript to analyze
            
        Returns:
            Dict containing success status and analysis or error
        """
        try:
            if not transcript.strip():
                return {"success": False, "error": "No transcript to analyze"}
            
            # Get advanced analysis settings
            analysis_settings = SETTINGS.get("advanced_analysis", {})
            
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
            
            # Get the model based on current AI provider
            ai_provider = SETTINGS.get("ai_provider", "openai")
            
            # Select the appropriate model based on provider
            if ai_provider == "openai":
                model = analysis_settings.get("model", "gpt-4")
            elif ai_provider == "perplexity":
                model = analysis_settings.get("perplexity_model", "sonar-reasoning-pro")
            elif ai_provider == "grok":
                model = analysis_settings.get("grok_model", "grok-1")
            elif ai_provider == "ollama":
                model = analysis_settings.get("ollama_model", "llama3")
            elif ai_provider == "anthropic":
                model = analysis_settings.get("anthropic_model", "claude-3-sonnet-20240229")
            else:
                # Fallback to OpenAI model
                model = analysis_settings.get("model", "gpt-4")
            
            # Get provider-specific temperature if available
            temp_key = f"{ai_provider}_temperature"
            if temp_key in analysis_settings:
                temperature = analysis_settings[temp_key]
            
            # Generate analysis
            analysis = call_ai(model, system_message, prompt, temperature)
            
            logging.info("Generated differential diagnosis successfully")
            return {"success": True, "text": analysis}
            
        except Exception as e:
            logging.error(f"Failed to generate differential diagnosis: {e}")
            return {"success": False, "error": str(e)}
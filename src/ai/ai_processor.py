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
"""
Synopsis agent for generating concise summaries of SOAP notes.
"""

import logging
from typing import Optional, TYPE_CHECKING

from .base import BaseAgent
from .models import AgentConfig, AgentTask, AgentResponse

if TYPE_CHECKING:
    from .ai_caller import AICallerProtocol


logger = logging.getLogger(__name__)


class SynopsisAgent(BaseAgent):
    """Agent specialized in generating clinical synopses from SOAP notes."""
    
    # Default configuration for synopsis agent
    DEFAULT_CONFIG = AgentConfig(
        name="SynopsisAgent",
        description="Generates concise clinical synopses from SOAP notes",
        system_prompt="""You are a medical documentation specialist. Your task is to create concise, 
        clinically relevant synopses from SOAP notes. The synopsis should:
        
        1. Be under 200 words
        2. Capture the key clinical findings and plan
        3. Use clear, professional medical language
        4. Focus on the most important diagnostic and treatment information
        5. Maintain the clinical context and patient safety considerations
        
        Format the synopsis as a single paragraph that a healthcare provider could quickly read
        to understand the essential clinical picture.""",
        model="gpt-4",
        temperature=0.3,  # Lower temperature for more focused summaries
        max_tokens=300  # Limit tokens to ensure concise output
    )
    
    def __init__(self, config: Optional[AgentConfig] = None, ai_caller: Optional['AICallerProtocol'] = None):
        """
        Initialize the synopsis agent.

        Args:
            config: Optional custom configuration. Uses default if not provided.
            ai_caller: Optional AI caller for dependency injection.
        """
        super().__init__(config or self.DEFAULT_CONFIG, ai_caller=ai_caller)
        
    def execute(self, task: AgentTask) -> AgentResponse:
        """
        Generate a synopsis from a SOAP note.
        
        Args:
            task: Task containing the SOAP note in input_data['soap_note']
            
        Returns:
            AgentResponse with the synopsis
        """
        try:
            # Extract SOAP note from task
            soap_note = task.input_data.get('soap_note', '')
            if not soap_note:
                return AgentResponse(
                    result="",
                    success=False,
                    error="No SOAP note provided in task input_data"
                )
            
            # Build the prompt
            prompt = self._build_prompt(soap_note, task.context)
            
            # Call AI to generate synopsis
            synopsis = self._call_ai(prompt)
            
            # Clean and validate the synopsis
            synopsis = self._clean_synopsis(synopsis)
            
            # Check word count
            word_count = len(synopsis.split())
            if word_count > 200:
                logger.warning(f"Synopsis exceeded 200 words ({word_count} words). Truncating...")
                synopsis = self._truncate_to_word_limit(synopsis, 200)
            
            # Create response
            response = AgentResponse(
                result=synopsis,
                thoughts=f"Generated {word_count} word synopsis from SOAP note",
                success=True,
                metadata={
                    'word_count': word_count,
                    'soap_length': len(soap_note),
                    'model_used': self.config.model
                }
            )
            
            # Add to history
            self.add_to_history(task, response)
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating synopsis: {e}")
            return AgentResponse(
                result="",
                success=False,
                error=str(e)
            )
    
    def _build_prompt(self, soap_note: str, context: Optional[str] = None) -> str:
        """Build the prompt for synopsis generation."""
        prompt_parts = []
        
        if context:
            prompt_parts.append(f"Additional Context: {context}\n")
            
        prompt_parts.append("Please create a clinical synopsis (under 200 words) for the following SOAP note:\n")
        prompt_parts.append(f"SOAP Note:\n{soap_note}\n")
        prompt_parts.append("Synopsis:")
        
        return "\n".join(prompt_parts)
    
    def _clean_synopsis(self, synopsis: str) -> str:
        """Clean and format the synopsis."""
        # Remove any leading/trailing whitespace
        synopsis = synopsis.strip()
        
        # Remove any markdown formatting
        synopsis = synopsis.replace('**', '').replace('*', '')
        
        # Remove any leading "Synopsis:" or similar labels
        for prefix in ['Synopsis:', 'Summary:', 'Clinical Synopsis:']:
            if synopsis.startswith(prefix):
                synopsis = synopsis[len(prefix):].strip()
                
        return synopsis
    
    def _truncate_to_word_limit(self, text: str, word_limit: int) -> str:
        """Truncate text to specified word limit, ending at sentence boundary."""
        words = text.split()
        if len(words) <= word_limit:
            return text
            
        # Find the last complete sentence within the word limit
        truncated_words = words[:word_limit]
        truncated_text = ' '.join(truncated_words)
        
        # Find the last sentence ending
        last_period = truncated_text.rfind('.')
        last_question = truncated_text.rfind('?')
        last_exclamation = truncated_text.rfind('!')
        
        last_sentence_end = max(last_period, last_question, last_exclamation)
        
        if last_sentence_end > 0:
            return truncated_text[:last_sentence_end + 1]
        else:
            # If no sentence ending found, just truncate and add ellipsis
            return truncated_text + "..."
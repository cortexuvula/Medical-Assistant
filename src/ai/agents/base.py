"""
Base agent class for all agents in the system.

This module uses dependency injection for AI calls to avoid circular imports.
The AICallerProtocol defines the interface, and DefaultAICaller provides the
standard implementation that lazily loads AI functions.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, TYPE_CHECKING
import logging

from .models import AgentConfig, AgentTask, AgentResponse
from .ai_caller import AICallerProtocol, get_default_ai_caller

if TYPE_CHECKING:
    from .ai_caller import BaseAICaller


logger = logging.getLogger(__name__)

# Maximum prompt length for agent AI calls (characters)
# This is a safety limit to prevent excessive token usage and API errors
MAX_AGENT_PROMPT_LENGTH = 50000

# Maximum system message length
MAX_SYSTEM_MESSAGE_LENGTH = 10000

# Maximum history entries to keep per agent (prevents memory growth)
MAX_AGENT_HISTORY_SIZE = 100


class BaseAgent(ABC):
    """Abstract base class for all agents.

    Uses dependency injection for AI calls to avoid circular imports.
    An AICallerProtocol implementation can be injected at construction time,
    or the default caller will be used.
    """

    def __init__(self, config: AgentConfig, ai_caller: Optional[AICallerProtocol] = None):
        """
        Initialize the agent with configuration.

        Args:
            config: Agent configuration
            ai_caller: Optional AI caller implementation for dependency injection.
                      If not provided, uses the default AI caller singleton.
        """
        self.config = config
        self.history: list = []
        self._ai_caller = ai_caller or get_default_ai_caller()
        
    @abstractmethod
    def execute(self, task: AgentTask) -> AgentResponse:
        """
        Execute a task and return the response.
        
        Args:
            task: The task to execute
            
        Returns:
            Agent response with result
        """
        pass
    
    @property
    def ai_caller(self) -> AICallerProtocol:
        """Get the AI caller for this agent.

        Returns:
            The AI caller implementation used by this agent.
        """
        return self._ai_caller
    
    def _validate_and_sanitize_input(self, prompt: str, system_message: str) -> tuple[str, str]:
        """
        Validate and sanitize prompt and system message before sending to AI.

        Args:
            prompt: The user prompt to validate
            system_message: The system message to validate

        Returns:
            Tuple of (sanitized_prompt, sanitized_system_message)

        Raises:
            ValueError: If inputs are invalid or too large
        """
        # Import sanitization utility
        from utils.validation import sanitize_prompt

        # Validate prompt is not empty
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        # Validate prompt length
        if len(prompt) > MAX_AGENT_PROMPT_LENGTH:
            logger.warning(
                f"Agent {self.config.name}: Prompt length ({len(prompt)}) exceeds maximum "
                f"({MAX_AGENT_PROMPT_LENGTH}). Truncating."
            )
            prompt = prompt[:MAX_AGENT_PROMPT_LENGTH] + "\n\n[Content truncated due to length]"

        # Validate system message length
        if system_message and len(system_message) > MAX_SYSTEM_MESSAGE_LENGTH:
            logger.warning(
                f"Agent {self.config.name}: System message length ({len(system_message)}) exceeds "
                f"maximum ({MAX_SYSTEM_MESSAGE_LENGTH}). Truncating."
            )
            system_message = system_message[:MAX_SYSTEM_MESSAGE_LENGTH]

        # Sanitize the prompt to remove potentially dangerous content
        sanitized_prompt = sanitize_prompt(prompt)

        # Log if sanitization changed the prompt significantly
        if len(sanitized_prompt) < len(prompt) * 0.9:  # More than 10% removed
            logger.warning(
                f"Agent {self.config.name}: Prompt was significantly modified during sanitization "
                f"(original: {len(prompt)} chars, sanitized: {len(sanitized_prompt)} chars)"
            )

        return sanitized_prompt, system_message or ""

    def _call_ai(self, prompt: str, **kwargs) -> str:
        """
        Call the AI provider with the given prompt.

        Uses the injected AI caller to avoid circular imports and enable
        dependency injection for testing.

        Args:
            prompt: The prompt to send
            **kwargs: Additional arguments for the AI call

        Returns:
            AI response text

        Raises:
            ValueError: If prompt validation fails
            Exception: If AI call fails
        """
        # Extract parameters with fallbacks to config
        model = kwargs.get('model', self.config.model)
        system_message = kwargs.get('system_message', self.config.system_prompt)
        temperature = kwargs.get('temperature', self.config.temperature)

        # Validate and sanitize inputs before sending to AI
        try:
            sanitized_prompt, sanitized_system_message = self._validate_and_sanitize_input(
                prompt, system_message
            )
        except ValueError as e:
            logger.error(f"Input validation failed for agent {self.config.name}: {e}")
            raise

        try:
            # Use the injected AI caller - it handles provider routing
            if hasattr(self.config, 'provider') and self.config.provider:
                # Use provider-specific call
                logger.info(f"Agent {self.config.name} calling provider={self.config.provider}, model={model}")
                response = self._ai_caller.call_with_provider(
                    provider=self.config.provider,
                    model=model,
                    system_message=sanitized_system_message,
                    prompt=sanitized_prompt,
                    temperature=temperature
                )
            else:
                # Use default routing
                logger.info(f"Agent {self.config.name} using default routing with model={model}")
                response = self._ai_caller.call(
                    model=model,
                    system_message=sanitized_system_message,
                    prompt=sanitized_prompt,
                    temperature=temperature
                )
            return response
        except Exception as e:
            logger.error(f"Error calling AI for agent {self.config.name}: {e}")
            raise
            
    def add_to_history(self, task: AgentTask, response: AgentResponse):
        """Add a task and response to the agent's history.

        Automatically prunes old entries when history exceeds MAX_AGENT_HISTORY_SIZE.
        """
        self.history.append({
            'task': task,
            'response': response
        })

        # Prune old entries if history is too large
        if len(self.history) > MAX_AGENT_HISTORY_SIZE:
            # Keep only the most recent entries
            self.history = self.history[-MAX_AGENT_HISTORY_SIZE:]
            logger.debug(f"Agent {self.config.name}: Pruned history to {MAX_AGENT_HISTORY_SIZE} entries")
        
    def clear_history(self):
        """Clear the agent's history."""
        self.history.clear()
        
    def get_context_from_history(self, max_entries: int = 5) -> str:
        """
        Get context from recent history.
        
        Args:
            max_entries: Maximum number of history entries to include
            
        Returns:
            Formatted context string
        """
        if not self.history:
            return ""
            
        recent_history = self.history[-max_entries:]
        context_parts = []
        
        for entry in recent_history:
            task = entry['task']
            response = entry['response']
            
            context_parts.append(f"Task: {task.task_description}")
            if task.context:
                context_parts.append(f"Context: {task.context}")
            context_parts.append(f"Result: {response.result}")
            context_parts.append("")  # Empty line between entries
            
        return "\n".join(context_parts)
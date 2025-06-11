"""
Base agent class for all agents in the system.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging

from .models import AgentConfig, AgentTask, AgentResponse


logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all agents."""
    
    def __init__(self, config: AgentConfig):
        """
        Initialize the agent with configuration.
        
        Args:
            config: Agent configuration
        """
        self.config = config
        self.history: list = []
        self._ai_provider = None
        
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
    
    def _get_ai_provider(self):
        """Get the AI provider for this agent."""
        if self._ai_provider is None:
            # Import here to avoid circular imports
            from ..ai import get_ai_provider
            self._ai_provider = get_ai_provider(self.config.provider or self.config.model)
        return self._ai_provider
    
    def _call_ai(self, prompt: str, **kwargs) -> str:
        """
        Call the AI provider with the given prompt.
        
        Args:
            prompt: The prompt to send
            **kwargs: Additional arguments for the AI call
            
        Returns:
            AI response text
        """
        # Import here to avoid circular imports
        from ..ai import call_ai
        
        # Extract only the kwargs that call_ai expects
        # call_ai signature: (model, system_message, prompt, temperature)
        model = kwargs.get('model', self.config.model)
        system_message = kwargs.get('system_message', self.config.system_prompt)
        temperature = kwargs.get('temperature', self.config.temperature)
        
        try:
            response = call_ai(
                model=model,
                system_message=system_message,
                prompt=prompt,
                temperature=temperature
            )
            return response
        except Exception as e:
            logger.error(f"Error calling AI for agent {self.config.name}: {e}")
            raise
            
    def add_to_history(self, task: AgentTask, response: AgentResponse):
        """Add a task and response to the agent's history."""
        self.history.append({
            'task': task,
            'response': response
        })
        
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
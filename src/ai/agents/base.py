"""
Base agent class for all agents in the system.

This module uses dependency injection for AI calls to avoid circular imports.
The AICallerProtocol defines the interface, and DefaultAICaller provides the
standard implementation that lazily loads AI functions.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, TYPE_CHECKING, List
import json
import hashlib
import time

from .models import AgentConfig, AgentTask, AgentResponse
from .ai_caller import AICallerProtocol, get_default_ai_caller
from utils.structured_logging import get_logger

if TYPE_CHECKING:
    from .ai_caller import BaseAICaller


logger = get_logger(__name__)

# Maximum prompt length for agent AI calls (characters)
# This is a safety limit to prevent excessive token usage and API errors
MAX_AGENT_PROMPT_LENGTH = 50000

# Maximum system message length
MAX_SYSTEM_MESSAGE_LENGTH = 10000

# Maximum history entries to keep per agent (prevents memory growth)
MAX_AGENT_HISTORY_SIZE = 100

# Cache settings for agent responses
AGENT_CACHE_TTL_SECONDS = 300  # 5 minutes
MAX_CACHE_ENTRIES = 50  # Maximum cached responses per agent


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

        # Response cache: {hash: (response, timestamp)}
        self._response_cache: Dict[str, tuple] = {}
        self._cache_enabled = True
        
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

    def _validate_task_input(
        self,
        task: AgentTask,
        required_fields: Optional[List[str]] = None
    ) -> None:
        """
        Validate task input data before processing.

        This method should be called at the start of execute() implementations
        to ensure the task has valid structure and required fields.

        Args:
            task: The task to validate
            required_fields: Optional list of required field names in task.input_data.
                           If any are missing, ValueError is raised.

        Raises:
            ValueError: If task validation fails (wrong type, missing fields, etc.)

        Example:
            def execute(self, task: AgentTask) -> AgentResponse:
                self._validate_task_input(task, required_fields=['clinical_text'])
                # Now we can safely access task.input_data['clinical_text']
        """
        # Validate task is AgentTask instance
        if not isinstance(task, AgentTask):
            raise ValueError(
                f"Task must be an AgentTask instance, got {type(task).__name__}"
            )

        # Validate input_data is a dictionary
        if not isinstance(task.input_data, dict):
            raise ValueError(
                f"Task input_data must be a dictionary, got {type(task.input_data).__name__}"
            )

        # Validate task_description is not empty
        if not task.task_description or not task.task_description.strip():
            raise ValueError("Task description cannot be empty")

        # Validate required fields exist in input_data
        if required_fields:
            missing_fields = [
                field for field in required_fields
                if field not in task.input_data
            ]
            if missing_fields:
                raise ValueError(
                    f"Missing required fields in input_data: {missing_fields}"
                )

            # Check that required fields have non-empty values
            empty_fields = [
                field for field in required_fields
                if field in task.input_data and not task.input_data[field]
            ]
            if empty_fields:
                logger.warning(
                    f"Agent {self.config.name}: Required fields have empty values: {empty_fields}"
                )

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

    # =========================================================================
    # Structured Output Methods
    # =========================================================================

    def _get_structured_response(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get AI response in structured JSON format.

        This method instructs the AI to return a JSON response matching the provided
        schema, then parses and validates the response.

        Args:
            prompt: The prompt to send to the AI
            response_schema: JSON schema describing the expected response structure.
                           Used to instruct the AI on the output format.
            **kwargs: Additional arguments for the AI call

        Returns:
            Parsed JSON response as a dictionary

        Raises:
            ValueError: If the AI response is not valid JSON
            json.JSONDecodeError: If JSON parsing fails

        Example:
            schema = {
                "medications": [{"name": "str", "dose": "str", "frequency": "str"}],
                "interactions": [{"drug1": "str", "drug2": "str", "severity": "str"}]
            }
            result = self._get_structured_response(prompt, schema)
        """
        # Build enhanced system message requesting JSON output
        base_system_message = kwargs.get('system_message', self.config.system_prompt) or ""

        json_instruction = f"""
{base_system_message}

CRITICAL: You MUST respond with ONLY valid JSON. No additional text, explanations, or markdown.

Expected JSON structure:
```json
{json.dumps(response_schema, indent=2)}
```

Rules:
1. Output ONLY the JSON object, starting with {{ and ending with }}
2. Do not include ```json or ``` markers
3. Ensure all strings are properly escaped
4. Use null for missing optional values
5. Arrays can be empty [] if no items match
"""

        # Override system message with JSON-aware version
        kwargs['system_message'] = json_instruction

        # Call AI and parse response
        response_text = self._call_ai(prompt, **kwargs)

        # Clean up response - remove any markdown code blocks
        cleaned_response = self._clean_json_response(response_text)

        try:
            parsed = json.loads(cleaned_response)
            logger.debug(f"Agent {self.config.name}: Successfully parsed structured response")
            return parsed
        except json.JSONDecodeError as e:
            logger.warning(
                f"Agent {self.config.name}: Failed to parse JSON response. "
                f"Error: {e}. Response: {cleaned_response[:500]}..."
            )
            # Attempt recovery by extracting JSON from response
            recovered = self._extract_json_from_text(response_text)
            if recovered:
                logger.info(f"Agent {self.config.name}: Recovered JSON from response")
                return recovered
            raise ValueError(f"AI response was not valid JSON: {e}")

    def _clean_json_response(self, response: str) -> str:
        """
        Clean up AI response to extract pure JSON.

        Removes markdown code blocks, leading/trailing whitespace, and other
        common formatting issues.

        Args:
            response: Raw AI response text

        Returns:
            Cleaned JSON string
        """
        cleaned = response.strip()

        # Remove markdown code blocks
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        cleaned = cleaned.strip()

        # Find the JSON object boundaries
        start_idx = cleaned.find('{')
        end_idx = cleaned.rfind('}')

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            cleaned = cleaned[start_idx:end_idx + 1]

        return cleaned

    def _extract_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to extract JSON object from mixed text response.

        Args:
            text: Text that may contain JSON

        Returns:
            Parsed JSON dict if found, None otherwise
        """
        # Try to find JSON object in the text
        brace_count = 0
        start_idx = None

        for i, char in enumerate(text):
            if char == '{':
                if start_idx is None:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx is not None:
                    try:
                        json_str = text[start_idx:i + 1]
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        start_idx = None
                        continue

        return None

    def _get_structured_response_with_fallback(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        fallback_parser: Optional[callable] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get structured response with optional fallback to text parsing.

        This is a robust version that falls back to a custom parser if
        JSON parsing fails entirely.

        Args:
            prompt: The prompt to send to the AI
            response_schema: Expected JSON structure
            fallback_parser: Optional function(text) -> dict that parses free text
            **kwargs: Additional arguments for AI call

        Returns:
            Parsed response as dictionary

        Raises:
            ValueError: If both JSON parsing and fallback parser fail
        """
        try:
            return self._get_structured_response(prompt, response_schema, **kwargs)
        except (ValueError, json.JSONDecodeError) as e:
            if fallback_parser:
                logger.info(
                    f"Agent {self.config.name}: JSON parsing failed, using fallback parser"
                )
                # Get raw response for fallback parsing
                raw_response = self._call_ai(prompt, **kwargs)
                return fallback_parser(raw_response)
            raise

    # =========================================================================
    # Response Caching Methods
    # =========================================================================

    def _compute_cache_key(self, prompt: str, **kwargs) -> str:
        """
        Compute a cache key for the given prompt and parameters.

        Args:
            prompt: The prompt text
            **kwargs: Additional parameters that affect the response

        Returns:
            SHA256 hash string as cache key
        """
        # Include relevant parameters that would change the response
        key_parts = [
            prompt,
            str(kwargs.get('model', self.config.model)),
            str(kwargs.get('temperature', self.config.temperature)),
            str(kwargs.get('system_message', '')[:500])  # First 500 chars of system message
        ]
        key_string = '|'.join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _get_cached_response(self, cache_key: str) -> Optional[str]:
        """
        Get a cached response if it exists and hasn't expired.

        Args:
            cache_key: The cache key to look up

        Returns:
            Cached response string, or None if not found/expired
        """
        if not self._cache_enabled:
            return None

        if cache_key in self._response_cache:
            response, timestamp = self._response_cache[cache_key]
            if time.time() - timestamp < AGENT_CACHE_TTL_SECONDS:
                logger.debug(f"Agent {self.config.name}: Cache hit for key {cache_key[:16]}...")
                return response
            else:
                # Cache entry expired, remove it
                del self._response_cache[cache_key]
                logger.debug(f"Agent {self.config.name}: Cache entry expired for key {cache_key[:16]}...")

        return None

    def _cache_response(self, cache_key: str, response: str):
        """
        Cache a response with the current timestamp.

        Args:
            cache_key: The cache key
            response: The response to cache
        """
        if not self._cache_enabled:
            return

        # Prune cache if too large
        if len(self._response_cache) >= MAX_CACHE_ENTRIES:
            self._prune_cache()

        self._response_cache[cache_key] = (response, time.time())
        logger.debug(f"Agent {self.config.name}: Cached response for key {cache_key[:16]}...")

    def _prune_cache(self):
        """Remove expired and oldest cache entries to stay under limit."""
        current_time = time.time()

        # First, remove all expired entries
        expired_keys = [
            key for key, (_, timestamp) in self._response_cache.items()
            if current_time - timestamp >= AGENT_CACHE_TTL_SECONDS
        ]
        for key in expired_keys:
            del self._response_cache[key]

        # If still too large, remove oldest entries
        while len(self._response_cache) >= MAX_CACHE_ENTRIES:
            oldest_key = min(
                self._response_cache.keys(),
                key=lambda k: self._response_cache[k][1]
            )
            del self._response_cache[oldest_key]

        logger.debug(f"Agent {self.config.name}: Pruned cache to {len(self._response_cache)} entries")

    def _call_ai_cached(self, prompt: str, **kwargs) -> str:
        """
        Call AI with caching support.

        Checks cache first, returns cached response if valid.
        Otherwise calls AI and caches the response.

        Args:
            prompt: The prompt to send
            **kwargs: Additional arguments for the AI call

        Returns:
            AI response text (from cache or fresh)
        """
        cache_key = self._compute_cache_key(prompt, **kwargs)

        # Check cache first
        cached = self._get_cached_response(cache_key)
        if cached is not None:
            return cached

        # Call AI and cache result
        response = self._call_ai(prompt, **kwargs)
        self._cache_response(cache_key, response)
        return response

    def clear_cache(self):
        """Clear all cached responses."""
        self._response_cache.clear()
        logger.debug(f"Agent {self.config.name}: Cache cleared")

    def set_cache_enabled(self, enabled: bool):
        """
        Enable or disable response caching.

        Args:
            enabled: Whether caching should be enabled
        """
        self._cache_enabled = enabled
        if not enabled:
            self.clear_cache()
        logger.debug(f"Agent {self.config.name}: Caching {'enabled' if enabled else 'disabled'}")
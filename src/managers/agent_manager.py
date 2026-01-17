"""
Agent Manager Module

Manages AI agent instances and provides a unified interface for
accessing and using agents throughout the application.

Error Handling Contract:
- All public methods return None or a typed response rather than raising exceptions
- Internal errors are logged and wrapped in appropriate response types
- AgentResponse.success indicates whether the operation succeeded
- AgentResponse.error contains a human-readable error message when success=False
"""

import time
import asyncio
from typing import Dict, Optional, Type, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

from ai.agents.base import BaseAgent
from utils.structured_logging import get_logger
from ai.agents.models import (
    AgentConfig, AgentType, AgentTask, AgentResponse, SubAgentConfig,
    AdvancedConfig, RetryConfig, RetryStrategy, PerformanceMetrics,
    ResponseFormat
)
from ai.agents.ai_caller import AICallerProtocol, get_default_ai_caller
from ai.agents.synopsis import SynopsisAgent
from ai.agents.diagnostic import DiagnosticAgent
from ai.agents.medication import MedicationAgent
from ai.agents.referral import ReferralAgent
from ai.agents.data_extraction import DataExtractionAgent
from ai.agents.workflow import WorkflowAgent
from ai.agents.chat import ChatAgent
from settings.settings_manager import settings_manager
from utils.safe_eval import safe_eval


class AgentInitializationError(Exception):
    """Raised when an agent fails to initialize."""
    pass


class AgentExecutionError(Exception):
    """Raised when an agent execution fails."""
    pass


class AgentNotAvailableError(Exception):
    """Raised when a requested agent is not available."""
    pass


logger = get_logger(__name__)


class AgentManager:
    """Singleton manager for AI agents."""
    
    _instance = None
    
    # Agent class mapping
    AGENT_CLASSES: Dict[AgentType, Type[BaseAgent]] = {
        AgentType.SYNOPSIS: SynopsisAgent,
        AgentType.DIAGNOSTIC: DiagnosticAgent,
        AgentType.MEDICATION: MedicationAgent,
        AgentType.REFERRAL: ReferralAgent,
        AgentType.DATA_EXTRACTION: DataExtractionAgent,
        AgentType.WORKFLOW: WorkflowAgent,
        AgentType.CHAT: ChatAgent,
    }
    
    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super(AgentManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, ai_caller: Optional[AICallerProtocol] = None):
        """Initialize the agent manager.

        Args:
            ai_caller: Optional AI caller for dependency injection.
                      If not provided, uses the default AI caller.
                      This caller is passed to all created agents.
        """
        if self._initialized:
            return

        self._agents: Dict[AgentType, BaseAgent] = {}
        self._ai_caller = ai_caller or get_default_ai_caller()
        self._initialized = True
        self._load_agents()
        
    def _load_agents(self) -> None:
        """Load and initialize enabled agents from settings.

        Errors during initialization are logged but do not propagate,
        allowing other agents to still be loaded.
        """
        agent_config = settings_manager.get("agent_config", {})

        for agent_type in AgentType:
            agent_key = agent_type.value
            config_dict = agent_config.get(agent_key, {})

            # Only load enabled agents that have implementations
            if config_dict.get("enabled", False) and agent_type in self.AGENT_CLASSES:
                try:
                    self._initialize_agent(agent_type, config_dict)
                except (ValueError, TypeError, KeyError) as e:
                    logger.error(f"Configuration error for {agent_key} agent: {e}")
                except AgentInitializationError as e:
                    logger.error(f"Failed to initialize {agent_key} agent: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error initializing {agent_key} agent: {e}", exc_info=True)
                    
    def _initialize_agent(self, agent_type: AgentType, config_dict: dict):
        """Initialize a specific agent.
        
        Args:
            agent_type: The type of agent to initialize
            config_dict: Configuration dictionary from settings
        """
        agent_class = self.AGENT_CLASSES.get(agent_type)
        if not agent_class:
            logger.warning(f"No implementation found for agent type: {agent_type.value}")
            return
            
        # Create advanced config
        advanced_dict = config_dict.get("advanced", {})
        retry_dict = advanced_dict.get("retry_config", {})
        
        # Handle response format enum
        response_format = advanced_dict.get("response_format", ResponseFormat.PLAIN_TEXT.value)
        if isinstance(response_format, str):
            try:
                response_format = ResponseFormat(response_format)
            except ValueError:
                response_format = ResponseFormat.PLAIN_TEXT
        
        # Handle retry strategy enum
        retry_strategy = retry_dict.get("strategy", RetryStrategy.EXPONENTIAL_BACKOFF.value)
        if isinstance(retry_strategy, str):
            try:
                retry_strategy = RetryStrategy(retry_strategy)
            except ValueError:
                retry_strategy = RetryStrategy.EXPONENTIAL_BACKOFF
        
        advanced_config = AdvancedConfig(
            response_format=response_format,
            context_window_size=advanced_dict.get("context_window_size", 5),
            timeout_seconds=advanced_dict.get("timeout_seconds", 30.0),
            retry_config=RetryConfig(
                strategy=retry_strategy,
                max_retries=retry_dict.get("max_retries", 3),
                initial_delay=retry_dict.get("initial_delay", 1.0),
                max_delay=retry_dict.get("max_delay", 60.0),
                backoff_factor=retry_dict.get("backoff_factor", 2.0)
            ),
            enable_caching=advanced_dict.get("enable_caching", True),
            cache_ttl_seconds=advanced_dict.get("cache_ttl_seconds", 3600),
            enable_logging=advanced_dict.get("enable_logging", True),
            enable_metrics=advanced_dict.get("enable_metrics", True)
        )
        
        # Create sub-agent configs
        sub_agents = []
        for sub_agent_dict in config_dict.get("sub_agents", []):
            # Handle agent type enum
            agent_type_value = sub_agent_dict.get("agent_type")
            if agent_type_value:
                if isinstance(agent_type_value, str):
                    try:
                        agent_type_value = AgentType(agent_type_value)
                    except ValueError:
                        logger.warning(f"Invalid agent type: {agent_type_value}")
                        continue
                
                sub_agent_config = SubAgentConfig(
                    agent_type=agent_type_value,
                    enabled=sub_agent_dict.get("enabled", True),
                    priority=sub_agent_dict.get("priority", 0),
                    required=sub_agent_dict.get("required", False),
                    pass_context=sub_agent_dict.get("pass_context", True),
                    output_key=sub_agent_dict.get("output_key", f"{agent_type_value}_output"),
                    condition=sub_agent_dict.get("condition")
                )
                sub_agents.append(sub_agent_config)
        
        # Create AgentConfig from settings
        config = AgentConfig(
            name=agent_type.value,
            description=f"{agent_type.value.replace('_', ' ').title()} Agent",
            system_prompt=config_dict.get("system_prompt", ""),
            model=config_dict.get("model", "gpt-4"),
            temperature=config_dict.get("temperature", 0.7),
            max_tokens=config_dict.get("max_tokens"),
            provider=config_dict.get("provider"),
            advanced=advanced_config,
            sub_agents=sub_agents
        )
        
        # For SynopsisAgent, merge with default config if system prompt is empty
        if agent_type == AgentType.SYNOPSIS and not config.system_prompt:
            # Import here to avoid circular imports
            from ai.agents.synopsis import SynopsisAgent
            config.system_prompt = SynopsisAgent.DEFAULT_CONFIG.system_prompt

        # Create agent instance with injected AI caller
        agent = agent_class(config, ai_caller=self._ai_caller)
        self._agents[agent_type] = agent
        logger.info(f"Initialized {agent_type.value} agent with provider={config.provider}, model={config.model}")
        
    def get_agent(self, agent_type: AgentType) -> Optional[BaseAgent]:
        """Get an agent instance by type.
        
        Args:
            agent_type: The type of agent to retrieve
            
        Returns:
            Agent instance if available and enabled, None otherwise
        """
        return self._agents.get(agent_type)
        
    def is_agent_enabled(self, agent_type: AgentType) -> bool:
        """Check if an agent is enabled.
        
        Args:
            agent_type: The type of agent to check
            
        Returns:
            True if agent is enabled, False otherwise
        """
        agent_config = settings_manager.get("agent_config", {})
        agent_key = agent_type.value
        return agent_config.get(agent_key, {}).get("enabled", False)
        
    def execute_agent_task(self, agent_type: AgentType, task: AgentTask) -> Optional[AgentResponse]:
        """Execute a task using the specified agent with retry logic and sub-agent support.

        Args:
            agent_type: The type of agent to use
            task: The task to execute

        Returns:
            AgentResponse with success=True and result if successful,
            AgentResponse with success=False and error message if failed,
            None only if the agent is not available/enabled

        Error Handling:
            - Network/API errors are retried according to retry_config
            - Timeout errors return failure response with timeout message
            - Validation errors return failure response immediately (no retry)
            - All errors are logged with appropriate severity
        """
        agent = self.get_agent(agent_type)
        if not agent:
            logger.warning(f"Agent {agent_type.value} not available or not enabled")
            return None

        start_time = time.time()
        retry_count = 0

        try:
            # Execute with retry logic
            response, retry_count = self._execute_with_retry(agent, task)

            # Execute sub-agents if configured
            if agent.config and agent.config.sub_agents:
                sub_results = self._execute_sub_agents(agent.config.sub_agents, task, response)
                response.sub_agent_results = sub_results

            # Add performance metrics if enabled
            if agent.config and agent.config.advanced.enable_metrics:
                end_time = time.time()
                response.metrics = PerformanceMetrics(
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=end_time - start_time,
                    tokens_used=0,  # Would be populated from actual usage
                    tokens_input=0,
                    tokens_output=0,
                    cost_estimate=0.0,
                    retry_count=retry_count,
                    cache_hit=False
                )

            return response

        except TimeoutError as e:
            error_msg = f"Agent {agent_type.value} timed out after {agent.config.advanced.timeout_seconds if agent.config else 30}s"
            logger.error(error_msg)
            return AgentResponse(
                result="",
                success=False,
                error=error_msg
            )
        except (ValueError, TypeError) as e:
            error_msg = f"Invalid input for {agent_type.value} agent: {e}"
            logger.error(error_msg)
            return AgentResponse(
                result="",
                success=False,
                error=error_msg
            )
        except AgentExecutionError as e:
            logger.error(f"Execution error with {agent_type.value} agent: {e}")
            return AgentResponse(
                result="",
                success=False,
                error=str(e)
            )
        except Exception as e:
            logger.error(f"Unexpected error executing task with {agent_type.value} agent: {e}", exc_info=True)
            return AgentResponse(
                result="",
                success=False,
                error=f"An unexpected error occurred: {str(e)}"
            )
            
    def _execute_with_retry(self, agent: BaseAgent, task: AgentTask) -> tuple[AgentResponse, int]:
        """Execute agent task with retry logic based on configuration.

        Args:
            agent: The agent to execute
            task: The task to execute

        Returns:
            Tuple of (AgentResponse from the agent, number of retries attempted)

        Raises:
            AgentExecutionError: If all retry attempts fail
        """
        if not agent.config or not agent.config.advanced.retry_config:
            return agent.execute(task), 0

        retry_config = agent.config.advanced.retry_config

        if retry_config.strategy == RetryStrategy.NO_RETRY:
            return agent.execute(task), 0

        last_error = None
        delay = retry_config.initial_delay
        retry_count = 0

        for attempt in range(retry_config.max_retries + 1):
            try:
                return agent.execute(task), retry_count
            except (ConnectionError, TimeoutError, OSError) as e:
                # Network-related errors - worth retrying
                last_error = e
                retry_count = attempt
                logger.warning(f"Attempt {attempt + 1} failed for {agent.config.name} (network error): {e}")
            except (ValueError, TypeError) as e:
                # Validation errors - don't retry, raise immediately
                raise
            except Exception as e:
                last_error = e
                retry_count = attempt
                logger.warning(f"Attempt {attempt + 1} failed for {agent.config.name}: {e}")

            if attempt < retry_config.max_retries:
                # Calculate next delay based on strategy
                if retry_config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
                    delay = min(delay * retry_config.backoff_factor, retry_config.max_delay)
                elif retry_config.strategy == RetryStrategy.LINEAR_BACKOFF:
                    delay = min(delay + retry_config.initial_delay, retry_config.max_delay)
                # FIXED_DELAY keeps the same delay

                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)

        # All retries failed
        raise AgentExecutionError(f"All {retry_config.max_retries + 1} attempts failed: {last_error}")
        
    def _execute_sub_agents(
        self,
        sub_agent_configs: List[SubAgentConfig],
        parent_task: AgentTask,
        parent_response: AgentResponse
    ) -> Dict[str, AgentResponse]:
        """Execute sub-agents based on configuration.

        Args:
            sub_agent_configs: List of sub-agent configurations
            parent_task: The parent task
            parent_response: The parent agent's response

        Returns:
            Dictionary mapping output keys to sub-agent responses.
            Failed sub-agents will have success=False in their response.
        """
        results: Dict[str, AgentResponse] = {}

        # Sort by priority (higher priority first)
        sorted_configs = sorted(sub_agent_configs, key=lambda x: x.priority, reverse=True)

        # Filter enabled sub-agents
        enabled_configs = [cfg for cfg in sorted_configs if cfg.enabled]

        if not enabled_configs:
            return results

        # Execute sub-agents
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Prepare futures
            futures: Dict[Any, SubAgentConfig] = {}

            for sub_config in enabled_configs:
                # Check condition if specified
                if sub_config.condition and not self._evaluate_condition(
                    sub_config.condition, parent_task, parent_response, results
                ):
                    logger.info(f"Skipping sub-agent {sub_config.agent_type.value} due to condition")
                    continue

                # Prepare sub-task
                sub_task = self._prepare_sub_task(sub_config, parent_task, parent_response)

                # Submit for execution
                future = executor.submit(
                    self.execute_agent_task,
                    sub_config.agent_type,
                    sub_task
                )
                futures[future] = sub_config

            # Collect results
            for future in as_completed(futures):
                sub_config = futures[future]

                try:
                    sub_response = future.result()

                    if sub_response:
                        results[sub_config.output_key] = sub_response

                        # Check if required sub-agent failed
                        if sub_config.required and not sub_response.success:
                            logger.error(
                                f"Required sub-agent {sub_config.agent_type.value} failed: {sub_response.error}"
                            )

                except FuturesTimeoutError:
                    error_msg = f"Sub-agent {sub_config.agent_type.value} timed out"
                    logger.error(error_msg)
                    results[sub_config.output_key] = AgentResponse(
                        result="",
                        success=False,
                        error=error_msg
                    )
                except Exception as e:
                    error_msg = f"Error executing sub-agent {sub_config.agent_type.value}: {e}"
                    logger.error(error_msg, exc_info=True)

                    # Always record failure for sub-agents, regardless of required status
                    results[sub_config.output_key] = AgentResponse(
                        result="",
                        success=False,
                        error=str(e)
                    )

        return results
        
    def _evaluate_condition(
        self,
        condition: str,
        task: AgentTask,
        response: AgentResponse,
        sub_results: Dict[str, AgentResponse]
    ) -> bool:
        """Evaluate a condition expression safely.

        Args:
            condition: The condition expression
            task: The current task
            response: The current response
            sub_results: Results from previous sub-agents

        Returns:
            True if condition is met, False otherwise
        """
        # Build evaluation context with safe access to task/response data
        context = {
            "task": task,
            "task_description": task.task_description if task else "",
            "task_context": task.context if task else "",
            "input_data": task.input_data if task else {},
            "response": response,
            "result": response.result if response else "",
            "success": response.success if response else False,
            "results": sub_results,
        }

        # Use safe expression evaluator instead of eval()
        result = safe_eval(condition, context, default=True)

        if not isinstance(result, bool):
            # Convert to boolean if needed
            result = bool(result)

        return result
            
    def _prepare_sub_task(
        self,
        sub_config: SubAgentConfig,
        parent_task: AgentTask,
        parent_response: AgentResponse
    ) -> AgentTask:
        """Prepare a task for a sub-agent.
        
        Args:
            sub_config: Sub-agent configuration
            parent_task: Parent task
            parent_response: Parent agent's response
            
        Returns:
            Task for the sub-agent
        """
        # Build context for sub-agent
        context_parts = []
        
        if sub_config.pass_context and parent_task.context:
            context_parts.append(f"Parent context: {parent_task.context}")
            
        if parent_response.result:
            context_parts.append(f"Parent result: {parent_response.result}")
            
        context = "\n\n".join(context_parts) if context_parts else None
        
        # Create sub-task
        return AgentTask(
            task_description=f"Sub-task from {parent_task.task_description}",
            context=context,
            input_data={
                **parent_task.input_data,
                "parent_result": parent_response.result,
                "parent_thoughts": parent_response.thoughts
            },
            max_iterations=parent_task.max_iterations
        )
            
    def reload_agents(self):
        """Reload agents from current settings."""
        logger.info("Reloading agents from settings")
        # Reload settings from file to get latest changes
        settings_manager.reload()
        self._agents.clear()
        self._load_agents()
        
    def get_enabled_agents(self) -> Dict[AgentType, BaseAgent]:
        """Get all currently enabled agents.
        
        Returns:
            Dictionary of enabled agent types to agent instances
        """
        return self._agents.copy()
        
    def generate_synopsis(self, soap_note: str, context: Optional[str] = None) -> Optional[str]:
        """Convenience method to generate a synopsis from a SOAP note.
        
        Args:
            soap_note: The SOAP note text
            context: Optional additional context
            
        Returns:
            Synopsis text if successful, None otherwise
        """
        if not self.is_agent_enabled(AgentType.SYNOPSIS):
            logger.info("Synopsis agent is not enabled")
            return None
            
        task = AgentTask(
            task_description="Generate a clinical synopsis from this SOAP note",
            context=context,
            input_data={"soap_note": soap_note}
        )
        
        response = self.execute_agent_task(AgentType.SYNOPSIS, task)
        if response and response.success:
            return response.result
        return None


# Global agent manager instance
agent_manager = AgentManager()
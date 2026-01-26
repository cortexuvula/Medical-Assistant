"""
Pydantic models for the agent system.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Literal, Union
from enum import Enum
from datetime import timedelta


class ToolParameter(BaseModel):
    """Represents a parameter for an agent tool."""
    name: str = Field(..., description="Parameter name")
    type: Literal["string", "integer", "boolean", "object", "array", "number"] = Field(..., description="Parameter type")
    description: str = Field(..., description="Parameter description")
    required: bool = Field(True, description="Whether the parameter is required")
    default: Optional[Any] = Field(None, description="Default value if not required")


class Tool(BaseModel):
    """Represents a tool that an agent can use."""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: List[ToolParameter] = Field(default_factory=list, description="Tool parameters")
    
    
class ToolCall(BaseModel):
    """Represents a call to a tool by an agent."""
    tool_name: str = Field(..., description="Name of the tool to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to the tool")
    

class AgentTask(BaseModel):
    """Input model for agent tasks."""
    task_description: str = Field(..., description="Description of the task to perform")
    context: Optional[str] = Field(None, description="Additional context for the task")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Input data for the task")
    max_iterations: Optional[int] = Field(5, description="Maximum iterations for the agent")
    

class PerformanceMetrics(BaseModel):
    """Performance metrics for agent execution."""
    start_time: float = Field(..., description="Start timestamp")
    end_time: float = Field(..., description="End timestamp")
    duration_seconds: float = Field(..., description="Total execution time in seconds")
    tokens_used: int = Field(0, description="Total tokens consumed")
    tokens_input: int = Field(0, description="Input tokens")
    tokens_output: int = Field(0, description="Output tokens")
    cost_estimate: float = Field(0.0, description="Estimated cost in USD")
    retry_count: int = Field(0, description="Number of retries")
    cache_hit: bool = Field(False, description="Whether response was from cache")
    

class AgentType(str, Enum):
    """Types of agents available in the system."""
    SYNOPSIS = "synopsis"
    DIAGNOSTIC = "diagnostic"
    MEDICATION = "medication"
    REFERRAL = "referral"
    DATA_EXTRACTION = "data_extraction"
    WORKFLOW = "workflow"
    CHAT = "chat"
    COMPLIANCE = "compliance"


class ResponseFormat(str, Enum):
    """Output format options for agent responses."""
    PLAIN_TEXT = "plain_text"
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"


class RetryStrategy(str, Enum):
    """Retry strategies for failed agent operations."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    NO_RETRY = "no_retry"


class AgentResponse(BaseModel):
    """Output model for agent responses."""
    result: str = Field(..., description="The agent's result/output")
    thoughts: Optional[str] = Field(None, description="Agent's reasoning process")
    tool_calls: List[ToolCall] = Field(default_factory=list, description="Tools called during execution")
    success: bool = Field(True, description="Whether the task was successful")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    metrics: Optional[PerformanceMetrics] = Field(None, description="Performance metrics")
    sub_agent_results: Dict[str, 'AgentResponse'] = Field(default_factory=dict, description="Results from sub-agents")
    

class RetryConfig(BaseModel):
    """Configuration for retry logic."""
    strategy: RetryStrategy = Field(RetryStrategy.EXPONENTIAL_BACKOFF, description="Retry strategy")
    max_retries: int = Field(3, ge=0, le=10, description="Maximum number of retries")
    initial_delay: float = Field(1.0, ge=0.1, le=60.0, description="Initial delay in seconds")
    max_delay: float = Field(60.0, ge=1.0, le=300.0, description="Maximum delay in seconds")
    backoff_factor: float = Field(2.0, ge=1.0, le=10.0, description="Backoff multiplication factor")


class AdvancedConfig(BaseModel):
    """Advanced configuration options for agents."""
    response_format: ResponseFormat = Field(ResponseFormat.PLAIN_TEXT, description="Output format")
    context_window_size: int = Field(5, ge=0, le=20, description="Number of historical interactions to include")
    timeout_seconds: float = Field(30.0, ge=5.0, le=300.0, description="Timeout for agent operations")
    retry_config: RetryConfig = Field(default_factory=RetryConfig, description="Retry configuration")
    enable_caching: bool = Field(True, description="Whether to cache agent responses")
    cache_ttl_seconds: int = Field(3600, ge=0, description="Cache time-to-live in seconds")
    enable_logging: bool = Field(True, description="Whether to log agent operations")
    enable_metrics: bool = Field(True, description="Whether to collect performance metrics")
    

class SubAgentConfig(BaseModel):
    """Configuration for sub-agents."""
    agent_type: AgentType = Field(..., description="Type of the sub-agent")
    enabled: bool = Field(True, description="Whether the sub-agent is enabled")
    priority: int = Field(0, ge=0, le=100, description="Execution priority (higher = earlier)")
    required: bool = Field(False, description="Whether this sub-agent must succeed")
    pass_context: bool = Field(True, description="Whether to pass parent context to sub-agent")
    output_key: str = Field(..., description="Key to store sub-agent output")
    condition: Optional[str] = Field(None, description="Condition expression for conditional execution")


class AgentConfig(BaseModel):
    """Configuration for an agent."""
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    system_prompt: str = Field(..., description="System prompt for the agent")
    available_tools: List[Tool] = Field(default_factory=list, description="Tools available to the agent")
    model: str = Field("gpt-4", description="AI model to use")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Temperature for AI model")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens for response")
    provider: Optional[str] = Field(None, description="AI provider (if different from default)")
    # New fields
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig, description="Advanced configuration")
    sub_agents: List[SubAgentConfig] = Field(default_factory=list, description="Sub-agent configurations")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    version: str = Field("1.0.0", description="Configuration version")


class ChainNodeType(str, Enum):
    """Types of nodes in an agent chain."""
    AGENT = "agent"
    CONDITION = "condition"
    TRANSFORMER = "transformer"
    AGGREGATOR = "aggregator"
    PARALLEL = "parallel"
    LOOP = "loop"


class ChainNode(BaseModel):
    """Represents a node in an agent chain."""
    id: str = Field(..., description="Unique node identifier")
    type: ChainNodeType = Field(..., description="Type of node")
    name: str = Field(..., description="Node name")
    agent_type: Optional[AgentType] = Field(None, description="Agent type (if node type is AGENT)")
    config: Dict[str, Any] = Field(default_factory=dict, description="Node-specific configuration")
    inputs: List[str] = Field(default_factory=list, description="Input node IDs")
    outputs: List[str] = Field(default_factory=list, description="Output node IDs")
    position: Dict[str, float] = Field(default_factory=dict, description="Visual position (x, y)")


class AgentChain(BaseModel):
    """Represents a chain of agents working together."""
    id: str = Field(..., description="Unique chain identifier")
    name: str = Field(..., description="Chain name")
    description: str = Field(..., description="Chain description")
    nodes: List[ChainNode] = Field(default_factory=list, description="Nodes in the chain")
    start_node_id: str = Field(..., description="ID of the starting node")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chain metadata")


class AgentTemplate(BaseModel):
    """Template for pre-configured agent setups."""
    id: str = Field(..., description="Template ID")
    name: str = Field(..., description="Template name")
    description: str = Field(..., description="Template description")
    category: str = Field(..., description="Template category")
    agent_configs: Dict[AgentType, AgentConfig] = Field(..., description="Agent configurations")
    chain: Optional[AgentChain] = Field(None, description="Optional agent chain")
    tags: List[str] = Field(default_factory=list, description="Template tags")
    author: str = Field("system", description="Template author")
    version: str = Field("1.0.0", description="Template version")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
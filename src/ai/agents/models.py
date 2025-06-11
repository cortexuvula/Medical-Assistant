"""
Pydantic models for the agent system.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
from enum import Enum


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
    

class AgentResponse(BaseModel):
    """Output model for agent responses."""
    result: str = Field(..., description="The agent's result/output")
    thoughts: Optional[str] = Field(None, description="Agent's reasoning process")
    tool_calls: List[ToolCall] = Field(default_factory=list, description="Tools called during execution")
    success: bool = Field(True, description="Whether the task was successful")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    

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


class AgentType(str, Enum):
    """Types of agents available in the system."""
    SYNOPSIS = "synopsis"
    DIAGNOSTIC = "diagnostic"
    MEDICATION = "medication"
    REFERRAL = "referral"
    DATA_EXTRACTION = "data_extraction"
    WORKFLOW = "workflow"
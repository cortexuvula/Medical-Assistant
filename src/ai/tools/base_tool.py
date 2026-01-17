"""
Base tool class for all agent tools.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from ..agents.models import Tool, ToolParameter
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class ToolResult(BaseModel):
    """Result from a tool execution."""
    success: bool = Field(..., description="Whether the tool executed successfully")
    output: Any = Field(..., description="The output from the tool")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    requires_confirmation: bool = Field(False, description="Whether user confirmation is needed")
    confirmation_message: Optional[str] = Field(None, description="Message to show for confirmation")


class BaseTool(ABC):
    """Base class for all tools that agents can use."""
    
    def __init__(self):
        """Initialize the tool."""
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        
    @abstractmethod
    def get_definition(self) -> Tool:
        """
        Get the tool definition.
        
        Returns:
            Tool definition with name, description, and parameters
        """
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with the given arguments.
        
        Args:
            **kwargs: Tool-specific arguments
            
        Returns:
            ToolResult with output and status
        """
        pass
    
    def validate_arguments(self, **kwargs) -> Optional[str]:
        """
        Validate the arguments against the tool definition.
        
        Args:
            **kwargs: Arguments to validate
            
        Returns:
            Error message if validation fails, None if valid
        """
        tool_def = self.get_definition()
        
        # Check required parameters
        for param in tool_def.parameters:
            if param.required and param.name not in kwargs:
                return f"Missing required parameter: {param.name}"
                
        # Check parameter types
        for param in tool_def.parameters:
            if param.name in kwargs:
                value = kwargs[param.name]
                if not self._validate_type(value, param.type):
                    return f"Invalid type for {param.name}: expected {param.type}, got {type(value).__name__}"
                    
        return None
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate that a value matches the expected type."""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict
        }
        
        expected = type_map.get(expected_type)
        if expected is None:
            return True  # Unknown type, allow it
            
        return isinstance(value, expected)
    
    def safe_execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with validation and error handling.
        
        Args:
            **kwargs: Tool-specific arguments
            
        Returns:
            ToolResult with output and status
        """
        try:
            # Validate arguments
            error = self.validate_arguments(**kwargs)
            if error:
                return ToolResult(
                    success=False,
                    output=None,
                    error=error
                )
                
            # Execute the tool
            return self.execute(**kwargs)
            
        except Exception as e:
            self.logger.error(f"Tool execution failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )
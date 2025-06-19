"""
Tool registry for managing available tools.
"""

import logging
from typing import Dict, Type, Optional, List
from .base_tool import BaseTool
from ..agents.models import Tool


logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for managing available tools."""
    
    _instance = None
    
    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super(ToolRegistry, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the tool registry."""
        if self._initialized:
            return
            
        self._tools: Dict[str, Type[BaseTool]] = {}
        self._instances: Dict[str, BaseTool] = {}
        self._initialized = True
        
    def register(self, tool_class: Type[BaseTool]) -> None:
        """
        Register a tool class.
        
        Args:
            tool_class: The tool class to register
        """
        # Create instance to get the tool definition
        instance = tool_class()
        tool_def = instance.get_definition()
        
        if tool_def.name in self._tools:
            logger.warning(f"Tool '{tool_def.name}' is already registered, overwriting")
            
        self._tools[tool_def.name] = tool_class
        self._instances[tool_def.name] = instance
        logger.info(f"Registered tool: {tool_def.name}")
    
    def register_tool(self, tool_instance: BaseTool) -> None:
        """
        Register a tool instance directly.
        
        Args:
            tool_instance: The tool instance to register
        """
        tool_def = tool_instance.get_definition()
        
        if tool_def.name in self._tools:
            logger.warning(f"Tool '{tool_def.name}' is already registered, overwriting")
            
        self._tools[tool_def.name] = type(tool_instance)
        self._instances[tool_def.name] = tool_instance
        logger.info(f"Registered tool instance: {tool_def.name}")
        
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        Get a tool instance by name.
        
        Args:
            name: The tool name
            
        Returns:
            Tool instance if found, None otherwise
        """
        return self._instances.get(name)
        
    def get_tool_definition(self, name: str) -> Optional[Tool]:
        """
        Get a tool definition by name.
        
        Args:
            name: The tool name
            
        Returns:
            Tool definition if found, None otherwise
        """
        instance = self._instances.get(name)
        if instance:
            return instance.get_definition()
        return None
        
    def list_tools(self) -> List[str]:
        """
        List all registered tool names.
        
        Returns:
            List of tool names
        """
        return list(self._tools.keys())
        
    def get_all_definitions(self) -> List[Tool]:
        """
        Get all tool definitions.
        
        Returns:
            List of all tool definitions
        """
        definitions = []
        for instance in self._instances.values():
            definitions.append(instance.get_definition())
        return definitions
        
    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        self._instances.clear()
        logger.info("Cleared all registered tools")
    
    def clear_category(self, category: str) -> None:
        """Clear all tools in a specific category.
        
        Args:
            category: The category to clear (e.g., 'mcp')
        """
        tools_to_remove = []
        for name, instance in self._instances.items():
            if hasattr(instance, 'category') and instance.category == category:
                tools_to_remove.append(name)
        
        for name in tools_to_remove:
            del self._tools[name]
            del self._instances[name]
            
        if tools_to_remove:
            logger.info(f"Cleared {len(tools_to_remove)} tools from category '{category}'")


# Global registry instance
tool_registry = ToolRegistry()


def register_tool(tool_class: Type[BaseTool]) -> Type[BaseTool]:
    """
    Decorator to register a tool class.
    
    Args:
        tool_class: The tool class to register
        
    Returns:
        The tool class (unchanged)
    """
    tool_registry.register(tool_class)
    return tool_class
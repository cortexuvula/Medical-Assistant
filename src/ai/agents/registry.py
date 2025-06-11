"""
Tool registry for agent system.

This module provides a registry of tools that agents can use in the future.
Currently serves as a placeholder for future extensibility.
"""

from typing import Dict, Optional
import logging

from .models import Tool, ToolParameter


logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for agent tools."""
    
    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, Tool] = {}
        self._initialize_default_tools()
        
    def _initialize_default_tools(self):
        """Initialize default tools. Currently placeholder for future tools."""
        # Example tools for future implementation
        example_tools = [
            Tool(
                name="search_icd_codes",
                description="Search for ICD-10 diagnostic codes",
                parameters=[
                    ToolParameter(
                        name="query",
                        type="string",
                        description="Search query for ICD codes",
                        required=True
                    ),
                    ToolParameter(
                        name="limit",
                        type="integer",
                        description="Maximum number of results",
                        required=False,
                        default=10
                    )
                ]
            ),
            Tool(
                name="lookup_drug_interactions",
                description="Check for drug interactions between medications",
                parameters=[
                    ToolParameter(
                        name="medications",
                        type="array",
                        description="List of medication names",
                        required=True
                    )
                ]
            ),
            Tool(
                name="format_referral",
                description="Format a referral letter with proper structure",
                parameters=[
                    ToolParameter(
                        name="specialty",
                        type="string",
                        description="Medical specialty for referral",
                        required=True
                    ),
                    ToolParameter(
                        name="reason",
                        type="string",
                        description="Reason for referral",
                        required=True
                    ),
                    ToolParameter(
                        name="urgency",
                        type="string",
                        description="Urgency level (routine, urgent, emergent)",
                        required=False,
                        default="routine"
                    )
                ]
            ),
            Tool(
                name="extract_vitals",
                description="Extract vital signs from clinical text",
                parameters=[
                    ToolParameter(
                        name="text",
                        type="string",
                        description="Clinical text containing vitals",
                        required=True
                    )
                ]
            ),
            Tool(
                name="calculate_bmi",
                description="Calculate BMI from height and weight",
                parameters=[
                    ToolParameter(
                        name="weight_kg",
                        type="number",
                        description="Weight in kilograms",
                        required=True
                    ),
                    ToolParameter(
                        name="height_cm",
                        type="number",
                        description="Height in centimeters",
                        required=True
                    )
                ]
            )
        ]
        
        # Note: These are placeholder tools for future implementation
        # They are not currently functional but show the intended pattern
        
    def register_tool(self, tool: Tool):
        """
        Register a new tool.
        
        Args:
            tool: Tool to register
        """
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered. Overwriting...")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
        
    def get_tool(self, name: str) -> Optional[Tool]:
        """
        Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool if found, None otherwise
        """
        return self._tools.get(name)
        
    def list_tools(self) -> Dict[str, Tool]:
        """
        List all registered tools.
        
        Returns:
            Dictionary of tool name to Tool object
        """
        return self._tools.copy()
        
    def remove_tool(self, name: str) -> bool:
        """
        Remove a tool from the registry.
        
        Args:
            name: Tool name to remove
            
        Returns:
            True if removed, False if not found
        """
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Removed tool: {name}")
            return True
        return False
        
    def get_tools_for_agent(self, agent_type: str) -> Dict[str, Tool]:
        """
        Get tools suitable for a specific agent type.
        
        This is a placeholder for future tool filtering based on agent type.
        
        Args:
            agent_type: Type of agent
            
        Returns:
            Dictionary of suitable tools
        """
        # For now, return empty dict as no tools are implemented
        # In the future, this would filter tools based on agent capabilities
        return {}


# Global tool registry instance
tool_registry = ToolRegistry()
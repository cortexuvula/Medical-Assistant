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
        # Register medication-related tools
        self._tools = {
            "search_icd_codes": Tool(
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
            "lookup_drug_interactions": Tool(
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
            "search_medications": Tool(
                name="search_medications",
                description="Search medication database by name, class, or indication",
                parameters=[
                    ToolParameter(
                        name="query",
                        type="string",
                        description="Search query (drug name, class, or indication)",
                        required=True
                    ),
                    ToolParameter(
                        name="search_type",
                        type="string",
                        description="Type of search: 'name', 'class', 'indication'",
                        required=False,
                        default="name"
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
            "calculate_dosage": Tool(
                name="calculate_dosage",
                description="Calculate medication dosage based on patient parameters",
                parameters=[
                    ToolParameter(
                        name="medication",
                        type="string",
                        description="Medication name",
                        required=True
                    ),
                    ToolParameter(
                        name="indication",
                        type="string",
                        description="Indication for use",
                        required=True
                    ),
                    ToolParameter(
                        name="patient_weight_kg",
                        type="number",
                        description="Patient weight in kilograms",
                        required=False
                    ),
                    ToolParameter(
                        name="patient_age",
                        type="integer",
                        description="Patient age in years",
                        required=False
                    ),
                    ToolParameter(
                        name="renal_function",
                        type="string",
                        description="Renal function status: 'normal', 'mild', 'moderate', 'severe'",
                        required=False,
                        default="normal"
                    )
                ]
            ),
            "check_contraindications": Tool(
                name="check_contraindications",
                description="Check medication contraindications based on patient conditions",
                parameters=[
                    ToolParameter(
                        name="medication",
                        type="string",
                        description="Medication name",
                        required=True
                    ),
                    ToolParameter(
                        name="patient_conditions",
                        type="array",
                        description="List of patient medical conditions",
                        required=True
                    ),
                    ToolParameter(
                        name="patient_allergies",
                        type="array",
                        description="List of patient allergies",
                        required=False,
                        default=[]
                    )
                ]
            ),
            "format_prescription": Tool(
                name="format_prescription",
                description="Format medication prescription for printing or electronic transmission",
                parameters=[
                    ToolParameter(
                        name="medication_name",
                        type="string",
                        description="Medication name (generic or brand)",
                        required=True
                    ),
                    ToolParameter(
                        name="dose",
                        type="string",
                        description="Dose amount and units",
                        required=True
                    ),
                    ToolParameter(
                        name="route",
                        type="string",
                        description="Route of administration",
                        required=True
                    ),
                    ToolParameter(
                        name="frequency",
                        type="string",
                        description="Dosing frequency",
                        required=True
                    ),
                    ToolParameter(
                        name="duration",
                        type="string",
                        description="Duration of treatment",
                        required=True
                    ),
                    ToolParameter(
                        name="quantity",
                        type="string",
                        description="Quantity to dispense",
                        required=True
                    ),
                    ToolParameter(
                        name="refills",
                        type="integer",
                        description="Number of refills",
                        required=False,
                        default=0
                    ),
                    ToolParameter(
                        name="indication",
                        type="string",
                        description="Indication for use",
                        required=False
                    )
                ]
            ),
            "check_duplicate_therapy": Tool(
                name="check_duplicate_therapy",
                description="Check for duplicate therapy in medication list",
                parameters=[
                    ToolParameter(
                        name="medications",
                        type="array",
                        description="List of current medications",
                        required=True
                    ),
                    ToolParameter(
                        name="new_medication",
                        type="string",
                        description="New medication being considered",
                        required=True
                    )
                ]
            ),
            "format_referral": Tool(
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
            "extract_vitals": Tool(
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
            "calculate_bmi": Tool(
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
        }
        
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
        
        This filters tools based on agent capabilities.
        
        Args:
            agent_type: Type of agent
            
        Returns:
            Dictionary of suitable tools
        """
        # Define tool mappings for different agent types
        agent_tool_mappings = {
            "medication": [
                "lookup_drug_interactions",
                "search_medications",
                "calculate_dosage",
                "check_contraindications",
                "format_prescription",
                "check_duplicate_therapy"
            ],
            "diagnostic": [
                "search_icd_codes",
                "extract_vitals",
                "calculate_bmi"
            ],
            "referral": [
                "format_referral"
            ]
        }
        
        # Get tools for the specified agent type
        tool_names = agent_tool_mappings.get(agent_type.lower(), [])
        
        # Return dictionary of matching tools
        return {
            name: tool for name, tool in self._tools.items()
            if name in tool_names
        }


# Global tool registry instance
tool_registry = ToolRegistry()
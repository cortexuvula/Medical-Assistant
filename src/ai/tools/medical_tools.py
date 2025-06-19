"""
Medical-specific tools for the agent system.
"""

import re
from typing import Dict, Any, List

from .base_tool import BaseTool, ToolResult
from .tool_registry import register_tool
from ..agents.models import Tool, ToolParameter


@register_tool
class DrugInteractionTool(BaseTool):
    """Tool for checking drug interactions (mock implementation)."""
    
    def get_definition(self) -> Tool:
        return Tool(
            name="check_drug_interaction",
            description="Check for potential drug interactions between medications",
            parameters=[
                ToolParameter(
                    name="drug1",
                    type="string",
                    description="First medication name",
                    required=True
                ),
                ToolParameter(
                    name="drug2",
                    type="string",
                    description="Second medication name",
                    required=True
                )
            ]
        )
        
    def execute(self, drug1: str, drug2: str) -> ToolResult:
        """Check drug interactions (mock implementation)."""
        try:
            # This is a mock implementation
            # In a real system, this would query a drug interaction database
            
            # Common mock interactions for demonstration
            interactions = {
                ("warfarin", "aspirin"): {
                    "severity": "Major",
                    "description": "Increased risk of bleeding when warfarin is taken with aspirin"
                },
                ("lisinopril", "potassium"): {
                    "severity": "Moderate",
                    "description": "Risk of hyperkalemia when ACE inhibitors are taken with potassium supplements"
                },
                ("metformin", "alcohol"): {
                    "severity": "Moderate",
                    "description": "Increased risk of lactic acidosis when metformin is combined with alcohol"
                }
            }
            
            # Normalize drug names
            d1 = drug1.lower().strip()
            d2 = drug2.lower().strip()
            
            # Check both orders
            interaction = interactions.get((d1, d2)) or interactions.get((d2, d1))
            
            if interaction:
                result = {
                    "interaction_found": True,
                    "drug1": drug1,
                    "drug2": drug2,
                    "severity": interaction["severity"],
                    "description": interaction["description"],
                    "recommendation": "Consult with healthcare provider before using together"
                }
            else:
                result = {
                    "interaction_found": False,
                    "drug1": drug1,
                    "drug2": drug2,
                    "message": "No major interactions found in database (Note: This is a mock implementation)"
                }
                
            return ToolResult(
                success=True,
                output=result,
                metadata={"tool": "drug_interaction_checker"}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Drug interaction check failed: {str(e)}"
            )


@register_tool
class BMICalculatorTool(BaseTool):
    """Tool for calculating BMI and interpreting results."""
    
    def get_definition(self) -> Tool:
        return Tool(
            name="calculate_bmi",
            description="Calculate Body Mass Index (BMI) from height and weight",
            parameters=[
                ToolParameter(
                    name="weight",
                    type="number",
                    description="Weight in kilograms",
                    required=True
                ),
                ToolParameter(
                    name="height",
                    type="number",
                    description="Height in centimeters",
                    required=True
                )
            ]
        )
        
    def execute(self, weight: float, height: float) -> ToolResult:
        """Calculate BMI and provide interpretation."""
        try:
            # Convert height from cm to meters
            height_m = height / 100
            
            # Calculate BMI
            bmi = weight / (height_m ** 2)
            
            # Interpret BMI
            if bmi < 18.5:
                category = "Underweight"
                health_risk = "Increased risk of malnutrition and osteoporosis"
            elif 18.5 <= bmi < 25:
                category = "Normal weight"
                health_risk = "Low risk"
            elif 25 <= bmi < 30:
                category = "Overweight"
                health_risk = "Increased risk of cardiovascular disease"
            elif 30 <= bmi < 35:
                category = "Obese Class I"
                health_risk = "Moderate risk of obesity-related conditions"
            elif 35 <= bmi < 40:
                category = "Obese Class II"
                health_risk = "Severe risk of obesity-related conditions"
            else:
                category = "Obese Class III"
                health_risk = "Very severe risk of obesity-related conditions"
                
            result = {
                "bmi": round(bmi, 1),
                "category": category,
                "health_risk": health_risk,
                "weight_kg": weight,
                "height_cm": height,
                "ideal_weight_range": {
                    "min_kg": round(18.5 * height_m ** 2, 1),
                    "max_kg": round(24.9 * height_m ** 2, 1)
                }
            }
            
            return ToolResult(
                success=True,
                output=result,
                metadata={"calculation": "BMI"}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"BMI calculation error: {str(e)}"
            )


@register_tool
class DosageCalculatorTool(BaseTool):
    """Tool for calculating medication dosages."""
    
    def get_definition(self) -> Tool:
        return Tool(
            name="calculate_dosage",
            description="Calculate medication dosage based on weight or body surface area",
            parameters=[
                ToolParameter(
                    name="medication",
                    type="string",
                    description="Medication name",
                    required=True
                ),
                ToolParameter(
                    name="dose_per_kg",
                    type="number",
                    description="Dose per kilogram of body weight",
                    required=True
                ),
                ToolParameter(
                    name="weight",
                    type="number",
                    description="Patient weight in kilograms",
                    required=True
                ),
                ToolParameter(
                    name="frequency",
                    type="string",
                    description="Dosing frequency (e.g., 'once daily', 'twice daily', 'every 8 hours')",
                    required=False,
                    default="once daily"
                ),
                ToolParameter(
                    name="max_dose",
                    type="number",
                    description="Maximum allowed dose per administration",
                    required=False
                )
            ]
        )
        
    def execute(self, medication: str, dose_per_kg: float, weight: float, 
                frequency: str = "once daily", max_dose: float = None) -> ToolResult:
        """Calculate medication dosage."""
        try:
            # Calculate base dose
            calculated_dose = dose_per_kg * weight
            
            # Apply maximum dose limit if specified
            actual_dose = calculated_dose
            dose_limited = False
            
            if max_dose and calculated_dose > max_dose:
                actual_dose = max_dose
                dose_limited = True
                
            # Calculate daily total based on frequency
            frequency_map = {
                "once daily": 1,
                "twice daily": 2,
                "three times daily": 3,
                "four times daily": 4,
                "every 12 hours": 2,
                "every 8 hours": 3,
                "every 6 hours": 4,
                "every 4 hours": 6
            }
            
            doses_per_day = frequency_map.get(frequency.lower(), 1)
            daily_total = actual_dose * doses_per_day
            
            result = {
                "medication": medication,
                "calculated_dose_mg": round(calculated_dose, 2),
                "actual_dose_mg": round(actual_dose, 2),
                "frequency": frequency,
                "doses_per_day": doses_per_day,
                "daily_total_mg": round(daily_total, 2),
                "dose_limited": dose_limited,
                "patient_weight_kg": weight
            }
            
            if dose_limited:
                result["warning"] = f"Dose limited to maximum of {max_dose}mg per administration"
                
            return ToolResult(
                success=True,
                output=result,
                metadata={"calculation": "dosage"}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Dosage calculation error: {str(e)}"
            )
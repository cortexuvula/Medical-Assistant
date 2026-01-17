"""
Workflow agent for managing multi-step clinical processes and protocols.
"""

import json
import re
from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING
from datetime import datetime

from .base import BaseAgent
from .models import AgentConfig, AgentTask, AgentResponse, ToolCall
from utils.structured_logging import get_logger

if TYPE_CHECKING:
    from .ai_caller import AICallerProtocol


logger = get_logger(__name__)


class WorkflowAgent(BaseAgent):
    """Agent specialized in coordinating multi-step clinical workflows and protocols."""
    
    # Default configuration for workflow agent
    DEFAULT_CONFIG = AgentConfig(
        name="WorkflowAgent",
        description="Manages multi-step clinical processes and protocols",
        system_prompt="""You are a clinical workflow coordinator with expertise in managing healthcare processes.

Your role is to:
1. Guide healthcare providers through multi-step clinical workflows
2. Provide structured, step-by-step protocols for common medical procedures
3. Coordinate patient intake processes
4. Plan diagnostic workups systematically
5. Manage treatment protocols with clear milestones
6. Schedule and track follow-up care

Guidelines:
- Break down complex processes into clear, actionable steps
- Include decision points and conditional pathways
- Provide estimated timeframes for each step
- Flag critical safety checkpoints
- Allow flexibility for clinical judgment
- Include relevant documentation requirements
- Consider resource availability and constraints
- Maintain patient-centered approach

Workflow Types:
1. PATIENT INTAKE: Registration, history, consent, initial assessment
2. DIAGNOSTIC WORKUP: Test ordering, result tracking, interpretation
3. TREATMENT PROTOCOL: Medication regimens, procedures, monitoring
4. FOLLOW-UP CARE: Appointments, monitoring schedules, outcome tracking

Format workflows as:
WORKFLOW: [Name]
TYPE: [Intake/Diagnostic/Treatment/Follow-up]
DURATION: [Estimated total time]
STEPS:
1. [Step name] - [Duration] - [Description]
   ✓ Checkpoint: [What to verify]
   → Next: [Condition for proceeding]
2. [Continue pattern...]

Always include:
- Clear success criteria for each step
- Alternative pathways for common variations
- Documentation requirements
- Safety considerations""",
        model="gpt-4",
        temperature=0.3,
        max_tokens=500
    )
    
    def __init__(self, config: Optional[AgentConfig] = None, ai_caller: Optional['AICallerProtocol'] = None):
        """Initialize the workflow agent.

        Args:
            config: Optional configuration override
            ai_caller: Optional AI caller for dependency injection.
        """
        super().__init__(config or self.DEFAULT_CONFIG, ai_caller=ai_caller)
        
    def execute(self, task: AgentTask) -> AgentResponse:
        """Execute a workflow coordination task.
        
        Args:
            task: The workflow task to execute
            
        Returns:
            AgentResponse containing the workflow guidance
        """
        try:
            # Extract workflow parameters
            workflow_type = task.input_data.get("workflow_type", "general")
            clinical_context = task.input_data.get("clinical_context", "")
            patient_info = task.input_data.get("patient_info", {})
            current_step = task.input_data.get("current_step", None)
            workflow_state = task.input_data.get("workflow_state", {})
            
            # Determine which workflow method to use
            if workflow_type == "patient_intake":
                return self._patient_intake_workflow(
                    clinical_context, patient_info, current_step, workflow_state
                )
            elif workflow_type == "diagnostic_workup":
                return self._diagnostic_workup_workflow(
                    clinical_context, patient_info, current_step, workflow_state
                )
            elif workflow_type == "treatment_protocol":
                return self._treatment_protocol_workflow(
                    clinical_context, patient_info, current_step, workflow_state
                )
            elif workflow_type == "follow_up_care":
                return self._follow_up_care_workflow(
                    clinical_context, patient_info, current_step, workflow_state
                )
            else:
                # General workflow guidance
                return self._general_workflow_guidance(
                    task, clinical_context, patient_info
                )
                
        except Exception as e:
            logger.error(f"Error executing workflow task: {e}")
            return AgentResponse(
                result="",
                success=False,
                error=str(e)
            )
    
    def _patient_intake_workflow(
        self, 
        clinical_context: str,
        patient_info: Dict[str, Any],
        current_step: Optional[int],
        workflow_state: Dict[str, Any]
    ) -> AgentResponse:
        """Generate patient intake workflow.
        
        Args:
            clinical_context: Clinical context and requirements
            patient_info: Patient information
            current_step: Current step in workflow (if resuming)
            workflow_state: Current workflow state
            
        Returns:
            AgentResponse with intake workflow
        """
        # Build prompt for patient intake workflow
        prompt = f"""Create a comprehensive patient intake workflow.

Clinical Context: {clinical_context}
Patient Type: {patient_info.get('type', 'General')}
Visit Type: {patient_info.get('visit_type', 'New Patient')}
Current Step: {current_step or 'Beginning'}

Generate a detailed patient intake workflow including:
1. Registration and demographics
2. Insurance verification
3. Medical history collection
4. Consent forms
5. Initial vital signs
6. Chief complaint documentation
7. Medication reconciliation
8. Allergy verification
9. Social history
10. Family history

Include specific forms, estimated times, and validation checkpoints."""

        # Call AI to generate workflow
        workflow_text = self._call_ai(prompt)
        
        # Parse workflow into structured format
        structured_workflow = self._parse_workflow(workflow_text, "patient_intake")
        
        # Add metadata
        metadata = {
            "workflow_type": "patient_intake",
            "total_steps": len(structured_workflow.get("steps", [])),
            "estimated_duration": structured_workflow.get("duration", "30-45 minutes"),
            "checkpoints": structured_workflow.get("checkpoints", []),
            "required_forms": [
                "Patient Registration Form",
                "HIPAA Consent",
                "Insurance Information",
                "Medical History Questionnaire"
            ]
        }
        
        return AgentResponse(
            result=workflow_text,
            success=True,
            metadata=metadata,
            thoughts="Generated comprehensive patient intake workflow with all required components"
        )
    
    def _diagnostic_workup_workflow(
        self,
        clinical_context: str,
        patient_info: Dict[str, Any],
        current_step: Optional[int],
        workflow_state: Dict[str, Any]
    ) -> AgentResponse:
        """Generate diagnostic workup workflow.
        
        Args:
            clinical_context: Clinical presentation and symptoms
            patient_info: Patient information
            current_step: Current step in workflow
            workflow_state: Current workflow state
            
        Returns:
            AgentResponse with diagnostic workflow
        """
        # Extract relevant information
        symptoms = patient_info.get('symptoms', '')
        suspected_conditions = patient_info.get('suspected_conditions', [])
        
        prompt = f"""Create a systematic diagnostic workup workflow.

Clinical Context: {clinical_context}
Presenting Symptoms: {symptoms}
Suspected Conditions: {', '.join(suspected_conditions) if suspected_conditions else 'To be determined'}
Patient Age: {patient_info.get('age', 'Unknown')}
Gender: {patient_info.get('gender', 'Unknown')}

Generate a diagnostic workup workflow including:
1. Initial assessment and triage
2. Laboratory tests (with priorities)
3. Imaging studies (if indicated)
4. Specialist consultations needed
5. Result interpretation checkpoints
6. Differential diagnosis refinement
7. Additional testing decisions
8. Final diagnosis confirmation

Include test priorities, turnaround times, and decision trees."""

        # Call AI to generate workflow
        workflow_text = self._call_ai(prompt)
        
        # Parse and structure the workflow
        structured_workflow = self._parse_workflow(workflow_text, "diagnostic_workup")
        
        # Extract test recommendations
        tests = self._extract_diagnostic_tests(workflow_text)
        
        metadata = {
            "workflow_type": "diagnostic_workup",
            "total_steps": len(structured_workflow.get("steps", [])),
            "recommended_tests": tests,
            "priority_levels": ["STAT", "Urgent", "Routine"],
            "decision_points": structured_workflow.get("decision_points", [])
        }
        
        return AgentResponse(
            result=workflow_text,
            success=True,
            metadata=metadata,
            thoughts="Created systematic diagnostic workup with prioritized testing strategy"
        )
    
    def _treatment_protocol_workflow(
        self,
        clinical_context: str,
        patient_info: Dict[str, Any],
        current_step: Optional[int],
        workflow_state: Dict[str, Any]
    ) -> AgentResponse:
        """Generate treatment protocol workflow.
        
        Args:
            clinical_context: Diagnosis and treatment goals
            patient_info: Patient information
            current_step: Current step in workflow
            workflow_state: Current workflow state
            
        Returns:
            AgentResponse with treatment workflow
        """
        diagnosis = patient_info.get('diagnosis', '')
        treatment_goals = patient_info.get('treatment_goals', [])
        
        prompt = f"""Create a comprehensive treatment protocol workflow.

Clinical Context: {clinical_context}
Primary Diagnosis: {diagnosis}
Treatment Goals: {', '.join(treatment_goals) if treatment_goals else 'Standard care'}
Patient Factors: Age {patient_info.get('age', 'Unknown')}, {patient_info.get('comorbidities', 'No known comorbidities')}

Generate a treatment protocol workflow including:
1. Treatment initiation steps
2. Medication administration schedule
3. Monitoring parameters and frequency
4. Side effect management
5. Response assessment criteria
6. Dose adjustment protocols
7. Treatment milestones
8. Discontinuation criteria

Include safety checkpoints, monitoring schedules, and outcome measures."""

        # Call AI to generate workflow
        workflow_text = self._call_ai(prompt)
        
        # Parse workflow
        structured_workflow = self._parse_workflow(workflow_text, "treatment_protocol")
        
        # Extract monitoring parameters
        monitoring_params = self._extract_monitoring_parameters(workflow_text)
        
        metadata = {
            "workflow_type": "treatment_protocol",
            "total_steps": len(structured_workflow.get("steps", [])),
            "monitoring_parameters": monitoring_params,
            "safety_checkpoints": structured_workflow.get("safety_checkpoints", []),
            "outcome_measures": structured_workflow.get("outcome_measures", []),
            "treatment_duration": structured_workflow.get("duration", "Varies")
        }
        
        return AgentResponse(
            result=workflow_text,
            success=True,
            metadata=metadata,
            thoughts="Developed comprehensive treatment protocol with safety monitoring"
        )
    
    def _follow_up_care_workflow(
        self,
        clinical_context: str,
        patient_info: Dict[str, Any],
        current_step: Optional[int],
        workflow_state: Dict[str, Any]
    ) -> AgentResponse:
        """Generate follow-up care workflow.
        
        Args:
            clinical_context: Treatment completed and follow-up needs
            patient_info: Patient information
            current_step: Current step in workflow
            workflow_state: Current workflow state
            
        Returns:
            AgentResponse with follow-up workflow
        """
        treatment_completed = patient_info.get('treatment_completed', '')
        follow_up_duration = patient_info.get('follow_up_duration', '6 months')
        
        prompt = f"""Create a structured follow-up care workflow.

Clinical Context: {clinical_context}
Treatment Completed: {treatment_completed}
Follow-up Duration: {follow_up_duration}
Risk Factors: {patient_info.get('risk_factors', 'Standard risk')}

Generate a follow-up care workflow including:
1. Follow-up appointment schedule
2. Monitoring tests and frequency
3. Symptom tracking requirements
4. Medication adherence checks
5. Lifestyle modification tracking
6. Warning signs to monitor
7. Re-evaluation criteria
8. Transition to maintenance care

Include specific timelines, monitoring parameters, and escalation criteria."""

        # Call AI to generate workflow
        workflow_text = self._call_ai(prompt)
        
        # Parse workflow
        structured_workflow = self._parse_workflow(workflow_text, "follow_up_care")
        
        # Generate follow-up schedule
        schedule = self._generate_follow_up_schedule(structured_workflow, follow_up_duration)
        
        metadata = {
            "workflow_type": "follow_up_care",
            "total_steps": len(structured_workflow.get("steps", [])),
            "follow_up_schedule": schedule,
            "monitoring_frequency": structured_workflow.get("monitoring_frequency", {}),
            "warning_signs": structured_workflow.get("warning_signs", []),
            "transition_criteria": structured_workflow.get("transition_criteria", [])
        }
        
        return AgentResponse(
            result=workflow_text,
            success=True,
            metadata=metadata,
            thoughts="Created comprehensive follow-up care plan with monitoring schedule"
        )
    
    def _general_workflow_guidance(
        self,
        task: AgentTask,
        clinical_context: str,
        patient_info: Dict[str, Any]
    ) -> AgentResponse:
        """Provide general workflow guidance.
        
        Args:
            task: The original task
            clinical_context: Clinical context
            patient_info: Patient information
            
        Returns:
            AgentResponse with general workflow guidance
        """
        prompt = f"""Provide clinical workflow guidance.

Task: {task.task_description}
Context: {clinical_context}
{f"Additional Context: {task.context}" if task.context else ""}

Create a structured workflow that:
1. Breaks down the process into clear steps
2. Includes timeframes and dependencies
3. Identifies key decision points
4. Provides safety checkpoints
5. Suggests documentation requirements
6. Allows for clinical flexibility

Format as a practical, actionable workflow."""

        # Call AI for general guidance
        workflow_text = self._call_ai(prompt)
        
        # Basic parsing
        structured_workflow = self._parse_workflow(workflow_text, "general")
        
        metadata = {
            "workflow_type": "general",
            "total_steps": len(structured_workflow.get("steps", [])),
            "customizable": True
        }
        
        return AgentResponse(
            result=workflow_text,
            success=True,
            metadata=metadata,
            thoughts="Provided flexible clinical workflow guidance"
        )
    
    def _parse_workflow(self, workflow_text: str, workflow_type: str) -> Dict[str, Any]:
        """Parse workflow text into structured format.
        
        Args:
            workflow_text: Raw workflow text
            workflow_type: Type of workflow
            
        Returns:
            Structured workflow dictionary
        """
        structured = {
            "type": workflow_type,
            "steps": [],
            "checkpoints": [],
            "decision_points": [],
            "duration": "Varies",
            "safety_checkpoints": []
        }
        
        # Parse steps (numbered items)
        import re
        step_pattern = r'(\d+)\.\s*([^-\n]+)(?:\s*-\s*([^-\n]+))?(?:\s*-\s*(.+))?'
        steps = re.findall(step_pattern, workflow_text, re.MULTILINE)
        
        for step in steps:
            step_num, step_name, duration, description = step
            structured["steps"].append({
                "number": int(step_num),
                "name": step_name.strip(),
                "duration": duration.strip() if duration else None,
                "description": description.strip() if description else None
            })
        
        # Extract checkpoints
        checkpoint_pattern = r'✓\s*Checkpoint:\s*(.+)'
        checkpoints = re.findall(checkpoint_pattern, workflow_text)
        structured["checkpoints"] = [cp.strip() for cp in checkpoints]
        
        # Extract duration if specified
        duration_pattern = r'DURATION:\s*(.+)'
        duration_match = re.search(duration_pattern, workflow_text)
        if duration_match:
            structured["duration"] = duration_match.group(1).strip()
        
        return structured
    
    def _extract_diagnostic_tests(self, workflow_text: str) -> List[Dict[str, str]]:
        """Extract diagnostic tests from workflow.
        
        Args:
            workflow_text: Workflow text containing test recommendations
            
        Returns:
            List of test dictionaries
        """
        tests = []
        
        # Common test patterns
        test_patterns = [
            r'(?:Lab(?:oratory)?|Blood)\s*(?:test|work)s?:\s*(.+?)(?:\n|$)',
            r'(?:Imaging|Radiology):\s*(.+?)(?:\n|$)',
            r'(?:Test|Order):\s*(.+?)(?:\n|$)'
        ]
        
        for pattern in test_patterns:
            matches = re.findall(pattern, workflow_text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                # Split multiple tests
                test_items = re.split(r'[,;]', match)
                for test in test_items:
                    test = test.strip()
                    if test:
                        # Determine priority
                        priority = "Routine"
                        if any(word in test.upper() for word in ["STAT", "URGENT", "IMMEDIATE"]):
                            priority = "STAT"
                        elif "urgent" in test.lower():
                            priority = "Urgent"
                        
                        tests.append({
                            "name": test,
                            "priority": priority,
                            "category": "Laboratory" if "lab" in pattern.lower() else "Imaging"
                        })
        
        return tests
    
    def _extract_monitoring_parameters(self, workflow_text: str) -> List[Dict[str, str]]:
        """Extract monitoring parameters from treatment workflow.
        
        Args:
            workflow_text: Workflow text
            
        Returns:
            List of monitoring parameters
        """
        parameters = []
        
        # Look for monitoring patterns
        monitor_patterns = [
            r'Monitor(?:ing)?:\s*(.+?)(?:\n|$)',
            r'(?:Check|Assess|Measure):\s*(.+?)(?:\n|$)',
            r'Parameters?:\s*(.+?)(?:\n|$)'
        ]
        
        for pattern in monitor_patterns:
            matches = re.findall(pattern, workflow_text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                param_items = re.split(r'[,;]', match)
                for param in param_items:
                    param = param.strip()
                    if param:
                        # Determine frequency
                        frequency = "As needed"
                        if "daily" in param.lower():
                            frequency = "Daily"
                        elif "weekly" in param.lower():
                            frequency = "Weekly"
                        elif "monthly" in param.lower():
                            frequency = "Monthly"
                        
                        parameters.append({
                            "parameter": param,
                            "frequency": frequency
                        })
        
        return parameters
    
    def _generate_follow_up_schedule(
        self, 
        structured_workflow: Dict[str, Any],
        duration: str
    ) -> List[Dict[str, str]]:
        """Generate follow-up appointment schedule.
        
        Args:
            structured_workflow: Parsed workflow structure
            duration: Follow-up duration
            
        Returns:
            List of scheduled appointments
        """
        schedule = []
        
        # Common follow-up intervals
        intervals = {
            "1 week": 7,
            "2 weeks": 14,
            "1 month": 30,
            "3 months": 90,
            "6 months": 180,
            "1 year": 365
        }
        
        # Extract from workflow steps
        for step in structured_workflow.get("steps", []):
            step_name = step.get("name", "").lower()
            if "follow" in step_name or "appointment" in step_name:
                # Try to extract timing
                for interval, days in intervals.items():
                    if interval in step_name.lower():
                        schedule.append({
                            "interval": interval,
                            "days_from_start": days,
                            "appointment_type": "Follow-up",
                            "purpose": step.get("description", "Routine follow-up")
                        })
                        break
        
        # If no specific schedule found, create default
        if not schedule:
            if "month" in duration.lower():
                # Create monthly follow-ups
                months = 6  # Default
                try:
                    months = int(re.search(r'(\d+)', duration).group(1))
                except (AttributeError, ValueError, TypeError):
                    pass  # Use default if parsing fails
                
                for i in range(1, min(months + 1, 7)):
                    schedule.append({
                        "interval": f"{i} month{'s' if i > 1 else ''}",
                        "days_from_start": i * 30,
                        "appointment_type": "Follow-up",
                        "purpose": "Progress evaluation"
                    })
        
        return schedule
"""
Unit tests for the MedicationAgent class.
"""

import unittest
from unittest.mock import Mock, patch
import json

from ai.agents.medication import MedicationAgent
from ai.agents.models import AgentTask, AgentConfig


class TestMedicationAgent(unittest.TestCase):
    """Test cases for MedicationAgent."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.agent = MedicationAgent()
        
    def test_initialization(self):
        """Test agent initialization."""
        self.assertIsInstance(self.agent, MedicationAgent)
        self.assertIsInstance(self.agent.config, AgentConfig)
        self.assertEqual(self.agent.config.name, "MedicationAgent")
        self.assertEqual(self.agent.config.temperature, 0.2)
        
    def test_custom_config(self):
        """Test agent with custom configuration."""
        custom_config = AgentConfig(
            name="CustomMedAgent",
            description="Custom medication agent",
            system_prompt="Custom prompt",
            temperature=0.5
        )
        agent = MedicationAgent(custom_config)
        self.assertEqual(agent.config.name, "CustomMedAgent")
        self.assertEqual(agent.config.temperature, 0.5)
        
    @patch.object(MedicationAgent, '_call_ai')
    def test_extract_medications(self, mock_call_ai):
        """Test medication extraction from clinical text."""
        # Mock AI response
        mock_call_ai.return_value = """
        1. Metformin 500mg - Twice daily
           Route: Oral
           Indication: Type 2 Diabetes
           
        2. Lisinopril 10mg - Once daily
           Route: Oral
           Indication: Hypertension
        """
        
        task = AgentTask(
            task_description="Extract medications from clinical text",
            input_data={
                "clinical_text": "Patient is on metformin 500mg twice daily for diabetes and lisinopril 10mg daily for blood pressure."
            }
        )
        
        response = self.agent.execute(task)
        
        self.assertTrue(response.success)
        self.assertIn("Metformin", response.result)
        self.assertIn("Lisinopril", response.result)
        self.assertEqual(response.metadata['medication_count'], 2)
        
    @patch.object(MedicationAgent, '_call_ai')
    def test_check_interactions(self, mock_call_ai):
        """Test drug interaction checking."""
        # Mock AI response
        mock_call_ai.return_value = """
        Drug Interaction Analysis:
        
        Warfarin + Aspirin:
        - Severity: MAJOR
        - Clinical Significance: Increased risk of bleeding
        - Recommended Action: Use with extreme caution, monitor INR closely
        - Monitoring: Check INR more frequently, watch for signs of bleeding
        """
        
        task = AgentTask(
            task_description="Check drug interactions",
            input_data={
                "medications": ["Warfarin 5mg", "Aspirin 81mg"]
            }
        )
        
        response = self.agent.execute(task)
        
        self.assertTrue(response.success)
        self.assertIn("MAJOR", response.result)
        self.assertIn("bleeding", response.result.lower())
        self.assertTrue(response.metadata['has_major_interaction'])
        self.assertEqual(len(response.tool_calls), 1)
        self.assertEqual(response.tool_calls[0].tool_name, "lookup_drug_interactions")
        
    @patch.object(MedicationAgent, '_call_ai')
    def test_generate_prescription(self, mock_call_ai):
        """Test prescription generation."""
        # Mock AI response
        mock_call_ai.return_value = """
        PRESCRIPTION:
        
        Medication: Amoxicillin 500mg
        Dose: 500mg
        Route: By mouth (PO)
        Frequency: Three times daily (TID)
        Duration: 7 days
        Quantity: #21 (twenty-one)
        Refills: 0
        
        Instructions: Take with food to minimize stomach upset. Complete entire course.
        Warnings: May cause diarrhea. Notify if rash develops (possible allergy).
        """
        
        task = AgentTask(
            task_description="Generate prescription",
            input_data={
                "medication": {"name": "Amoxicillin", "strength": "500mg"},
                "indication": "Acute sinusitis",
                "patient_info": {"age": 35, "weight": "70kg"}
            }
        )
        
        response = self.agent.execute(task)
        
        self.assertTrue(response.success)
        self.assertIn("Amoxicillin 500mg", response.result)
        self.assertIn("Three times daily", response.result)
        self.assertIn("#21", response.result)
        
    @patch.object(MedicationAgent, '_call_ai')
    def test_validate_dosing(self, mock_call_ai):
        """Test dosing validation."""
        # Mock AI response
        mock_call_ai.return_value = """
        Dosing Assessment:
        
        The prescribed dose of Metformin 2000mg twice daily (4g/day) is INAPPROPRIATE.
        
        - Maximum recommended dose: 2550mg/day
        - Current dose: 4000mg/day
        - Recommendation: Reduce to 1000mg twice daily or 850mg three times daily
        - Patient's renal function should be checked before high doses
        """
        
        task = AgentTask(
            task_description="Validate medication dosing",
            input_data={
                "medication": {
                    "name": "Metformin",
                    "dose": "2000mg",
                    "frequency": "twice daily"
                },
                "patient_factors": {
                    "age": 65,
                    "weight": "80kg",
                    "renal_function": "mild impairment"
                }
            }
        )
        
        response = self.agent.execute(task)
        
        self.assertTrue(response.success)
        self.assertIn("INAPPROPRIATE", response.result)
        self.assertFalse(response.metadata['dosing_appropriate'])
        
    @patch.object(MedicationAgent, '_call_ai')
    def test_suggest_alternatives(self, mock_call_ai):
        """Test alternative medication suggestions."""
        # Mock AI response
        mock_call_ai.return_value = """
        Alternative Medications:
        
        1. Losartan (Cozaar) 50mg daily
           - Advantages: No cough side effect, renal protective
           - Disadvantages: May cause hyperkalemia
           - Cost: Similar to lisinopril
           
        2. Amlodipine (Norvasc) 5mg daily
           - Advantages: Different mechanism, no cough
           - Disadvantages: May cause ankle edema
           - Cost: Generic available, affordable
           
        3. Hydrochlorothiazide 25mg daily
           - Advantages: Mild, well-tolerated
           - Disadvantages: May affect electrolytes
           - Cost: Very inexpensive
        """
        
        task = AgentTask(
            task_description="Suggest alternative medications",
            input_data={
                "current_medication": {"name": "Lisinopril", "dose": "10mg"},
                "reason": "Persistent dry cough",
                "patient_factors": {"age": 55}
            }
        )
        
        response = self.agent.execute(task)
        
        self.assertTrue(response.success)
        self.assertIn("Losartan", response.result)
        self.assertIn("Amlodipine", response.result)
        self.assertEqual(response.metadata['alternative_count'], 3)
        
    def test_determine_task_type(self):
        """Test task type determination."""
        test_cases = [
            ("Extract medications from text", "extract"),
            ("Check drug interactions between meds", "check_interactions"),
            ("Generate prescription for patient", "generate_prescription"),
            ("Validate dosing for medication", "validate_dosing"),
            ("Suggest alternative to current drug", "suggest_alternatives"),
            ("Analyze medications comprehensively", "comprehensive")
        ]
        
        for description, expected_type in test_cases:
            task = AgentTask(task_description=description, input_data={})
            task_type = self.agent._determine_task_type(task)
            self.assertEqual(task_type, expected_type)
            
    def test_parse_medication_list(self):
        """Test medication parsing functionality."""
        text = """
        1. Metformin 500mg
           Dose: 500mg
           Frequency: Twice daily
           Route: Oral
           
        2. Lisinopril 10mg
           Dose: 10mg
           Frequency: Once daily
           Route: Oral
        """
        
        medications = self.agent._parse_medication_list(text)
        
        self.assertEqual(len(medications), 2)
        self.assertEqual(medications[0]['name'], 'Metformin 500mg')
        self.assertEqual(medications[0]['dose'], '500mg')
        self.assertEqual(medications[1]['name'], 'Lisinopril 10mg')
        
    @patch.object(MedicationAgent, '_call_ai')
    def test_comprehensive_analysis(self, mock_call_ai):
        """Test comprehensive medication analysis."""
        # Mock AI response
        mock_call_ai.return_value = """
        Comprehensive Medication Analysis:
        
        1. Medications Identified:
           - Metformin 500mg twice daily
           - Lisinopril 10mg daily
           
        2. Drug Interactions: None significant
        
        3. Dosing Assessment: All doses appropriate
        
        4. Missing Medications:
           - Consider statin for cardiovascular protection
           - Low-dose aspirin may be beneficial
           
        5. Optimization: Current regimen is reasonable
        
        6. Safety Concerns: Monitor renal function
        
        7. Monitoring: HbA1c every 3 months, BP checks
        """
        
        task = AgentTask(
            task_description="Comprehensive medication analysis",
            input_data={
                "clinical_text": "Patient with diabetes and hypertension",
                "current_medications": ["Metformin 500mg BID", "Lisinopril 10mg daily"]
            }
        )
        
        response = self.agent.execute(task)
        
        self.assertTrue(response.success)
        self.assertIn("Comprehensive Medication Analysis", response.result)
        self.assertEqual(response.metadata['analysis_type'], 'comprehensive')
        
    def test_error_handling(self):
        """Test error handling for invalid inputs."""
        # Test with no medications for interaction check
        task = AgentTask(
            task_description="Check drug interactions",
            input_data={"medications": []}
        )
        
        response = self.agent.execute(task)
        
        self.assertFalse(response.success)
        self.assertIn("At least two medications", response.result)
        
        # Test with no clinical text for extraction
        task = AgentTask(
            task_description="Extract medications",
            input_data={}
        )
        
        response = self.agent.execute(task)
        
        self.assertFalse(response.success)
        self.assertIn("No clinical text provided", response.error)


if __name__ == '__main__':
    unittest.main()
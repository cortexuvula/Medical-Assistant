"""
Unit tests for the AI agent system.
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ai.agents import (
    BaseAgent, SynopsisAgent, DiagnosticAgent,
    AgentTask, AgentResponse, AgentConfig, AgentType
)
from managers.agent_manager import agent_manager


class TestAgentModels(unittest.TestCase):
    """Test agent model classes."""
    
    def test_agent_config_creation(self):
        """Test creating an agent configuration."""
        config = AgentConfig(
            name="TestAgent",
            description="Test agent for unit tests",
            system_prompt="You are a test agent.",
            model="gpt-3.5-turbo",
            temperature=0.5,
            max_tokens=100
        )
        
        self.assertEqual(config.name, "TestAgent")
        self.assertEqual(config.temperature, 0.5)
        self.assertEqual(config.max_tokens, 100)
        
    def test_agent_task_creation(self):
        """Test creating an agent task."""
        task = AgentTask(
            task_description="Test task",
            context="Test context",
            input_data={"key": "value"}
        )
        
        self.assertEqual(task.task_description, "Test task")
        self.assertEqual(task.context, "Test context")
        self.assertEqual(task.input_data["key"], "value")
        
    def test_agent_response_creation(self):
        """Test creating an agent response."""
        response = AgentResponse(
            result="Test result",
            success=True,
            thoughts="Test thoughts",
            metadata={"test": True}
        )
        
        self.assertTrue(response.success)
        self.assertEqual(response.result, "Test result")
        self.assertEqual(response.metadata["test"], True)


class TestSynopsisAgent(unittest.TestCase):
    """Test synopsis agent functionality."""
    
    def setUp(self):
        """Set up test agent."""
        self.agent = SynopsisAgent()
        
    def test_agent_initialization(self):
        """Test agent initializes with correct config."""
        self.assertEqual(self.agent.config.name, "SynopsisAgent")
        self.assertEqual(self.agent.config.temperature, 0.3)
        self.assertEqual(self.agent.config.max_tokens, 300)
        
    def test_execute_without_soap_note(self):
        """Test executing without required input."""
        task = AgentTask(
            task_description="Generate synopsis",
            input_data={}
        )
        
        response = self.agent.execute(task)
        self.assertFalse(response.success)
        self.assertIn("No SOAP note provided", response.error)
        
    def test_word_limit_handling(self):
        """Test synopsis word limit enforcement."""
        # Create a very long text
        long_text = " ".join(["word"] * 500)
        
        # The agent should truncate this
        result = self.agent._truncate_to_word_limit(long_text, 200)
        word_count = len(result.split())
        
        self.assertLessEqual(word_count, 200)


class TestDiagnosticAgent(unittest.TestCase):
    """Test diagnostic agent functionality."""
    
    def setUp(self):
        """Set up test agent."""
        self.agent = DiagnosticAgent()
        
    def test_agent_initialization(self):
        """Test agent initializes with correct config."""
        self.assertEqual(self.agent.config.name, "DiagnosticAgent")
        self.assertEqual(self.agent.config.temperature, 0.1)
        self.assertEqual(self.agent.config.max_tokens, 500)
        
    def test_clinical_findings_extraction(self):
        """Test extraction of clinical findings from SOAP note."""
        soap_note = """
        Subjective: Patient reports headache and fever.
        Objective: Temperature 38.5°C, BP 120/80.
        Assessment: Likely viral infection.
        Plan: Rest and fluids.
        """
        
        findings = self.agent._extract_clinical_findings(soap_note)
        self.assertIn("headache and fever", findings)
        self.assertIn("Temperature 38.5°C", findings)
        
    def test_execute_without_findings(self):
        """Test executing without required input."""
        task = AgentTask(
            task_description="Analyze findings",
            input_data={}
        )
        
        response = self.agent.execute(task)
        self.assertFalse(response.success)
        self.assertIn("No clinical findings", response.error)


class TestAgentManager(unittest.TestCase):
    """Test agent manager functionality."""
    
    def test_singleton_pattern(self):
        """Test agent manager is a singleton."""
        manager1 = agent_manager
        manager2 = agent_manager
        self.assertIs(manager1, manager2)
        
    def test_agent_type_checking(self):
        """Test checking if agent types are enabled."""
        # This will depend on current settings
        # Just test the method exists and returns boolean
        result = agent_manager.is_agent_enabled(AgentType.SYNOPSIS)
        self.assertIsInstance(result, bool)
        
    def test_get_enabled_agents(self):
        """Test getting list of enabled agents."""
        agents = agent_manager.get_enabled_agents()
        self.assertIsInstance(agents, dict)
        # All values should be BaseAgent instances
        for agent in agents.values():
            self.assertIsInstance(agent, BaseAgent)


class TestAgentIntegration(unittest.TestCase):
    """Test integration between components."""
    
    def test_agent_history_tracking(self):
        """Test that agents track their history."""
        agent = SynopsisAgent()
        
        # Create and execute a task
        task = AgentTask(
            task_description="Test task",
            input_data={"soap_note": "Test SOAP note"}
        )
        
        # Clear history first
        agent.clear_history()
        self.assertEqual(len(agent.history), 0)
        
        # Note: We can't test actual execution without API keys
        # But we can test the history mechanism structure
        
    def test_agent_context_building(self):
        """Test building context from history."""
        agent = SynopsisAgent()
        agent.clear_history()
        
        # Manually add history entries
        task1 = AgentTask(task_description="Task 1", input_data={})
        response1 = AgentResponse(result="Result 1", success=True)
        agent.add_to_history(task1, response1)
        
        task2 = AgentTask(task_description="Task 2", context="Context 2", input_data={})
        response2 = AgentResponse(result="Result 2", success=True)
        agent.add_to_history(task2, response2)
        
        # Get context
        context = agent.get_context_from_history(max_entries=2)
        
        self.assertIn("Task 1", context)
        self.assertIn("Result 1", context)
        self.assertIn("Task 2", context)
        self.assertIn("Context 2", context)
        self.assertIn("Result 2", context)


if __name__ == "__main__":
    unittest.main()
"""
Agent System Demonstration

This script demonstrates how to use the AI agent system for medical documentation.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ai.agents import AgentTask, AgentType
from managers.agent_manager import agent_manager
from settings.settings import SETTINGS, save_settings


def demo_synopsis_agent():
    """Demonstrate synopsis generation from a SOAP note."""
    print("\n=== SYNOPSIS AGENT DEMO ===\n")
    
    # Sample SOAP note
    soap_note = """
SOAP Note:
ICD-9 Code: 780.60

Subjective:
The patient reports experiencing a high fever for the past 3 days, reaching up to 39.5°C (103.1°F). 
Associated symptoms include severe body aches, chills, fatigue, and mild headache. No cough, 
shortness of breath, or gastrointestinal symptoms. The patient denies recent travel or sick contacts.

Objective:
Temperature: 38.8°C (101.8°F), Blood pressure: 125/78 mmHg, Pulse: 92 bpm, Respiratory rate: 18/min.
General appearance: Appears fatigued but alert. Throat examination reveals mild erythema without exudate.
No lymphadenopathy. Lungs clear to auscultation bilaterally. Heart sounds regular without murmurs.

Assessment:
Acute febrile illness, likely viral in origin. Differential includes influenza, COVID-19, and other viral syndromes.

Plan:
- Rapid influenza and COVID-19 testing ordered
- Supportive care with acetaminophen for fever and body aches
- Encourage fluid intake and rest
- Return if symptoms worsen or new symptoms develop
- Follow up in 3-5 days if not improving
"""
    
    # Check if synopsis agent is enabled
    if agent_manager.is_agent_enabled(AgentType.SYNOPSIS):
        synopsis = agent_manager.generate_synopsis(soap_note)
        if synopsis:
            print("Generated Synopsis:")
            print("-" * 50)
            print(synopsis)
            print("-" * 50)
        else:
            print("Synopsis generation failed.")
    else:
        print("Synopsis agent is not enabled. Enable it in Agent Settings.")


def demo_diagnostic_agent():
    """Demonstrate diagnostic analysis."""
    print("\n=== DIAGNOSTIC AGENT DEMO ===\n")
    
    # Clinical findings for analysis
    clinical_findings = """
Patient Complaints:
- Severe headache for 2 weeks, progressively worsening
- Headache is unilateral (right-sided), throbbing in nature
- Associated with nausea and photophobia
- Worse in the morning
- Some relief with rest in dark room
- Family history of migraines (mother and sister)

Examination Findings:
- Vital signs: BP 130/85, HR 78, Temp 37.0°C
- Neurological exam: No focal deficits, cranial nerves intact
- Fundoscopy: Normal optic discs, no papilledema
- Neck: No stiffness or meningeal signs
"""
    
    if agent_manager.is_agent_enabled(AgentType.DIAGNOSTIC):
        task = AgentTask(
            task_description="Analyze clinical findings and provide differential diagnosis",
            input_data={"clinical_findings": clinical_findings}
        )
        
        response = agent_manager.execute_agent_task(AgentType.DIAGNOSTIC, task)
        if response and response.success:
            print("Diagnostic Analysis:")
            print("-" * 50)
            print(response.result)
            print("-" * 50)
            print(f"\nMetadata: {response.metadata}")
        else:
            print(f"Diagnostic analysis failed: {response.error if response else 'Unknown error'}")
    else:
        print("Diagnostic agent is not enabled. Enable it in Agent Settings.")


def enable_agents_for_demo():
    """Temporarily enable agents for the demo."""
    print("\nEnabling agents for demo...")
    
    # Ensure agent_config exists
    if "agent_config" not in SETTINGS:
        SETTINGS["agent_config"] = {}
    
    # Enable synopsis agent
    if "synopsis" not in SETTINGS["agent_config"]:
        SETTINGS["agent_config"]["synopsis"] = {}
    SETTINGS["agent_config"]["synopsis"]["enabled"] = True
    
    # Enable diagnostic agent
    if "diagnostic" not in SETTINGS["agent_config"]:
        SETTINGS["agent_config"]["diagnostic"] = {}
    SETTINGS["agent_config"]["diagnostic"]["enabled"] = True
    
    # Save settings
    save_settings(SETTINGS)
    
    # Reload agents
    agent_manager.reload_agents()
    print("Agents enabled successfully!")


def main():
    """Run the agent demonstration."""
    print("Medical Assistant Agent System Demo")
    print("===================================")
    
    # Enable agents for the demo
    enable_agents_for_demo()
    
    # Run demos
    demo_synopsis_agent()
    demo_diagnostic_agent()
    
    print("\n\nDemo completed!")
    print("\nTo configure agents in the application:")
    print("1. Open Medical Assistant")
    print("2. Go to Settings > Agent Settings")
    print("3. Enable/disable agents and configure their parameters")
    print("4. Test configurations before saving")


if __name__ == "__main__":
    main()
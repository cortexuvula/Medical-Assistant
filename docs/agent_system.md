# AI Agent System Documentation

## Overview

The Medical Assistant now includes a modular AI agent system that allows for specialized medical documentation tasks. Each agent is designed for a specific purpose and can be configured independently.

## Available Agents

### 1. Synopsis Agent (Implemented)
- **Purpose**: Generates concise clinical synopses from SOAP notes
- **Default Model**: GPT-4
- **Temperature**: 0.3 (focused output)
- **Max Tokens**: 300
- **Output**: A brief paragraph summarizing key clinical findings

### 2. Diagnostic Agent (Implemented)
- **Purpose**: Analyzes symptoms and suggests differential diagnoses
- **Default Model**: GPT-4
- **Temperature**: 0.1 (highly consistent)
- **Max Tokens**: 500
- **Output**: Structured diagnostic analysis with:
  - Clinical summary
  - Differential diagnoses ranked by likelihood
  - Red flags
  - Recommended investigations
  - Clinical pearls

### 3. Medication Agent (Implemented)
- **Purpose**: Comprehensive medication analysis and interaction checking
- **Default Model**: GPT-4
- **Temperature**: 0.2 (high accuracy for safety)
- **Features**:
  - Extract medications from clinical text
  - Check drug-drug interactions with severity levels
  - Validate dosing appropriateness
  - Suggest medication alternatives
  - Generate prescriptions
  - Comprehensive safety analysis

See [medication_agent.md](medication_agent.md) for detailed documentation.

### 4. Referral Agent (Implemented)
- **Purpose**: Generate professional referral letters
- **Default Model**: GPT-4
- **Temperature**: 0.3
- **Features**:
  - Address book integration
  - Automatic specialty inference
  - Professional formatting
  - Clinical summary inclusion

### 5. Data Extraction Agent (Implemented)
- **Purpose**: Extract structured data from clinical text
- **Default Model**: GPT-4
- **Temperature**: 0.1 (highly consistent)
- **Output**: Structured extraction of:
  - Vital signs
  - Lab values
  - Medications
  - Diagnoses
  - Allergies

### 6. Workflow Agent (Implemented)
- **Purpose**: Multi-step clinical process coordination
- **Default Model**: GPT-4
- **Temperature**: 0.3
- **Features**:
  - Patient intake workflows
  - Diagnostic workup planning
  - Treatment protocol guidance
  - Follow-up care coordination
  - Interactive checklist tracking

### 7. Chat Agent (Implemented)
- **Purpose**: Interactive clinical Q&A and assistance
- **Default Model**: GPT-4
- **Temperature**: 0.7 (balanced)
- **Features**:
  - Context-aware responses
  - Medical knowledge queries
  - Documentation assistance

## Configuration

### Using the UI

1. Open Medical Assistant
2. Navigate to **Settings → Agent Settings**
3. Select the agent tab you want to configure
4. Adjust settings:
   - Enable/disable the agent
   - Select AI provider and model
   - Adjust temperature (0.0 = focused, 2.0 = creative)
   - Set max tokens
   - Customize system prompt
5. Test configuration before saving
6. Click "Save Settings"

### Configuration Parameters

#### Temperature
- **0.0-0.3**: Best for clinical tasks requiring consistency (diagnostics, data extraction)
- **0.4-0.7**: Balanced for general medical documentation
- **0.8-1.0**: More creative output (patient letters, explanations)

#### Max Tokens
- Synopsis: 200-300 tokens
- Diagnostic: 400-600 tokens
- Referral: 300-400 tokens
- Complex analysis: 600-1000 tokens

#### System Prompts
Each agent has a carefully crafted default system prompt. You can customize these to:
- Add institution-specific guidelines
- Include preferred formatting
- Emphasize certain aspects
- Add specialty-specific knowledge

## Usage in Code

### Agent Manager

The `AgentManager` provides a centralized interface for all agents:

```python
from managers.agent_manager import agent_manager
from ai.agents import AgentTask, AgentType

# Check if an agent is enabled
if agent_manager.is_agent_enabled(AgentType.SYNOPSIS):
    # Generate synopsis
    synopsis = agent_manager.generate_synopsis(soap_note_text)
```

### Direct Agent Usage

```python
from ai.agents import DiagnosticAgent, AgentTask

# Create agent with custom config
agent = DiagnosticAgent()

# Create task
task = AgentTask(
    task_description="Analyze symptoms",
    input_data={"clinical_findings": findings_text}
)

# Execute
response = agent.execute(task)
if response.success:
    print(response.result)
```

## Creating New Agents

To add a new agent type:

1. **Define the agent type** in `src/ai/agents/models.py`:
```python
class AgentType(str, Enum):
    # ... existing types ...
    MY_NEW_AGENT = "my_new_agent"
```

2. **Create agent implementation** in `src/ai/agents/my_agent.py`:
```python
from .base import BaseAgent
from .models import AgentConfig, AgentTask, AgentResponse

class MyNewAgent(BaseAgent):
    DEFAULT_CONFIG = AgentConfig(
        name="MyNewAgent",
        description="Description",
        system_prompt="...",
        model="gpt-4",
        temperature=0.5
    )
    
    def execute(self, task: AgentTask) -> AgentResponse:
        # Implementation
        pass
```

3. **Register in agent manager** (`src/managers/agent_manager.py`):
```python
AGENT_CLASSES = {
    # ... existing agents ...
    AgentType.MY_NEW_AGENT: MyNewAgent
}
```

4. **Add default settings** in `src/settings/settings.py`

5. **Update UI** in `src/ui/dialogs/agent_settings_dialog.py`

## Best Practices

1. **Test Configurations**: Always test agent configurations before deploying
2. **Monitor Performance**: Check agent response times and quality
3. **Iterative Refinement**: Adjust prompts based on actual usage
4. **Error Handling**: Agents gracefully handle errors without disrupting workflow
5. **Resource Management**: Be mindful of token usage and API costs

## Integration Points

- **SOAP Generation**: Synopsis agent automatically appends to SOAP notes
- **Chat Interface**: Agents can be invoked through chat commands
- **Processing Queue**: Agent tasks can be queued for background processing
- **Workflow Automation**: Chain multiple agents for complex tasks

## Troubleshooting

### Agent Not Working
1. Check if agent is enabled in settings
2. Verify API keys are configured
3. Test agent configuration in settings dialog
4. Check logs for error messages

### Poor Output Quality
1. Adjust temperature settings
2. Refine system prompt
3. Increase max tokens if output is truncated
4. Try different AI models

### Performance Issues
1. Reduce max tokens
2. Use faster models (e.g., GPT-3.5-turbo)
3. Enable caching if available
4. Consider async processing for non-critical tasks
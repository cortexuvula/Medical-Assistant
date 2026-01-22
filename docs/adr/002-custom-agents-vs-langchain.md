# ADR-002: Custom Agents vs LangChain

## Status

Accepted

## Date

2024-06

## Context

Medical Assistant requires specialized AI agents for clinical tasks:

- **Medication Agent**: Drug interaction checking, dosing validation, alternative suggestions
- **Diagnostic Agent**: Differential diagnosis generation from symptoms
- **Workflow Agent**: Clinical process coordination (patient intake, treatment protocols)
- **Referral Agent**: Specialist referral letter generation
- **Synopsis Agent**: SOAP note summarization

We needed to decide between:
1. Using an existing agent framework (LangChain, AutoGen, CrewAI)
2. Building a custom lightweight agent system

## Decision

We chose to build a **custom agent system** with a simple `BaseAgent` class and task-specific implementations.

Architecture:
```
src/ai/agents/
├── base.py          # BaseAgent class
├── models.py        # AgentConfig, AgentTask, AgentResponse (Pydantic)
├── medication.py    # MedicationAgent
├── diagnostic.py    # DiagnosticAgent
├── workflow.py      # WorkflowAgent
├── referral.py      # ReferralAgent
└── synopsis.py      # SynopsisAgent
```

Each agent:
- Inherits from `BaseAgent`
- Implements `execute(task: AgentTask) -> AgentResponse`
- Uses provider-agnostic AI calls via `call_ai()` router
- Has domain-specific prompts and output parsing

## Consequences

### Positive

- **Simplicity**: ~200 lines for base + models vs thousands for LangChain
- **No framework lock-in**: Easy to swap AI providers or modify behavior
- **Predictable behavior**: No "magic" - clear control flow from input to output
- **Medical domain focus**: Prompts and validation tailored to clinical use cases
- **Fast iteration**: Adding a new agent is straightforward (inherit, implement execute)
- **Minimal dependencies**: No large framework dependencies to manage
- **Debugging**: Stack traces are clear, no framework abstraction layers
- **Performance**: Direct API calls without framework overhead
- **Provider flexibility**: Already supports OpenAI, Anthropic, Gemini, Ollama

### Negative

- **No built-in tools**: Had to implement our own tool/function calling patterns
- **No agent orchestration**: Multi-agent workflows require manual coordination
- **No memory abstractions**: Conversation history managed manually per agent
- **Missing features**: No automatic retry logic, caching, or tracing (added separately)
- **Documentation burden**: Must document our own patterns vs referencing framework docs
- **Fewer examples**: Contributors can't reference LangChain tutorials

### Neutral

- Agents are stateless by design (state managed externally in UI/database)
- Each agent call is independent (no persistent agent "sessions")

## Alternatives Considered

### LangChain

**Rejected because:**
- Heavy dependency (~100+ transitive packages)
- Frequent breaking changes between versions
- Abstraction overhead for simple prompt->response patterns
- "Chain" metaphor doesn't fit our discrete task model
- Most features (vector stores, document loaders) already implemented separately
- Complex debugging when things go wrong
- Overkill for our use case (we don't need complex chains or autonomous agents)

### AutoGen / CrewAI

**Rejected because:**
- Designed for multi-agent conversation scenarios
- Our agents are task-focused, not conversational
- Additional complexity without clear benefit
- Newer frameworks with less stability guarantees

### OpenAI Assistants API

**Rejected because:**
- Vendor lock-in to OpenAI
- Less control over prompt engineering
- Persistent assistant state adds complexity
- We already support multiple AI providers

### No Agent Abstraction (Direct Prompts)

**Rejected because:**
- Code duplication across similar tasks
- Harder to maintain consistent patterns
- No centralized configuration for agent behavior
- Difficult to add cross-cutting concerns (logging, metrics)

## Implementation Details

### BaseAgent Pattern

```python
class BaseAgent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = get_logger(self.__class__.__name__)

    def execute(self, task: AgentTask) -> AgentResponse:
        raise NotImplementedError

    def _call_ai(self, prompt: str, system_message: str) -> str:
        return call_ai(
            model=self.config.model,
            system_message=system_message,
            prompt=prompt,
            temperature=self.config.temperature
        )
```

### Agent Manager

```python
class AgentManager:
    """Singleton managing agent lifecycle and execution."""

    def get_agent(self, agent_type: AgentType) -> BaseAgent:
        # Lazy initialization with caching

    def execute_agent_task(self, agent_type: AgentType, task: AgentTask) -> AgentResponse:
        agent = self.get_agent(agent_type)
        return agent.execute(task)
```

## References

- [src/ai/agents/](../../src/ai/agents/) - Agent implementations
- [docs/agent_system.md](../agent_system.md) - Detailed agent documentation
- [docs/medication_agent.md](../medication_agent.md) - Medication agent specifics

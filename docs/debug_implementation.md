# Debug Implementation for Chat Agent

## Overview

A comprehensive debugging system has been implemented to track and diagnose issues with the chat agent's tool-calling and response generation capabilities.

## Components

### 1. Debug Module (`src/ai/debug/`)

- **chat_debug.py**: Core debugging functionality
  - `ChatDebugger` class for tracking execution steps
  - Logs all prompts, responses, tool calls, and configurations
  - Saves detailed execution logs to `AppData/debug/`
  - Provides execution summaries and error tracking

### 2. Instrumented Chat Agent

The chat agent (`src/ai/agents/chat.py`) has been enhanced with:
- Debug logging at every step of execution
- Tracking of tool discovery and execution
- Response length and truncation detection
- Configuration logging

### 3. Key Fixes Implemented

1. **Tool Registry**: Fixed to use global tool registry instead of creating new instance
2. **MCP Tool Integration**: Ensured MCP tools are registered before chat agent creation
3. **System Prompt**: Preserved tool-calling instructions when custom config is provided
4. **Model Selection**: Fixed to use configured model (GPT-4) instead of falling back to GPT-3.5
5. **Follow-up Prompts**: Improved to extract specific information from tool results

## Debug Output

Debug information is saved to:
- `AppData/debug/chat_debug_YYYYMMDD_HHMMSS.log` - Detailed log file
- `AppData/debug/execution_<id>.json` - Complete execution trace
- `AppData/debug/last_test_summary.json` - Summary of last test

## Usage

### In Production
The debug system automatically tracks all chat agent executions when the application runs.

### For Testing
```python
from ai.debug import chat_debugger

# Debug info is automatically collected during execution
# Access summary:
summary = chat_debugger.get_debug_summary()
```

## Debug Log Structure

Each execution tracks:
1. Configuration (model, temperature, available tools)
2. Initial prompt and response
3. Tool extraction and execution
4. Tool results
5. Follow-up prompt and final response
6. Timing information
7. Error details (if any)

## Common Issues Diagnosed

1. **Missing Tools**: Tools not available due to initialization order
2. **Wrong Model**: System falling back to default model
3. **Incomplete Responses**: Responses being truncated or incomplete
4. **Tool Call Format**: AI not using correct tool call syntax
5. **Rate Limiting**: MCP tools hitting API rate limits

## Future Enhancements

1. Add debug UI panel to show real-time execution info
2. Add metrics tracking (token usage, response times)
3. Add automated issue detection and alerts
4. Integration with monitoring services
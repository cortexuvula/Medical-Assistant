"""
Chat agent with tool-calling capabilities.
"""

import logging
import json
import re
from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING

from .base import BaseAgent
from .models import AgentConfig, AgentTask, AgentResponse, ToolCall
from ..tools import ToolExecutor, ToolResult
from ..tools.tool_registry import tool_registry
from ..debug import chat_debugger

if TYPE_CHECKING:
    from .ai_caller import AICallerProtocol


logger = logging.getLogger(__name__)


class ChatAgent(BaseAgent):
    """Agent specialized for chat interactions with tool-calling capabilities."""
    
    # Default configuration for chat agent
    DEFAULT_CONFIG = AgentConfig(
        name="ChatAgent",
        description="Interactive chat agent with tool-calling capabilities",
        system_prompt="""You are a helpful medical AI assistant with access to various tools.

When a user asks you to perform a task that would benefit from using a tool, you MUST:
1. First, make the necessary tool call(s) using the exact format shown below
2. Wait for the tool results before providing your final answer

ALWAYS USE TOOLS FOR:
- Medical guidelines, recommendations, or protocols
- Specific medical values, targets, ranges, or thresholds
- Current best practices or standards
- Drug information, interactions, or dosing
- Any query asking for specific medical facts or data
- Questions about conditions, treatments, or procedures
- Queries mentioning specific years (e.g., "2025 guidelines")
- When users ask "what is", "what are", "how much", etc.

To use a tool, you MUST format your tool call EXACTLY like this:
<tool_call>
{
  "tool_name": "tool_name_here",
  "arguments": {
    "param1": "value1",
    "param2": "value2"
  }
}
</tool_call>

IMPORTANT RULES:
- Always make tool calls BEFORE providing descriptive text
- You can make multiple tool calls if needed
- Each tool call must be in its own <tool_call> block
- The JSON inside must be valid and properly formatted
- When I provide tool results, respond with a natural, helpful answer - NOT another tool call
- For medical queries, ALWAYS use search tools to get current information

Example for a medical guideline request:
<tool_call>
{
  "tool_name": "mcp_brave-search_brave_web_search",
  "arguments": {
    "query": "2025 Canadian hypertension guidelines BP target 50 year old"
  }
}
</tool_call>

I'll search for the latest Canadian hypertension guidelines...

Remember: ALWAYS use tools for medical information queries to ensure accuracy and currency.""",
        model="gpt-4",
        temperature=0.7,
        max_tokens=1000,
        available_tools=[]  # Will be populated from registry
    )
    
    def __init__(self, config: Optional[AgentConfig] = None,
                 tool_executor: Optional[ToolExecutor] = None,
                 ai_caller: Optional['AICallerProtocol'] = None):
        """
        Initialize the chat agent.

        Args:
            config: Optional custom configuration
            tool_executor: Optional tool executor instance
            ai_caller: Optional AI caller for dependency injection.
        """
        # If a config is provided, ensure it has the proper tool-calling system prompt
        if config:
            # Preserve the tool-calling instructions from DEFAULT_CONFIG
            if not config.system_prompt or "tool_call" not in config.system_prompt:
                config.system_prompt = self.DEFAULT_CONFIG.system_prompt

        super().__init__(config or self.DEFAULT_CONFIG, ai_caller=ai_caller)
        
        # Use the global tool registry and executor
        self.tool_registry = tool_registry
        self.tool_executor = tool_executor or ToolExecutor()

        # Track cache version to avoid unnecessary refreshes
        self._last_cache_version = -1

        # Update available tools in config
        self.refresh_available_tools()

    def refresh_available_tools(self) -> bool:
        """Refresh the available tools from the registry if cache changed.

        Returns:
            True if tools were refreshed, False if cache was still valid
        """
        cache_version, is_cached = self.tool_registry.get_cache_info()

        if cache_version != self._last_cache_version:
            self.config.available_tools = self.tool_registry.get_all_definitions()
            self._last_cache_version = cache_version
            logger.info(f"Refreshed available tools (cache v{cache_version}). Total: {len(self.config.available_tools)}")
            return True

        logger.debug(f"Tools cache still valid (v{cache_version}), skipping refresh")
        return False
        
    def execute(self, task: AgentTask) -> AgentResponse:
        """
        Execute a chat task with potential tool usage.
        
        Args:
            task: The chat task to execute
            
        Returns:
            AgentResponse with the result
        """
        # Start debug tracking
        chat_debugger.start_execution(task.task_description)
        
        try:
            # Log configuration
            chat_debugger.log_config("agent_config", {
                "model": self.config.model,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "provider": self.config.provider,
                "available_tools_count": len(self.config.available_tools) if self.config.available_tools else 0
            })
            
            # Refresh available tools before execution (only if cache changed)
            tools_updated = self.refresh_available_tools()
            chat_debugger.log_step("tools_checked", {
                "refreshed": tools_updated,
                "tool_count": len(self.config.available_tools),
                "tool_names": [t.name for t in self.config.available_tools] if self.config.available_tools else []
            })
            
            # Build the prompt with available tools
            prompt = self._build_prompt(task)
            chat_debugger.log_prompt("initial", prompt, self.config.model, self.config.temperature)
            
            # Get initial response from AI
            ai_response = self._call_ai(prompt)
            chat_debugger.log_response("initial", ai_response, {
                "length": len(ai_response) if ai_response else 0,
                "truncated": "..." in str(ai_response) if ai_response else False
            })
            
            # Check for tool calls in the response
            tool_calls, remaining_text = self._extract_tool_calls(ai_response)
            chat_debugger.log_step("tool_extraction", {
                "tool_calls_found": len(tool_calls),
                "remaining_text_length": len(remaining_text),
                "tool_names": [tc.tool_name for tc in tool_calls]
            })
            
            if tool_calls:
                # Execute the tools
                tool_results = self._execute_tools(tool_calls)
                
                # Log tool results
                for tool_call in tool_calls:
                    result = tool_results.get(tool_call.tool_name)
                    chat_debugger.log_tool_call(
                        tool_call.tool_name,
                        tool_call.arguments,
                        result
                    )
                
                # Build follow-up prompt with tool results
                follow_up_prompt = self._build_follow_up_prompt(
                    task, ai_response, tool_results
                )
                chat_debugger.log_prompt("follow_up", follow_up_prompt, self.config.model, self.config.temperature)
                
                # Get final response incorporating tool results
                final_response = self._call_ai(follow_up_prompt)
                chat_debugger.log_response("final", final_response, {
                    "length": len(final_response) if final_response else 0,
                    "truncated": "..." in str(final_response) if final_response else False
                })
                
                response = AgentResponse(
                    result=final_response,
                    tool_calls=tool_calls,
                    success=True,
                    metadata={
                        "used_tools": True,
                        "tool_count": len(tool_calls),
                        "tool_results": tool_results
                    }
                )
                
                chat_debugger.end_execution(True, final_response)
                return response
            else:
                # No tools used, return direct response
                response = AgentResponse(
                    result=ai_response,
                    tool_calls=[],
                    success=True,
                    metadata={"used_tools": False}
                )
                
                chat_debugger.end_execution(True, ai_response)
                return response
                
        except Exception as e:
            logger.error(f"Chat agent execution failed: {e}", exc_info=True)
            chat_debugger.log_step("execution_error", {"error": str(e)}, e)
            chat_debugger.end_execution(False, None)
            
            return AgentResponse(
                result="",
                success=False,
                error=str(e)
            )
            
    def _build_prompt(self, task: AgentTask) -> str:
        """Build the initial prompt including available tools."""
        # Get tool descriptions
        tool_descriptions = []
        for tool in self.config.available_tools:
            params = []
            for param in tool.parameters:
                param_desc = f"  - {param.name} ({param.type}): {param.description}"
                if not param.required:
                    param_desc += f" [optional, default: {param.default}]"
                params.append(param_desc)
                
            tool_desc = f"- {tool.name}: {tool.description}\n  Parameters:\n" + "\n".join(params)
            tool_descriptions.append(tool_desc)
            
        tools_section = "Available tools:\n" + "\n\n".join(tool_descriptions) if tool_descriptions else "No tools available."
        
        # Build complete prompt
        prompt_parts = [
            f"User request: {task.task_description}",
            ""
        ]
        
        if task.context:
            prompt_parts.extend([
                "Context:",
                task.context,
                ""
            ])
            
        prompt_parts.extend([
            tools_section,
            "",
            "Please help the user with their request. Use tools if they would be helpful."
        ])
        
        return "\n".join(prompt_parts)
        
    def _extract_tool_calls(self, response: str) -> Tuple[List[ToolCall], str]:
        """Extract tool calls from the AI response."""
        tool_calls = []
        remaining_text = response
        
        # Find all tool call blocks
        pattern = r'<tool_call>(.*?)</tool_call>'
        matches = re.findall(pattern, response, re.DOTALL)
        
        for match in matches:
            try:
                # Parse the JSON content
                tool_data = json.loads(match.strip())
                
                tool_call = ToolCall(
                    tool_name=tool_data.get("tool_name", ""),
                    arguments=tool_data.get("arguments", {})
                )
                tool_calls.append(tool_call)
                
                # Remove the tool call from the text
                remaining_text = remaining_text.replace(f'<tool_call>{match}</tool_call>', '')
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse tool call JSON: {e}")
                continue
                
        return tool_calls, remaining_text.strip()
        
    def _execute_tools(self, tool_calls: List[ToolCall]) -> Dict[str, ToolResult]:
        """Execute the requested tools."""
        results = {}
        
        for tool_call in tool_calls:
            logger.info(f"Executing tool: {tool_call.tool_name}")
            
            result = self.tool_executor.execute_tool(
                tool_call.tool_name,
                tool_call.arguments
            )
            
            results[tool_call.tool_name] = result
            
        return results
        
    def _build_follow_up_prompt(self, task: AgentTask, initial_response: str, 
                               tool_results: Dict[str, ToolResult]) -> str:
        """Build follow-up prompt with tool results."""
        prompt_parts = [
            "You made the following tool calls and here are the results:",
            ""
        ]
        
        for tool_name, result in tool_results.items():
            if result.success:
                prompt_parts.append(f"Tool: {tool_name}")
                prompt_parts.append(f"Result: {json.dumps(result.output, indent=2)}")
            else:
                prompt_parts.append(f"Tool: {tool_name}")
                prompt_parts.append(f"Error: {result.error}")
            prompt_parts.append("")
            
        prompt_parts.extend([
            "Original user request:",
            task.task_description,
            "",
            "Based on these search results, please provide a complete, informative response to the user's request.",
            "Extract and present the specific information the user asked for from the search results."
        ])
        
        # Analyze the request to provide specific guidance
        request_lower = task.task_description.lower()
        
        if "hypertension" in request_lower or "bp" in request_lower or "blood pressure" in request_lower:
            prompt_parts.extend([
                "",
                "For hypertension guidelines, include:",
                "1. The specific recommended BP ranges",
                "2. Any different targets for specific populations (elderly, diabetic, etc.)",
                "3. Which guideline year/version you're referencing",
                "Focus on extracting the actual BP numbers (e.g., <130/80 mmHg)."
            ])
        elif "diabetes" in request_lower or "glucose" in request_lower or "a1c" in request_lower:
            prompt_parts.extend([
                "",
                "For diabetes guidelines, include:",
                "1. The specific recommended glucose ranges (fasting, postprandial)",
                "2. HbA1c targets if mentioned",
                "3. Any different targets for specific populations",
                "4. Which guideline year/version you're referencing",
                "Focus on extracting the actual glucose values and units."
            ])
        elif "cholesterol" in request_lower or "lipid" in request_lower:
            prompt_parts.extend([
                "",
                "For lipid/cholesterol guidelines, include:",
                "1. The specific target levels for LDL, HDL, total cholesterol",
                "2. Triglyceride targets if mentioned",
                "3. Risk-based targets if applicable",
                "4. Which guideline year/version you're referencing"
            ])
        
        return "\n".join(prompt_parts)
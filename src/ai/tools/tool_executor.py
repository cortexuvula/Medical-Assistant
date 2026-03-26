"""
Tool executor for safely executing tools with proper isolation and controls.
"""

import time
import threading
from typing import Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import traceback

from .base_tool import ToolResult
from .tool_registry import tool_registry
from settings.settings_manager import settings_manager
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class ToolExecutor:
    """Executes tools with safety controls and resource limits."""
    
    def __init__(self, confirm_callback: Optional[Callable[[str], bool]] = None):
        """
        Initialize the tool executor.
        
        Args:
            confirm_callback: Optional callback for user confirmation
        """
        self.confirm_callback = confirm_callback
        self._executor = ThreadPoolExecutor(max_workers=3)
        self._execution_history = []
        
        # Load settings
        self.timeout_seconds = settings_manager.get_nested("tool_execution.timeout_seconds", 30)
        self.require_confirmation = settings_manager.get_nested("tool_execution.require_confirmation", True)
        self.log_executions = settings_manager.get_nested("tool_execution.log_executions", True)
        self.max_retries = settings_manager.get_nested("tool_execution.max_retries", 2)
        
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """
        Execute a tool with the given arguments.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool
            
        Returns:
            ToolResult from the tool execution
        """
        start_time = time.time()
        
        # Get the tool
        tool = tool_registry.get_tool(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                output=None,
                error=f"Tool '{tool_name}' not found"
            )
            
        # Log execution attempt
        if self.log_executions:
            logger.info(f"Executing tool '{tool_name}' with arguments: {arguments}")
            
        try:
            # Execute the tool once
            result = self._execute_with_timeout(tool, arguments)

            # If the tool signals it needs confirmation, ask the user
            # before re-executing (the first call returned early without
            # performing the destructive action).
            if result.requires_confirmation and self.require_confirmation and self.confirm_callback:
                message = result.confirmation_message or f"Tool '{tool_name}' requires confirmation to proceed."
                if not self.confirm_callback(message):
                    return ToolResult(
                        success=False,
                        output=None,
                        error="User cancelled the operation"
                    )
                # User confirmed — re-execute to perform the actual operation.
                # Tools that return requires_confirmation=True must NOT perform
                # the action on that first call (they return early as a gate).
                result = self._execute_with_timeout(tool, arguments)

            # Record execution
            execution_time = time.time() - start_time
            self._record_execution(tool_name, arguments, result, execution_time)

            return result
            
        except Exception as e:
            logger.error(f"Tool execution failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                output=None,
                error=f"Execution failed: {str(e)}"
            )
            
    def _execute_with_timeout(self, tool, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool with timeout protection."""
        future = self._executor.submit(tool.safe_execute, **arguments)
        
        try:
            return future.result(timeout=self.timeout_seconds)
        except TimeoutError:
            future.cancel()
            return ToolResult(
                success=False,
                output=None,
                error=f"Tool execution timed out after {self.timeout_seconds} seconds"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Tool execution error: {str(e)}"
            )
            
    def _record_execution(self, tool_name: str, arguments: Dict[str, Any], 
                         result: ToolResult, execution_time: float):
        """Record tool execution for history and debugging."""
        record = {
            'tool_name': tool_name,
            'arguments': arguments,
            'success': result.success,
            'execution_time': execution_time,
            'timestamp': time.time(),
            'error': result.error
        }
        
        self._execution_history.append(record)
        
        # Keep only recent history (last 100 executions)
        if len(self._execution_history) > 100:
            self._execution_history = self._execution_history[-100:]
            
    def get_execution_history(self) -> list:
        """Get the tool execution history."""
        return self._execution_history.copy()
        
    def clear_history(self):
        """Clear the execution history."""
        self._execution_history.clear()
        
    def shutdown(self):
        """Shutdown the executor."""
        self._executor.shutdown(wait=True)
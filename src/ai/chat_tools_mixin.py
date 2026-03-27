"""
Chat Tools Mixin

Provides tool usage detection, MCP initialization, tool confirmation,
and tool management for ChatProcessor. Extracted to keep the main
processor focused on AI orchestration.
"""

import re
import threading
import tkinter as tk
from typing import TYPE_CHECKING

from settings.settings_manager import settings_manager
from utils.structured_logging import get_logger

if TYPE_CHECKING:
    from ai.agents.chat import ChatAgent
    from ai.tools.tool_executor import ToolExecutor

logger = get_logger(__name__)


class ChatToolsMixin:
    """Tool management methods for ChatProcessor."""

    def _should_use_tools(self, user_message: str) -> bool:
        """Determine if the message might benefit from tool usage."""
        if not self.use_tools or not self.chat_agent:
            return False

        message_lower = user_message.lower()

        # Keywords that suggest tool usage
        tool_keywords = [
            # Calculation keywords
            "calculate", "compute", "math", "add", "subtract", "multiply", "divide",
            # Time/date keywords
            "what time", "what date", "current time", "today", "tomorrow",
            # File operation keywords
            "read file", "open file", "save file", "write file",
            # Search keywords
            "search", "find", "look up", "lookup",
            # Data format keywords
            "parse json", "format json",
            # Medical calculation keywords
            "bmi", "body mass index", "drug interaction", "medication interaction",
            "dosage", "dose calculation", "mg/kg",
            # Medical guideline keywords
            "guideline", "guidelines", "recommendation", "recommendations",
            "protocol", "protocols", "standard", "standards", "best practice",
            # Medical value queries
            "target", "range", "level", "levels", "dose", "dosing",
            "threshold", "normal value", "reference range",
            # Question patterns
            "what is the", "what are the", "how much", "how many",
            "what should", "what does", "when should",
            # Medical specialties and conditions
            "hypertension", "blood pressure", "bp target", "diabetes",
            "cholesterol", "lipid", "glucose", "a1c", "hba1c",
            # Information queries
            "latest", "current", "recent", "updated", "new",
            "according to", "based on"
        ]

        # Check for any keyword match
        if any(keyword in message_lower for keyword in tool_keywords):
            return True

        # Check for year patterns (e.g., "2025 guidelines", "2024 recommendations")
        year_pattern = r'\b20\d{2}\b'  # Matches years 2000-2099
        if re.search(year_pattern, message_lower):
            return True

        # Check for question patterns that likely need information retrieval
        question_patterns = [
            r'^what\s+is\s+',
            r'^what\s+are\s+',
            r'^how\s+much\s+',
            r'^how\s+many\s+',
            r'^when\s+should\s+',
            r'^where\s+can\s+',
            r'^who\s+should\s+',
            r'^why\s+is\s+',
            r'\?$'  # Any message ending with a question mark
        ]

        for pattern in question_patterns:
            if re.search(pattern, message_lower):
                return True

        return False

    def _confirm_tool_execution(self, message: str) -> bool:
        """Callback to confirm tool execution with the user.

        Called from a worker thread. Schedules a dialog on the main thread
        and blocks until the user responds or a 30-second timeout elapses.
        """
        try:
            from tkinter import messagebox

            result = [False]
            event = threading.Event()

            def show_confirmation():
                try:
                    result[0] = messagebox.askyesno(
                        "Tool Confirmation",
                        message,
                        parent=self.app
                    )
                finally:
                    event.set()  # Unblock worker regardless of outcome

            self.app.after(0, show_confirmation)

            # Block efficiently until dialog is dismissed or timeout
            if not event.wait(timeout=30):
                logger.warning("Tool confirmation timed out")
                return False

            return result[0]

        except (tk.TclError, RuntimeError) as e:
            logger.error(f"Error showing tool confirmation: {e}")
            return False  # Deny on error

    def _initialize_mcp(self):
        """Initialize MCP manager and register tools."""
        from ai.mcp.mcp_manager import mcp_manager, health_monitor
        from ai.mcp.mcp_tool_wrapper import register_mcp_tools
        from ai.tools.tool_registry import tool_registry

        try:
            mcp_config = settings_manager.get("mcp_config", {})

            # Load MCP servers
            mcp_manager.load_config(mcp_config)

            # Register MCP tools with the tool registry
            if mcp_config.get("enabled", False):
                registered = register_mcp_tools(tool_registry, mcp_manager)
                if registered > 0:
                    logger.info(f"Registered {registered} MCP tools")

                # Start health monitor for automatic server recovery
                health_monitor.start()
            else:
                # Stop health monitor if MCP is disabled
                health_monitor.stop()

        except (ImportError, OSError, ValueError) as e:
            logger.error(f"Error initializing MCP: {e}")

    def reload_mcp_tools(self):
        """Reload MCP tools after configuration change."""
        from ai.mcp.mcp_manager import mcp_manager, health_monitor
        from ai.tools.tool_registry import tool_registry

        try:
            # Stop health monitor first
            health_monitor.stop()

            # Stop all MCP servers
            mcp_manager.stop_all()

            # Clear restart attempts on reload
            health_monitor.restart_attempts.clear()

            # Clear existing MCP tools
            tool_registry.clear_category("mcp")

            # Reinitialize (will restart health monitor if enabled)
            self._initialize_mcp()

            # Recreate chat agent if tools are enabled
            if self.use_tools:
                from ai.agents.chat import ChatAgent
                self.chat_agent = ChatAgent(tool_executor=self.tool_executor)

        except (ImportError, OSError, ValueError) as e:
            logger.error(f"Error reloading MCP tools: {e}")

    def set_tools_enabled(self, enabled: bool):
        """Enable or disable tool usage.

        Args:
            enabled: Whether to enable tools
        """
        self.use_tools = enabled

        if enabled and not self.chat_agent:
            # Create chat agent with tools
            from ai.agents.chat import ChatAgent
            from ai.tools.tool_executor import ToolExecutor
            self.tool_executor = ToolExecutor(confirm_callback=self._confirm_tool_execution)
            self.chat_agent = ChatAgent(tool_executor=self.tool_executor)
        elif not enabled:
            # Disable tools
            self.chat_agent = None

        # Update settings
        settings_manager.set_nested("chat_interface.enable_tools", enabled)

"""
MCP (Model Context Protocol) Integration Module

This module provides integration with MCP servers to extend the chat agent's
capabilities with external tools and services.
"""

from .mcp_manager import MCPManager
from .mcp_tool_wrapper import MCPToolWrapper

__all__ = ['MCPManager', 'MCPToolWrapper']
"""
Agent system for Medical Assistant.

This module provides a Pydantic-based agent framework for structured AI interactions.
"""

from .base import BaseAgent
from .synopsis import SynopsisAgent
from .diagnostic import DiagnosticAgent
from .models import AgentTask, AgentResponse, AgentConfig, AgentType
from .registry import ToolRegistry

__all__ = [
    'BaseAgent',
    'SynopsisAgent',
    'DiagnosticAgent',
    'AgentTask',
    'AgentResponse',
    'AgentConfig',
    'AgentType',
    'ToolRegistry'
]
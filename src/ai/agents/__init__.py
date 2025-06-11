"""
Agent system for Medical Assistant.

This module provides a Pydantic-based agent framework for structured AI interactions.
"""

from .base import BaseAgent
from .synopsis import SynopsisAgent
from .models import AgentTask, AgentResponse, AgentConfig
from .registry import ToolRegistry

__all__ = [
    'BaseAgent',
    'SynopsisAgent',
    'AgentTask',
    'AgentResponse',
    'AgentConfig',
    'ToolRegistry'
]
"""
Built-in tools for the agent system.
"""

import os
import re
import json
import datetime
from typing import Dict, Any, List
import requests

from .base_tool import BaseTool, ToolResult
from .tool_registry import register_tool
from ..agents.models import Tool, ToolParameter


@register_tool
class CalculatorTool(BaseTool):
    """Tool for performing mathematical calculations."""
    
    def get_definition(self) -> Tool:
        return Tool(
            name="calculator",
            description="Perform mathematical calculations. Supports basic arithmetic and common functions.",
            parameters=[
                ToolParameter(
                    name="expression",
                    type="string",
                    description="Mathematical expression to evaluate (e.g., '2 + 2', 'sqrt(16)', '10 * (5 + 3)')",
                    required=True
                )
            ]
        )
        
    def execute(self, expression: str) -> ToolResult:
        """Execute a mathematical calculation."""
        try:
            # Safe evaluation of mathematical expressions
            import ast
            import operator
            import math
            
            # Define allowed operations
            allowed_ops = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Pow: operator.pow,
                ast.USub: operator.neg,
                ast.UAdd: operator.pos,
            }
            
            # Define allowed functions
            allowed_funcs = {
                'sqrt': math.sqrt,
                'abs': abs,
                'round': round,
                'min': min,
                'max': max,
                'sum': sum,
                'sin': math.sin,
                'cos': math.cos,
                'tan': math.tan,
                'log': math.log,
                'exp': math.exp,
            }
            
            def safe_eval(node):
                if isinstance(node, ast.Constant):
                    return node.value
                elif isinstance(node, ast.BinOp):
                    left = safe_eval(node.left)
                    right = safe_eval(node.right)
                    return allowed_ops[type(node.op)](left, right)
                elif isinstance(node, ast.UnaryOp):
                    operand = safe_eval(node.operand)
                    return allowed_ops[type(node.op)](operand)
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in allowed_funcs:
                        args = [safe_eval(arg) for arg in node.args]
                        return allowed_funcs[node.func.id](*args)
                    else:
                        raise ValueError(f"Function '{node.func.id}' is not allowed")
                else:
                    raise ValueError(f"Unsupported operation: {type(node).__name__}")
            
            # Parse and evaluate the expression
            tree = ast.parse(expression, mode='eval')
            result = safe_eval(tree.body)
            
            return ToolResult(
                success=True,
                output=result,
                metadata={"expression": expression, "result": str(result)}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Calculation error: {str(e)}"
            )


@register_tool
class DateTimeTool(BaseTool):
    """Tool for date and time operations."""
    
    def get_definition(self) -> Tool:
        return Tool(
            name="datetime",
            description="Get current date/time or perform date calculations",
            parameters=[
                ToolParameter(
                    name="operation",
                    type="string",
                    description="Operation to perform: 'now', 'today', 'add_days', 'format'",
                    required=True
                ),
                ToolParameter(
                    name="days",
                    type="integer",
                    description="Number of days to add (for 'add_days' operation)",
                    required=False
                ),
                ToolParameter(
                    name="format",
                    type="string",
                    description="Date format string (for 'format' operation)",
                    required=False,
                    default="%Y-%m-%d %H:%M:%S"
                )
            ]
        )
        
    def execute(self, operation: str, days: int = 0, format: str = "%Y-%m-%d %H:%M:%S") -> ToolResult:
        """Execute date/time operations."""
        try:
            now = datetime.datetime.now()
            
            if operation == "now":
                result = now.strftime(format)
            elif operation == "today":
                result = now.date().strftime("%Y-%m-%d")
            elif operation == "add_days":
                future_date = now + datetime.timedelta(days=days)
                result = future_date.strftime(format)
            elif operation == "format":
                result = now.strftime(format)
            else:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Unknown operation: {operation}"
                )
                
            return ToolResult(
                success=True,
                output=result,
                metadata={"operation": operation, "result": result}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Date/time error: {str(e)}"
            )


@register_tool
class FileReadTool(BaseTool):
    """Tool for reading file contents."""
    
    def get_definition(self) -> Tool:
        return Tool(
            name="read_file",
            description="Read the contents of a file",
            parameters=[
                ToolParameter(
                    name="file_path",
                    type="string",
                    description="Path to the file to read",
                    required=True
                ),
                ToolParameter(
                    name="encoding",
                    type="string",
                    description="File encoding",
                    required=False,
                    default="utf-8"
                )
            ]
        )
        
    def execute(self, file_path: str, encoding: str = "utf-8") -> ToolResult:
        """Read a file's contents."""
        try:
            # Security check - ensure path is within allowed directories
            # For now, we'll just check if it exists
            if not os.path.exists(file_path):
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"File not found: {file_path}"
                )
                
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
                
            return ToolResult(
                success=True,
                output=content,
                metadata={"file_path": file_path, "size": len(content)}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"File read error: {str(e)}"
            )


@register_tool
class FileWriteTool(BaseTool):
    """Tool for writing content to files."""
    
    def get_definition(self) -> Tool:
        return Tool(
            name="write_file",
            description="Write content to a file",
            parameters=[
                ToolParameter(
                    name="file_path",
                    type="string",
                    description="Path to the file to write",
                    required=True
                ),
                ToolParameter(
                    name="content",
                    type="string",
                    description="Content to write to the file",
                    required=True
                ),
                ToolParameter(
                    name="mode",
                    type="string",
                    description="Write mode: 'write' (overwrite) or 'append'",
                    required=False,
                    default="write"
                ),
                ToolParameter(
                    name="encoding",
                    type="string",
                    description="File encoding",
                    required=False,
                    default="utf-8"
                )
            ]
        )
        
    def execute(self, file_path: str, content: str, mode: str = "write", encoding: str = "utf-8") -> ToolResult:
        """Write content to a file."""
        try:
            # This operation requires confirmation
            if mode == "write" and os.path.exists(file_path):
                return ToolResult(
                    success=True,
                    output=None,
                    requires_confirmation=True,
                    confirmation_message=f"File '{file_path}' already exists. Overwrite it?"
                )
                
            file_mode = 'w' if mode == "write" else 'a'
            
            with open(file_path, file_mode, encoding=encoding) as f:
                f.write(content)
                
            return ToolResult(
                success=True,
                output=f"Successfully wrote {len(content)} characters to {file_path}",
                metadata={"file_path": file_path, "mode": mode, "size": len(content)}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"File write error: {str(e)}"
            )


@register_tool
class WebSearchTool(BaseTool):
    """Tool for searching the web."""
    
    def get_definition(self) -> Tool:
        return Tool(
            name="web_search",
            description="Search the web for information",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Search query",
                    required=True
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum number of results to return",
                    required=False,
                    default=5
                )
            ]
        )
        
    def execute(self, query: str, max_results: int = 5) -> ToolResult:
        """Perform a web search."""
        try:
            # This is a placeholder implementation
            # In a real implementation, you would use a search API
            # For now, we'll return a mock result
            
            results = [
                {
                    "title": f"Result {i+1} for: {query}",
                    "url": f"https://example.com/result{i+1}",
                    "snippet": f"This is a snippet for result {i+1} about {query}..."
                }
                for i in range(min(max_results, 3))
            ]
            
            return ToolResult(
                success=True,
                output=results,
                metadata={"query": query, "result_count": len(results)}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Search error: {str(e)}"
            )


@register_tool
class JSONTool(BaseTool):
    """Tool for JSON operations."""
    
    def get_definition(self) -> Tool:
        return Tool(
            name="json",
            description="Parse, format, or manipulate JSON data",
            parameters=[
                ToolParameter(
                    name="operation",
                    type="string",
                    description="Operation: 'parse', 'format', 'get_value'",
                    required=True
                ),
                ToolParameter(
                    name="data",
                    type="string",
                    description="JSON string or data",
                    required=True
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="JSON path for 'get_value' operation (e.g., 'user.name')",
                    required=False
                ),
                ToolParameter(
                    name="indent",
                    type="integer",
                    description="Indentation for 'format' operation",
                    required=False,
                    default=2
                )
            ]
        )
        
    def execute(self, operation: str, data: str, path: str = None, indent: int = 2) -> ToolResult:
        """Execute JSON operations."""
        try:
            if operation == "parse":
                result = json.loads(data)
                return ToolResult(
                    success=True,
                    output=result,
                    metadata={"operation": "parse", "type": type(result).__name__}
                )
                
            elif operation == "format":
                obj = json.loads(data) if isinstance(data, str) else data
                result = json.dumps(obj, indent=indent)
                return ToolResult(
                    success=True,
                    output=result,
                    metadata={"operation": "format", "indent": indent}
                )
                
            elif operation == "get_value":
                obj = json.loads(data) if isinstance(data, str) else data
                
                if path:
                    # Navigate the path
                    parts = path.split('.')
                    current = obj
                    for part in parts:
                        if isinstance(current, dict) and part in current:
                            current = current[part]
                        elif isinstance(current, list) and part.isdigit():
                            current = current[int(part)]
                        else:
                            return ToolResult(
                                success=False,
                                output=None,
                                error=f"Path '{path}' not found in JSON"
                            )
                    result = current
                else:
                    result = obj
                    
                return ToolResult(
                    success=True,
                    output=result,
                    metadata={"operation": "get_value", "path": path}
                )
                
            else:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Unknown operation: {operation}"
                )
                
        except json.JSONDecodeError as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"JSON decode error: {str(e)}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"JSON operation error: {str(e)}"
            )
"""
MCP Tool Wrapper - Bridges MCP tools with the existing tool system
"""

import logging
import time
import threading
import hashlib
import json
from typing import Dict, Any, Optional, Tuple
from ai.tools.base_tool import BaseTool, ToolResult
from ai.agents.models import Tool, ToolParameter

logger = logging.getLogger(__name__)

# Rate limiting for specific MCP servers
RATE_LIMITS = {
    "brave-search": {
        "requests_per_second": 0.5,  # More conservative: 1 request every 2 seconds
        "last_request_time": {},
        "minimum_interval": 2.0,  # Minimum 2 seconds between requests
        "global_last_request": 0  # Track last request across all Brave tools
    }
}

# Lock for thread-safe rate limiting
rate_limit_lock = threading.Lock()


class ResultCache:
    """LRU cache for MCP tool results with TTL support."""

    def __init__(self, max_size: int = 100, default_ttl: float = 300.0):
        """Initialize the result cache.

        Args:
            max_size: Maximum number of cached results
            default_ttl: Default time-to-live in seconds (5 minutes)
        """
        self._cache: Dict[str, Tuple[float, ToolResult]] = {}
        self._access_order: list = []
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[ToolResult]:
        """Get a cached result if valid.

        Args:
            key: Cache key

        Returns:
            Cached ToolResult or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            timestamp, result = self._cache[key]

            # Check if expired
            if time.time() - timestamp > self._default_ttl:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                self._misses += 1
                return None

            # Update access order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

            self._hits += 1
            logger.debug(f"Cache hit for key: {key[:32]}...")
            return result

    def set(self, key: str, result: ToolResult) -> None:
        """Store a result in the cache.

        Args:
            key: Cache key
            result: Result to cache
        """
        with self._lock:
            # Evict oldest if at capacity
            while len(self._cache) >= self._max_size and self._access_order:
                oldest_key = self._access_order.pop(0)
                if oldest_key in self._cache:
                    del self._cache[oldest_key]

            self._cache[key] = (time.time(), result)
            self._access_order.append(key)

    def clear(self) -> None:
        """Clear all cached results."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
            logger.info("MCP result cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with hits, misses, hit rate, and size
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{hit_rate:.1f}%",
                "size": len(self._cache),
                "max_size": self._max_size
            }


# Global result cache for MCP tools
result_cache = ResultCache(max_size=100, default_ttl=300.0)


class MCPToolWrapper(BaseTool):
    """Wraps an MCP tool to work with the existing tool system"""
    
    def __init__(self, mcp_manager, server_name: str, tool_info: Dict[str, Any]):
        """Initialize MCP tool wrapper
        
        Args:
            mcp_manager: The MCP manager instance
            server_name: Name of the MCP server
            tool_info: Tool information from MCP server
        """
        super().__init__()
        
        self.mcp_manager = mcp_manager
        self.server_name = server_name
        self.original_name = tool_info.get("name", "")
        self.input_schema = tool_info.get("inputSchema", {})
        
        # Create a unique name for the tool
        self.name = f"mcp_{server_name}_{self.original_name}"
        self.description = tool_info.get("description", f"MCP tool from {server_name}")
        self.category = "mcp"
    
    def validate_args(self, **kwargs) -> Optional[str]:
        """Validate arguments against the tool's input schema
        
        Returns:
            Error message if validation fails, None if valid
        """
        # Basic validation against schema if provided
        if self.input_schema and "properties" in self.input_schema:
            required = self.input_schema.get("required", [])
            properties = self.input_schema.get("properties", {})
            
            # Check required fields
            for field in required:
                if field not in kwargs:
                    return f"Missing required field: {field}"
            
            # Check types if specified
            for field, value in kwargs.items():
                if field in properties:
                    prop = properties[field]
                    expected_type = prop.get("type")
                    
                    if expected_type:
                        if expected_type == "string" and not isinstance(value, str):
                            return f"Field {field} must be a string"
                        elif expected_type == "number" and not isinstance(value, (int, float)):
                            return f"Field {field} must be a number"
                        elif expected_type == "boolean" and not isinstance(value, bool):
                            return f"Field {field} must be a boolean"
                        elif expected_type == "array" and not isinstance(value, list):
                            return f"Field {field} must be an array"
                        elif expected_type == "object" and not isinstance(value, dict):
                            return f"Field {field} must be an object"
        
        return None
    
    def _get_cache_key(self, **kwargs) -> str:
        """Generate a cache key from tool name and arguments.

        Args:
            **kwargs: Tool arguments

        Returns:
            MD5 hash string as cache key
        """
        try:
            args_str = json.dumps(kwargs, sort_keys=True, default=str)
        except (TypeError, ValueError):
            args_str = str(kwargs)
        key_content = f"{self.name}:{args_str}"
        return hashlib.md5(key_content.encode()).hexdigest()

    def execute(self, **kwargs) -> ToolResult:
        """Execute the MCP tool

        Args:
            **kwargs: Tool arguments

        Returns:
            ToolResult with success status and output
        """
        try:
            # Validate arguments
            error = self.validate_args(**kwargs)
            if error:
                return ToolResult(
                    success=False,
                    output="",  # Required field
                    error=f"Argument validation failed: {error}"
                )

            # Check cache first
            cache_key = self._get_cache_key(**kwargs)
            cached_result = result_cache.get(cache_key)
            if cached_result is not None:
                # Add cache hit indicator to metadata
                cached_result = ToolResult(
                    success=cached_result.success,
                    output=cached_result.output,
                    error=cached_result.error,
                    metadata={**cached_result.metadata, "cached": True}
                )
                return cached_result

            # Check rate limits for this server
            if self.server_name in RATE_LIMITS:
                with rate_limit_lock:
                    rate_config = RATE_LIMITS[self.server_name]
                    min_interval = rate_config.get("minimum_interval", 1.0 / rate_config["requests_per_second"])
                    
                    current_time = time.time()
                    
                    # Check global rate limit for this server
                    global_last = rate_config.get("global_last_request", 0)
                    global_time_since_last = current_time - global_last
                    
                    if global_time_since_last < min_interval:
                        wait_time = min_interval - global_time_since_last
                        logger.info(f"Global rate limiting for {self.server_name}: waiting {wait_time:.2f}s")
                        time.sleep(wait_time)
                        current_time = time.time()
                    
                    # Also check per-tool rate limit
                    tool_key = f"{self.server_name}:{self.original_name}"
                    last_time = rate_config["last_request_time"].get(tool_key, 0)
                    time_since_last = current_time - last_time
                    
                    # If not enough time has passed for this specific tool, wait
                    if time_since_last < min_interval:
                        wait_time = min_interval - time_since_last
                        logger.info(f"Tool rate limiting: waiting {wait_time:.2f}s before calling {self.original_name}")
                        time.sleep(wait_time)
                    
                    # Update last request times
                    rate_config["global_last_request"] = time.time()
                    rate_config["last_request_time"][tool_key] = time.time()
            
            # Execute the tool via MCP with retry logic
            logger.info(f"Executing MCP tool {self.original_name} on server {self.server_name}")
            
            max_retries = 3
            retry_count = 0
            base_wait_time = 2.0
            
            while retry_count < max_retries:
                try:
                    result = self.mcp_manager.execute_tool(
                        self.server_name,
                        self.original_name,
                        kwargs
                    )
                    break  # Success, exit the retry loop
                except Exception as e:
                    error_str = str(e).lower()
                    if 'rate limit' in error_str or '429' in error_str:
                        retry_count += 1
                        if retry_count < max_retries:
                            # Exponential backoff
                            wait_time = base_wait_time * (2 ** (retry_count - 1))
                            logger.warning(f"Rate limit hit, retrying in {wait_time}s (attempt {retry_count}/{max_retries})")
                            time.sleep(wait_time)
                            continue
                    # Re-raise if not a rate limit error or max retries reached
                    raise
            
            # Handle different result formats
            if isinstance(result, dict):
                # Check if this is an error response
                if result.get("isError", False):
                    error_text = "Unknown error"
                    if "content" in result and isinstance(result["content"], list):
                        # Extract error text
                        text_parts = []
                        for item in result["content"]:
                            if item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                        error_text = "\n".join(text_parts) if text_parts else str(result)
                    
                    # Check if it's a rate limit error
                    if "429" in error_text or "rate" in error_text.lower():
                        logger.warning(f"Rate limit error from MCP: {error_text}")
                    
                    return ToolResult(
                        success=False,
                        output="",
                        error=error_text
                    )
                
                # Not an error, process normally
                if "content" in result and isinstance(result["content"], list):
                    # Extract text content
                    text_parts = []
                    for item in result["content"]:
                        if item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
                    
                    output = "\n".join(text_parts) if text_parts else str(result)
                else:
                    output = str(result)
            else:
                output = str(result)
            
            tool_result = ToolResult(
                success=True,
                output=output,
                metadata={
                    "server": self.server_name,
                    "tool": self.original_name,
                    "cached": False
                }
            )

            # Cache successful results
            result_cache.set(cache_key, tool_result)

            return tool_result

        except Exception as e:
            logger.error(f"Error executing MCP tool {self.name}: {e}")
            return ToolResult(
                success=False,
                output="",  # Required field
                error=str(e)
            )
    
    def get_usage_example(self) -> str:
        """Get a usage example for this tool"""
        # Build example from schema
        if self.input_schema and "properties" in self.input_schema:
            properties = self.input_schema.get("properties", {})
            example_args = {}
            
            for field, prop in properties.items():
                field_type = prop.get("type", "string")
                description = prop.get("description", "")
                
                # Create example values
                if field_type == "string":
                    if "query" in field.lower() or "search" in field.lower():
                        example_args[field] = "example search query"
                    else:
                        example_args[field] = f"example {field}"
                elif field_type == "number":
                    example_args[field] = 10
                elif field_type == "boolean":
                    example_args[field] = True
                elif field_type == "array":
                    example_args[field] = ["item1", "item2"]
                elif field_type == "object":
                    example_args[field] = {"key": "value"}
            
            return f"Use {self.name} with arguments: {example_args}"
        
        return f"Use {self.name} to {self.description}"
    
    def get_definition(self) -> Tool:
        """Get the tool definition for the agent system"""
        # Convert input schema to parameters
        parameters = []
        if self.input_schema and "properties" in self.input_schema:
            properties = self.input_schema.get("properties", {})
            required = self.input_schema.get("required", [])
            
            for field, prop in properties.items():
                param = ToolParameter(
                    name=field,
                    type=prop.get("type", "string"),
                    description=prop.get("description", f"Parameter {field}"),
                    required=field in required
                )
                parameters.append(param)
        
        return Tool(
            name=self.name,
            description=self.description,
            parameters=parameters
        )


def register_mcp_tools(tool_registry, mcp_manager):
    """Register all MCP tools with the tool registry
    
    Args:
        tool_registry: The tool registry to register tools with
        mcp_manager: The MCP manager instance
    """
    try:
        # Get all available tools from MCP servers
        all_tools = mcp_manager.get_all_tools()
        
        # Clear existing MCP tools first
        tool_registry.clear_category("mcp")
        
        # Register each tool
        registered_count = 0
        for server_name, tool_info in all_tools:
            try:
                wrapper = MCPToolWrapper(mcp_manager, server_name, tool_info)
                tool_registry.register_tool(wrapper)
                registered_count += 1
                logger.info(f"Registered MCP tool: {wrapper.name}")
            except Exception as e:
                logger.error(f"Failed to register MCP tool {tool_info.get('name')}: {e}")
        
        logger.info(f"Registered {registered_count} MCP tools")
        return registered_count
        
    except Exception as e:
        logger.error(f"Error registering MCP tools: {e}")
        return 0
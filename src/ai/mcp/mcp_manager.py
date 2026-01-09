"""
MCP Manager - Handles MCP server lifecycle and tool discovery
"""

import asyncio
import logging
import json
import subprocess
import os
import sys
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import threading
import queue
import time

logger = logging.getLogger(__name__)


@dataclass
class MCPServer:
    """Represents an MCP server configuration and state"""
    name: str
    command: str
    args: List[str]
    env: Dict[str, str]
    enabled: bool
    process: Optional[subprocess.Popen] = None
    protocol: Optional['MCPProtocol'] = None
    tools: List[Dict[str, Any]] = None
    error_log: List[str] = None  # Stores recent stderr output

    def __post_init__(self):
        """Initialize mutable defaults."""
        if self.error_log is None:
            self.error_log = []

    def add_error(self, message: str, max_entries: int = 100) -> None:
        """Add an error message to the log.

        Args:
            message: Error message to add
            max_entries: Maximum log entries to keep
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.error_log.append(f"[{timestamp}] {message}")
        # Keep only last N entries
        if len(self.error_log) > max_entries:
            self.error_log = self.error_log[-max_entries:]

    def get_error_log(self) -> str:
        """Get the full error log as a string.

        Returns:
            Newline-separated error log entries
        """
        return "\n".join(self.error_log) if self.error_log else "No errors logged"

    def clear_error_log(self) -> None:
        """Clear the error log."""
        self.error_log.clear()

    def to_dict(self):
        """Convert to dictionary for settings storage"""
        return {
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "enabled": self.enabled
        }


class MCPProtocol:
    """Handles JSON-RPC 2.0 communication with MCP servers"""

    def __init__(self, process: subprocess.Popen, server: MCPServer = None):
        self.process = process
        self.server = server  # Reference to store errors
        self.request_id = 0
        self.response_queue = queue.Queue()
        self.reader_thread = threading.Thread(target=self._read_responses, daemon=True)
        self.reader_thread.start()
        # Start stderr reader to capture errors
        self.stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self.stderr_thread.start()
    
    def _read_responses(self):
        """Read responses from the MCP server stdout"""
        try:
            while True:
                line = self.process.stdout.readline()
                if not line:
                    # Check if process has terminated
                    if self.process.poll() is not None:
                        logger.warning(f"MCP server process terminated with code: {self.process.returncode}")
                        break
                    continue
                    
                try:
                    response = json.loads(line)
                    logger.debug(f"MCP response: {response}")
                    self.response_queue.put(response)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from MCP server: {line}")
        except Exception as e:
            logger.error(f"Error reading MCP responses: {e}")
    
    def _read_stderr(self):
        """Read stderr output from the MCP server"""
        try:
            while True:
                line = self.process.stderr.readline()
                if not line:
                    # Check if process has terminated
                    if self.process.poll() is not None:
                        logger.warning(f"MCP server stderr reader: process terminated")
                        break
                    continue

                stderr_msg = line.strip()
                logger.info(f"MCP server stderr: {stderr_msg}")

                # Store in server's error log if available
                if self.server is not None:
                    self.server.add_error(stderr_msg)
        except Exception as e:
            logger.error(f"Error reading MCP stderr: {e}")
    
    def send_request(self, method: str, params: Dict[str, Any] = None, timeout: float = 30.0) -> Any:
        """Send a JSON-RPC request and wait for response"""
        # Check if process is still running
        if self.process.poll() is not None:
            raise Exception(f"MCP server process has terminated with code: {self.process.returncode}")
            
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self.request_id
        }
        if params:
            request["params"] = params
        
        # Send request
        request_str = json.dumps(request) + "\n"
        logger.debug(f"Sending MCP request: {request_str.strip()}")
        try:
            self.process.stdin.write(request_str)
            self.process.stdin.flush()
        except Exception as e:
            raise Exception(f"Failed to send request to MCP server: {e}")
        
        # Wait for response
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Check if process terminated while waiting
            if self.process.poll() is not None:
                raise Exception(f"MCP server process terminated while waiting for response (code: {self.process.returncode})")
                
            try:
                response = self.response_queue.get(timeout=0.1)
                if response.get("id") == self.request_id:
                    if "error" in response:
                        error = response['error']
                        # Extract error details
                        if isinstance(error, dict):
                            code = error.get('code', 'Unknown')
                            message = error.get('message', 'Unknown error')
                            data = error.get('data', {})
                            
                            # Check for rate limit error
                            if code == 429 or 'rate' in str(message).lower():
                                retry_after = data.get('retry_after', 60)
                                raise Exception(f"Rate limit exceeded: {message}. Retry after {retry_after} seconds")
                            else:
                                raise Exception(f"MCP error (code {code}): {message}")
                        else:
                            raise Exception(f"MCP error: {error}")
                    return response.get("result")
            except queue.Empty:
                continue
        
        raise Exception(f"Timeout waiting for MCP response to {method}")


class MCPManager:
    """Manages MCP server lifecycle and tool discovery"""
    
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self._lock = threading.Lock()
    
    def load_config(self, mcp_config: Dict[str, Any]) -> None:
        """Load MCP configuration from settings"""
        if not mcp_config.get("enabled", False):
            logger.info("MCP is disabled in settings")
            return
        
        servers = mcp_config.get("servers", {})
        for name, config in servers.items():
            server = MCPServer(
                name=name,
                command=config.get("command", ""),
                args=config.get("args", []),
                env=config.get("env", {}),
                enabled=config.get("enabled", True)
            )
            self.servers[name] = server
            
            if server.enabled:
                try:
                    self.start_server(name)
                except Exception as e:
                    logger.error(f"Failed to start MCP server {name}: {e}")
    
    def start_server(self, name: str) -> None:
        """Start an MCP server"""
        with self._lock:
            server = self.servers.get(name)
            if not server:
                raise Exception(f"Unknown MCP server: {name}")
            
            if server.process and server.process.poll() is None:
                logger.warning(f"MCP server {name} is already running")
                return
            
            # Prepare environment
            env = os.environ.copy()
            env.update(server.env)
            
            # Start the process
            try:
                # Handle npx specially on Windows
                if sys.platform == "win32" and server.command == "npx":
                    # Use npx.cmd on Windows
                    command = "npx.cmd"
                else:
                    command = server.command
                
                server.process = subprocess.Popen(
                    [command] + server.args,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    text=True,  # Use text mode for JSON-RPC
                    bufsize=1  # Line buffered
                )
                
                logger.info(f"Started MCP server {name} (PID: {server.process.pid})")

                # Initialize communication (pass server reference for error logging)
                server.protocol = MCPProtocol(server.process, server)
                
                # Initialize the connection
                server.protocol.send_request("initialize", {
                    "protocolVersion": "1.0",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "Medical Assistant",
                        "version": "1.0.0"
                    }
                })
                
                # Discover tools
                server.tools = self._discover_tools(server.protocol)
                logger.info(f"Discovered {len(server.tools)} tools from {name}")
                
            except Exception as e:
                logger.error(f"Failed to start MCP server {name}: {e}")
                if server.process:
                    server.process.terminate()
                    server.process = None
                raise
    
    def stop_server(self, name: str) -> None:
        """Stop an MCP server"""
        with self._lock:
            server = self.servers.get(name)
            if not server or not server.process:
                return
            
            try:
                # Try graceful shutdown first
                server.process.terminate()
                server.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if needed
                server.process.kill()
            
            server.process = None
            server.protocol = None
            server.tools = None
            logger.info(f"Stopped MCP server {name}")
    
    def restart_server(self, name: str) -> None:
        """Restart an MCP server"""
        self.stop_server(name)
        time.sleep(0.5)  # Brief delay
        self.start_server(name)
    
    def stop_all(self) -> None:
        """Stop all MCP servers"""
        for name in list(self.servers.keys()):
            self.stop_server(name)
    
    def _discover_tools(self, protocol: MCPProtocol) -> List[Dict[str, Any]]:
        """Discover available tools from an MCP server"""
        try:
            result = protocol.send_request("tools/list")
            tools = result.get("tools", [])
            
            # Convert to our internal format
            converted_tools = []
            for tool in tools:
                converted_tools.append({
                    "name": tool.get("name"),
                    "description": tool.get("description", ""),
                    "inputSchema": tool.get("inputSchema", {})
                })
            
            return converted_tools
        except Exception as e:
            logger.error(f"Failed to discover tools: {e}")
            return []
    
    def execute_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool on an MCP server"""
        with self._lock:
            server = self.servers.get(server_name)
            if not server or not server.process:
                raise Exception(f"MCP server {server_name} is not running")
            
            if not server.protocol:
                raise Exception(f"MCP server {server_name} has no active protocol")
            
            try:
                # Log the request for debugging
                request_params = {
                    "name": tool_name,
                    "arguments": arguments
                }
                logger.debug(f"Sending tool call request: {request_params}")
                
                result = server.protocol.send_request("tools/call", request_params)
                return result
            except Exception as e:
                logger.error(f"Failed to execute tool {tool_name} on {server_name}: {e}")
                raise
    
    def get_all_tools(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Get all available tools from all running servers"""
        all_tools = []
        with self._lock:
            for server_name, server in self.servers.items():
                if server.process and server.tools:
                    for tool in server.tools:
                        all_tools.append((server_name, tool))
        return all_tools
    
    def add_server(self, name: str, config: Dict[str, Any]) -> None:
        """Add a new MCP server configuration"""
        server = MCPServer(
            name=name,
            command=config.get("command", ""),
            args=config.get("args", []),
            env=config.get("env", {}),
            enabled=config.get("enabled", True)
        )
        self.servers[name] = server
        
        if server.enabled:
            self.start_server(name)
    
    def remove_server(self, name: str) -> None:
        """Remove an MCP server"""
        self.stop_server(name)
        with self._lock:
            if name in self.servers:
                del self.servers[name]
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration for saving"""
        config = {
            "enabled": True,
            "servers": {}
        }
        
        with self._lock:
            for name, server in self.servers.items():
                config["servers"][name] = server.to_dict()
        
        return config
    
    def test_server(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Test an MCP server configuration"""
        test_name = f"_test_{time.time()}"
        try:
            self.add_server(test_name, config)
            time.sleep(2)  # Give it more time to start
            
            server = self.servers.get(test_name)
            if server and server.process and server.process.poll() is None:
                tool_count = len(server.tools) if server.tools else 0
                return True, f"Connected successfully. Found {tool_count} tools."
            else:
                return False, "Server failed to start"
                
        except Exception as e:
            return False, str(e)
        finally:
            self.remove_server(test_name)


class HealthMonitor:
    """Monitors MCP server health and restarts crashed servers."""

    def __init__(self, mcp_manager: MCPManager, check_interval: float = 30.0, max_restarts: int = 3):
        """Initialize the health monitor.

        Args:
            mcp_manager: The MCP manager to monitor
            check_interval: Seconds between health checks
            max_restarts: Maximum restart attempts per server
        """
        self.mcp_manager = mcp_manager
        self.check_interval = check_interval
        self.max_restarts = max_restarts
        self.restart_attempts: Dict[str, int] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the health monitoring thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="MCP-HealthMonitor")
        self._thread.start()
        logger.info("MCP Health Monitor started")

    def stop(self) -> None:
        """Stop the health monitoring thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("MCP Health Monitor stopped")

    def reset_attempts(self, server_name: str) -> None:
        """Reset restart attempts for a server (call after manual restart).

        Args:
            server_name: Name of the server to reset
        """
        self.restart_attempts[server_name] = 0

    def _monitor_loop(self) -> None:
        """Main monitoring loop running in background thread."""
        while self._running:
            try:
                self._check_servers()
            except Exception as e:
                logger.error(f"Error in health monitor: {e}")

            # Sleep in small intervals to allow quick shutdown
            for _ in range(int(self.check_interval)):
                if not self._running:
                    break
                time.sleep(1)

    def _check_servers(self) -> None:
        """Check all servers and restart any that have crashed."""
        with self.mcp_manager._lock:
            for name, server in list(self.mcp_manager.servers.items()):
                if not server.enabled:
                    continue

                if server.process is None:
                    # Server was never started, skip
                    continue

                if server.process.poll() is not None:
                    # Process has terminated
                    exit_code = server.process.returncode
                    logger.warning(f"MCP server '{name}' crashed with exit code {exit_code}")
                    self._handle_crash(name, server)

    def _handle_crash(self, name: str, server: MCPServer) -> None:
        """Handle a crashed server with restart logic.

        Args:
            name: Server name
            server: Server instance
        """
        attempts = self.restart_attempts.get(name, 0)

        if attempts >= self.max_restarts:
            logger.error(f"MCP server '{name}' exceeded max restarts ({self.max_restarts}). Giving up.")
            return

        # Exponential backoff: 1s, 2s, 4s, 8s...
        backoff = 2 ** attempts
        logger.info(f"Attempting to restart MCP server '{name}' in {backoff}s (attempt {attempts + 1}/{self.max_restarts})")

        # Clean up old process
        server.process = None
        server.protocol = None
        server.tools = None

        # Wait with backoff
        time.sleep(backoff)

        if not self._running:
            return

        try:
            # Release lock temporarily for restart
            self.mcp_manager._lock.release()
            try:
                self.mcp_manager.start_server(name)
                self.restart_attempts[name] = 0  # Reset on success
                logger.info(f"Successfully restarted MCP server '{name}'")
            finally:
                self.mcp_manager._lock.acquire()
        except Exception as e:
            self.restart_attempts[name] = attempts + 1
            logger.error(f"Failed to restart MCP server '{name}': {e}")


# Global instances
mcp_manager = MCPManager()
health_monitor = HealthMonitor(mcp_manager)
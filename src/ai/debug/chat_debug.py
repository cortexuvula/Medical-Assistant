"""
Chat Debug Module - Comprehensive debugging for chat agent responses

Debug files are only created when explicitly enabled via CHAT_DEBUG_ENABLED setting.
Files are stored in the proper AppData/debug directory and cleaned up periodically.
"""

import logging
import json
import time
from datetime import datetime
from typing import Any, Dict, Optional, List
from pathlib import Path
import traceback
import os

# Create a dedicated debug logger
debug_logger = logging.getLogger("chat_debug")
debug_logger.setLevel(logging.DEBUG)

# Configuration
MAX_DEBUG_FILES = 20  # Keep only this many debug files to prevent disk bloat
DEBUG_ENABLED = os.environ.get("CHAT_DEBUG_ENABLED", "").lower() == "true"

# Debug directory setup - use data_folder_manager for proper path
DEBUG_DIR: Optional[Path] = None
_file_handler_added = False


def _get_debug_dir() -> Path:
    """Get the debug directory, creating it if needed."""
    global DEBUG_DIR
    if DEBUG_DIR is None:
        try:
            from managers.data_folder_manager import data_folder_manager
            DEBUG_DIR = data_folder_manager.logs_folder / "debug"
        except ImportError:
            # Fallback for testing or early initialization
            DEBUG_DIR = Path("AppData/debug")
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    return DEBUG_DIR


def _setup_file_handler():
    """Set up file handler for debug logging (only when debug is enabled)."""
    global _file_handler_added
    if _file_handler_added or not DEBUG_ENABLED:
        return

    debug_dir = _get_debug_dir()
    debug_file = debug_dir / f"chat_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(debug_file)
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    debug_logger.addHandler(file_handler)
    _file_handler_added = True

    # Clean up old debug files
    _cleanup_old_debug_files(debug_dir)


def _cleanup_old_debug_files(debug_dir: Path):
    """Remove old debug files to prevent disk bloat."""
    try:
        # Get all debug files sorted by modification time
        debug_files = sorted(
            [f for f in debug_dir.glob("*.log") if f.is_file()],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )

        # Remove files beyond the limit
        for old_file in debug_files[MAX_DEBUG_FILES:]:
            try:
                old_file.unlink()
                debug_logger.debug(f"Cleaned up old debug file: {old_file.name}")
            except OSError:
                pass

        # Also clean up execution JSON files
        json_files = sorted(
            [f for f in debug_dir.glob("execution_*.json") if f.is_file()],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        for old_file in json_files[MAX_DEBUG_FILES:]:
            try:
                old_file.unlink()
            except OSError:
                pass
    except Exception as e:
        debug_logger.warning(f"Failed to cleanup old debug files: {e}")


class ChatDebugger:
    """Debugger for chat agent execution"""

    def __init__(self):
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.execution_steps = []
        self.current_execution = None
        self._debug_enabled = DEBUG_ENABLED

    def start_execution(self, task_description: str):
        """Start tracking a new execution"""
        if not self._debug_enabled:
            return

        # Setup file handler on first actual use
        _setup_file_handler()

        self.current_execution = {
            'id': f"{self.session_id}_{int(time.time() * 1000)}",
            'task': task_description,
            'start_time': time.time(),
            'steps': []
        }
        debug_logger.info(f"=== START EXECUTION: {self.current_execution['id']} ===")
        debug_logger.info(f"Task: {task_description}")
        
    def log_step(self, step_name: str, data: Any, error: Optional[Exception] = None):
        """Log a step in the execution"""
        if not self.current_execution:
            return
            
        step_info = {
            'name': step_name,
            'timestamp': time.time(),
            'data': self._serialize_data(data),
            'error': str(error) if error else None,
            'traceback': traceback.format_exc() if error else None
        }
        
        self.current_execution['steps'].append(step_info)
        
        # Log to file
        debug_logger.info(f"--- Step: {step_name} ---")
        if isinstance(data, str) and len(data) > 1000:
            debug_logger.info(f"Data (truncated): {data[:500]}...{data[-500:]}")
            debug_logger.info(f"Data length: {len(data)} characters")
        else:
            debug_logger.info(f"Data: {json.dumps(step_info['data'], indent=2)}")
        
        if error:
            debug_logger.error(f"Error: {error}")
            debug_logger.error(f"Traceback: {step_info['traceback']}")
            
    def log_prompt(self, prompt_type: str, prompt: str, model: str = None, temperature: float = None):
        """Log an AI prompt"""
        step_data = {
            'prompt_type': prompt_type,
            'prompt': prompt,
            'prompt_length': len(prompt),
            'model': model,
            'temperature': temperature
        }
        self.log_step(f"prompt_{prompt_type}", step_data)
        
    def log_response(self, response_type: str, response: str, metadata: Dict[str, Any] = None):
        """Log an AI response"""
        step_data = {
            'response_type': response_type,
            'response': response,
            'response_length': len(response) if response else 0,
            'metadata': metadata or {}
        }
        self.log_step(f"response_{response_type}", step_data)
        
    def log_tool_call(self, tool_name: str, arguments: Dict[str, Any], result: Any):
        """Log a tool call"""
        step_data = {
            'tool': tool_name,
            'arguments': arguments,
            'result': self._serialize_data(result),
            'success': result.success if hasattr(result, 'success') else True
        }
        self.log_step(f"tool_call_{tool_name}", step_data)
        
    def log_config(self, config_name: str, config_data: Dict[str, Any]):
        """Log configuration data"""
        self.log_step(f"config_{config_name}", config_data)
        
    def end_execution(self, success: bool = True, final_response: str = None):
        """End tracking the current execution"""
        if not self.current_execution or not self._debug_enabled:
            return

        self.current_execution['end_time'] = time.time()
        self.current_execution['duration'] = self.current_execution['end_time'] - self.current_execution['start_time']
        self.current_execution['success'] = success
        self.current_execution['final_response'] = final_response

        # Save to debug file using proper path
        debug_dir = _get_debug_dir()
        debug_file_path = debug_dir / f"execution_{self.current_execution['id']}.json"
        with open(debug_file_path, 'w') as f:
            json.dump(self.current_execution, f, indent=2)
            
        debug_logger.info(f"=== END EXECUTION: {self.current_execution['id']} ===")
        debug_logger.info(f"Duration: {self.current_execution['duration']:.2f}s")
        debug_logger.info(f"Success: {success}")
        debug_logger.info(f"Final response length: {len(final_response) if final_response else 0}")
        debug_logger.info(f"Debug file: {debug_file_path}")
        
        self.execution_steps.append(self.current_execution)
        self.current_execution = None
        
    def _serialize_data(self, data: Any) -> Any:
        """Serialize data for JSON storage"""
        if isinstance(data, (str, int, float, bool, type(None))):
            return data
        elif isinstance(data, (list, tuple)):
            return [self._serialize_data(item) for item in data]
        elif isinstance(data, dict):
            return {k: self._serialize_data(v) for k, v in data.items()}
        elif hasattr(data, '__dict__'):
            return self._serialize_data(data.__dict__)
        else:
            return str(data)
            
    def get_debug_summary(self) -> Dict[str, Any]:
        """Get a summary of the current debug session"""
        if self.current_execution:
            return {
                'status': 'in_progress',
                'current_execution': self.current_execution,
                'completed_executions': len(self.execution_steps)
            }
        else:
            return {
                'status': 'idle',
                'completed_executions': len(self.execution_steps),
                'last_execution': self.execution_steps[-1] if self.execution_steps else None
            }


# Global debugger instance
chat_debugger = ChatDebugger()
"""
Command Registry

Centralizes all application commands in one place, reducing coupling
between app.py, sidebar, and menu systems.

Commands are registered with:
- A unique ID
- A method name on the app instance
- Optional metadata (category, icon, description)

This allows:
- Single source of truth for command definitions
- Lazy binding to the app instance
- Easy addition/modification of commands
- Consistent command routing across UI components
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Any
from enum import Enum
from utils.structured_logging import get_logger

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = get_logger(__name__)


class CommandCategory(Enum):
    """Categories for organizing commands."""
    FILE = "file"
    EDIT = "edit"
    PROCESS = "process"
    GENERATE = "generate"
    TOOLS = "tools"
    RECORDING = "recording"
    VIEW = "view"
    SETTINGS = "settings"


@dataclass
class Command:
    """Represents a single application command."""
    id: str
    method_name: str
    category: CommandCategory
    description: str = ""
    shortcut: str = ""
    icon: str = ""
    enabled: bool = True
    visible: bool = True

    # For commands that delegate to controllers
    controller_name: Optional[str] = None
    controller_method: Optional[str] = None


class CommandRegistry:
    """Registry for all application commands.

    This class provides:
    - Centralized command definitions
    - Lazy binding to app methods
    - Command lookup by ID or category
    - Consistent command execution with error handling
    """

    def __init__(self):
        """Initialize the command registry."""
        self._commands: Dict[str, Command] = {}
        self._app: Optional['MedicalDictationApp'] = None
        self._register_default_commands()

    def bind_app(self, app: 'MedicalDictationApp') -> None:
        """Bind the registry to an app instance.

        Args:
            app: The main application instance
        """
        self._app = app

    def _register_default_commands(self) -> None:
        """Register all default application commands."""

        # ========================================
        # File Commands
        # ========================================
        self.register(Command(
            id="new_session",
            method_name="new_session",
            category=CommandCategory.FILE,
            description="Start a new dictation session",
            shortcut="Ctrl+N",
            icon="📄"
        ))

        self.register(Command(
            id="save_text",
            method_name="save_text",
            category=CommandCategory.FILE,
            description="Save current text",
            shortcut="Ctrl+S",
            icon="💾"
        ))

        self.register(Command(
            id="load_audio_file",
            method_name="load_audio_file",
            category=CommandCategory.FILE,
            description="Load and transcribe audio file",
            shortcut="Ctrl+O",
            icon="📁"
        ))

        self.register(Command(
            id="export_as_pdf",
            method_name="export_as_pdf",
            category=CommandCategory.FILE,
            description="Export as PDF"
        ))

        self.register(Command(
            id="export_as_word",
            method_name="export_as_word",
            category=CommandCategory.FILE,
            description="Export as Word document"
        ))

        self.register(Command(
            id="export_prompts",
            method_name="export_prompts",
            category=CommandCategory.FILE,
            description="Export prompts to file"
        ))

        self.register(Command(
            id="import_prompts",
            method_name="import_prompts",
            category=CommandCategory.FILE,
            description="Import prompts from file"
        ))

        # ========================================
        # Edit Commands
        # ========================================
        self.register(Command(
            id="undo_text",
            method_name="undo_text",
            category=CommandCategory.EDIT,
            description="Undo last text change",
            shortcut="Ctrl+Z",
            icon="↩"
        ))

        self.register(Command(
            id="redo_text",
            method_name="redo_text",
            category=CommandCategory.EDIT,
            description="Redo last text change",
            shortcut="Ctrl+Y",
            icon="↪"
        ))

        self.register(Command(
            id="copy_text",
            method_name="copy_text",
            category=CommandCategory.EDIT,
            description="Copy text to clipboard",
            shortcut="Ctrl+C",
            icon="📋"
        ))

        self.register(Command(
            id="clear_text",
            method_name="clear_text",
            category=CommandCategory.EDIT,
            description="Clear transcript text"
        ))

        # ========================================
        # Process Commands
        # ========================================
        self.register(Command(
            id="refine_text",
            method_name="refine_text",
            category=CommandCategory.PROCESS,
            description="Refine text with AI",
            icon="✨"
        ))

        self.register(Command(
            id="improve_text",
            method_name="improve_text",
            category=CommandCategory.PROCESS,
            description="Improve text with AI",
            icon="📝"
        ))

        # ========================================
        # Generate Commands
        # ========================================
        self.register(Command(
            id="create_soap_note",
            method_name="create_soap_note",
            category=CommandCategory.GENERATE,
            description="Generate SOAP note",
            icon="📋"
        ))

        self.register(Command(
            id="create_referral",
            method_name="create_referral",
            category=CommandCategory.GENERATE,
            description="Create referral letter",
            icon="📨"
        ))

        self.register(Command(
            id="create_letter",
            method_name="create_letter",
            category=CommandCategory.GENERATE,
            description="Create letter",
            icon="✉"
        ))

        self.register(Command(
            id="create_diagnostic_analysis",
            method_name="create_diagnostic_analysis",
            category=CommandCategory.GENERATE,
            description="Create diagnostic analysis",
            icon="🔬"
        ))

        self.register(Command(
            id="analyze_medications",
            method_name="analyze_medications",
            category=CommandCategory.GENERATE,
            description="Analyze medications",
            icon="💊"
        ))

        self.register(Command(
            id="extract_clinical_data",
            method_name="extract_clinical_data",
            category=CommandCategory.GENERATE,
            description="Extract clinical data",
            icon="📊"
        ))

        self.register(Command(
            id="manage_workflow",
            method_name="manage_workflow",
            category=CommandCategory.GENERATE,
            description="Manage clinical workflows",
            icon="📋"
        ))

        # ========================================
        # Recording Commands
        # ========================================
        self.register(Command(
            id="toggle_soap_recording",
            method_name="toggle_soap_recording",
            category=CommandCategory.RECORDING,
            description="Start/stop SOAP recording",
            shortcut="F5",
            icon="🎤"
        ))

        self.register(Command(
            id="toggle_soap_pause",
            method_name="toggle_soap_pause",
            category=CommandCategory.RECORDING,
            description="Pause/resume recording",
            shortcut="Space",
            icon="⏸"
        ))

        self.register(Command(
            id="cancel_soap_recording",
            method_name="cancel_soap_recording",
            category=CommandCategory.RECORDING,
            description="Cancel current recording",
            shortcut="Escape",
            icon="⏹"
        ))

        # ========================================
        # Tools Commands
        # ========================================
        self.register(Command(
            id="open_translation",
            method_name="open_translation_dialog",
            category=CommandCategory.TOOLS,
            description="Open translation assistant",
            icon="🌐"
        ))

        self.register(Command(
            id="open_rsvp_reader",
            method_name="open_rsvp_reader",
            category=CommandCategory.TOOLS,
            description="Open RSVP speed reader",
            icon="◉"
        ))

        self.register(Command(
            id="show_rsvp_reader",
            method_name="show_rsvp_reader",
            category=CommandCategory.TOOLS,
            description="Open RSVP for current SOAP note"
        ))

        self.register(Command(
            id="show_recordings_dialog",
            method_name="show_recordings_dialog",
            category=CommandCategory.TOOLS,
            description="View recordings history",
            icon="📚"
        ))

        self.register(Command(
            id="show_diagnostic_history",
            method_name="show_diagnostic_history",
            category=CommandCategory.TOOLS,
            description="View diagnostic history"
        ))

        self.register(Command(
            id="show_diagnostic_comparison",
            method_name="show_diagnostic_comparison",
            category=CommandCategory.TOOLS,
            description="Compare diagnostics"
        ))

        self.register(Command(
            id="import_contacts_from_csv",
            method_name="import_contacts_from_csv",
            category=CommandCategory.TOOLS,
            description="Import contacts from CSV"
        ))

        self.register(Command(
            id="manage_address_book",
            method_name="manage_address_book",
            category=CommandCategory.TOOLS,
            description="Manage address book"
        ))

        # ========================================
        # View Commands
        # ========================================
        self.register(Command(
            id="toggle_theme",
            method_name="toggle_theme",
            category=CommandCategory.VIEW,
            description="Toggle light/dark theme",
            shortcut="Alt+T"
        ))

        self.register(Command(
            id="view_logs",
            method_name="view_logs",
            category=CommandCategory.VIEW,
            description="View application logs"
        ))

        self.register(Command(
            id="show_undo_history",
            method_name="show_undo_history",
            category=CommandCategory.VIEW,
            description="Show undo history"
        ))

        # ========================================
        # Settings Commands
        # ========================================
        self.register(Command(
            id="show_preferences",
            method_name="show_preferences",
            category=CommandCategory.SETTINGS,
            description="Show preferences dialog",
            shortcut="Ctrl+,"
        ))

        self.register(Command(
            id="show_api_keys_dialog",
            method_name="show_api_keys_dialog",
            category=CommandCategory.SETTINGS,
            description="Update API keys"
        ))

        self.register(Command(
            id="set_default_folder",
            method_name="set_default_folder",
            category=CommandCategory.SETTINGS,
            description="Set default storage folder"
        ))

        self.register(Command(
            id="toggle_quick_continue_mode",
            method_name="toggle_quick_continue_mode",
            category=CommandCategory.SETTINGS,
            description="Toggle quick continue mode"
        ))

        # ========================================
        # Analysis Commands
        # ========================================
        self.register(Command(
            id="clear_advanced_analysis",
            method_name="clear_advanced_analysis_text",
            category=CommandCategory.TOOLS,
            description="Clear advanced analysis text"
        ))

    def register(self, command: Command) -> None:
        """Register a command.

        Args:
            command: The command to register
        """
        if command.id in self._commands:
            logger.warning(f"Command '{command.id}' already registered, overwriting")
        self._commands[command.id] = command

    def get(self, command_id: str) -> Optional[Command]:
        """Get a command by ID.

        Args:
            command_id: The command ID

        Returns:
            The command, or None if not found
        """
        return self._commands.get(command_id)

    def get_by_category(self, category: CommandCategory) -> List[Command]:
        """Get all commands in a category.

        Args:
            category: The category to filter by

        Returns:
            List of commands in the category
        """
        return [cmd for cmd in self._commands.values() if cmd.category == category]

    def execute(self, command_id: str, *args, **kwargs) -> Any:
        """Execute a command by ID.

        Args:
            command_id: The command ID to execute
            *args: Positional arguments to pass to the command
            **kwargs: Keyword arguments to pass to the command

        Returns:
            The result of the command execution

        Raises:
            ValueError: If command not found or app not bound
        """
        if not self._app:
            raise ValueError("CommandRegistry not bound to app instance")

        command = self.get(command_id)
        if not command:
            raise ValueError(f"Command '{command_id}' not found")

        if not command.enabled:
            logger.warning(f"Command '{command_id}' is disabled")
            return None

        # Get the method to call
        method = getattr(self._app, command.method_name, None)
        if not method:
            # Try controller delegation
            if command.controller_name and command.controller_method:
                controller = getattr(self._app, command.controller_name, None)
                if controller:
                    method = getattr(controller, command.controller_method, None)

        if not method:
            raise ValueError(f"Method '{command.method_name}' not found on app")

        try:
            return method(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error executing command '{command_id}': {e}")
            raise

    def get_command_map(self) -> Dict[str, Callable]:
        """Get a command map for UI components.

        Returns a dictionary mapping command IDs to callable functions
        that execute the commands.

        Returns:
            Dict mapping command IDs to callables
        """
        if not self._app:
            raise ValueError("CommandRegistry not bound to app instance")

        result = {}
        for cmd_id, cmd in self._commands.items():
            if cmd.enabled and cmd.visible:
                method = getattr(self._app, cmd.method_name, None)
                if method:
                    result[cmd_id] = method

        return result

    def list_commands(self) -> List[str]:
        """Get list of all registered command IDs.

        Returns:
            List of command IDs
        """
        return list(self._commands.keys())


# Global singleton instance
_registry: Optional[CommandRegistry] = None


def get_command_registry() -> CommandRegistry:
    """Get the global command registry instance.

    Returns:
        The global CommandRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = CommandRegistry()
    return _registry


__all__ = [
    'Command',
    'CommandCategory',
    'CommandRegistry',
    'get_command_registry',
]

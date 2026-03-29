"""
Tests for src/core/command_registry.py

Covers CommandCategory enum, Command dataclass, CommandRegistry
(register, get, get_by_category, execute, list_commands, default commands),
and the get_command_registry singleton.
App binding is mocked — no Tkinter required.
"""

import sys
import pytest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import core.command_registry as cr_module
from core.command_registry import (
    CommandCategory,
    Command,
    CommandRegistry,
    get_command_registry,
)


# ---------------------------------------------------------------------------
# Singleton reset fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singleton():
    cr_module._registry = None
    yield
    cr_module._registry = None


# ===========================================================================
# CommandCategory enum
# ===========================================================================

class TestCommandCategory:
    def test_file_value(self):
        assert CommandCategory.FILE.value == "file"

    def test_edit_value(self):
        assert CommandCategory.EDIT.value == "edit"

    def test_process_value(self):
        assert CommandCategory.PROCESS.value == "process"

    def test_generate_value(self):
        assert CommandCategory.GENERATE.value == "generate"

    def test_tools_value(self):
        assert CommandCategory.TOOLS.value == "tools"

    def test_recording_value(self):
        assert CommandCategory.RECORDING.value == "recording"

    def test_view_value(self):
        assert CommandCategory.VIEW.value == "view"

    def test_settings_value(self):
        assert CommandCategory.SETTINGS.value == "settings"


# ===========================================================================
# Command dataclass
# ===========================================================================

class TestCommand:
    def test_create_minimal_command(self):
        cmd = Command(
            id="test_cmd",
            method_name="test_method",
            category=CommandCategory.FILE,
        )
        assert cmd.id == "test_cmd"
        assert cmd.method_name == "test_method"
        assert cmd.category == CommandCategory.FILE

    def test_defaults_description_empty(self):
        cmd = Command(id="x", method_name="m", category=CommandCategory.FILE)
        assert cmd.description == ""

    def test_defaults_shortcut_empty(self):
        cmd = Command(id="x", method_name="m", category=CommandCategory.FILE)
        assert cmd.shortcut == ""

    def test_defaults_icon_empty(self):
        cmd = Command(id="x", method_name="m", category=CommandCategory.FILE)
        assert cmd.icon == ""

    def test_defaults_enabled_true(self):
        cmd = Command(id="x", method_name="m", category=CommandCategory.FILE)
        assert cmd.enabled is True

    def test_defaults_visible_true(self):
        cmd = Command(id="x", method_name="m", category=CommandCategory.FILE)
        assert cmd.visible is True

    def test_defaults_controller_name_none(self):
        cmd = Command(id="x", method_name="m", category=CommandCategory.FILE)
        assert cmd.controller_name is None

    def test_defaults_controller_method_none(self):
        cmd = Command(id="x", method_name="m", category=CommandCategory.FILE)
        assert cmd.controller_method is None

    def test_custom_attributes(self):
        cmd = Command(
            id="save",
            method_name="save_text",
            category=CommandCategory.FILE,
            description="Save file",
            shortcut="Ctrl+S",
            icon="💾",
            enabled=False,
            visible=False,
        )
        assert cmd.description == "Save file"
        assert cmd.shortcut == "Ctrl+S"
        assert cmd.enabled is False
        assert cmd.visible is False


# ===========================================================================
# CommandRegistry.register and .get
# ===========================================================================

class TestCommandRegistryRegisterGet:
    def test_register_adds_command(self):
        reg = CommandRegistry()
        cmd = Command(id="my_cmd", method_name="my_method", category=CommandCategory.FILE)
        reg.register(cmd)
        assert reg.get("my_cmd") is cmd

    def test_get_returns_none_for_unknown_id(self):
        reg = CommandRegistry()
        assert reg.get("nonexistent") is None

    def test_register_overwrites_existing(self):
        reg = CommandRegistry()
        cmd1 = Command(id="cmd", method_name="method_a", category=CommandCategory.FILE)
        cmd2 = Command(id="cmd", method_name="method_b", category=CommandCategory.FILE)
        reg.register(cmd1)
        reg.register(cmd2)
        assert reg.get("cmd").method_name == "method_b"

    def test_get_returns_correct_command_object(self):
        reg = CommandRegistry()
        cmd = Command(id="x", method_name="m", category=CommandCategory.EDIT, description="test")
        reg.register(cmd)
        result = reg.get("x")
        assert result.description == "test"


# ===========================================================================
# CommandRegistry.get_by_category
# ===========================================================================

class TestCommandRegistryGetByCategory:
    def test_returns_list(self):
        reg = CommandRegistry()
        result = reg.get_by_category(CommandCategory.FILE)
        assert isinstance(result, list)

    def test_returns_commands_in_category(self):
        reg = CommandRegistry()
        # Clear defaults to isolate test
        reg._commands.clear()
        cmd1 = Command(id="a", method_name="ma", category=CommandCategory.FILE)
        cmd2 = Command(id="b", method_name="mb", category=CommandCategory.EDIT)
        reg.register(cmd1)
        reg.register(cmd2)
        result = reg.get_by_category(CommandCategory.FILE)
        assert len(result) == 1
        assert result[0].id == "a"

    def test_returns_empty_for_empty_category(self):
        reg = CommandRegistry()
        reg._commands.clear()
        result = reg.get_by_category(CommandCategory.VIEW)
        assert result == []

    def test_returns_all_in_category(self):
        reg = CommandRegistry()
        reg._commands.clear()
        for i in range(3):
            reg.register(Command(id=f"c{i}", method_name=f"m{i}", category=CommandCategory.TOOLS))
        result = reg.get_by_category(CommandCategory.TOOLS)
        assert len(result) == 3


# ===========================================================================
# CommandRegistry.execute
# ===========================================================================

class TestCommandRegistryExecute:
    def test_raises_if_not_bound(self):
        reg = CommandRegistry()
        with pytest.raises(ValueError, match="not bound"):
            reg.execute("save_text")

    def test_raises_if_command_not_found(self):
        reg = CommandRegistry()
        reg._app = MagicMock()
        with pytest.raises(ValueError, match="not found"):
            reg.execute("nonexistent_command_xyz")

    def test_calls_app_method(self):
        reg = CommandRegistry()
        mock_app = MagicMock()
        reg.bind_app(mock_app)
        reg._commands.clear()
        cmd = Command(id="do_it", method_name="do_it_method", category=CommandCategory.FILE)
        reg.register(cmd)
        reg.execute("do_it")
        mock_app.do_it_method.assert_called_once()

    def test_disabled_command_returns_none(self):
        reg = CommandRegistry()
        mock_app = MagicMock()
        reg.bind_app(mock_app)
        reg._commands.clear()
        cmd = Command(id="disabled", method_name="some_method", category=CommandCategory.FILE, enabled=False)
        reg.register(cmd)
        result = reg.execute("disabled")
        assert result is None
        mock_app.some_method.assert_not_called()

    def test_raises_if_method_not_on_app(self):
        reg = CommandRegistry()
        mock_app = MagicMock(spec=[])  # Empty spec — no methods
        reg.bind_app(mock_app)
        reg._commands.clear()
        cmd = Command(id="missing", method_name="missing_method", category=CommandCategory.FILE)
        reg.register(cmd)
        with pytest.raises(ValueError, match="not found on app"):
            reg.execute("missing")


# ===========================================================================
# CommandRegistry.list_commands
# ===========================================================================

class TestCommandRegistryListCommands:
    def test_returns_list(self):
        reg = CommandRegistry()
        assert isinstance(reg.list_commands(), list)

    def test_contains_registered_ids(self):
        reg = CommandRegistry()
        reg._commands.clear()
        reg.register(Command(id="cmd_a", method_name="m", category=CommandCategory.FILE))
        reg.register(Command(id="cmd_b", method_name="m", category=CommandCategory.FILE))
        ids = reg.list_commands()
        assert "cmd_a" in ids
        assert "cmd_b" in ids

    def test_empty_when_no_commands(self):
        reg = CommandRegistry()
        reg._commands.clear()
        assert reg.list_commands() == []


# ===========================================================================
# Default commands (registered in __init__)
# ===========================================================================

class TestDefaultCommands:
    def test_has_new_session_command(self):
        reg = CommandRegistry()
        assert reg.get("new_session") is not None

    def test_has_save_text_command(self):
        reg = CommandRegistry()
        assert reg.get("save_text") is not None

    def test_has_file_category_commands(self):
        reg = CommandRegistry()
        file_cmds = reg.get_by_category(CommandCategory.FILE)
        assert len(file_cmds) > 0

    def test_has_edit_category_commands(self):
        reg = CommandRegistry()
        edit_cmds = reg.get_by_category(CommandCategory.EDIT)
        assert len(edit_cmds) > 0

    def test_substantial_command_count(self):
        reg = CommandRegistry()
        assert len(reg.list_commands()) >= 10


# ===========================================================================
# get_command_registry singleton
# ===========================================================================

class TestGetCommandRegistry:
    def test_returns_command_registry_instance(self):
        reg = get_command_registry()
        assert isinstance(reg, CommandRegistry)

    def test_returns_same_instance_on_repeated_calls(self):
        r1 = get_command_registry()
        r2 = get_command_registry()
        assert r1 is r2

    def test_new_instance_after_singleton_reset(self):
        r1 = get_command_registry()
        cr_module._registry = None
        r2 = get_command_registry()
        assert r1 is not r2

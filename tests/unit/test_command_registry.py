"""
Tests for src/core/command_registry.py

Covers: CommandCategory enum, Command dataclass, CommandRegistry
(register, get, get_by_category, list_commands, default commands),
and the get_command_registry() singleton helper.

NOTE: execute() and get_command_map() require a bound app instance with real
Tkinter methods and are intentionally not tested here.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from core.command_registry import (
    CommandCategory,
    Command,
    CommandRegistry,
    get_command_registry,
)
import core.command_registry as _cr_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the module-level singleton before and after every test."""
    _cr_module._registry = None
    yield
    _cr_module._registry = None


@pytest.fixture()
def registry():
    return CommandRegistry()


# ===========================================================================
# 1. CommandCategory enum
# ===========================================================================

class TestCommandCategoryEnum:
    def test_has_eight_members(self):
        assert len(CommandCategory) == 8

    def test_has_file(self):
        assert hasattr(CommandCategory, "FILE")

    def test_has_edit(self):
        assert hasattr(CommandCategory, "EDIT")

    def test_has_process(self):
        assert hasattr(CommandCategory, "PROCESS")

    def test_has_generate(self):
        assert hasattr(CommandCategory, "GENERATE")

    def test_has_tools(self):
        assert hasattr(CommandCategory, "TOOLS")

    def test_has_recording(self):
        assert hasattr(CommandCategory, "RECORDING")

    def test_has_view(self):
        assert hasattr(CommandCategory, "VIEW")

    def test_has_settings(self):
        assert hasattr(CommandCategory, "SETTINGS")

    def test_file_value(self):
        assert CommandCategory.FILE.value == "file"

    def test_settings_value(self):
        assert CommandCategory.SETTINGS.value == "settings"

    def test_members_are_enum_instances(self):
        for member in CommandCategory:
            assert isinstance(member, CommandCategory)


# ===========================================================================
# 2. Command dataclass – defaults
# ===========================================================================

class TestCommandDataclassDefaults:
    def test_enabled_default_true(self):
        cmd = Command(id="x", method_name="x", category=CommandCategory.FILE)
        assert cmd.enabled is True

    def test_visible_default_true(self):
        cmd = Command(id="x", method_name="x", category=CommandCategory.FILE)
        assert cmd.visible is True

    def test_description_default_empty_string(self):
        cmd = Command(id="x", method_name="x", category=CommandCategory.FILE)
        assert cmd.description == ""

    def test_shortcut_default_empty_string(self):
        cmd = Command(id="x", method_name="x", category=CommandCategory.FILE)
        assert cmd.shortcut == ""

    def test_icon_default_empty_string(self):
        cmd = Command(id="x", method_name="x", category=CommandCategory.FILE)
        assert cmd.icon == ""

    def test_controller_name_default_none(self):
        cmd = Command(id="x", method_name="x", category=CommandCategory.FILE)
        assert cmd.controller_name is None

    def test_controller_method_default_none(self):
        cmd = Command(id="x", method_name="x", category=CommandCategory.FILE)
        assert cmd.controller_method is None


# ===========================================================================
# 3. Command dataclass – custom values stored correctly
# ===========================================================================

class TestCommandDataclassCustomValues:
    def test_id_stored(self):
        cmd = Command(id="my_cmd", method_name="do_it", category=CommandCategory.EDIT)
        assert cmd.id == "my_cmd"

    def test_method_name_stored(self):
        cmd = Command(id="my_cmd", method_name="do_it", category=CommandCategory.EDIT)
        assert cmd.method_name == "do_it"

    def test_category_stored(self):
        cmd = Command(id="my_cmd", method_name="do_it", category=CommandCategory.EDIT)
        assert cmd.category is CommandCategory.EDIT

    def test_description_stored(self):
        cmd = Command(
            id="x", method_name="x", category=CommandCategory.FILE,
            description="Do something useful",
        )
        assert cmd.description == "Do something useful"

    def test_shortcut_stored(self):
        cmd = Command(
            id="x", method_name="x", category=CommandCategory.FILE,
            shortcut="Ctrl+X",
        )
        assert cmd.shortcut == "Ctrl+X"

    def test_enabled_false_stored(self):
        cmd = Command(
            id="x", method_name="x", category=CommandCategory.FILE,
            enabled=False,
        )
        assert cmd.enabled is False

    def test_visible_false_stored(self):
        cmd = Command(
            id="x", method_name="x", category=CommandCategory.FILE,
            visible=False,
        )
        assert cmd.visible is False

    def test_controller_name_stored(self):
        cmd = Command(
            id="x", method_name="x", category=CommandCategory.FILE,
            controller_name="my_ctrl",
        )
        assert cmd.controller_name == "my_ctrl"

    def test_controller_method_stored(self):
        cmd = Command(
            id="x", method_name="x", category=CommandCategory.FILE,
            controller_method="ctrl_method",
        )
        assert cmd.controller_method == "ctrl_method"


# ===========================================================================
# 4. CommandRegistry constructor / default commands
# ===========================================================================

class TestCommandRegistryConstructor:
    def test_creates_successfully(self, registry):
        assert registry is not None

    def test_has_default_commands(self, registry):
        assert len(registry._commands) > 0

    def test_app_initially_none(self, registry):
        assert registry._app is None

    def test_bind_app_stores_app(self, registry):
        fake_app = object()
        registry.bind_app(fake_app)
        assert registry._app is fake_app


# ===========================================================================
# 5. register() and get()
# ===========================================================================

class TestRegisterAndGet:
    def test_register_adds_command(self, registry):
        cmd = Command(id="test_cmd", method_name="test_method", category=CommandCategory.TOOLS)
        registry.register(cmd)
        assert registry.get("test_cmd") is cmd

    def test_get_existing_command(self, registry):
        result = registry.get("new_session")
        assert result is not None
        assert isinstance(result, Command)

    def test_get_missing_command_returns_none(self, registry):
        result = registry.get("definitely_not_a_real_command_xyz")
        assert result is None

    def test_overwrite_existing_command(self, registry):
        original = registry.get("new_session")
        replacement = Command(
            id="new_session",
            method_name="replaced_method",
            category=CommandCategory.FILE,
        )
        registry.register(replacement)
        assert registry.get("new_session").method_name == "replaced_method"

    def test_register_multiple_commands(self, registry):
        for i in range(5):
            cmd = Command(
                id=f"dynamic_cmd_{i}",
                method_name=f"method_{i}",
                category=CommandCategory.TOOLS,
            )
            registry.register(cmd)

        for i in range(5):
            assert registry.get(f"dynamic_cmd_{i}") is not None

    def test_get_returns_correct_category(self, registry):
        cmd = Command(
            id="cat_test", method_name="m", category=CommandCategory.GENERATE
        )
        registry.register(cmd)
        assert registry.get("cat_test").category is CommandCategory.GENERATE


# ===========================================================================
# 6. get_by_category()
# ===========================================================================

class TestGetByCategory:
    def test_file_category_non_empty(self, registry):
        cmds = registry.get_by_category(CommandCategory.FILE)
        assert len(cmds) > 0

    def test_file_category_all_correct_category(self, registry):
        cmds = registry.get_by_category(CommandCategory.FILE)
        for cmd in cmds:
            assert cmd.category is CommandCategory.FILE

    def test_process_category_non_empty(self, registry):
        cmds = registry.get_by_category(CommandCategory.PROCESS)
        assert len(cmds) > 0

    def test_generate_category_non_empty(self, registry):
        cmds = registry.get_by_category(CommandCategory.GENERATE)
        assert len(cmds) > 0

    def test_recording_category_non_empty(self, registry):
        cmds = registry.get_by_category(CommandCategory.RECORDING)
        assert len(cmds) > 0

    def test_tools_category_non_empty(self, registry):
        cmds = registry.get_by_category(CommandCategory.TOOLS)
        assert len(cmds) > 0

    def test_settings_category_non_empty(self, registry):
        cmds = registry.get_by_category(CommandCategory.SETTINGS)
        assert len(cmds) > 0

    def test_view_category_non_empty(self, registry):
        cmds = registry.get_by_category(CommandCategory.VIEW)
        assert len(cmds) > 0

    def test_returns_list(self, registry):
        result = registry.get_by_category(CommandCategory.FILE)
        assert isinstance(result, list)

    def test_all_results_are_command_instances(self, registry):
        for cat in CommandCategory:
            for cmd in registry.get_by_category(cat):
                assert isinstance(cmd, Command)

    def test_file_category_has_multiple_commands(self, registry):
        cmds = registry.get_by_category(CommandCategory.FILE)
        assert len(cmds) > 1

    def test_newly_registered_command_appears_in_category(self, registry):
        cmd = Command(
            id="new_tools_cmd", method_name="m", category=CommandCategory.TOOLS
        )
        registry.register(cmd)
        ids = [c.id for c in registry.get_by_category(CommandCategory.TOOLS)]
        assert "new_tools_cmd" in ids


# ===========================================================================
# 7. list_commands()
# ===========================================================================

class TestListCommands:
    def test_returns_list(self, registry):
        result = registry.list_commands()
        assert isinstance(result, list)

    def test_non_empty(self, registry):
        assert len(registry.list_commands()) > 0

    def test_contains_only_strings(self, registry):
        for item in registry.list_commands():
            assert isinstance(item, str)

    def test_contains_new_session(self, registry):
        assert "new_session" in registry.list_commands()

    def test_contains_save_text(self, registry):
        assert "save_text" in registry.list_commands()

    def test_contains_create_soap_note(self, registry):
        assert "create_soap_note" in registry.list_commands()

    def test_newly_registered_command_appears_in_list(self, registry):
        cmd = Command(
            id="list_test_cmd", method_name="m", category=CommandCategory.EDIT
        )
        registry.register(cmd)
        assert "list_test_cmd" in registry.list_commands()

    def test_count_matches_commands_dict(self, registry):
        assert len(registry.list_commands()) == len(registry._commands)


# ===========================================================================
# 8. Specific default commands
# ===========================================================================

class TestDefaultCommands:
    def test_new_session_exists(self, registry):
        cmd = registry.get("new_session")
        assert cmd is not None

    def test_new_session_method_name(self, registry):
        assert registry.get("new_session").method_name == "new_session"

    def test_new_session_category_file(self, registry):
        assert registry.get("new_session").category is CommandCategory.FILE

    def test_new_session_shortcut_ctrl_n(self, registry):
        assert registry.get("new_session").shortcut == "Ctrl+N"

    def test_new_session_enabled(self, registry):
        assert registry.get("new_session").enabled is True

    def test_save_text_exists(self, registry):
        assert registry.get("save_text") is not None

    def test_save_text_category_file(self, registry):
        assert registry.get("save_text").category is CommandCategory.FILE

    def test_save_text_shortcut_ctrl_s(self, registry):
        assert registry.get("save_text").shortcut == "Ctrl+S"

    def test_create_soap_note_exists(self, registry):
        assert registry.get("create_soap_note") is not None

    def test_create_soap_note_category_generate(self, registry):
        assert registry.get("create_soap_note").category is CommandCategory.GENERATE

    def test_toggle_soap_recording_exists(self, registry):
        assert registry.get("toggle_soap_recording") is not None

    def test_toggle_soap_recording_shortcut_f5(self, registry):
        assert registry.get("toggle_soap_recording").shortcut == "F5"

    def test_show_preferences_exists(self, registry):
        assert registry.get("show_preferences") is not None

    def test_show_preferences_category_settings(self, registry):
        assert registry.get("show_preferences").category is CommandCategory.SETTINGS

    def test_toggle_theme_exists(self, registry):
        assert registry.get("toggle_theme") is not None

    def test_toggle_theme_category_view(self, registry):
        assert registry.get("toggle_theme").category is CommandCategory.VIEW

    def test_load_audio_file_exists(self, registry):
        assert registry.get("load_audio_file") is not None

    def test_load_audio_file_shortcut_ctrl_o(self, registry):
        assert registry.get("load_audio_file").shortcut == "Ctrl+O"


# ===========================================================================
# 9. get_command_registry() singleton
# ===========================================================================

class TestGetCommandRegistrySingleton:
    def test_returns_command_registry_instance(self):
        reg = get_command_registry()
        assert isinstance(reg, CommandRegistry)

    def test_returns_same_object_on_second_call(self):
        r1 = get_command_registry()
        r2 = get_command_registry()
        assert r1 is r2

    def test_singleton_reset_by_fixture_creates_fresh_instance(self):
        reg = get_command_registry()
        assert reg is not None

    def test_singleton_has_default_commands(self):
        reg = get_command_registry()
        assert len(reg.list_commands()) > 0

    def test_singleton_can_find_new_session(self):
        reg = get_command_registry()
        assert reg.get("new_session") is not None

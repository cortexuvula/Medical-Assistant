"""
Unified Settings Dialog

A comprehensive tabbed settings dialog that consolidates all application
settings into a single, organized interface.
"""

import os
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog
import ttkbootstrap as ttk
from typing import Dict, Optional, Callable

from ui.scaling_utils import ui_scaler
from ui.dialogs.dialog_utils import create_toplevel_dialog
from ui.tooltip import ToolTip
from settings.settings_manager import settings_manager
from utils.structured_logging import get_logger

from ui.dialogs.settings_tabs import (
    ApiKeysTabMixin,
    AudioSttTabMixin,
    AiModelsTabMixin,
    PromptsTabMixin,
    StorageTabMixin,
    RagGuidelinesTabMixin,
    GeneralTabMixin,
)

logger = get_logger(__name__)


class UnifiedSettingsDialog(
    ApiKeysTabMixin,
    AudioSttTabMixin,
    AiModelsTabMixin,
    PromptsTabMixin,
    StorageTabMixin,
    RagGuidelinesTabMixin,
    GeneralTabMixin,
):
    """Main unified settings dialog with tabbed interface."""

    TAB_API_KEYS = "API Keys"
    TAB_AUDIO_STT = "Audio & STT"
    TAB_AI_MODELS = "AI Models"
    TAB_PROMPTS = "Prompts"
    TAB_STORAGE = "Storage"
    TAB_RAG_GUIDELINES = "RAG & Guidelines"
    TAB_GENERAL = "General"

    def __init__(self, parent):
        """Initialize the unified settings dialog.

        Args:
            parent: Parent window
        """
        self.parent = parent
        self.dialog: Optional[tk.Toplevel] = None
        self.notebook: Optional[ttk.Notebook] = None
        self.widgets: Dict[str, Dict] = {}
        self._modified = False

    # Sub-tab name constants for initial_subtab parameter
    SUBTAB_ELEVENLABS = "ElevenLabs"
    SUBTAB_DEEPGRAM = "Deepgram"
    SUBTAB_GROQ = "Groq"
    SUBTAB_TTS = "TTS"
    SUBTAB_TEMPERATURE = "Temperature"
    SUBTAB_TRANSLATION = "Translation"

    def show(self, initial_tab: str = None, initial_subtab: str = None):
        """Show the dialog, optionally selecting a specific tab and sub-tab.

        Args:
            initial_tab: Optional tab name to select initially (use TAB_* constants)
            initial_subtab: Optional sub-tab name within Audio & STT or AI Models
                (use SUBTAB_* constants)
        """
        # Create dialog
        dialog_width, dialog_height = ui_scaler.get_dialog_size(900, 700)
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Preferences")
        self.dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.minsize(800, 600)
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.update_idletasks()
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        x = (screen_width // 2) - (dialog_width // 2)
        y = (screen_height // 2) - (dialog_height // 2)
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # Configure grid
        self.dialog.rowconfigure(0, weight=1)
        self.dialog.columnconfigure(0, weight=1)

        # Create main frame
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # Create notebook
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew", pady=(0, 10))

        # Create tabs
        self._create_api_keys_tab()
        self._create_audio_stt_tab()
        self._create_ai_models_tab()
        self._create_prompts_tab()
        self._create_storage_tab()
        self._create_rag_guidelines_tab()
        self._create_general_tab()

        # Create button frame
        self._create_buttons(main_frame)

        # Select initial tab if specified
        if initial_tab:
            tab_names = [self.TAB_API_KEYS, self.TAB_AUDIO_STT, self.TAB_AI_MODELS,
                        self.TAB_PROMPTS, self.TAB_STORAGE, self.TAB_RAG_GUIDELINES,
                        self.TAB_GENERAL]
            if initial_tab in tab_names:
                self.notebook.select(tab_names.index(initial_tab))

        # Select initial sub-tab if specified
        if initial_subtab:
            self._select_subtab(initial_subtab)

        # Grab focus
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        self.parent.wait_window(self.dialog)

    def _select_subtab(self, subtab_name: str):
        """Select a sub-tab within a nested notebook.

        Args:
            subtab_name: The sub-tab name to select (use SUBTAB_* constants)
        """
        # Audio & STT sub-tabs
        audio_subtabs = {
            self.SUBTAB_ELEVENLABS: 0,
            self.SUBTAB_DEEPGRAM: 1,
            self.SUBTAB_GROQ: 2,
            self.SUBTAB_TTS: 3,
        }
        if subtab_name in audio_subtabs and hasattr(self, '_audio_stt_notebook'):
            try:
                self._audio_stt_notebook.select(audio_subtabs[subtab_name])
            except Exception:
                pass
            return

        # AI Models sub-tabs
        ai_subtabs = {
            self.SUBTAB_TEMPERATURE: 0,
            self.SUBTAB_TRANSLATION: 1,
        }
        if subtab_name in ai_subtabs and hasattr(self, '_ai_models_notebook'):
            try:
                self._ai_models_notebook.select(ai_subtabs[subtab_name])
            except Exception:
                pass

    def _create_buttons(self, parent):
        """Create save/cancel/reset buttons."""
        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=1, column=0, sticky="e", pady=(10, 0))

        reset_btn = ttk.Button(btn_frame, text="Reset Defaults", command=self._reset_to_defaults)
        reset_btn.pack(side=tk.LEFT, padx=5)
        ToolTip(reset_btn, "Reset all settings to their default values")

        cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=5)
        ToolTip(cancel_btn, "Discard changes and close")

        save_btn = ttk.Button(btn_frame, text="Save", command=self._save_all_settings, bootstyle="success")
        save_btn.pack(side=tk.RIGHT, padx=5)
        ToolTip(save_btn, "Save all settings and close")

    def _save_all_settings(self):
        """Save all settings from all tabs."""
        try:
            # Save API Keys
            from utils.security import get_security_manager
            security_mgr = get_security_manager()

            api_keys = self.widgets.get('api_keys', {})
            for key_id in ['openai', 'anthropic', 'gemini',
                          'deepgram', 'elevenlabs', 'groq']:
                if key_id in api_keys:
                    value = api_keys[key_id].get().strip()
                    if value:
                        security_mgr.store_api_key(key_id, value)

            # Save Ollama URL to environment
            if 'ollama_url' in api_keys:
                os.environ["OLLAMA_API_URL"] = api_keys['ollama_url'].get().strip()

            # Save Audio/STT settings using settings_manager
            audio_stt = self.widgets.get('audio_stt', {})

            if 'elevenlabs' in audio_stt:
                el_widgets = audio_stt['elevenlabs']

                # Handle entity detection checkboxes -> array
                entity_detection = []
                if el_widgets.get('entity_phi', tk.BooleanVar()).get():
                    entity_detection.append('phi')
                if el_widgets.get('entity_pii', tk.BooleanVar()).get():
                    entity_detection.append('pii')
                if el_widgets.get('entity_pci', tk.BooleanVar()).get():
                    entity_detection.append('pci')
                if el_widgets.get('entity_offensive', tk.BooleanVar()).get():
                    entity_detection.append('offensive')
                settings_manager.set_nested('elevenlabs.entity_detection', entity_detection, auto_save=False)

                # Handle keyterms string -> array
                keyterms_str = el_widgets.get('keyterms', tk.StringVar()).get()
                keyterms = [t.strip() for t in keyterms_str.split(',') if t.strip()]
                settings_manager.set_nested('elevenlabs.keyterms', keyterms[:100], auto_save=False)

                # Handle num_speakers (string -> int or None)
                num_speakers_str = el_widgets.get('num_speakers', tk.StringVar()).get().strip()
                if num_speakers_str:
                    try:
                        settings_manager.set_nested('elevenlabs.num_speakers', int(num_speakers_str), auto_save=False)
                    except ValueError:
                        settings_manager.set_nested('elevenlabs.num_speakers', None, auto_save=False)
                else:
                    settings_manager.set_nested('elevenlabs.num_speakers', None, auto_save=False)

                # Handle diarization_threshold (string -> float or None)
                threshold_str = el_widgets.get('diarization_threshold', tk.StringVar()).get().strip()
                if threshold_str:
                    try:
                        settings_manager.set_nested('elevenlabs.diarization_threshold', float(threshold_str), auto_save=False)
                    except ValueError:
                        settings_manager.set_nested('elevenlabs.diarization_threshold', None, auto_save=False)
                else:
                    settings_manager.set_nested('elevenlabs.diarization_threshold', None, auto_save=False)

                # Handle regular settings
                special_keys = {'entity_phi', 'entity_pii', 'entity_pci', 'entity_offensive',
                                'keyterms', 'num_speakers', 'diarization_threshold'}
                for key, var in el_widgets.items():
                    if key in special_keys or key.startswith('entity_'):
                        continue  # Already handled above
                    settings_manager.set_nested(f'elevenlabs.{key}', var.get(), auto_save=False)

            if 'deepgram' in audio_stt:
                for key, var in audio_stt['deepgram'].items():
                    settings_manager.set_nested(f'deepgram.{key}', var.get(), auto_save=False)

            if 'groq' in audio_stt:
                for key, var in audio_stt['groq'].items():
                    settings_manager.set_nested(f'groq.{key}', var.get(), auto_save=False)

            if 'tts' in audio_stt:
                for key, var in audio_stt['tts'].items():
                    settings_manager.set_nested(f'tts.{key}', var.get(), auto_save=False)

            # Save AI Models settings
            ai_models = self.widgets.get('ai_models', {})

            if 'temperature' in ai_models and 'global' in ai_models['temperature']:
                settings_manager.set('temperature', ai_models['temperature']['global'].get(), auto_save=False)

            if 'translation' in ai_models:
                for key, var in ai_models['translation'].items():
                    settings_manager.set_nested(f'translation.{key}', var.get(), auto_save=False)

            # Save Storage settings - write to all keys for consistency
            storage = self.widgets.get('storage', {})
            if 'default_folder' in storage:
                folder_path = storage['default_folder'].get()
                settings_manager.set('default_folder', folder_path, auto_save=False)
                settings_manager.set('storage_folder', folder_path, auto_save=False)
                settings_manager.set('default_storage_folder', folder_path, auto_save=False)

            # Save RAG & Guidelines settings
            rag = self.widgets.get('rag_guidelines', {})
            if rag:
                # Save to settings.json
                if 'neon_database_url' in rag:
                    settings_manager.set('neon_database_url', rag['neon_database_url'].get().strip(), auto_save=False)

                for key in ['neo4j_uri', 'neo4j_user', 'neo4j_password']:
                    if key in rag:
                        settings_manager.set(key, rag[key].get().strip(), auto_save=False)

                guidelines_settings = {}
                for settings_key, widget_key in [
                    ('database_url', 'guidelines_database_url'),
                    ('neo4j_uri', 'guidelines_neo4j_uri'),
                    ('neo4j_user', 'guidelines_neo4j_user'),
                    ('neo4j_password', 'guidelines_neo4j_password'),
                ]:
                    if widget_key in rag:
                        guidelines_settings[settings_key] = rag[widget_key].get().strip()
                if guidelines_settings:
                    settings_manager.set('clinical_guidelines', guidelines_settings, auto_save=False)

                # Update os.environ for immediate use
                env_mapping = {
                    'neon_database_url': 'NEON_DATABASE_URL',
                    'neo4j_uri': 'NEO4J_URI',
                    'neo4j_user': 'NEO4J_USER',
                    'neo4j_password': 'NEO4J_PASSWORD',
                    'guidelines_database_url': 'CLINICAL_GUIDELINES_DATABASE_URL',
                    'guidelines_neo4j_uri': 'CLINICAL_GUIDELINES_NEO4J_URI',
                    'guidelines_neo4j_user': 'CLINICAL_GUIDELINES_NEO4J_USER',
                    'guidelines_neo4j_password': 'CLINICAL_GUIDELINES_NEO4J_PASSWORD',
                }
                for widget_key, env_key in env_mapping.items():
                    if widget_key in rag:
                        value = rag[widget_key].get().strip()
                        if value:
                            os.environ[env_key] = value

                # Optionally persist to .env file
                if rag.get('save_to_env', tk.BooleanVar()).get():
                    self._update_env_file(rag, env_mapping)

            # Save General settings
            general = self.widgets.get('general', {})
            if 'quick_continue_mode' in general:
                settings_manager.set('quick_continue_mode', general['quick_continue_mode'].get(), auto_save=False)
            if 'theme' in general:
                settings_manager.set('theme', general['theme'].get(), auto_save=False)
            if 'sidebar_collapsed' in general:
                settings_manager.set('sidebar_collapsed', general['sidebar_collapsed'].get(), auto_save=False)

            # Persist all settings at once
            settings_manager.save()

            messagebox.showinfo("Settings Saved", "All settings have been saved successfully.")
            self.dialog.destroy()

        except Exception as e:
            from utils.error_handling import show_error_dialog
            show_error_dialog("save_settings", e, parent=self.dialog)

    def _update_env_file(self, rag_widgets: dict, env_mapping: dict):
        """Update or create .env file with RAG & Guidelines values.

        Args:
            rag_widgets: Dictionary of widget StringVars keyed by widget_key
            env_mapping: Mapping from widget_key to ENV_VAR_NAME
        """
        try:
            from managers.data_folder_manager import data_folder_manager
            env_path = data_folder_manager.env_file_path
        except Exception as e:
            logger.debug(f"Could not get env path from data_folder_manager, using fallback: {e}")
            import pathlib
            env_path = pathlib.Path(__file__).parent.parent.parent.parent / '.env'

        # Read existing lines
        existing_lines = []
        if env_path.exists():
            try:
                existing_lines = env_path.read_text(encoding="utf-8").splitlines()
            except Exception as e:
                logger.debug(f"Could not read existing .env file: {e}")

        # Build a dict of KEY=value to update
        updates = {}
        for widget_key, env_key in env_mapping.items():
            if widget_key in rag_widgets:
                value = rag_widgets[widget_key].get().strip()
                if value:
                    updates[env_key] = value

        if not updates:
            return

        # Update existing lines or track which keys were already set
        written_keys = set()
        new_lines = []
        for line in existing_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and '=' in stripped:
                key = stripped.split('=', 1)[0].strip()
                if key in updates:
                    new_lines.append(f"{key}={updates[key]}")
                    written_keys.add(key)
                    continue
            new_lines.append(line)

        # Append keys that weren't already in the file
        for key, value in updates.items():
            if key not in written_keys:
                if new_lines and new_lines[-1].strip():
                    new_lines.append("")  # blank line before new entries
                new_lines.append(f"{key}={value}")

        # Write back
        try:
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        except Exception as e:
            messagebox.showwarning("Warning", f"Could not write .env file: {e}")

    def _reset_to_defaults(self):
        """Reset all settings to defaults."""
        if not messagebox.askyesno("Reset Settings",
                                   "Are you sure you want to reset all settings to defaults?"):
            return

        # Reset Audio/STT
        audio_stt = self.widgets.get('audio_stt', {})

        if 'elevenlabs' in audio_stt:
            defaults = settings_manager.get_default('elevenlabs', {})
            el_widgets = audio_stt['elevenlabs']

            # Reset entity detection checkboxes
            default_entities = defaults.get('entity_detection', [])
            if 'entity_phi' in el_widgets:
                el_widgets['entity_phi'].set('phi' in default_entities)
            if 'entity_pii' in el_widgets:
                el_widgets['entity_pii'].set('pii' in default_entities)
            if 'entity_pci' in el_widgets:
                el_widgets['entity_pci'].set('pci' in default_entities)
            if 'entity_offensive' in el_widgets:
                el_widgets['entity_offensive'].set('offensive' in default_entities)

            # Reset keyterms
            if 'keyterms' in el_widgets:
                default_keyterms = defaults.get('keyterms', [])
                el_widgets['keyterms'].set(', '.join(default_keyterms))

            # Reset regular settings
            for key, var in el_widgets.items():
                if key.startswith('entity_') or key == 'keyterms':
                    continue  # Already handled above
                if key in defaults:
                    var.set(defaults[key])

        if 'deepgram' in audio_stt:
            defaults = settings_manager.get_default('deepgram', {})
            for key, var in audio_stt['deepgram'].items():
                if key in defaults:
                    var.set(defaults[key])

        if 'groq' in audio_stt:
            defaults = settings_manager.get_default('groq', {})
            for key, var in audio_stt['groq'].items():
                if key in defaults:
                    var.set(defaults[key])

        if 'tts' in audio_stt:
            defaults = settings_manager.get_default('tts', {})
            for key, var in audio_stt['tts'].items():
                if key in defaults:
                    var.set(defaults[key])

        # Reset AI Models
        ai_models = self.widgets.get('ai_models', {})
        if 'temperature' in ai_models and 'global' in ai_models['temperature']:
            ai_models['temperature']['global'].set(0.7)

        if 'translation' in ai_models:
            defaults = settings_manager.get_default('translation', {})
            for key, var in ai_models['translation'].items():
                if key in defaults:
                    var.set(defaults[key])

        # Reset General
        general = self.widgets.get('general', {})
        if 'quick_continue_mode' in general:
            general['quick_continue_mode'].set(False)
        if 'theme' in general:
            general['theme'].set('darkly')
        if 'sidebar_collapsed' in general:
            general['sidebar_collapsed'].set(False)

        messagebox.showinfo("Reset Complete", "Settings have been reset to defaults.\n"
                           "Click Save to apply changes.")


def show_unified_settings_dialog(parent, initial_tab: str = None, initial_subtab: str = None):
    """Show the unified settings dialog.

    Args:
        parent: Parent window
        initial_tab: Optional tab name to select initially
            (use UnifiedSettingsDialog.TAB_* constants)
        initial_subtab: Optional sub-tab name within Audio & STT or AI Models
            (use UnifiedSettingsDialog.SUBTAB_* constants)
    """
    dialog = UnifiedSettingsDialog(parent)
    dialog.show(initial_tab, initial_subtab)

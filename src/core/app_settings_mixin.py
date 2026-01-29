"""
App Settings Mixin Module

Contains settings dialog and save settings methods for the MedicalDictationApp class.
These are extracted as a mixin to reduce the size of the main app.py file.
"""

import tkinter as tk
from tkinter import messagebox
from typing import Any, Dict, Optional

import ttkbootstrap as ttk

from settings import settings_manager


class AppSettingsMixin:
    """Mixin class providing settings-related methods for MedicalDictationApp."""

    def show_refine_settings_dialog(self) -> None:
        """Show the refine text settings dialog."""
        from settings.settings import _DEFAULT_SETTINGS
        from ai.prompts import REFINE_PROMPT, REFINE_SYSTEM_MESSAGE
        from ui.dialogs.dialogs import show_settings_dialog

        cfg = settings_manager.get_model_config("refine_text")
        show_settings_dialog(
            parent=self,
            title="Refine Text Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["refine_text"],
            current_prompt=cfg.get("prompt", REFINE_PROMPT),
            current_model=cfg.get("model", _DEFAULT_SETTINGS["refine_text"].get("model", "gpt-3.5-turbo")),
            save_callback=self.save_refine_settings,
            current_ollama=cfg.get("ollama_model", _DEFAULT_SETTINGS["refine_text"].get("ollama_model", "llama3")),
            current_system_prompt=cfg.get("system_message", REFINE_SYSTEM_MESSAGE),
            current_anthropic=cfg.get("anthropic_model", _DEFAULT_SETTINGS["refine_text"].get("anthropic_model", "claude-sonnet-4-20250514")),
            current_gemini=cfg.get("gemini_model", _DEFAULT_SETTINGS["refine_text"].get("gemini_model", "gemini-1.5-flash"))
        )

    def show_improve_settings_dialog(self) -> None:
        """Show the improve text settings dialog."""
        from settings.settings import _DEFAULT_SETTINGS
        from ai.prompts import IMPROVE_PROMPT, IMPROVE_SYSTEM_MESSAGE
        from ui.dialogs.dialogs import show_settings_dialog

        cfg = settings_manager.get_model_config("improve_text")
        show_settings_dialog(
            parent=self,
            title="Improve Text Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["improve_text"],
            current_prompt=cfg.get("prompt", IMPROVE_PROMPT),
            current_model=cfg.get("model", _DEFAULT_SETTINGS["improve_text"].get("model", "gpt-3.5-turbo")),
            save_callback=self.save_improve_settings,
            current_ollama=cfg.get("ollama_model", _DEFAULT_SETTINGS["improve_text"].get("ollama_model", "llama3")),
            current_system_prompt=cfg.get("system_message", IMPROVE_SYSTEM_MESSAGE),
            current_anthropic=cfg.get("anthropic_model", _DEFAULT_SETTINGS["improve_text"].get("anthropic_model", "claude-sonnet-4-20250514")),
            current_gemini=cfg.get("gemini_model", _DEFAULT_SETTINGS["improve_text"].get("gemini_model", "gemini-1.5-flash"))
        )

    def show_soap_settings_dialog(self) -> None:
        """Show the SOAP note settings dialog."""
        from settings.settings import _DEFAULT_SETTINGS
        from ai.prompts import SOAP_PROMPT_TEMPLATE, SOAP_SYSTEM_MESSAGE, SOAP_PROVIDERS
        from ui.dialogs.dialogs import show_settings_dialog

        cfg = settings_manager.get_soap_config()
        default_system_prompt = _DEFAULT_SETTINGS["soap_note"].get("system_message", SOAP_SYSTEM_MESSAGE)
        default_model = _DEFAULT_SETTINGS["soap_note"].get("model", "")

        # Collect per-provider system messages
        provider_messages = {}
        for provider in SOAP_PROVIDERS:
            key = f"{provider}_system_message"
            provider_messages[key] = cfg.get(key, "")

        show_settings_dialog(
            parent=self,
            title="SOAP Note Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["soap_note"],
            current_prompt=cfg.get("prompt", SOAP_PROMPT_TEMPLATE),
            current_model=cfg.get("model", default_model),
            save_callback=self.save_soap_settings,
            current_ollama=cfg.get("ollama_model", _DEFAULT_SETTINGS["soap_note"].get("ollama_model", "llama3")),
            current_system_prompt=cfg.get("system_message", default_system_prompt),
            current_anthropic=cfg.get("anthropic_model", _DEFAULT_SETTINGS["soap_note"].get("anthropic_model", "claude-sonnet-4-20250514")),
            current_gemini=cfg.get("gemini_model", _DEFAULT_SETTINGS["soap_note"].get("gemini_model", "gemini-1.5-flash")),
            current_icd_version=cfg.get("icd_code_version", "ICD-9"),
            is_soap_settings=True,
            provider_messages=provider_messages
        )

    def show_referral_settings_dialog(self) -> None:
        """Show the referral settings dialog."""
        from settings.settings import _DEFAULT_SETTINGS
        from ui.dialogs.dialogs import show_settings_dialog

        cfg = settings_manager.get_model_config("referral")
        default_prompt = _DEFAULT_SETTINGS["referral"].get("prompt", "")
        default_system_prompt = _DEFAULT_SETTINGS["referral"].get("system_message", "")
        default_model = _DEFAULT_SETTINGS["referral"].get("model", "")
        show_settings_dialog(
            parent=self,
            title="Referral Prompt Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["referral"],
            current_prompt=cfg.get("prompt", default_prompt),
            current_model=cfg.get("model", default_model),
            save_callback=self.save_referral_settings,
            current_ollama=cfg.get("ollama_model", _DEFAULT_SETTINGS["referral"].get("ollama_model", "llama3")),
            current_system_prompt=cfg.get("system_message", default_system_prompt),
            current_anthropic=cfg.get("anthropic_model", _DEFAULT_SETTINGS["referral"].get("anthropic_model", "claude-sonnet-4-20250514")),
            current_gemini=cfg.get("gemini_model", _DEFAULT_SETTINGS["referral"].get("gemini_model", "gemini-1.5-flash"))
        )

    def show_advanced_analysis_settings_dialog(self) -> None:
        """Show the advanced analysis settings dialog."""
        from settings.settings import _DEFAULT_SETTINGS
        from ui.dialogs.dialogs import show_settings_dialog

        cfg = settings_manager.get_advanced_analysis_settings()
        default_prompt = _DEFAULT_SETTINGS["advanced_analysis"].get("prompt", "")
        default_system_prompt = _DEFAULT_SETTINGS["advanced_analysis"].get("system_message", "")
        default_model = _DEFAULT_SETTINGS["advanced_analysis"].get("model", "")
        show_settings_dialog(
            parent=self,
            title="Advanced Analysis Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["advanced_analysis"],
            current_prompt=cfg.get("prompt", default_prompt),
            current_model=cfg.get("model", default_model),
            save_callback=self.save_advanced_analysis_settings,
            current_ollama=cfg.get("ollama_model", _DEFAULT_SETTINGS["advanced_analysis"].get("ollama_model", "llama3")),
            current_system_prompt=cfg.get("system_message", default_system_prompt),
            current_anthropic=cfg.get("anthropic_model", _DEFAULT_SETTINGS["advanced_analysis"].get("anthropic_model", "claude-sonnet-4-20250514")),
            current_gemini=cfg.get("gemini_model", _DEFAULT_SETTINGS["advanced_analysis"].get("gemini_model", "gemini-1.5-flash")),
            current_provider=cfg.get("provider", ""),
            is_advanced_analysis=True,
            current_specialty=cfg.get("specialty", "general")
        )

    def show_temperature_settings(self) -> None:
        """Show dialog to configure temperature settings for each AI provider."""
        from ui.dialogs.temperature_dialog import show_temperature_settings_dialog
        show_temperature_settings_dialog(self)
        self.status_manager.success("Temperature settings saved successfully")

    def show_agent_settings(self) -> None:
        """Show dialog to configure AI agent settings."""
        from utils.structured_logging import get_logger
        logger = get_logger(__name__)

        # Check if advanced settings should be shown based on a setting or default to basic
        use_advanced = settings_manager.get("use_advanced_agent_settings", True)

        try:
            if use_advanced:
                from ui.dialogs.advanced_agent_settings_dialog import show_advanced_agent_settings_dialog
                show_advanced_agent_settings_dialog(self)
            else:
                from ui.dialogs.agent_settings_dialog import show_agent_settings_dialog
                show_agent_settings_dialog(self)

            # Reload agents after settings change
            from managers.agent_manager import agent_manager
            agent_manager.reload_agents()

            self.status_manager.success("Agent settings saved successfully")
        except Exception as e:
            # Fall back to basic dialog on error
            logger.error(f"Error showing agent settings dialog: {e}", exc_info=True)
            try:
                from ui.dialogs.agent_settings_dialog import show_agent_settings_dialog
                show_agent_settings_dialog(self)
                self.status_manager.warning("Showing basic agent settings due to error")
            except Exception as e2:
                logger.error(f"Error showing basic dialog: {e2}", exc_info=True)
                self.status_manager.error("Failed to show agent settings dialog")

    def show_vocabulary_settings(self) -> None:
        """Show dialog to configure custom vocabulary corrections."""
        from ui.dialogs.vocabulary_dialog import VocabularyDialog
        dialog = VocabularyDialog(self)
        if dialog.show():
            self.status_manager.success("Vocabulary settings saved successfully")

    def show_preferences(self) -> None:
        """Show the unified Preferences dialog."""
        from ui.dialogs.unified_settings_dialog import show_unified_settings_dialog
        show_unified_settings_dialog(self)

    def show_mcp_config(self) -> None:
        """Show MCP configuration dialog."""
        from utils.structured_logging import get_logger
        logger = get_logger(__name__)
        try:
            from ui.dialogs.mcp_config_dialog import show_mcp_config_dialog
            from ai.mcp.mcp_manager import mcp_manager

            # Show dialog and check if configuration was saved
            # Note: Dialog still needs SETTINGS dict directly for now
            if show_mcp_config_dialog(self, mcp_manager, settings_manager._settings):
                # Configuration was saved, reload MCP tools
                if hasattr(self, 'chat_processor') and self.chat_processor:
                    self.chat_processor.reload_mcp_tools()
                self.status_manager.success("MCP configuration updated")
        except Exception as e:
            logger.error(f"Error showing MCP config dialog: {e}")
            self.status_manager.error("Failed to open MCP configuration")

    def save_refine_settings(self, prompt: str, openai_model: str,
                             ollama_model: str, system_prompt: str,
                             anthropic_model: str, gemini_model: str = "") -> None:
        """Save refine text settings."""
        settings_manager.set_model_config("refine_text", {
            "prompt": prompt,
            "system_message": system_prompt,
            "model": openai_model,
            "ollama_model": ollama_model,
            "anthropic_model": anthropic_model,
            "gemini_model": gemini_model
        })
        self.status_manager.success("Refine text settings saved successfully")

    def save_improve_settings(self, prompt: str, openai_model: str,
                              ollama_model: str, system_prompt: str,
                              anthropic_model: str, gemini_model: str = "") -> None:
        """Save improve text settings."""
        settings_manager.set_model_config("improve_text", {
            "prompt": prompt,
            "system_message": system_prompt,
            "model": openai_model,
            "ollama_model": ollama_model,
            "anthropic_model": anthropic_model,
            "gemini_model": gemini_model
        })
        self.status_manager.success("Improve text settings saved successfully")

    def save_soap_settings(self, prompt: str, openai_model: str,
                           ollama_model: str,
                           anthropic_model: str, gemini_model: str = "",
                           icd_code_version: str = "ICD-9",
                           provider_messages: Optional[Dict[str, Any]] = None) -> None:
        """Save SOAP note settings with per-provider system messages.

        Args:
            prompt: User prompt (shared across providers)
            openai_model: OpenAI model name
            ollama_model: Ollama model name
            anthropic_model: Anthropic model name
            gemini_model: Gemini model name
            icd_code_version: ICD code version (ICD-9, ICD-10, or both)
            provider_messages: Dict mapping provider_system_message keys to values
        """
        # Preserve existing temperature settings by using set_nested for each field
        settings_manager.set_nested("soap_note.prompt", prompt, auto_save=False)
        settings_manager.set_nested("soap_note.model", openai_model, auto_save=False)
        settings_manager.set_nested("soap_note.ollama_model", ollama_model, auto_save=False)
        settings_manager.set_nested("soap_note.anthropic_model", anthropic_model, auto_save=False)
        settings_manager.set_nested("soap_note.gemini_model", gemini_model, auto_save=False)
        settings_manager.set_nested("soap_note.icd_code_version", icd_code_version, auto_save=False)

        # Save per-provider system messages
        if provider_messages:
            for key, value in provider_messages.items():
                settings_manager.set_nested(f"soap_note.{key}", value, auto_save=False)
        # Clear legacy system_message since we now use per-provider messages
        settings_manager.set_nested("soap_note.system_message", "", auto_save=False)

        # Save all changes at once
        settings_manager.save()
        self.status_manager.success("SOAP note settings saved successfully")

    def save_referral_settings(self, prompt: str, openai_model: str,
                               ollama_model: str, system_prompt: str,
                               anthropic_model: str, gemini_model: str = "") -> None:
        """Save referral settings."""
        # Preserve existing temperature settings by using set_nested for each field
        settings_manager.set_nested("referral.prompt", prompt, auto_save=False)
        settings_manager.set_nested("referral.system_message", system_prompt, auto_save=False)
        settings_manager.set_nested("referral.model", openai_model, auto_save=False)
        settings_manager.set_nested("referral.ollama_model", ollama_model, auto_save=False)
        settings_manager.set_nested("referral.anthropic_model", anthropic_model, auto_save=False)
        settings_manager.set_nested("referral.gemini_model", gemini_model, auto_save=False)
        settings_manager.save()
        self.status_manager.success("Referral settings saved successfully")

    def save_advanced_analysis_settings(self, prompt: str, openai_model: str,
                                        ollama_model: str, system_prompt: str,
                                        anthropic_model: str, gemini_model: str = "",
                                        provider: str = "", specialty: str = "general") -> None:
        """Save advanced analysis settings.

        Args:
            prompt: The analysis prompt
            openai_model: OpenAI model to use
            ollama_model: Ollama model to use
            system_prompt: System message for the AI
            anthropic_model: Anthropic model to use
            gemini_model: Gemini model to use
            provider: AI provider to use (empty = use global setting)
            specialty: Clinical specialty focus (e.g., "general", "emergency", "cardiology")
        """
        # Preserve existing temperature settings by using set_nested for each field
        settings_manager.set_nested("advanced_analysis.prompt", prompt, auto_save=False)
        settings_manager.set_nested("advanced_analysis.system_message", system_prompt, auto_save=False)
        settings_manager.set_nested("advanced_analysis.model", openai_model, auto_save=False)
        settings_manager.set_nested("advanced_analysis.ollama_model", ollama_model, auto_save=False)
        settings_manager.set_nested("advanced_analysis.anthropic_model", anthropic_model, auto_save=False)
        settings_manager.set_nested("advanced_analysis.gemini_model", gemini_model, auto_save=False)
        settings_manager.set_nested("advanced_analysis.provider", provider, auto_save=False)
        settings_manager.set_nested("advanced_analysis.specialty", specialty, auto_save=False)
        settings_manager.save()
        self.status_manager.success("Advanced analysis settings saved successfully")

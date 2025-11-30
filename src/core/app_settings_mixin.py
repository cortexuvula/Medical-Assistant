"""
App Settings Mixin Module

Contains settings dialog and save settings methods for the MedicalDictationApp class.
These are extracted as a mixin to reduce the size of the main app.py file.
"""

import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk


class AppSettingsMixin:
    """Mixin class providing settings-related methods for MedicalDictationApp."""

    def show_refine_settings_dialog(self) -> None:
        """Show the refine text settings dialog."""
        from settings.settings import SETTINGS, _DEFAULT_SETTINGS
        from ai.prompts import REFINE_PROMPT, REFINE_SYSTEM_MESSAGE
        from ui.dialogs.dialogs import show_settings_dialog

        cfg = SETTINGS.get("refine_text", {})
        show_settings_dialog(
            parent=self,
            title="Refine Text Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["refine_text"],
            current_prompt=cfg.get("prompt", REFINE_PROMPT),
            current_model=cfg.get("model", _DEFAULT_SETTINGS["refine_text"].get("model", "gpt-3.5-turbo")),
            current_perplexity=cfg.get("perplexity_model", _DEFAULT_SETTINGS["refine_text"].get("perplexity_model", "sonar-reasoning-pro")),
            current_grok=cfg.get("grok_model", _DEFAULT_SETTINGS["refine_text"].get("grok_model", "grok-1")),
            save_callback=self.save_refine_settings,
            current_ollama=cfg.get("ollama_model", _DEFAULT_SETTINGS["refine_text"].get("ollama_model", "llama3")),
            current_system_prompt=cfg.get("system_message", REFINE_SYSTEM_MESSAGE),
            current_anthropic=cfg.get("anthropic_model", _DEFAULT_SETTINGS["refine_text"].get("anthropic_model", "claude-3-sonnet-20240229")),
            current_gemini=cfg.get("gemini_model", _DEFAULT_SETTINGS["refine_text"].get("gemini_model", "gemini-1.5-flash"))
        )

    def show_improve_settings_dialog(self) -> None:
        """Show the improve text settings dialog."""
        from settings.settings import SETTINGS, _DEFAULT_SETTINGS
        from ai.prompts import IMPROVE_PROMPT, IMPROVE_SYSTEM_MESSAGE
        from ui.dialogs.dialogs import show_settings_dialog

        cfg = SETTINGS.get("improve_text", {})
        show_settings_dialog(
            parent=self,
            title="Improve Text Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["improve_text"],
            current_prompt=cfg.get("prompt", IMPROVE_PROMPT),
            current_model=cfg.get("model", _DEFAULT_SETTINGS["improve_text"].get("model", "gpt-3.5-turbo")),
            current_perplexity=cfg.get("perplexity_model", _DEFAULT_SETTINGS["improve_text"].get("perplexity_model", "sonar-reasoning-pro")),
            current_grok=cfg.get("grok_model", _DEFAULT_SETTINGS["improve_text"].get("grok_model", "grok-1")),
            save_callback=self.save_improve_settings,
            current_ollama=cfg.get("ollama_model", _DEFAULT_SETTINGS["improve_text"].get("ollama_model", "llama3")),
            current_system_prompt=cfg.get("system_message", IMPROVE_SYSTEM_MESSAGE),
            current_anthropic=cfg.get("anthropic_model", _DEFAULT_SETTINGS["improve_text"].get("anthropic_model", "claude-3-sonnet-20240229")),
            current_gemini=cfg.get("gemini_model", _DEFAULT_SETTINGS["improve_text"].get("gemini_model", "gemini-1.5-flash"))
        )

    def show_soap_settings_dialog(self) -> None:
        """Show the SOAP note settings dialog."""
        from settings.settings import SETTINGS, _DEFAULT_SETTINGS
        from ai.prompts import SOAP_PROMPT_TEMPLATE, SOAP_SYSTEM_MESSAGE
        from ui.dialogs.dialogs import show_settings_dialog

        cfg = SETTINGS.get("soap_note", {})
        default_system_prompt = _DEFAULT_SETTINGS["soap_note"].get("system_message", SOAP_SYSTEM_MESSAGE)
        default_model = _DEFAULT_SETTINGS["soap_note"].get("model", "")
        show_settings_dialog(
            parent=self,
            title="SOAP Note Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["soap_note"],
            current_prompt=cfg.get("prompt", SOAP_PROMPT_TEMPLATE),
            current_model=cfg.get("model", default_model),
            current_perplexity=cfg.get("perplexity_model", _DEFAULT_SETTINGS["soap_note"].get("perplexity_model", "sonar-reasoning-pro")),
            current_grok=cfg.get("grok_model", _DEFAULT_SETTINGS["soap_note"].get("grok_model", "grok-1")),
            save_callback=self.save_soap_settings,
            current_ollama=cfg.get("ollama_model", _DEFAULT_SETTINGS["soap_note"].get("ollama_model", "llama3")),
            current_system_prompt=cfg.get("system_message", default_system_prompt),
            current_anthropic=cfg.get("anthropic_model", _DEFAULT_SETTINGS["soap_note"].get("anthropic_model", "claude-3-sonnet-20240229")),
            current_gemini=cfg.get("gemini_model", _DEFAULT_SETTINGS["soap_note"].get("gemini_model", "gemini-1.5-flash"))
        )

    def show_referral_settings_dialog(self) -> None:
        """Show the referral settings dialog."""
        from settings.settings import SETTINGS, _DEFAULT_SETTINGS
        from ui.dialogs.dialogs import show_settings_dialog

        cfg = SETTINGS.get("referral", {})
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
            current_perplexity=cfg.get("perplexity_model", _DEFAULT_SETTINGS["referral"].get("perplexity_model", "sonar-reasoning-pro")),
            current_grok=cfg.get("grok_model", _DEFAULT_SETTINGS["referral"].get("grok_model", "grok-1")),
            save_callback=self.save_referral_settings,
            current_ollama=cfg.get("ollama_model", _DEFAULT_SETTINGS["referral"].get("ollama_model", "llama3")),
            current_system_prompt=cfg.get("system_message", default_system_prompt),
            current_anthropic=cfg.get("anthropic_model", _DEFAULT_SETTINGS["referral"].get("anthropic_model", "claude-3-sonnet-20240229")),
            current_gemini=cfg.get("gemini_model", _DEFAULT_SETTINGS["referral"].get("gemini_model", "gemini-1.5-flash"))
        )

    def show_advanced_analysis_settings_dialog(self) -> None:
        """Show the advanced analysis settings dialog."""
        from settings.settings import SETTINGS, _DEFAULT_SETTINGS
        from ui.dialogs.dialogs import show_settings_dialog

        cfg = SETTINGS.get("advanced_analysis", {})
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
            current_perplexity=cfg.get("perplexity_model", _DEFAULT_SETTINGS["advanced_analysis"].get("perplexity_model", "sonar-reasoning-pro")),
            current_grok=cfg.get("grok_model", _DEFAULT_SETTINGS["advanced_analysis"].get("grok_model", "grok-1")),
            save_callback=self.save_advanced_analysis_settings,
            current_ollama=cfg.get("ollama_model", _DEFAULT_SETTINGS["advanced_analysis"].get("ollama_model", "llama3")),
            current_system_prompt=cfg.get("system_message", default_system_prompt),
            current_anthropic=cfg.get("anthropic_model", _DEFAULT_SETTINGS["advanced_analysis"].get("anthropic_model", "claude-3-sonnet-20240229")),
            current_gemini=cfg.get("gemini_model", _DEFAULT_SETTINGS["advanced_analysis"].get("gemini_model", "gemini-1.5-flash"))
        )

    def show_temperature_settings(self) -> None:
        """Show dialog to configure temperature settings for each AI provider."""
        from ui.dialogs.temperature_dialog import show_temperature_settings_dialog
        show_temperature_settings_dialog(self)
        self.status_manager.success("Temperature settings saved successfully")

    def show_agent_settings(self) -> None:
        """Show dialog to configure AI agent settings."""
        import logging
        logger = logging.getLogger(__name__)

        # Check if advanced settings should be shown based on a setting or default to basic
        from settings.settings import SETTINGS
        use_advanced = SETTINGS.get("use_advanced_agent_settings", True)

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

    def save_refine_settings(self, prompt: str, openai_model: str, perplexity_model: str,
                             grok_model: str, ollama_model: str, system_prompt: str,
                             anthropic_model: str, gemini_model: str = "") -> None:
        """Save refine text settings."""
        from settings.settings import save_settings, SETTINGS
        SETTINGS["refine_text"] = {
            "prompt": prompt,
            "system_message": system_prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model,
            "ollama_model": ollama_model,
            "anthropic_model": anthropic_model,
            "gemini_model": gemini_model
        }
        save_settings(SETTINGS)
        self.status_manager.success("Refine text settings saved successfully")

    def save_improve_settings(self, prompt: str, openai_model: str, perplexity_model: str,
                              grok_model: str, ollama_model: str, system_prompt: str,
                              anthropic_model: str, gemini_model: str = "") -> None:
        """Save improve text settings."""
        from settings.settings import save_settings, SETTINGS
        SETTINGS["improve_text"] = {
            "prompt": prompt,
            "system_message": system_prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model,
            "ollama_model": ollama_model,
            "anthropic_model": anthropic_model,
            "gemini_model": gemini_model
        }
        save_settings(SETTINGS)
        self.status_manager.success("Improve text settings saved successfully")

    def save_soap_settings(self, prompt: str, openai_model: str, perplexity_model: str,
                           grok_model: str, ollama_model: str, system_prompt: str,
                           anthropic_model: str, gemini_model: str = "") -> None:
        """Save SOAP note settings."""
        from settings.settings import save_settings, SETTINGS
        # Preserve existing temperature settings
        SETTINGS["soap_note"]["prompt"] = prompt
        SETTINGS["soap_note"]["system_message"] = system_prompt
        SETTINGS["soap_note"]["model"] = openai_model
        SETTINGS["soap_note"]["perplexity_model"] = perplexity_model
        SETTINGS["soap_note"]["grok_model"] = grok_model
        SETTINGS["soap_note"]["ollama_model"] = ollama_model
        SETTINGS["soap_note"]["anthropic_model"] = anthropic_model
        SETTINGS["soap_note"]["gemini_model"] = gemini_model
        save_settings(SETTINGS)
        self.status_manager.success("SOAP note settings saved successfully")

    def save_referral_settings(self, prompt: str, openai_model: str, perplexity_model: str,
                               grok_model: str, ollama_model: str, system_prompt: str,
                               anthropic_model: str, gemini_model: str = "") -> None:
        """Save referral settings."""
        from settings.settings import save_settings, SETTINGS
        # Preserve existing temperature settings
        SETTINGS["referral"]["prompt"] = prompt
        SETTINGS["referral"]["system_message"] = system_prompt
        SETTINGS["referral"]["model"] = openai_model
        SETTINGS["referral"]["perplexity_model"] = perplexity_model
        SETTINGS["referral"]["grok_model"] = grok_model
        SETTINGS["referral"]["ollama_model"] = ollama_model
        SETTINGS["referral"]["anthropic_model"] = anthropic_model
        SETTINGS["referral"]["gemini_model"] = gemini_model
        save_settings(SETTINGS)
        self.status_manager.success("Referral settings saved successfully")

    def save_advanced_analysis_settings(self, prompt: str, openai_model: str, perplexity_model: str,
                                        grok_model: str, ollama_model: str, system_prompt: str,
                                        anthropic_model: str, gemini_model: str = "") -> None:
        """Save advanced analysis settings."""
        from settings.settings import save_settings, SETTINGS
        # Preserve existing temperature settings
        SETTINGS["advanced_analysis"]["prompt"] = prompt
        SETTINGS["advanced_analysis"]["system_message"] = system_prompt
        SETTINGS["advanced_analysis"]["model"] = openai_model
        SETTINGS["advanced_analysis"]["perplexity_model"] = perplexity_model
        SETTINGS["advanced_analysis"]["grok_model"] = grok_model
        SETTINGS["advanced_analysis"]["ollama_model"] = ollama_model
        SETTINGS["advanced_analysis"]["anthropic_model"] = anthropic_model
        SETTINGS["advanced_analysis"]["gemini_model"] = gemini_model
        save_settings(SETTINGS)
        self.status_manager.success("Advanced analysis settings saved successfully")

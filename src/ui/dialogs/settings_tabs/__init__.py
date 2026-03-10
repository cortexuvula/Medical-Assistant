"""
Settings tab mixins for UnifiedSettingsDialog.

Each mixin provides a single tab's creation logic, keeping the main
dialog class focused on orchestration and save/reset logic.
"""

from .api_keys_tab import ApiKeysTabMixin
from .audio_stt_tab import AudioSttTabMixin
from .ai_models_tab import AiModelsTabMixin
from .prompts_tab import PromptsTabMixin
from .storage_tab import StorageTabMixin
from .rag_guidelines_tab import RagGuidelinesTabMixin
from .general_tab import GeneralTabMixin

__all__ = [
    "ApiKeysTabMixin",
    "AudioSttTabMixin",
    "AiModelsTabMixin",
    "PromptsTabMixin",
    "StorageTabMixin",
    "RagGuidelinesTabMixin",
    "GeneralTabMixin",
]

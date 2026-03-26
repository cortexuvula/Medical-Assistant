"""
Application Protocol for Mixin Type Safety.

Defines the AppProtocol that specifies the interface mixins expect from the
main application object. This enables static type checking across mixin
boundaries without introducing circular imports.

Phase 9.1 of technical debt remediation.

Usage in mixins:
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from core.protocols import AppProtocol

    class SomeMixin:
        # Type hint for self when used as a mixin
        self: AppProtocol

Or for method signatures:
    def some_helper(app: AppProtocol) -> None: ...
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional, Protocol, runtime_checkable


@runtime_checkable
class AppProtocol(Protocol):
    """Protocol defining the interface that mixins expect from the app object.

    This captures the most commonly accessed attributes across all mixins,
    handlers, and controllers. Types use ``Any`` where importing the real
    type would cause circular imports or pull in heavyweight UI dependencies.
    """

    # ------------------------------------------------------------------
    # Core managers
    # ------------------------------------------------------------------
    recording_manager: Any  # RecordingManager
    audio_handler: Any  # AudioHandler
    audio_state_manager: Any  # AudioStateManager
    status_manager: Any  # StatusManager
    ui_state_manager: Any  # UIStateManager
    db: Any  # Database
    config_controller: Any  # ConfigController
    recording_controller: Any  # RecordingController
    processing_queue: Any  # ProcessingQueue
    processing_controller: Any  # ProcessingController
    document_generators: Any  # DocumentGenerators
    chat_processor: Any  # ChatProcessor
    soap_processor: Any  # SOAPProcessor
    ai_processor: Any  # AIProcessor
    notification_manager: Any  # NotificationManager
    theme_manager: Any  # ThemeManager
    menu_manager: Any  # MenuManager
    file_processor: Any  # FileProcessor
    text_processor: Any  # TextProcessor
    soap_audio_processor: Any  # SOAPAudioProcessor
    periodic_analyzer: Any  # PeriodicAnalyzer

    # ------------------------------------------------------------------
    # Text widgets (tkinter.Text or similar)
    # ------------------------------------------------------------------
    transcript_text: Any
    soap_text: Any
    referral_text: Any
    letter_text: Any
    context_text: Any

    # ------------------------------------------------------------------
    # UI components
    # ------------------------------------------------------------------
    notebook: Any  # ttkbootstrap.Notebook (text-editor tabs)
    workflow_notebook: Any  # ttkbootstrap.Notebook (workflow tabs)
    progress_bar: Any  # ttk.Progressbar
    mic_combobox: Any  # ttk.Combobox
    provider_combobox: Any  # ttk.Combobox
    stt_combobox: Any  # ttk.Combobox

    # ------------------------------------------------------------------
    # Application state
    # ------------------------------------------------------------------
    current_recording_id: Optional[int]
    selected_recording_id: Optional[int]
    current_theme: str
    soap_recording: bool
    listening: bool

    # ------------------------------------------------------------------
    # API keys
    # ------------------------------------------------------------------
    openai_api_key: Optional[str]
    anthropic_api_key: Optional[str]
    gemini_api_key: Optional[str]
    groq_api_key: Optional[str]
    deepgram_api_key: Optional[str]
    elevenlabs_api_key: Optional[str]
    cerebras_api_key: Optional[str]
    modulate_api_key: Optional[str]

    # ------------------------------------------------------------------
    # Thread-pool executors
    # ------------------------------------------------------------------
    executor: ThreadPoolExecutor
    io_executor: ThreadPoolExecutor

    # ------------------------------------------------------------------
    # Tkinter methods (inherited from tk.Tk / ttkbootstrap.Window)
    # ------------------------------------------------------------------
    def after(self, ms: int, func: Callable[..., Any] | None = ..., *args: Any) -> str:
        """Schedule a callback after a delay in milliseconds."""
        ...

    def after_cancel(self, id: str) -> None:
        """Cancel a previously scheduled callback."""
        ...

    def bind(self, sequence: str, func: Callable[..., Any] | None = ..., add: str | None = ...) -> str:
        """Bind a callback to a widget event."""
        ...

    def event_generate(self, sequence: str, **kw: Any) -> None:
        """Generate a synthetic event."""
        ...

    def update_idletasks(self) -> None:
        """Process pending idle callbacks."""
        ...

    def winfo_exists(self) -> bool:
        """Return True if the widget exists."""
        ...

    # ------------------------------------------------------------------
    # Key application methods used by mixins
    # ------------------------------------------------------------------
    def update_status(self, message: str, msg_type: str = "info") -> None:
        """Update the status bar message."""
        ...

    def new_session(self) -> None:
        """Start a new recording/editing session."""
        ...

    def save_text(self) -> None:
        """Save current text content to the database."""
        ...

    def toggle_theme(self) -> None:
        """Toggle between light and dark themes."""
        ...

    def show_preferences(self) -> None:
        """Open the unified preferences dialog."""
        ...

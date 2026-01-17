"""
RSVP Reading Mode Panel

Handles the reading mode UI for the RSVP reader including:
- Canvas-based word display with ORP highlighting
- Control panel (play/pause, speed, navigation)
- Progress tracking and statistics
- Keyboard shortcuts
"""

import tkinter as tk
import ttkbootstrap as ttk
import tkinter.font as tkfont
from typing import Callable, Optional, List
import time

from .core import RSVPEngine, RSVPSettings, RSVPTheme
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class ReadingModePanel:
    """Panel for RSVP reading mode - word display and controls."""

    def __init__(
        self,
        parent_frame: tk.Frame,
        dialog: tk.Toplevel,
        engine: RSVPEngine,
        settings: RSVPSettings,
        colors: dict,
        on_back: Callable[[], None],
        on_theme_toggle: Callable[[], None],
        on_settings_save: Callable[[], None]
    ):
        """Initialize the reading mode panel.

        Args:
            parent_frame: Parent frame to build UI in
            dialog: The toplevel dialog window (for keyboard bindings)
            engine: RSVPEngine instance with parsed text
            settings: RSVPSettings instance
            colors: Color dictionary from RSVPTheme
            on_back: Callback when user clicks "Back to Input"
            on_theme_toggle: Callback for theme toggle
            on_settings_save: Callback to save settings
        """
        self.parent = parent_frame
        self.dialog = dialog
        self.engine = engine
        self.settings = settings
        self.colors = colors
        self.on_back = on_back
        self.on_theme_toggle = on_theme_toggle
        self.on_settings_save = on_settings_save

        # Playback state
        self.current_index = 0
        self.is_playing = False
        self.timer_id: Optional[str] = None

        # Statistics
        self.start_time: Optional[float] = None
        self.wpm_history: List[int] = []

        # Fullscreen state (managed externally but tracked here)
        self.is_fullscreen = False

        # UI widgets (initialized in _create_ui)
        self.canvas: Optional[tk.Canvas] = None
        self.play_btn: Optional[ttk.Button] = None
        self.speed_var: Optional[tk.IntVar] = None
        self.wpm_label: Optional[ttk.Label] = None
        self.font_var: Optional[tk.IntVar] = None
        self.font_label: Optional[ttk.Label] = None
        self.chunk_var: Optional[tk.IntVar] = None
        self.progress_var: Optional[tk.DoubleVar] = None
        self.progress_bar: Optional[ttk.Progressbar] = None
        self.word_count_display: Optional[tk.Label] = None
        self.time_label: Optional[tk.Label] = None
        self.context_label: Optional[tk.Label] = None
        self.context_btn: Optional[ttk.Button] = None
        self.audio_btn: Optional[ttk.Button] = None
        self.theme_btn: Optional[ttk.Button] = None

        # Frame references for theme updates
        self.context_frame: Optional[tk.Frame] = None
        self.display_frame: Optional[tk.Frame] = None
        self.control_frame: Optional[tk.Frame] = None
        self.progress_frame: Optional[tk.Frame] = None
        self.row1: Optional[tk.Frame] = None
        self.row2: Optional[tk.Frame] = None
        self.speed_frame: Optional[tk.Frame] = None
        self.nav_frame: Optional[tk.Frame] = None
        self.font_frame: Optional[tk.Frame] = None
        self.chunk_frame: Optional[tk.Frame] = None
        self.settings_frame: Optional[tk.Frame] = None

        self._create_ui()
        self._bind_keys()

    def _create_ui(self) -> None:
        """Create the reading mode UI."""
        # Context display area
        self.context_frame = tk.Frame(self.parent, bg=self.colors['bg'], height=80)
        self.context_frame.pack(fill=tk.X, padx=20, pady=(15, 0))
        self.context_frame.pack_propagate(False)

        self.context_label = tk.Label(
            self.context_frame,
            text="",
            bg=self.colors['bg'],
            fg=self.colors['context'],
            font=("Helvetica", 10),
            wraplength=820,
            justify=tk.CENTER
        )
        self.context_label.pack(expand=True, fill=tk.BOTH, padx=15, pady=8)

        # Word display area
        self.display_frame = tk.Frame(self.parent, bg=self.colors['bg'], height=250)
        self.display_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self.display_frame.pack_propagate(False)

        self.canvas = tk.Canvas(
            self.display_frame,
            bg=self.colors['bg'],
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind('<Configure>', self._on_resize)

        # Control panel
        self._create_control_panel()

        # Progress section
        self._create_progress_section()

        # Back button
        back_frame = tk.Frame(self.parent, bg=self.colors['bg'])
        back_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(
            back_frame,
            text="<< Back to Input",
            command=self._on_back_click,
            width=15,
            bootstyle="secondary"
        ).pack(side=tk.LEFT, padx=10)

        # Display first word
        self._display_word()
        self._update_progress()

        # Focus dialog for keyboard input
        self.dialog.focus_set()

    def _create_control_panel(self) -> None:
        """Create the control panel."""
        self.control_frame = tk.Frame(self.parent, bg=self.colors['control_bg'], height=100)
        self.control_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        self.control_frame.pack_propagate(False)

        # Row 1: Play, Speed, Navigation
        self.row1 = tk.Frame(self.control_frame, bg=self.colors['control_bg'])
        self.row1.pack(fill=tk.X, pady=(8, 4))

        row1_inner = tk.Frame(self.row1, bg=self.colors['control_bg'])
        row1_inner.pack(expand=True)

        # Play/Pause button
        self.play_btn = ttk.Button(
            row1_inner,
            text="Play",
            command=self._toggle_playback,
            width=10,
            bootstyle="success"
        )
        self.play_btn.pack(side=tk.LEFT, padx=8)

        # Speed control
        self.speed_frame = tk.Frame(row1_inner, bg=self.colors['control_bg'])
        self.speed_frame.pack(side=tk.LEFT, padx=8)

        ttk.Label(
            self.speed_frame,
            text="Speed:",
            background=self.colors['control_bg'],
            foreground=self.colors['text']
        ).pack(side=tk.LEFT, padx=(0, 3))

        ttk.Button(
            self.speed_frame,
            text="-",
            command=self._speed_down,
            width=2,
            bootstyle="secondary"
        ).pack(side=tk.LEFT)

        self.speed_var = tk.IntVar(value=self.settings.wpm)
        speed_slider = ttk.Scale(
            self.speed_frame,
            from_=self.settings.MIN_WPM,
            to=self.settings.MAX_WPM,
            orient=tk.HORIZONTAL,
            length=100,
            variable=self.speed_var,
            command=self._on_speed_change
        )
        speed_slider.pack(side=tk.LEFT, padx=2)

        ttk.Button(
            self.speed_frame,
            text="+",
            command=self._speed_up,
            width=2,
            bootstyle="secondary"
        ).pack(side=tk.LEFT)

        self.wpm_label = ttk.Label(
            self.speed_frame,
            text=f"{self.settings.wpm} WPM",
            width=9,
            background=self.colors['control_bg'],
            foreground=self.colors['text']
        )
        self.wpm_label.pack(side=tk.LEFT, padx=(5, 0))

        # Navigation buttons
        self.nav_frame = tk.Frame(row1_inner, bg=self.colors['control_bg'])
        self.nav_frame.pack(side=tk.LEFT, padx=8)

        for symbol, cmd in [("<<", self._go_to_start), ("<", self._prev_word),
                           (">", self._next_word), (">>", self._go_to_end)]:
            ttk.Button(
                self.nav_frame,
                text=symbol,
                command=cmd,
                width=3,
                bootstyle="secondary"
            ).pack(side=tk.LEFT, padx=1)

        # Row 2: Font, Chunk, Settings
        self.row2 = tk.Frame(self.control_frame, bg=self.colors['control_bg'])
        self.row2.pack(fill=tk.X, pady=(4, 8))

        row2_inner = tk.Frame(self.row2, bg=self.colors['control_bg'])
        row2_inner.pack(expand=True)

        # Font size control
        self.font_frame = tk.Frame(row2_inner, bg=self.colors['control_bg'])
        self.font_frame.pack(side=tk.LEFT, padx=8)

        ttk.Label(
            self.font_frame,
            text="Font:",
            background=self.colors['control_bg'],
            foreground=self.colors['text']
        ).pack(side=tk.LEFT, padx=(0, 3))

        self.font_var = tk.IntVar(value=self.settings.font_size)
        font_slider = ttk.Scale(
            self.font_frame,
            from_=self.settings.MIN_FONT_SIZE,
            to=self.settings.MAX_FONT_SIZE,
            orient=tk.HORIZONTAL,
            length=80,
            variable=self.font_var,
            command=self._on_font_change
        )
        font_slider.pack(side=tk.LEFT, padx=2)

        self.font_label = ttk.Label(
            self.font_frame,
            text=f"{self.settings.font_size}pt",
            width=5,
            background=self.colors['control_bg'],
            foreground=self.colors['text']
        )
        self.font_label.pack(side=tk.LEFT, padx=(3, 0))

        # Chunk size control
        self.chunk_frame = tk.Frame(row2_inner, bg=self.colors['control_bg'])
        self.chunk_frame.pack(side=tk.LEFT, padx=8)

        ttk.Label(
            self.chunk_frame,
            text="Words:",
            background=self.colors['control_bg'],
            foreground=self.colors['text']
        ).pack(side=tk.LEFT, padx=(0, 3))

        self.chunk_var = tk.IntVar(value=self.settings.chunk_size)
        for i in [1, 2, 3]:
            rb = ttk.Radiobutton(
                self.chunk_frame,
                text=str(i),
                variable=self.chunk_var,
                value=i,
                command=self._on_chunk_change,
                bootstyle="info-toolbutton"
            )
            rb.pack(side=tk.LEFT, padx=1)

        # Settings buttons
        self.settings_frame = tk.Frame(row2_inner, bg=self.colors['control_bg'])
        self.settings_frame.pack(side=tk.LEFT, padx=8)

        # Theme toggle
        self.theme_btn = ttk.Button(
            self.settings_frame,
            text="Light" if self.settings.dark_theme else "Dark",
            command=self.on_theme_toggle,
            width=6,
            bootstyle="secondary"
        )
        self.theme_btn.pack(side=tk.LEFT, padx=2)

        # Fullscreen toggle
        ttk.Button(
            self.settings_frame,
            text="F11",
            command=self._toggle_fullscreen,
            width=4,
            bootstyle="secondary"
        ).pack(side=tk.LEFT, padx=2)

        # Context toggle
        self.context_btn = ttk.Button(
            self.settings_frame,
            text="Ctx*" if self.settings.show_context else "Ctx",
            command=self._toggle_context,
            width=4,
            bootstyle="info" if self.settings.show_context else "secondary"
        )
        self.context_btn.pack(side=tk.LEFT, padx=2)

        # Audio toggle
        self.audio_btn = ttk.Button(
            self.settings_frame,
            text="Snd*" if self.settings.audio_cue else "Snd",
            command=self._toggle_audio_cue,
            width=4,
            bootstyle="info" if self.settings.audio_cue else "secondary"
        )
        self.audio_btn.pack(side=tk.LEFT, padx=2)

        # Help button
        ttk.Button(
            self.settings_frame,
            text="?",
            command=self._show_shortcuts_help,
            width=2,
            bootstyle="secondary"
        ).pack(side=tk.LEFT, padx=2)

    def _create_progress_section(self) -> None:
        """Create the progress bar and info section."""
        self.progress_frame = tk.Frame(self.parent, bg=self.colors['progress_bg'], height=60)
        self.progress_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.progress_frame.pack_propagate(False)

        progress_inner = tk.Frame(self.progress_frame, bg=self.colors['progress_bg'])
        progress_inner.pack(fill=tk.X, padx=15, pady=10)

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            progress_inner,
            variable=self.progress_var,
            maximum=100,
            length=500,
            mode='determinate',
            bootstyle="info"
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Info labels
        info_frame = tk.Frame(progress_inner, bg=self.colors['progress_bg'])
        info_frame.pack(side=tk.RIGHT, padx=(15, 0))

        self.word_count_display = tk.Label(
            info_frame,
            text=f"0 / {self.engine.get_word_count()} words",
            bg=self.colors['progress_bg'],
            fg=self.colors['text']
        )
        self.word_count_display.pack(anchor=tk.E)

        self.time_label = tk.Label(
            info_frame,
            text="",
            bg=self.colors['progress_bg'],
            fg=self.colors['text']
        )
        self.time_label.pack(anchor=tk.E)

    def _bind_keys(self) -> None:
        """Bind keyboard shortcuts."""
        self.dialog.bind('<space>', lambda e: self._toggle_playback())
        self.dialog.bind('<Up>', lambda e: self._speed_up())
        self.dialog.bind('<Down>', lambda e: self._speed_down())
        self.dialog.bind('<Left>', lambda e: self._prev_word())
        self.dialog.bind('<Right>', lambda e: self._next_word())
        self.dialog.bind('<Home>', lambda e: self._go_to_start())
        self.dialog.bind('<End>', lambda e: self._go_to_end())
        self.dialog.bind('<Escape>', lambda e: self._handle_escape())
        self.dialog.bind('<F11>', lambda e: self._toggle_fullscreen())
        self.dialog.bind('<t>', lambda e: self.on_theme_toggle())
        self.dialog.bind('<T>', lambda e: self.on_theme_toggle())
        self.dialog.bind('<Key-1>', lambda e: self._set_chunk_size(1))
        self.dialog.bind('<Key-2>', lambda e: self._set_chunk_size(2))
        self.dialog.bind('<Key-3>', lambda e: self._set_chunk_size(3))

    # =========================================================================
    # WORD DISPLAY (ORP)
    # =========================================================================

    def _display_word(self) -> None:
        """Display current word(s) with ORP highlighting."""
        self.canvas.delete("all")

        if self.current_index >= self.engine.get_word_count():
            self._show_complete()
            return

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width < 10 or canvas_height < 10:
            self.dialog.after(50, self._display_word)
            return

        # Get chunk of words
        chunk_words = self.engine.get_chunk(self.current_index, self.settings.chunk_size)

        if self.settings.chunk_size == 1:
            self._display_single_word(chunk_words[0], canvas_width, canvas_height)
        else:
            self._display_chunk(chunk_words, canvas_width, canvas_height)

        self._update_context_display()

    def _display_single_word(self, word: str, canvas_width: int, canvas_height: int) -> None:
        """Display a single word with ORP highlighting."""
        orp_pos = RSVPEngine.calculate_orp(word)
        font = tkfont.Font(family="Helvetica", size=self.settings.font_size, weight="bold")

        pre = word[:orp_pos]
        orp_char = word[orp_pos] if orp_pos < len(word) else ''
        post = word[orp_pos + 1:] if orp_pos + 1 < len(word) else ''

        orp_width = font.measure(orp_char)
        center_x = canvas_width // 2
        center_y = canvas_height // 2

        # Draw vertical ORP indicator line
        self.canvas.create_line(
            center_x, 10, center_x, canvas_height - 10,
            fill=self.colors['orp'], width=2, dash=(4, 4)
        )

        # Draw triangle marker
        self.canvas.create_polygon(
            center_x - 8, 5,
            center_x + 8, 5,
            center_x, 15,
            fill=self.colors['orp']
        )

        orp_left_edge = center_x - (orp_width // 2)
        orp_right_edge = center_x + (orp_width // 2)

        # Draw pre-ORP text
        if pre:
            self.canvas.create_text(
                orp_left_edge, center_y,
                text=pre, font=font, fill=self.colors['text'], anchor=tk.E
            )

        # Draw ORP character (highlighted)
        if orp_char:
            self.canvas.create_text(
                center_x, center_y,
                text=orp_char, font=font, fill=self.colors['orp'], anchor=tk.CENTER
            )

        # Draw post-ORP text
        if post:
            self.canvas.create_text(
                orp_right_edge, center_y,
                text=post, font=font, fill=self.colors['text'], anchor=tk.W
            )

    def _display_chunk(self, words: List[str], canvas_width: int, canvas_height: int) -> None:
        """Display multiple words with ORP on focus word."""
        font_size = max(self.settings.MIN_FONT_SIZE, self.settings.font_size - 8)
        font = tkfont.Font(family="Helvetica", size=font_size, weight="bold")

        center_x = canvas_width // 2
        center_y = canvas_height // 2

        focus_idx = len(words) // 2
        focus_word = words[focus_idx]
        orp_pos = RSVPEngine.calculate_orp(focus_word)

        spacing = "  "
        word_widths = [font.measure(w) for w in words]
        spacing_width = font.measure(spacing)

        focus_word_start = sum(word_widths[:focus_idx]) + spacing_width * focus_idx
        pre_orp = focus_word[:orp_pos]
        orp_char = focus_word[orp_pos] if orp_pos < len(focus_word) else ''
        orp_char_width = font.measure(orp_char)
        pre_orp_width = font.measure(pre_orp)
        orp_center_in_chunk = focus_word_start + pre_orp_width + orp_char_width // 2
        start_x = center_x - orp_center_in_chunk

        # Draw ORP indicator
        self.canvas.create_line(
            center_x, 10, center_x, canvas_height - 10,
            fill=self.colors['orp'], width=2, dash=(4, 4)
        )
        self.canvas.create_polygon(
            center_x - 8, 5,
            center_x + 8, 5,
            center_x, 15,
            fill=self.colors['orp']
        )

        current_x = start_x
        for i, word in enumerate(words):
            if i == focus_idx:
                pre = word[:orp_pos]
                orp = word[orp_pos] if orp_pos < len(word) else ''
                post = word[orp_pos + 1:] if orp_pos + 1 < len(word) else ''

                if pre:
                    self.canvas.create_text(current_x, center_y, text=pre, font=font,
                                          fill=self.colors['text'], anchor=tk.W)
                    current_x += font.measure(pre)
                if orp:
                    self.canvas.create_text(current_x, center_y, text=orp, font=font,
                                          fill=self.colors['orp'], anchor=tk.W)
                    current_x += font.measure(orp)
                if post:
                    self.canvas.create_text(current_x, center_y, text=post, font=font,
                                          fill=self.colors['text'], anchor=tk.W)
                    current_x += font.measure(post)
            else:
                self.canvas.create_text(current_x, center_y, text=word, font=font,
                                       fill=self.colors['text'], anchor=tk.W)
                current_x += word_widths[i]

            if i < len(words) - 1:
                current_x += spacing_width

    def _update_context_display(self) -> None:
        """Update the sentence context display."""
        if not self.settings.show_context:
            self.context_label.config(text="")
            return

        sentence = self.engine.get_sentence_for_index(self.current_index)
        max_length = 200
        if len(sentence) > max_length:
            sentence_start = self.engine.get_sentence_start_index(self.current_index)
            words_before = self.current_index - sentence_start
            approx_char_pos = words_before * 6
            half_window = max_length // 2
            start = max(0, approx_char_pos - half_window)
            end = min(len(sentence), start + max_length)
            if end == len(sentence):
                start = max(0, end - max_length)
            truncated = sentence[start:end]
            if start > 0:
                truncated = "..." + truncated.lstrip()
            if end < len(sentence):
                truncated = truncated.rstrip() + "..."
            sentence = truncated

        self.context_label.config(text=sentence)

    def _show_complete(self) -> None:
        """Show completion message with statistics."""
        self.canvas.delete("all")
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        font = tkfont.Font(family="Helvetica", size=36, weight="bold")
        small_font = tkfont.Font(family="Helvetica", size=14)

        self.canvas.create_text(
            canvas_width // 2, canvas_height // 2 - 40,
            text="Complete!",
            font=font, fill=self.colors['text']
        )

        if self.start_time and self.wpm_history:
            elapsed = time.time() - self.start_time
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            avg_wpm = sum(self.wpm_history) // len(self.wpm_history)
            word_count = self.engine.get_word_count()
            stats_text = f"Time: {minutes}:{seconds:02d} | Avg: {avg_wpm} WPM | {word_count} words"
            self.canvas.create_text(
                canvas_width // 2, canvas_height // 2 + 10,
                text=stats_text, font=small_font, fill="#888888"
            )

        self.canvas.create_text(
            canvas_width // 2, canvas_height // 2 + 50,
            text="Press Home to restart or Escape to go back",
            font=small_font, fill="#666666"
        )

    # =========================================================================
    # PLAYBACK CONTROL
    # =========================================================================

    def _update_progress(self) -> None:
        """Update progress bar and info labels."""
        total = self.engine.get_word_count()
        current = min(self.current_index + 1, total) if total > 0 else 0

        progress = (current / total) * 100 if total > 0 else 0
        self.progress_var.set(progress)
        self.word_count_display.config(text=f"{current} / {total} words")

        time_str = RSVPEngine.calculate_time_remaining(
            max(0, total - current),
            self.settings.wpm
        )
        self.time_label.config(text=time_str)

    def _toggle_playback(self) -> None:
        """Toggle between play and pause."""
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def play(self) -> None:
        """Start or resume playback."""
        if self.current_index >= self.engine.get_word_count():
            self.current_index = 0
            self._display_word()
            self._update_progress()

        if self.start_time is None:
            self.start_time = time.time()
            self.wpm_history = []

        self.is_playing = True
        self.play_btn.configure(text="Pause", bootstyle="warning")
        self._schedule_next_word()

    def pause(self) -> None:
        """Pause playback."""
        self.is_playing = False

        if self.play_btn:
            try:
                self.play_btn.configure(text="Play", bootstyle="success")
            except tk.TclError:
                pass

        if self.timer_id:
            try:
                self.dialog.after_cancel(self.timer_id)
            except tk.TclError:
                pass
            self.timer_id = None

    def _schedule_next_word(self) -> None:
        """Schedule the next word display."""
        if not self.is_playing:
            return
        self.wpm_history.append(self.settings.wpm)
        delay = self.engine.calculate_delay_ms(self.current_index, self.settings.wpm)
        self.timer_id = self.dialog.after(delay, self._advance_word)

    def _advance_word(self) -> None:
        """Move to next word(s)."""
        self.current_index += self.settings.chunk_size

        if self.current_index >= self.engine.get_word_count():
            self.pause()
            self._show_complete()
            self._update_progress()
            return

        self._display_word()
        self._update_progress()
        self._schedule_next_word()

    def _prev_word(self) -> None:
        """Go to previous word(s)."""
        if self.current_index > 0:
            self.current_index = max(0, self.current_index - self.settings.chunk_size)
            self._display_word()
            self._update_progress()

    def _next_word(self) -> None:
        """Go to next word(s)."""
        word_count = self.engine.get_word_count()
        if self.current_index < word_count - 1:
            self.current_index = min(word_count - 1, self.current_index + self.settings.chunk_size)
            self._display_word()
            self._update_progress()

    def _go_to_start(self) -> None:
        """Go to the first word."""
        self.current_index = 0
        self.start_time = None
        self.wpm_history = []
        self._display_word()
        self._update_progress()

    def _go_to_end(self) -> None:
        """Go to the last word."""
        self.current_index = self.engine.get_word_count() - 1
        self._display_word()
        self._update_progress()

    # =========================================================================
    # SETTINGS CONTROLS
    # =========================================================================

    def _speed_up(self) -> None:
        """Increase reading speed."""
        new_wpm = min(self.settings.wpm + self.settings.WPM_STEP, self.settings.MAX_WPM)
        self._set_speed(new_wpm)

    def _speed_down(self) -> None:
        """Decrease reading speed."""
        new_wpm = max(self.settings.wpm - self.settings.WPM_STEP, self.settings.MIN_WPM)
        self._set_speed(new_wpm)

    def _set_speed(self, wpm: int) -> None:
        """Set the reading speed."""
        self.settings.wpm = wpm
        self.speed_var.set(wpm)
        self.wpm_label.config(text=f"{wpm} WPM")
        self._update_progress()
        self.on_settings_save()

    def _on_speed_change(self, value: str) -> None:
        """Handle speed slider change."""
        try:
            wpm = int(float(value))
            wpm = round(wpm / self.settings.WPM_STEP) * self.settings.WPM_STEP
            wpm = max(self.settings.MIN_WPM, min(self.settings.MAX_WPM, wpm))
            self.settings.wpm = wpm
            self.wpm_label.config(text=f"{wpm} WPM")
            self._update_progress()
            self.on_settings_save()
        except ValueError:
            pass

    def _on_font_change(self, value: str) -> None:
        """Handle font size slider change."""
        try:
            size = int(float(value))
            self.settings.font_size = self.settings.validate_font_size(size)
            self.font_label.config(text=f"{self.settings.font_size}pt")
            self._display_word()
            self.on_settings_save()
        except ValueError:
            pass

    def _on_chunk_change(self) -> None:
        """Handle chunk size change."""
        self.settings.chunk_size = self.chunk_var.get()
        self._display_word()
        self.on_settings_save()

    def _set_chunk_size(self, size: int) -> None:
        """Set chunk size from keyboard shortcut."""
        self.settings.chunk_size = size
        self.chunk_var.set(size)
        self._display_word()
        self.on_settings_save()

    def _toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode."""
        self.is_fullscreen = not self.is_fullscreen
        self.dialog.attributes('-fullscreen', self.is_fullscreen)

    def _toggle_context(self) -> None:
        """Toggle sentence context display."""
        self.settings.show_context = not self.settings.show_context
        self.context_btn.configure(
            text="Ctx*" if self.settings.show_context else "Ctx",
            bootstyle="info" if self.settings.show_context else "secondary"
        )
        self._update_context_display()
        self.on_settings_save()

    def _toggle_audio_cue(self) -> None:
        """Toggle audio cue."""
        self.settings.audio_cue = not self.settings.audio_cue
        self.audio_btn.configure(
            text="Snd*" if self.settings.audio_cue else "Snd",
            bootstyle="info" if self.settings.audio_cue else "secondary"
        )
        self.on_settings_save()

    def _show_shortcuts_help(self) -> None:
        """Show keyboard shortcuts help."""
        help_text = """RSVP Reader Keyboard Shortcuts

PLAYBACK
  Space          Play / Pause
  Up / Down      Increase / Decrease speed
  Left / Right   Previous / Next word
  Home / End     Jump to start / end

DISPLAY
  F11            Toggle fullscreen
  T              Toggle light/dark theme
  1 / 2 / 3      Set chunk size (words at once)

NAVIGATION
  Escape         Exit fullscreen (or go back)
  Ctrl+Enter     Start reading (input mode)

SETTINGS BUTTONS
  Light/Dark     Toggle theme
  F11            Fullscreen mode
  Ctx            Show sentence context
  Snd            Audio cue on sections"""

        help_popup = tk.Toplevel(self.dialog)
        help_popup.title("Keyboard Shortcuts")
        help_popup.geometry("380x420")
        help_popup.resizable(False, False)
        help_popup.transient(self.dialog)

        help_popup.update_idletasks()
        x = self.dialog.winfo_x() + (self.dialog.winfo_width() - 380) // 2
        y = self.dialog.winfo_y() + (self.dialog.winfo_height() - 420) // 2
        help_popup.geometry(f"+{x}+{y}")

        help_popup.configure(bg=self.colors['bg'])

        text_widget = tk.Text(
            help_popup,
            wrap=tk.WORD,
            bg=self.colors['bg'],
            fg=self.colors['text'],
            font=("Consolas", 10),
            relief=tk.FLAT,
            padx=15,
            pady=15,
            highlightthickness=0
        )
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))
        text_widget.insert("1.0", help_text)
        text_widget.config(state=tk.DISABLED)

        ttk.Button(
            help_popup,
            text="Close",
            command=help_popup.destroy,
            bootstyle="secondary"
        ).pack(pady=(5, 15))

        help_popup.bind('<Escape>', lambda e: help_popup.destroy())
        help_popup.focus_set()

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    def _handle_escape(self) -> None:
        """Handle Escape key."""
        if self.is_fullscreen:
            self._toggle_fullscreen()
        else:
            self._on_back_click()

    def _on_back_click(self) -> None:
        """Handle back button click."""
        self.pause()
        self.on_back()

    def _on_resize(self, event) -> None:
        """Handle canvas resize."""
        if hasattr(self, 'canvas') and self.engine.get_word_count() > 0:
            self._display_word()

    def update_colors(self, colors: dict) -> None:
        """Update colors for theme change."""
        self.colors = colors

        # Update main frames
        if self.context_frame:
            self.context_frame.configure(bg=colors['bg'])
        if self.context_label:
            self.context_label.configure(bg=colors['bg'], fg=colors['context'])
        if self.display_frame:
            self.display_frame.configure(bg=colors['bg'])
        if self.canvas:
            self.canvas.configure(bg=colors['bg'])
        if self.control_frame:
            self.control_frame.configure(bg=colors['control_bg'])
        if self.progress_frame:
            self.progress_frame.configure(bg=colors['progress_bg'])

        # Update control rows
        for frame in [self.row1, self.row2, self.speed_frame, self.nav_frame,
                      self.font_frame, self.chunk_frame, self.settings_frame]:
            if frame:
                frame.configure(bg=colors['control_bg'])
                for child in frame.winfo_children():
                    if isinstance(child, tk.Frame):
                        child.configure(bg=colors['control_bg'])

        # Update info labels
        if self.word_count_display:
            self.word_count_display.configure(bg=colors['progress_bg'], fg=colors['text'])
        if self.time_label:
            self.time_label.configure(bg=colors['progress_bg'], fg=colors['text'])

        # Redraw word display
        self._display_word()

    def update_theme_button(self, is_dark: bool) -> None:
        """Update theme button text."""
        if self.theme_btn:
            self.theme_btn.configure(text="Light" if is_dark else "Dark")


__all__ = ['ReadingModePanel']

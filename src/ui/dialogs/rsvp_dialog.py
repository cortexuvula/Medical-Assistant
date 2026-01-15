"""
RSVP (Rapid Serial Visual Presentation) Dialog

Displays text word-by-word at configurable speed for speed reading.
Uses ORP (Optimal Recognition Point) highlighting for improved comprehension.

Features:
- Persistent WPM setting
- Fullscreen mode (F11)
- Section navigation (jump to SOAP sections)
- Chunk mode (1-3 words at a time)
- Adjustable font size
- Auto-start option
- Light/Dark theme toggle
- Reading statistics
- Sentence context display
- Audio cue on section changes

Code Structure:
- Lines 30-60: Class constants (colors, limits, defaults)
- Lines 60-110: __init__ and setup with validated settings loading
- Lines 110-160: Theme colors and settings validation methods
- Lines 160-220: Text preprocessing (ICD removal, bullet cleanup)
- Lines 220-260: Text parsing with punctuation and section detection
- Lines 260-350: Dialog and widget creation
- Lines 350-560: Control panel widgets (play, speed, font, chunk, nav, settings)
- Lines 560-620: Progress section
- Lines 620-830: Word display methods (single word ORP, chunk mode ORP)
- Lines 830-920: Playback control and scheduling
- Lines 920-1050: Navigation and speed control
- Lines 1050-1180: Theme/settings toggles, help dialog, save/close
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import List, Tuple, Optional, Dict
import tkinter.font as tkfont
import time
import platform

from settings.settings import SETTINGS, save_settings


class RSVPDialog:
    """RSVP reader dialog for speed reading SOAP notes."""

    # Speed constants
    MIN_WPM = 50
    MAX_WPM = 2000
    DEFAULT_WPM = 300
    WPM_STEP = 25

    # Font size constants
    MIN_FONT_SIZE = 24
    MAX_FONT_SIZE = 96
    DEFAULT_FONT_SIZE = 48

    # Dark theme colors (default)
    DARK_BG = "#1E1E1E"
    DARK_TEXT = "#FFFFFF"
    DARK_ORP = "#FF6B6B"
    DARK_CONTROL_BG = "#2D2D2D"
    DARK_PROGRESS_BG = "#3D3D3D"
    DARK_CONTEXT_TEXT = "#666666"

    # Light theme colors
    LIGHT_BG = "#F5F5F5"
    LIGHT_TEXT = "#1E1E1E"
    LIGHT_ORP = "#E53935"
    LIGHT_CONTROL_BG = "#E0E0E0"
    LIGHT_PROGRESS_BG = "#D0D0D0"
    LIGHT_CONTEXT_TEXT = "#999999"

    def __init__(self, parent, text: str):
        """Initialize RSVP dialog.

        Args:
            parent: Parent window
            text: Text to display word-by-word
        """
        self.parent = parent
        self.original_text = text
        self.text = self._preprocess_text(text)
        self.words: List[Tuple[str, str]] = []  # (word, punct_type)
        self.sentences: List[Tuple[int, int, str]] = []  # (start_idx, end_idx, sentence_text)
        self.section_indices: Dict[str, int] = {}  # section_name -> word_index
        self.current_index = 0
        self.is_playing = False
        self.is_fullscreen = False
        self.timer_id: Optional[str] = None

        # Load settings with validation
        rsvp_settings = SETTINGS.get("rsvp", {})
        self.wpm = self._validate_wpm(rsvp_settings.get("wpm", self.DEFAULT_WPM))
        self.font_size = self._validate_font_size(rsvp_settings.get("font_size", self.DEFAULT_FONT_SIZE))
        self.chunk_size = self._validate_chunk_size(rsvp_settings.get("chunk_size", 1))
        self.is_dark_theme = self._validate_bool(rsvp_settings.get("dark_theme", True), True)
        self.audio_cue_enabled = self._validate_bool(rsvp_settings.get("audio_cue", False), False)
        self.show_context = self._validate_bool(rsvp_settings.get("show_context", False), False)
        self.auto_start = self._validate_bool(rsvp_settings.get("auto_start", False), False)

        # Statistics tracking
        self.start_time: Optional[float] = None
        self.wpm_history: List[int] = []
        self.last_section: Optional[str] = None

        # Set theme colors
        self._update_theme_colors()

        self._parse_text()

        if not self.words:
            return

        self._create_dialog()
        self._create_widgets()
        self._bind_keys()
        self._display_word()
        self._update_progress()

        # Auto-start if enabled
        if self.auto_start:
            self.dialog.after(500, self.play)

    def _update_theme_colors(self) -> None:
        """Update color variables based on current theme."""
        if self.is_dark_theme:
            self.BG_COLOR = self.DARK_BG
            self.TEXT_COLOR = self.DARK_TEXT
            self.ORP_COLOR = self.DARK_ORP
            self.CONTROL_BG = self.DARK_CONTROL_BG
            self.PROGRESS_BG = self.DARK_PROGRESS_BG
            self.CONTEXT_COLOR = self.DARK_CONTEXT_TEXT
        else:
            self.BG_COLOR = self.LIGHT_BG
            self.TEXT_COLOR = self.LIGHT_TEXT
            self.ORP_COLOR = self.LIGHT_ORP
            self.CONTROL_BG = self.LIGHT_CONTROL_BG
            self.PROGRESS_BG = self.LIGHT_PROGRESS_BG
            self.CONTEXT_COLOR = self.LIGHT_CONTEXT_TEXT

    def _validate_wpm(self, value) -> int:
        """Validate WPM setting with bounds checking."""
        try:
            wpm = int(value)
            return max(self.MIN_WPM, min(self.MAX_WPM, wpm))
        except (TypeError, ValueError):
            return self.DEFAULT_WPM

    def _validate_font_size(self, value) -> int:
        """Validate font size setting with bounds checking."""
        try:
            size = int(value)
            return max(self.MIN_FONT_SIZE, min(self.MAX_FONT_SIZE, size))
        except (TypeError, ValueError):
            return self.DEFAULT_FONT_SIZE

    def _validate_chunk_size(self, value) -> int:
        """Validate chunk size setting (1, 2, or 3)."""
        try:
            chunk = int(value)
            if chunk in (1, 2, 3):
                return chunk
            return 1
        except (TypeError, ValueError):
            return 1

    def _validate_bool(self, value, default: bool) -> bool:
        """Validate boolean setting."""
        if isinstance(value, bool):
            return value
        return default

    def _preprocess_text(self, text: str) -> str:
        """Clean SOAP note text for better RSVP readability.

        Removes:
        - ICD codes (ICD-9, ICD-10 lines)
        - Leading bullet dashes
        - "Not discussed" entries
        - Excess whitespace

        Args:
            text: Raw SOAP note text

        Returns:
            Cleaned text suitable for RSVP display
        """
        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Remove ICD code lines
            if line.upper().startswith(('ICD-9', 'ICD-10', 'ICD CODE')):
                continue

            # Remove "Not discussed" entries
            if 'not discussed' in line.lower():
                continue

            # Remove leading dashes (bullet points)
            if line.startswith('- '):
                line = line[2:]
            elif line.startswith('-'):
                line = line[1:].lstrip()

            if line:
                cleaned_lines.append(line)

        return ' '.join(cleaned_lines)

    def _parse_text(self) -> None:
        """Parse text into words with punctuation type for smart pausing."""
        raw_words = self.text.split()

        # Section headers that get extra pause
        section_keywords = {
            'subjective:', 'objective:', 'assessment:', 'plan:',
            'differential', 'diagnosis:', 'follow', 'up:',
            'clinical', 'synopsis:'
        }

        # Track sentences for context display
        current_sentence_start = 0
        current_sentence_words = []

        for word in raw_words:
            if not word:
                continue

            lower_word = word.lower()
            word_index = len(self.words)

            # Check for section headers (longest pause)
            if lower_word in section_keywords or lower_word.rstrip(':') + ':' in section_keywords:
                punct_type = 'section'
                # Track section index for navigation
                section_name = word.rstrip(':').capitalize()
                if section_name not in self.section_indices:
                    self.section_indices[section_name] = word_index
            # Determine punctuation type for timing
            elif word[-1:] in '.!?':
                punct_type = 'sentence'
            elif word[-1:] in ',;:':
                punct_type = 'clause'
            else:
                punct_type = 'none'

            self.words.append((word, punct_type))
            current_sentence_words.append(word)

            # Track sentence boundaries
            if punct_type == 'sentence':
                sentence_text = ' '.join(current_sentence_words)
                self.sentences.append((current_sentence_start, word_index, sentence_text))
                current_sentence_start = word_index + 1
                current_sentence_words = []

        # Add final sentence if not terminated
        if current_sentence_words:
            sentence_text = ' '.join(current_sentence_words)
            self.sentences.append((current_sentence_start, len(self.words) - 1, sentence_text))

    def _calculate_orp(self, word: str) -> int:
        """Calculate optimal recognition point index.

        The ORP is the character position where the eye naturally focuses.

        Args:
            word: The word to calculate ORP for

        Returns:
            Index of the ORP character
        """
        # Strip trailing punctuation for length calculation
        clean_word = word.rstrip('.,;:!?"\'-')
        length = len(clean_word)

        if length <= 1:
            return 0
        if length <= 3:
            return 0
        if length <= 5:
            return 1
        if length <= 9:
            return 2
        return 3

    def _create_dialog(self) -> None:
        """Create the main dialog window."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("RSVP Reader")
        self.dialog.geometry("900x600")
        self.dialog.configure(bg=self.BG_COLOR)
        self.dialog.resizable(True, True)
        self.dialog.minsize(800, 500)

        # Center on screen
        self.dialog.update_idletasks()
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        x = (screen_width // 2) - (900 // 2)
        y = (screen_height // 2) - (600 // 2)
        self.dialog.geometry(f"900x600+{x}+{y}")

        # Make modal
        self.dialog.transient(self.parent)
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        # Handle window close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_widgets(self) -> None:
        """Create all UI components."""
        # Main container
        self.main_frame = ttk.Frame(self.dialog)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Context display area (above main word, shows current sentence)
        self.context_frame = tk.Frame(self.main_frame, bg=self.BG_COLOR, height=40)
        self.context_frame.pack(fill=tk.X, padx=20, pady=(10, 0))
        self.context_frame.pack_propagate(False)

        self.context_label = tk.Label(
            self.context_frame,
            text="",
            bg=self.BG_COLOR,
            fg=self.CONTEXT_COLOR,
            font=("Helvetica", 12),
            wraplength=860
        )
        self.context_label.pack(expand=True)

        # Word display area (canvas for custom rendering)
        self.display_frame = tk.Frame(self.main_frame, bg=self.BG_COLOR, height=250)
        self.display_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self.display_frame.pack_propagate(False)

        self.canvas = tk.Canvas(
            self.display_frame,
            bg=self.BG_COLOR,
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Bind resize event
        self.canvas.bind('<Configure>', self._on_resize)

        # Section navigation buttons
        self._create_section_buttons()

        # Control panel
        self._create_control_panel()

        # Progress section
        self._create_progress_section()

    def _create_section_buttons(self) -> None:
        """Create section navigation buttons."""
        section_frame = tk.Frame(self.main_frame, bg=self.CONTROL_BG, height=45)
        section_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        section_frame.pack_propagate(False)

        inner_frame = tk.Frame(section_frame, bg=self.CONTROL_BG)
        inner_frame.pack(expand=True, pady=8)

        ttk.Label(
            inner_frame,
            text="Jump to:",
            background=self.CONTROL_BG,
            foreground=self.TEXT_COLOR
        ).pack(side=tk.LEFT, padx=(0, 10))

        # Create buttons for detected sections
        section_order = ['Subjective', 'Objective', 'Assessment', 'Plan', 'Differential', 'Clinical']
        for section in section_order:
            if section in self.section_indices:
                btn = ttk.Button(
                    inner_frame,
                    text=section,
                    command=lambda s=section: self._jump_to_section(s),
                    width=10,
                    bootstyle="info-outline"
                )
                btn.pack(side=tk.LEFT, padx=3)

        # If no sections found, show message
        if not self.section_indices:
            ttk.Label(
                inner_frame,
                text="(No sections detected)",
                background=self.CONTROL_BG,
                foreground="#888888"
            ).pack(side=tk.LEFT, padx=10)

    def _create_control_panel(self) -> None:
        """Create the main control panel with all controls."""
        control_frame = tk.Frame(self.main_frame, bg=self.CONTROL_BG, height=70)
        control_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        control_frame.pack_propagate(False)

        # Inner control frame for centering
        inner_control = tk.Frame(control_frame, bg=self.CONTROL_BG)
        inner_control.pack(expand=True, pady=10)

        # Play/Pause button
        self.play_btn = ttk.Button(
            inner_control,
            text="Play",
            command=self._toggle_playback,
            width=10,
            bootstyle="success"
        )
        self.play_btn.pack(side=tk.LEFT, padx=8)

        # Speed control section
        speed_frame = tk.Frame(inner_control, bg=self.CONTROL_BG)
        speed_frame.pack(side=tk.LEFT, padx=8)

        ttk.Label(
            speed_frame,
            text="Speed:",
            background=self.CONTROL_BG,
            foreground=self.TEXT_COLOR
        ).pack(side=tk.LEFT, padx=(0, 3))

        ttk.Button(
            speed_frame,
            text="-",
            command=self._speed_down,
            width=2,
            bootstyle="secondary"
        ).pack(side=tk.LEFT)

        self.speed_var = tk.IntVar(value=self.wpm)
        self.speed_slider = ttk.Scale(
            speed_frame,
            from_=self.MIN_WPM,
            to=self.MAX_WPM,
            orient=tk.HORIZONTAL,
            length=100,
            variable=self.speed_var,
            command=self._on_speed_change
        )
        self.speed_slider.pack(side=tk.LEFT, padx=2)

        ttk.Button(
            speed_frame,
            text="+",
            command=self._speed_up,
            width=2,
            bootstyle="secondary"
        ).pack(side=tk.LEFT)

        self.wpm_label = ttk.Label(
            speed_frame,
            text=f"{self.wpm} WPM",
            width=9,
            background=self.CONTROL_BG,
            foreground=self.TEXT_COLOR
        )
        self.wpm_label.pack(side=tk.LEFT, padx=(5, 0))

        # Font size control
        font_frame = tk.Frame(inner_control, bg=self.CONTROL_BG)
        font_frame.pack(side=tk.LEFT, padx=8)

        ttk.Label(
            font_frame,
            text="Font:",
            background=self.CONTROL_BG,
            foreground=self.TEXT_COLOR
        ).pack(side=tk.LEFT, padx=(0, 3))

        self.font_var = tk.IntVar(value=self.font_size)
        self.font_slider = ttk.Scale(
            font_frame,
            from_=self.MIN_FONT_SIZE,
            to=self.MAX_FONT_SIZE,
            orient=tk.HORIZONTAL,
            length=80,
            variable=self.font_var,
            command=self._on_font_change
        )
        self.font_slider.pack(side=tk.LEFT, padx=2)

        self.font_label = ttk.Label(
            font_frame,
            text=f"{self.font_size}pt",
            width=5,
            background=self.CONTROL_BG,
            foreground=self.TEXT_COLOR
        )
        self.font_label.pack(side=tk.LEFT, padx=(3, 0))

        # Chunk size control
        chunk_frame = tk.Frame(inner_control, bg=self.CONTROL_BG)
        chunk_frame.pack(side=tk.LEFT, padx=8)

        ttk.Label(
            chunk_frame,
            text="Words:",
            background=self.CONTROL_BG,
            foreground=self.TEXT_COLOR
        ).pack(side=tk.LEFT, padx=(0, 3))

        self.chunk_var = tk.IntVar(value=self.chunk_size)
        for i in [1, 2, 3]:
            rb = ttk.Radiobutton(
                chunk_frame,
                text=str(i),
                variable=self.chunk_var,
                value=i,
                command=self._on_chunk_change,
                bootstyle="info-toolbutton"
            )
            rb.pack(side=tk.LEFT, padx=1)

        # Navigation buttons
        nav_frame = tk.Frame(inner_control, bg=self.CONTROL_BG)
        nav_frame.pack(side=tk.LEFT, padx=8)

        for symbol, cmd in [("<<", self._go_to_start), ("<", self._prev_word),
                           (">", self._next_word), (">>", self._go_to_end)]:
            ttk.Button(
                nav_frame,
                text=symbol,
                command=cmd,
                width=3,
                bootstyle="secondary"
            ).pack(side=tk.LEFT, padx=1)

        # Settings buttons (theme, fullscreen, etc.)
        settings_frame = tk.Frame(inner_control, bg=self.CONTROL_BG)
        settings_frame.pack(side=tk.LEFT, padx=8)

        # Theme toggle
        self.theme_btn = ttk.Button(
            settings_frame,
            text="Light" if self.is_dark_theme else "Dark",
            command=self._toggle_theme,
            width=6,
            bootstyle="secondary"
        )
        self.theme_btn.pack(side=tk.LEFT, padx=2)

        # Fullscreen toggle
        ttk.Button(
            settings_frame,
            text="F11",
            command=self._toggle_fullscreen,
            width=4,
            bootstyle="secondary"
        ).pack(side=tk.LEFT, padx=2)

        # Context toggle
        self.context_btn = ttk.Button(
            settings_frame,
            text="Ctx" if not self.show_context else "Ctx*",
            command=self._toggle_context,
            width=4,
            bootstyle="info" if self.show_context else "secondary"
        )
        self.context_btn.pack(side=tk.LEFT, padx=2)

        # Audio toggle
        self.audio_btn = ttk.Button(
            settings_frame,
            text="Snd" if not self.audio_cue_enabled else "Snd*",
            command=self._toggle_audio_cue,
            width=4,
            bootstyle="info" if self.audio_cue_enabled else "secondary"
        )
        self.audio_btn.pack(side=tk.LEFT, padx=2)

        # Help button
        self.help_btn = ttk.Button(
            settings_frame,
            text="?",
            command=self._show_shortcuts_help,
            width=2,
            bootstyle="secondary"
        )
        self.help_btn.pack(side=tk.LEFT, padx=2)

    def _create_progress_section(self) -> None:
        """Create the progress bar and info section."""
        progress_frame = tk.Frame(self.main_frame, bg=self.PROGRESS_BG, height=60)
        progress_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        progress_frame.pack_propagate(False)

        progress_inner = tk.Frame(progress_frame, bg=self.PROGRESS_BG)
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

        # Word count and time
        info_frame = tk.Frame(progress_inner, bg=self.PROGRESS_BG)
        info_frame.pack(side=tk.RIGHT, padx=(15, 0))

        self.word_count_label = ttk.Label(
            info_frame,
            text=f"0 / {len(self.words)} words",
            background=self.PROGRESS_BG,
            foreground=self.TEXT_COLOR
        )
        self.word_count_label.pack(anchor=tk.E)

        self.time_label = ttk.Label(
            info_frame,
            text="",
            background=self.PROGRESS_BG,
            foreground=self.TEXT_COLOR
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
        self.dialog.bind('<t>', lambda e: self._toggle_theme())
        self.dialog.bind('<T>', lambda e: self._toggle_theme())
        self.dialog.bind('<1>', lambda e: self._set_chunk_size(1))
        self.dialog.bind('<2>', lambda e: self._set_chunk_size(2))
        self.dialog.bind('<3>', lambda e: self._set_chunk_size(3))

        # Focus the dialog to capture key events
        self.dialog.focus_set()

    def _display_word(self) -> None:
        """Display current word(s) with ORP highlighting on canvas."""
        # Clear canvas
        self.canvas.delete("all")

        if self.current_index >= len(self.words):
            self._show_complete()
            return

        # Get canvas dimensions
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width < 10 or canvas_height < 10:
            self.dialog.after(50, self._display_word)
            return

        # Get chunk of words to display
        end_idx = min(self.current_index + self.chunk_size, len(self.words))
        chunk_words = [w[0] for w in self.words[self.current_index:end_idx]]

        if self.chunk_size == 1:
            # Single word mode - use ORP highlighting
            word = chunk_words[0]
            self._display_single_word(word, canvas_width, canvas_height)
        else:
            # Multi-word mode - display chunk centered
            self._display_chunk(chunk_words, canvas_width, canvas_height)

        # Update context display
        self._update_context_display()

    def _display_single_word(self, word: str, canvas_width: int, canvas_height: int) -> None:
        """Display a single word with ORP highlighting."""
        orp_pos = self._calculate_orp(word)

        # Use user-selected font size
        font = tkfont.Font(family="Helvetica", size=self.font_size, weight="bold")

        # Split word into three parts
        pre = word[:orp_pos]
        orp_char = word[orp_pos] if orp_pos < len(word) else ''
        post = word[orp_pos + 1:] if orp_pos + 1 < len(word) else ''

        # Calculate text widths
        orp_width = font.measure(orp_char)

        # Center position
        center_x = canvas_width // 2
        center_y = canvas_height // 2

        # Draw vertical ORP indicator line
        self.canvas.create_line(
            center_x, 10, center_x, canvas_height - 10,
            fill=self.ORP_COLOR, width=2, dash=(4, 4)
        )

        # Draw small triangle marker at top
        self.canvas.create_polygon(
            center_x - 8, 5,
            center_x + 8, 5,
            center_x, 15,
            fill=self.ORP_COLOR
        )

        # Position text so ORP character is centered
        orp_left_edge = center_x - (orp_width // 2)
        orp_right_edge = center_x + (orp_width // 2)

        # Draw pre-ORP text
        if pre:
            self.canvas.create_text(
                orp_left_edge,
                center_y,
                text=pre,
                font=font,
                fill=self.TEXT_COLOR,
                anchor=tk.E
            )

        # Draw ORP character (highlighted)
        if orp_char:
            self.canvas.create_text(
                center_x,
                center_y,
                text=orp_char,
                font=font,
                fill=self.ORP_COLOR,
                anchor=tk.CENTER
            )

        # Draw post-ORP text
        if post:
            self.canvas.create_text(
                orp_right_edge,
                center_y,
                text=post,
                font=font,
                fill=self.TEXT_COLOR,
                anchor=tk.W
            )

    def _display_chunk(self, words: List[str], canvas_width: int, canvas_height: int) -> None:
        """Display multiple words as a chunk with ORP highlighting on middle word."""
        # Slightly smaller font for multi-word display
        font_size = max(self.MIN_FONT_SIZE, self.font_size - 8)
        font = tkfont.Font(family="Helvetica", size=font_size, weight="bold")

        center_x = canvas_width // 2
        center_y = canvas_height // 2

        # Calculate which word is the "focus" word (middle word)
        focus_idx = len(words) // 2

        # Calculate ORP for the focus word
        focus_word = words[focus_idx]
        orp_pos = self._calculate_orp(focus_word)

        # Build the full chunk with spacing
        spacing = "  "

        # Calculate positions for each word
        word_widths = [font.measure(w) for w in words]
        spacing_width = font.measure(spacing)
        total_width = sum(word_widths) + spacing_width * (len(words) - 1)

        # Calculate where the ORP character of the focus word should be centered
        # First, find the start position of the focus word
        focus_word_start = sum(word_widths[:focus_idx]) + spacing_width * focus_idx

        # Calculate position of ORP character within focus word
        pre_orp = focus_word[:orp_pos]
        orp_char = focus_word[orp_pos] if orp_pos < len(focus_word) else ''
        orp_char_width = font.measure(orp_char)
        pre_orp_width = font.measure(pre_orp)

        # Position of ORP character center within total chunk
        orp_center_in_chunk = focus_word_start + pre_orp_width + orp_char_width // 2

        # Calculate starting x position so ORP character is centered
        start_x = center_x - orp_center_in_chunk

        # Draw vertical ORP indicator line
        self.canvas.create_line(
            center_x, 10, center_x, canvas_height - 10,
            fill=self.ORP_COLOR, width=2, dash=(4, 4)
        )

        # Draw small triangle marker at top
        self.canvas.create_polygon(
            center_x - 8, 5,
            center_x + 8, 5,
            center_x, 15,
            fill=self.ORP_COLOR
        )

        # Draw each word
        current_x = start_x
        for i, word in enumerate(words):
            if i == focus_idx:
                # Draw focus word with ORP highlighting
                pre = word[:orp_pos]
                orp = word[orp_pos] if orp_pos < len(word) else ''
                post = word[orp_pos + 1:] if orp_pos + 1 < len(word) else ''

                # Draw pre-ORP
                if pre:
                    self.canvas.create_text(
                        current_x,
                        center_y,
                        text=pre,
                        font=font,
                        fill=self.TEXT_COLOR,
                        anchor=tk.W
                    )
                    current_x += font.measure(pre)

                # Draw ORP character (highlighted)
                if orp:
                    self.canvas.create_text(
                        current_x,
                        center_y,
                        text=orp,
                        font=font,
                        fill=self.ORP_COLOR,
                        anchor=tk.W
                    )
                    current_x += font.measure(orp)

                # Draw post-ORP
                if post:
                    self.canvas.create_text(
                        current_x,
                        center_y,
                        text=post,
                        font=font,
                        fill=self.TEXT_COLOR,
                        anchor=tk.W
                    )
                    current_x += font.measure(post)
            else:
                # Draw regular word
                self.canvas.create_text(
                    current_x,
                    center_y,
                    text=word,
                    font=font,
                    fill=self.TEXT_COLOR,
                    anchor=tk.W
                )
                current_x += word_widths[i]

            # Add spacing after word (except last)
            if i < len(words) - 1:
                current_x += spacing_width

    def _update_context_display(self) -> None:
        """Update the sentence context display."""
        if not self.show_context:
            self.context_label.config(text="")
            return

        sentence = self._get_current_sentence()
        self.context_label.config(text=sentence)

    def _get_current_sentence(self) -> str:
        """Get the sentence containing the current word."""
        for start, end, text in self.sentences:
            if start <= self.current_index <= end:
                return text
        return ""

    def _show_complete(self) -> None:
        """Show completion message with statistics."""
        self.canvas.delete("all")

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        font = tkfont.Font(family="Helvetica", size=36, weight="bold")
        small_font = tkfont.Font(family="Helvetica", size=14)

        self.canvas.create_text(
            canvas_width // 2,
            canvas_height // 2 - 40,
            text="Complete!",
            font=font,
            fill=self.TEXT_COLOR
        )

        # Show statistics if we have tracking data
        if self.start_time and self.wpm_history:
            elapsed = time.time() - self.start_time
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            avg_wpm = sum(self.wpm_history) // len(self.wpm_history)

            stats_text = f"Time: {minutes}:{seconds:02d} | Avg: {avg_wpm} WPM | {len(self.words)} words"
            self.canvas.create_text(
                canvas_width // 2,
                canvas_height // 2 + 10,
                text=stats_text,
                font=small_font,
                fill="#888888"
            )

        self.canvas.create_text(
            canvas_width // 2,
            canvas_height // 2 + 50,
            text="Press Home to restart or Escape to close",
            font=small_font,
            fill="#666666"
        )

    def _update_progress(self) -> None:
        """Update progress bar and info labels."""
        total = len(self.words)
        current = min(self.current_index + 1, total) if total > 0 else 0

        # Update progress bar
        progress = (current / total) * 100 if total > 0 else 0
        self.progress_var.set(progress)

        # Update word count
        self.word_count_label.config(text=f"{current} / {total} words")

        # Calculate time remaining
        words_remaining = max(0, total - current)
        seconds_remaining = (words_remaining * 60) / self.wpm if self.wpm > 0 else 0

        if seconds_remaining < 60:
            time_str = f"~{int(seconds_remaining)} sec remaining"
        else:
            minutes = int(seconds_remaining // 60)
            seconds = int(seconds_remaining % 60)
            time_str = f"~{minutes}:{seconds:02d} remaining"

        self.time_label.config(text=time_str)

    def _get_delay_ms(self) -> int:
        """Calculate delay for current word based on WPM and punctuation."""
        if self.current_index >= len(self.words):
            return 200

        base_delay = int(60000 / self.wpm)

        _, punct_type = self.words[self.current_index]

        multipliers = {
            'section': 3.0,
            'sentence': 2.5,
            'clause': 1.5,
            'none': 1.0
        }

        return int(base_delay * multipliers.get(punct_type, 1.0))

    def _toggle_playback(self) -> None:
        """Toggle between play and pause."""
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def play(self) -> None:
        """Start or resume playback."""
        if self.current_index >= len(self.words):
            self.current_index = 0
            self._display_word()
            self._update_progress()

        # Start tracking statistics
        if self.start_time is None:
            self.start_time = time.time()
            self.wpm_history = []

        self.is_playing = True
        self.play_btn.configure(text="Pause", bootstyle="warning")
        self._schedule_next_word()

    def pause(self) -> None:
        """Pause playback."""
        self.is_playing = False
        self.play_btn.configure(text="Play", bootstyle="success")
        if self.timer_id:
            self.dialog.after_cancel(self.timer_id)
            self.timer_id = None

    def _schedule_next_word(self) -> None:
        """Schedule the next word display."""
        if not self.is_playing:
            return

        # Track WPM for statistics
        self.wpm_history.append(self.wpm)

        delay = self._get_delay_ms()
        self.timer_id = self.dialog.after(delay, self._advance_word)

    def _advance_word(self) -> None:
        """Move to next word(s)."""
        # Check for section change before advancing
        old_section = self._get_current_section()

        self.current_index += self.chunk_size

        if self.current_index >= len(self.words):
            self.pause()
            self._show_complete()
            self._update_progress()
            return

        # Check for section change and play audio cue
        new_section = self._get_current_section()
        if self.audio_cue_enabled and old_section != new_section and new_section:
            self._play_section_cue()

        self._display_word()
        self._update_progress()
        self._schedule_next_word()

    def _get_current_section(self) -> Optional[str]:
        """Get the current section name based on word index."""
        current_section = None
        for section, idx in self.section_indices.items():
            if idx <= self.current_index:
                current_section = section
        return current_section

    def _play_section_cue(self) -> None:
        """Play an audio cue when entering a new section."""
        try:
            if platform.system() == "Windows":
                import winsound
                winsound.Beep(800, 100)
            else:
                self.dialog.bell()
        except Exception:
            pass

    def _prev_word(self) -> None:
        """Go to previous word(s)."""
        if self.current_index > 0:
            self.current_index = max(0, self.current_index - self.chunk_size)
            self._display_word()
            self._update_progress()

    def _next_word(self) -> None:
        """Go to next word(s)."""
        if self.current_index < len(self.words) - 1:
            self.current_index = min(len(self.words) - 1, self.current_index + self.chunk_size)
            self._display_word()
            self._update_progress()

    def _go_to_start(self) -> None:
        """Go to the first word."""
        self.current_index = 0
        self.start_time = None  # Reset statistics
        self.wpm_history = []
        self._display_word()
        self._update_progress()

    def _go_to_end(self) -> None:
        """Go to the last word."""
        self.current_index = len(self.words) - 1
        self._display_word()
        self._update_progress()

    def _jump_to_section(self, section: str) -> None:
        """Jump to a specific section."""
        if section in self.section_indices:
            self.current_index = self.section_indices[section]
            self._display_word()
            self._update_progress()

    def _speed_up(self) -> None:
        """Increase reading speed."""
        new_wpm = min(self.wpm + self.WPM_STEP, self.MAX_WPM)
        self._set_speed(new_wpm)

    def _speed_down(self) -> None:
        """Decrease reading speed."""
        new_wpm = max(self.wpm - self.WPM_STEP, self.MIN_WPM)
        self._set_speed(new_wpm)

    def _set_speed(self, wpm: int) -> None:
        """Set the reading speed and save to settings."""
        self.wpm = wpm
        self.speed_var.set(wpm)
        self.wpm_label.config(text=f"{wpm} WPM")
        self._update_progress()
        self._save_settings()

    def _on_speed_change(self, value: str) -> None:
        """Handle speed slider change."""
        try:
            wpm = int(float(value))
            wpm = round(wpm / self.WPM_STEP) * self.WPM_STEP
            wpm = max(self.MIN_WPM, min(self.MAX_WPM, wpm))
            self.wpm = wpm
            self.wpm_label.config(text=f"{wpm} WPM")
            self._update_progress()
            self._save_settings()
        except ValueError:
            pass

    def _on_font_change(self, value: str) -> None:
        """Handle font size slider change."""
        try:
            size = int(float(value))
            self.font_size = max(self.MIN_FONT_SIZE, min(self.MAX_FONT_SIZE, size))
            self.font_label.config(text=f"{self.font_size}pt")
            self._display_word()
            self._save_settings()
        except ValueError:
            pass

    def _on_chunk_change(self) -> None:
        """Handle chunk size change."""
        self.chunk_size = self.chunk_var.get()
        self._display_word()
        self._save_settings()

    def _set_chunk_size(self, size: int) -> None:
        """Set chunk size from keyboard shortcut."""
        self.chunk_size = size
        self.chunk_var.set(size)
        self._display_word()
        self._save_settings()

    def _toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode."""
        self.is_fullscreen = not self.is_fullscreen
        self.dialog.attributes('-fullscreen', self.is_fullscreen)

    def _toggle_theme(self) -> None:
        """Toggle between light and dark themes."""
        self.is_dark_theme = not self.is_dark_theme
        self._update_theme_colors()

        # Update UI elements
        self.dialog.configure(bg=self.BG_COLOR)
        self.canvas.configure(bg=self.BG_COLOR)
        self.display_frame.configure(bg=self.BG_COLOR)
        self.context_frame.configure(bg=self.BG_COLOR)
        self.context_label.configure(bg=self.BG_COLOR, fg=self.CONTEXT_COLOR)

        self.theme_btn.configure(text="Light" if self.is_dark_theme else "Dark")
        self._display_word()
        self._save_settings()

    def _toggle_context(self) -> None:
        """Toggle sentence context display."""
        self.show_context = not self.show_context
        self.context_btn.configure(
            text="Ctx*" if self.show_context else "Ctx",
            bootstyle="info" if self.show_context else "secondary"
        )
        self._update_context_display()
        self._save_settings()

    def _toggle_audio_cue(self) -> None:
        """Toggle audio cue on section changes."""
        self.audio_cue_enabled = not self.audio_cue_enabled
        self.audio_btn.configure(
            text="Snd*" if self.audio_cue_enabled else "Snd",
            bootstyle="info" if self.audio_cue_enabled else "secondary"
        )
        self._save_settings()

    def _show_shortcuts_help(self) -> None:
        """Show keyboard shortcuts help dialog."""
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
  Section buttons jump to SOAP sections
  Escape exits fullscreen (or closes dialog)

SETTINGS BUTTONS
  Light/Dark     Toggle theme
  F11            Fullscreen mode
  Ctx            Show sentence context
  Snd            Audio cue on sections"""

        # Create help popup
        help_popup = tk.Toplevel(self.dialog)
        help_popup.title("Keyboard Shortcuts")
        help_popup.geometry("380x400")
        help_popup.resizable(False, False)
        help_popup.transient(self.dialog)

        # Center on parent
        help_popup.update_idletasks()
        x = self.dialog.winfo_x() + (self.dialog.winfo_width() - 380) // 2
        y = self.dialog.winfo_y() + (self.dialog.winfo_height() - 400) // 2
        help_popup.geometry(f"+{x}+{y}")

        # Use current theme colors
        help_popup.configure(bg=self.BG_COLOR)

        # Help text
        text_widget = tk.Text(
            help_popup,
            wrap=tk.WORD,
            bg=self.BG_COLOR,
            fg=self.TEXT_COLOR,
            font=("Consolas", 10),
            relief=tk.FLAT,
            padx=15,
            pady=15,
            highlightthickness=0
        )
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))
        text_widget.insert("1.0", help_text)
        text_widget.config(state=tk.DISABLED)

        # Close button
        ttk.Button(
            help_popup,
            text="Close",
            command=help_popup.destroy,
            bootstyle="secondary"
        ).pack(pady=(5, 15))

        # Close on Escape
        help_popup.bind('<Escape>', lambda e: help_popup.destroy())
        help_popup.focus_set()

    def _save_settings(self) -> None:
        """Save current RSVP settings."""
        if "rsvp" not in SETTINGS:
            SETTINGS["rsvp"] = {}

        SETTINGS["rsvp"]["wpm"] = self.wpm
        SETTINGS["rsvp"]["font_size"] = self.font_size
        SETTINGS["rsvp"]["chunk_size"] = self.chunk_size
        SETTINGS["rsvp"]["dark_theme"] = self.is_dark_theme
        SETTINGS["rsvp"]["audio_cue"] = self.audio_cue_enabled
        SETTINGS["rsvp"]["show_context"] = self.show_context

        save_settings(SETTINGS)

    def _handle_escape(self) -> None:
        """Handle Escape key - exit fullscreen first, then close."""
        if self.is_fullscreen:
            self._toggle_fullscreen()
        else:
            self._on_close()

    def _on_resize(self, event) -> None:
        """Handle canvas resize - redraw the current word."""
        if hasattr(self, 'canvas') and self.words:
            self._display_word()

    def _on_close(self) -> None:
        """Handle dialog close."""
        self.pause()
        self.dialog.destroy()


__all__ = ["RSVPDialog"]

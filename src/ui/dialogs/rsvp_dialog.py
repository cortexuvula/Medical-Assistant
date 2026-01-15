"""
RSVP (Rapid Serial Visual Presentation) Dialog

Displays text word-by-word at configurable speed for speed reading.
Uses ORP (Optimal Recognition Point) highlighting for improved comprehension.
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import List, Tuple, Optional
import tkinter.font as tkfont


class RSVPDialog:
    """RSVP reader dialog for speed reading SOAP notes."""

    # Speed constants
    MIN_WPM = 50
    MAX_WPM = 2000
    DEFAULT_WPM = 300
    WPM_STEP = 25

    # Colors (dark theme for better focus)
    BG_COLOR = "#1E1E1E"
    TEXT_COLOR = "#FFFFFF"
    ORP_COLOR = "#FF6B6B"
    CONTROL_BG = "#2D2D2D"
    PROGRESS_BG = "#3D3D3D"

    def __init__(self, parent, text: str):
        """Initialize RSVP dialog.

        Args:
            parent: Parent window
            text: Text to display word-by-word
        """
        self.parent = parent
        self.text = text
        self.words: List[Tuple[str, str]] = []  # (word, punct_type)
        self.current_index = 0
        self.is_playing = False
        self.wpm = self.DEFAULT_WPM
        self.timer_id: Optional[str] = None

        self._parse_text()

        if not self.words:
            return

        self._create_dialog()
        self._create_widgets()
        self._bind_keys()
        self._display_word()
        self._update_progress()

    def _parse_text(self) -> None:
        """Parse text into words with punctuation type for smart pausing."""
        raw_words = self.text.split()

        for word in raw_words:
            if not word:
                continue

            # Determine punctuation type for timing
            last_char = word[-1:] if word else ''
            if last_char in '.!?':
                punct_type = 'sentence'  # Long pause
            elif last_char in ',;:':
                punct_type = 'clause'    # Medium pause
            else:
                punct_type = 'none'      # Normal timing

            self.words.append((word, punct_type))

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
        self.dialog.geometry("700x450")
        self.dialog.configure(bg=self.BG_COLOR)
        self.dialog.resizable(True, True)
        self.dialog.minsize(500, 350)

        # Center on screen
        self.dialog.update_idletasks()
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        x = (screen_width // 2) - (700 // 2)
        y = (screen_height // 2) - (450 // 2)
        self.dialog.geometry(f"700x450+{x}+{y}")

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
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Word display area (canvas for custom rendering)
        self.display_frame = tk.Frame(main_frame, bg=self.BG_COLOR, height=250)
        self.display_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        self.display_frame.pack_propagate(False)

        self.canvas = tk.Canvas(
            self.display_frame,
            bg=self.BG_COLOR,
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Bind resize event
        self.canvas.bind('<Configure>', self._on_resize)

        # Control panel
        control_frame = tk.Frame(main_frame, bg=self.CONTROL_BG, height=60)
        control_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        control_frame.pack_propagate(False)

        # Inner control frame for centering
        inner_control = tk.Frame(control_frame, bg=self.CONTROL_BG)
        inner_control.pack(expand=True)

        # Play/Pause button
        self.play_btn = ttk.Button(
            inner_control,
            text="▶ Play",
            command=self._toggle_playback,
            width=12,
            bootstyle="success"
        )
        self.play_btn.pack(side=tk.LEFT, padx=10, pady=15)

        # Speed control section
        speed_frame = tk.Frame(inner_control, bg=self.CONTROL_BG)
        speed_frame.pack(side=tk.LEFT, padx=20, pady=15)

        ttk.Label(
            speed_frame,
            text="Speed:",
            background=self.CONTROL_BG,
            foreground=self.TEXT_COLOR
        ).pack(side=tk.LEFT, padx=(0, 5))

        # Speed down button
        ttk.Button(
            speed_frame,
            text="−",
            command=self._speed_down,
            width=3,
            bootstyle="secondary"
        ).pack(side=tk.LEFT)

        # Speed slider
        self.speed_var = tk.IntVar(value=self.wpm)
        self.speed_slider = ttk.Scale(
            speed_frame,
            from_=self.MIN_WPM,
            to=self.MAX_WPM,
            orient=tk.HORIZONTAL,
            length=150,
            variable=self.speed_var,
            command=self._on_speed_change
        )
        self.speed_slider.pack(side=tk.LEFT, padx=5)

        # Speed up button
        ttk.Button(
            speed_frame,
            text="+",
            command=self._speed_up,
            width=3,
            bootstyle="secondary"
        ).pack(side=tk.LEFT)

        # WPM label
        self.wpm_label = ttk.Label(
            speed_frame,
            text=f"{self.wpm} WPM",
            width=10,
            background=self.CONTROL_BG,
            foreground=self.TEXT_COLOR
        )
        self.wpm_label.pack(side=tk.LEFT, padx=(10, 0))

        # Navigation buttons
        nav_frame = tk.Frame(inner_control, bg=self.CONTROL_BG)
        nav_frame.pack(side=tk.LEFT, padx=20, pady=15)

        ttk.Button(
            nav_frame,
            text="⏮",
            command=self._go_to_start,
            width=3,
            bootstyle="secondary"
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            nav_frame,
            text="◀",
            command=self._prev_word,
            width=3,
            bootstyle="secondary"
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            nav_frame,
            text="▶",
            command=self._next_word,
            width=3,
            bootstyle="secondary"
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            nav_frame,
            text="⏭",
            command=self._go_to_end,
            width=3,
            bootstyle="secondary"
        ).pack(side=tk.LEFT, padx=2)

        # Progress section
        progress_frame = tk.Frame(main_frame, bg=self.PROGRESS_BG, height=50)
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
            length=400,
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
        self.dialog.bind('<Escape>', lambda e: self._on_close())

        # Focus the dialog to capture key events
        self.dialog.focus_set()

    def _display_word(self) -> None:
        """Display current word with ORP highlighting on canvas."""
        # Clear canvas
        self.canvas.delete("all")

        if self.current_index >= len(self.words):
            self._show_complete()
            return

        word, _ = self.words[self.current_index]
        orp_pos = self._calculate_orp(word)

        # Get canvas dimensions
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width < 10 or canvas_height < 10:
            # Canvas not yet sized
            self.dialog.after(50, self._display_word)
            return

        # Calculate font size based on canvas size
        font_size = min(canvas_height // 4, 72)
        font = tkfont.Font(family="Helvetica", size=font_size, weight="bold")

        # Split word into three parts
        pre = word[:orp_pos]
        orp_char = word[orp_pos] if orp_pos < len(word) else ''
        post = word[orp_pos + 1:] if orp_pos + 1 < len(word) else ''

        # Calculate text widths
        pre_width = font.measure(pre)
        orp_width = font.measure(orp_char)

        # Center position (ORP character should be at center)
        center_x = canvas_width // 2
        center_y = canvas_height // 2

        # Draw vertical ORP indicator line
        self.canvas.create_line(
            center_x, 10, center_x, canvas_height - 10,
            fill=self.ORP_COLOR, width=2, dash=(4, 4)
        )

        # Draw small triangle marker at top pointing down
        self.canvas.create_polygon(
            center_x - 8, 5,
            center_x + 8, 5,
            center_x, 15,
            fill=self.ORP_COLOR
        )

        # Calculate starting position for text
        # The ORP character should be centered
        text_start_x = center_x - pre_width - (orp_width // 2)

        # Draw pre-ORP text
        if pre:
            self.canvas.create_text(
                text_start_x + pre_width // 2,
                center_y,
                text=pre,
                font=font,
                fill=self.TEXT_COLOR,
                anchor=tk.CENTER
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
            post_start_x = center_x + (orp_width // 2)
            post_width = font.measure(post)
            self.canvas.create_text(
                post_start_x + post_width // 2,
                center_y,
                text=post,
                font=font,
                fill=self.TEXT_COLOR,
                anchor=tk.CENTER
            )

    def _show_complete(self) -> None:
        """Show completion message."""
        self.canvas.delete("all")

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        font = tkfont.Font(family="Helvetica", size=36, weight="bold")

        self.canvas.create_text(
            canvas_width // 2,
            canvas_height // 2 - 20,
            text="Complete!",
            font=font,
            fill=self.TEXT_COLOR
        )

        small_font = tkfont.Font(family="Helvetica", size=16)
        self.canvas.create_text(
            canvas_width // 2,
            canvas_height // 2 + 30,
            text="Press Home to restart or Escape to close",
            font=small_font,
            fill="#888888"
        )

    def _update_progress(self) -> None:
        """Update progress bar and info labels."""
        total = len(self.words)
        current = self.current_index + 1 if self.current_index < total else total

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

        base_delay = int(60000 / self.wpm)  # ms per word at current WPM

        _, punct_type = self.words[self.current_index]

        multipliers = {
            'sentence': 2.5,  # Period, !, ?
            'clause': 1.5,    # Comma, semicolon, colon
            'none': 1.0       # Regular word
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

        self.is_playing = True
        self.play_btn.configure(text="⏸ Pause", bootstyle="warning")
        self._schedule_next_word()

    def pause(self) -> None:
        """Pause playback."""
        self.is_playing = False
        self.play_btn.configure(text="▶ Play", bootstyle="success")
        if self.timer_id:
            self.dialog.after_cancel(self.timer_id)
            self.timer_id = None

    def _schedule_next_word(self) -> None:
        """Schedule the next word display."""
        if not self.is_playing:
            return

        delay = self._get_delay_ms()
        self.timer_id = self.dialog.after(delay, self._advance_word)

    def _advance_word(self) -> None:
        """Move to next word."""
        self.current_index += 1

        if self.current_index >= len(self.words):
            self.pause()
            self._show_complete()
            self._update_progress()
            return

        self._display_word()
        self._update_progress()
        self._schedule_next_word()

    def _prev_word(self) -> None:
        """Go to previous word."""
        if self.current_index > 0:
            self.current_index -= 1
            self._display_word()
            self._update_progress()

    def _next_word(self) -> None:
        """Go to next word."""
        if self.current_index < len(self.words) - 1:
            self.current_index += 1
            self._display_word()
            self._update_progress()

    def _go_to_start(self) -> None:
        """Go to the first word."""
        self.current_index = 0
        self._display_word()
        self._update_progress()

    def _go_to_end(self) -> None:
        """Go to the last word."""
        self.current_index = len(self.words) - 1
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
        """Set the reading speed."""
        self.wpm = wpm
        self.speed_var.set(wpm)
        self.wpm_label.config(text=f"{wpm} WPM")
        self._update_progress()

    def _on_speed_change(self, value: str) -> None:
        """Handle speed slider change."""
        try:
            wpm = int(float(value))
            # Round to nearest step
            wpm = round(wpm / self.WPM_STEP) * self.WPM_STEP
            wpm = max(self.MIN_WPM, min(self.MAX_WPM, wpm))
            self.wpm = wpm
            self.wpm_label.config(text=f"{wpm} WPM")
            self._update_progress()
        except ValueError:
            pass

    def _on_resize(self, event) -> None:
        """Handle canvas resize - redraw the current word."""
        if hasattr(self, 'canvas') and self.words:
            self._display_word()

    def _on_close(self) -> None:
        """Handle dialog close."""
        self.pause()
        self.dialog.destroy()


__all__ = ["RSVPDialog"]

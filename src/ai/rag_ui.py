"""
RAG UI Rendering Mixin

Handles typing indicators, markdown rendering, message display,
and copy button functionality for the RAG processor.
"""

import re
import tkinter as tk
from datetime import datetime
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class RagUIMixin:
    """Mixin providing UI rendering methods for RagProcessor."""

    # Pre-compiled regex patterns for markdown rendering (class-level for efficiency)
    _BOLD_PATTERN = re.compile(r'\*\*(.*?)\*\*')
    _NUMBERED_LIST_PATTERN = re.compile(r'^\s*\d+\.\s')

    def _show_typing_indicator(self, indicator_type: str = 'search'):
        """Show animated typing indicator in RAG text widget.

        Args:
            indicator_type: 'search' for document search phase,
                          'generate' for AI response generation phase
        """
        def show():
            try:
                if not hasattr(self.app, 'rag_text'):
                    return

                rag_widget = self.app.rag_text
                self._current_indicator_type = indicator_type

                # Select appropriate frames based on type
                frames = self._search_frames if indicator_type == 'search' else self._generate_frames

                # If indicator already showing, just update text
                if self._typing_indicator_mark:
                    try:
                        rag_widget.delete(self._typing_indicator_mark, "end-1c")
                        self._typing_frame_index = 0
                        rag_widget.insert(self._typing_indicator_mark, frames[0], "typing_indicator")
                        return
                    except (tk.TclError, AttributeError):
                        pass

                # Mark the position where we insert the indicator
                self._typing_indicator_mark = rag_widget.index("end-1c")

                # Insert initial typing indicator
                self._typing_frame_index = 0
                rag_widget.insert("end", frames[0], "typing_indicator")
                rag_widget.tag_config("typing_indicator", foreground="#888888", font=("Arial", 10, "italic"))

                # Scroll to bottom
                rag_widget.see("end")

                # Start animation
                self._animate_typing_indicator()

            except (tk.TclError, AttributeError) as e:
                logger.debug(f"Error showing typing indicator: {e}")

        # Execute on main thread
        self.app.after(0, show)

    def _animate_typing_indicator(self):
        """Animate the typing indicator with cycling dots."""
        def animate():
            try:
                if not self._typing_indicator_mark:
                    return

                if not hasattr(self.app, 'rag_text'):
                    return

                rag_widget = self.app.rag_text

                # Select appropriate frames based on current type
                frames = self._search_frames if self._current_indicator_type == 'search' else self._generate_frames

                # Delete old indicator text
                rag_widget.delete(self._typing_indicator_mark, "end-1c")

                # Cycle through frames
                self._typing_frame_index = (self._typing_frame_index + 1) % len(frames)

                # Insert new frame
                rag_widget.insert(self._typing_indicator_mark, frames[self._typing_frame_index], "typing_indicator")

                # Scroll to keep indicator visible
                rag_widget.see("end")

                # Schedule next animation (500ms interval)
                self._typing_animation_id = self.app.after(500, animate)

            except (tk.TclError, AttributeError) as e:
                logger.debug(f"Error animating typing indicator: {e}")

        animate()

    def _hide_typing_indicator(self):
        """Remove typing indicator from RAG text widget."""
        def hide():
            try:
                # Cancel animation
                if self._typing_animation_id:
                    try:
                        self.app.after_cancel(self._typing_animation_id)
                    except (tk.TclError, ValueError):
                        pass
                    self._typing_animation_id = None

                # Remove indicator text if mark exists
                if self._typing_indicator_mark and hasattr(self.app, 'rag_text'):
                    rag_widget = self.app.rag_text
                    try:
                        # Delete from mark to end
                        rag_widget.delete(self._typing_indicator_mark, "end")
                    except tk.TclError:
                        pass
                    self._typing_indicator_mark = None

                self._typing_frame_index = 0
                self._current_indicator_type = None

            except (tk.TclError, AttributeError) as e:
                logger.debug(f"Error hiding typing indicator: {e}")

        # Execute on main thread
        self.app.after(0, hide)

    def _update_progress_message(self, message: str):
        """Update progress message in the typing indicator.

        Args:
            message: Progress message to display
        """
        # This is called from the main thread
        try:
            if hasattr(self.app, 'rag_text') and self._typing_indicator_mark:
                # The typing indicator animation already handles the display
                # Just log the progress for now
                logger.debug(f"RAG progress: {message}")
        except (tk.TclError, AttributeError) as e:
            logger.debug(f"Error updating progress message: {e}")

    def _add_message_to_rag_tab(self, sender: str, message: str):
        """Add a message to the RAG tab."""
        if not hasattr(self.app, 'rag_text'):
            return

        def update_ui():
            # Add timestamp
            timestamp = datetime.now().strftime("%I:%M %p")

            # Get current position
            self.app.rag_text.mark_set("insert_start", "end")

            # Insert sender name with timestamp
            self.app.rag_text.insert("end", f"{sender} ({timestamp}):\n", "sender")

            # If this is from the RAG Assistant, render markdown and add copy button
            if sender == "RAG Assistant":
                # Store the response start position
                response_start = self.app.rag_text.index("end-1c")
                self._render_markdown(message)
                response_end = self.app.rag_text.index("end-1c")

                # Add copy button
                self._add_copy_button(message)

                # Add feedback buttons for each source (if results available)
                if self._last_search_results:
                    self._add_feedback_buttons()
            else:
                # Insert plain message for user messages
                self.app.rag_text.insert("end", f"{message}\n\n", "message")

            # Add separator
            self.app.rag_text.insert("end", "-" * 50 + "\n\n")

            # Configure tags for styling
            self.app.rag_text.tag_config("sender", font=("Arial", 10, "bold"))
            self.app.rag_text.tag_config("message", font=("Arial", 10))

            # Scroll to bottom
            self.app.rag_text.see("end")

        # Update UI in main thread
        self.app.after(0, update_ui)

    def _render_markdown(self, markdown_text: str):
        """Render markdown text with basic formatting in the text widget.

        Optimizations:
        - Pre-compiled regex patterns at class level
        - Batch inserts where possible
        - Early detection of plain text lines
        """
        # Sanitize input before rendering
        markdown_text = self._sanitize_response(markdown_text)

        lines = markdown_text.split('\n')
        text_widget = self.app.rag_text  # Local reference for faster access

        # Batch plain text lines for fewer insert calls
        plain_buffer = []

        def flush_plain_buffer():
            """Flush accumulated plain text."""
            nonlocal plain_buffer
            if plain_buffer:
                text_widget.insert("end", '\n'.join(plain_buffer) + "\n", "message")
                plain_buffer = []

        for line in lines:
            # Headers - check in order of likelihood (h2/h3 more common than h1)
            if line.startswith('#'):
                flush_plain_buffer()
                if line.startswith('### '):
                    text_widget.insert("end", line[4:] + "\n", "h3")
                elif line.startswith('## '):
                    text_widget.insert("end", line[3:] + "\n", "h2")
                elif line.startswith('# '):
                    text_widget.insert("end", line[2:] + "\n", "h1")
                else:
                    plain_buffer.append(line)

            # Bold text - check for ** before doing regex
            elif '**' in line:
                flush_plain_buffer()
                parts = self._BOLD_PATTERN.split(line)
                for i, part in enumerate(parts):
                    if part:  # Skip empty strings
                        if i % 2 == 0:
                            text_widget.insert("end", part)
                        else:
                            text_widget.insert("end", part, "bold")
                text_widget.insert("end", "\n")

            # Bullet points
            elif line.lstrip().startswith(('- ', '* ')):
                flush_plain_buffer()
                stripped = line.lstrip()
                indent = len(line) - len(stripped)
                bullet_text = stripped[2:]
                text_widget.insert("end", " " * indent + "\u2022 " + bullet_text + "\n", "bullet")

            # Numbered lists
            elif self._NUMBERED_LIST_PATTERN.match(line):
                flush_plain_buffer()
                text_widget.insert("end", line + "\n", "numbered")

            # Code blocks (simple)
            elif line.lstrip().startswith('```'):
                flush_plain_buffer()
                text_widget.insert("end", line + "\n", "code")

            # Regular text - accumulate for batch insert
            else:
                plain_buffer.append(line)

        # Flush any remaining plain text
        flush_plain_buffer()

        # Add an extra newline at the end
        text_widget.insert("end", "\n")

        # Configure markdown tags
        self.app.rag_text.tag_config("h1", font=("Arial", 16, "bold"), spacing3=5)
        self.app.rag_text.tag_config("h2", font=("Arial", 14, "bold"), spacing3=4)
        self.app.rag_text.tag_config("h3", font=("Arial", 12, "bold"), spacing3=3)
        self.app.rag_text.tag_config("bold", font=("Arial", 10, "bold"))
        self.app.rag_text.tag_config("bullet", lmargin1=20, lmargin2=30)
        self.app.rag_text.tag_config("numbered", lmargin1=20, lmargin2=30)
        self.app.rag_text.tag_config("code", font=("Courier", 10), background="#f0f0f0", relief="solid", borderwidth=1)

    def _add_copy_button(self, response_text: str):
        """Add a copy button for the response."""
        import tkinter as tk
        import ttkbootstrap as ttk

        # Add some space before the button
        self.app.rag_text.insert("end", "  ")

        # Create frame for button
        button_frame = ttk.Frame(self.app.rag_text)
        button_frame.configure(cursor="arrow")

        # Create copy button
        copy_btn = ttk.Button(
            button_frame,
            text="Copy",
            bootstyle="secondary-link",
            command=lambda: self._copy_to_clipboard(response_text)
        )
        copy_btn.pack(padx=2)

        # Add tooltip
        from ui.tooltip import ToolTip
        ToolTip(copy_btn, "Copy this response to clipboard")

        # Create window for button frame in text widget
        self.app.rag_text.window_create("end-1c", window=button_frame)
        self.app.rag_text.insert("end", "\n\n")

    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard."""
        try:
            try:
                import pyperclip
                pyperclip.copy(text)
            except ImportError:
                self.app.clipboard_clear()
                self.app.clipboard_append(text)
                self.app.update()

            # Show brief success message
            if hasattr(self.app, 'status_manager'):
                self.app.status_manager.success("Response copied to clipboard")
            logger.info("RAG response copied to clipboard")
        except (tk.TclError, OSError) as e:
            logger.error(f"Failed to copy to clipboard: {e}")
            if hasattr(self.app, 'status_manager'):
                self.app.status_manager.error("Failed to copy response")

    def _display_error(self, error_message: str):
        """Display an error message in the RAG tab."""
        self._add_message_to_rag_tab("System Error", error_message)

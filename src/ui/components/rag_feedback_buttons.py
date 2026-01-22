"""
RAG Feedback Buttons Component.

Provides upvote/downvote/flag buttons for RAG search results.
"""

import logging
import tkinter as tk
from typing import Callable, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import LEFT

logger = logging.getLogger(__name__)


class RAGFeedbackButtons:
    """Feedback button component for RAG results."""

    # Button styling
    BUTTON_WIDTH = 3
    BUTTON_PADDING = 2

    def __init__(
        self,
        on_feedback: Optional[Callable[[str, int, str], None]] = None,
        show_flag: bool = True,
        compact: bool = False
    ):
        """Initialize the feedback buttons component.

        Args:
            on_feedback: Callback function(document_id, chunk_index, feedback_type)
            show_flag: Whether to show the flag button
            compact: Use compact layout (inline)
        """
        self._on_feedback = on_feedback
        self._show_flag = show_flag
        self._compact = compact
        self._buttons: dict[str, dict] = {}  # Store button references by key

    def create_buttons(
        self,
        parent: tk.Widget,
        document_id: str,
        chunk_index: int,
        current_feedback: Optional[str] = None
    ) -> ttk.Frame:
        """Create feedback buttons for a result.

        Args:
            parent: Parent widget
            document_id: Document identifier
            chunk_index: Chunk index within document
            current_feedback: Current feedback state ('upvote', 'downvote', or None)

        Returns:
            Frame containing the feedback buttons
        """
        key = f"{document_id}:{chunk_index}"

        # Create frame
        if self._compact:
            frame = ttk.Frame(parent)
        else:
            frame = ttk.Frame(parent, padding=(self.BUTTON_PADDING, 0))

        # Upvote button
        upvote_style = "success" if current_feedback == "upvote" else "success-outline"
        upvote_btn = ttk.Button(
            frame,
            text="\u25b2",  # Unicode up arrow
            width=self.BUTTON_WIDTH,
            bootstyle=upvote_style,
            command=lambda: self._handle_feedback(document_id, chunk_index, "upvote")
        )
        upvote_btn.pack(side=LEFT, padx=(0, 2))

        # Downvote button
        downvote_style = "danger" if current_feedback == "downvote" else "danger-outline"
        downvote_btn = ttk.Button(
            frame,
            text="\u25bc",  # Unicode down arrow
            width=self.BUTTON_WIDTH,
            bootstyle=downvote_style,
            command=lambda: self._handle_feedback(document_id, chunk_index, "downvote")
        )
        downvote_btn.pack(side=LEFT, padx=(0, 2))

        # Flag button (optional)
        flag_btn = None
        if self._show_flag:
            flag_style = "warning" if current_feedback == "flag" else "warning-outline"
            flag_btn = ttk.Button(
                frame,
                text="\u2691",  # Unicode flag
                width=self.BUTTON_WIDTH,
                bootstyle=flag_style,
                command=lambda: self._handle_feedback(document_id, chunk_index, "flag")
            )
            flag_btn.pack(side=LEFT)

        # Store button references for state updates
        self._buttons[key] = {
            "frame": frame,
            "upvote": upvote_btn,
            "downvote": downvote_btn,
            "flag": flag_btn,
            "document_id": document_id,
            "chunk_index": chunk_index,
            "current_feedback": current_feedback,
        }

        return frame

    def _handle_feedback(
        self,
        document_id: str,
        chunk_index: int,
        feedback_type: str
    ):
        """Handle feedback button click.

        Args:
            document_id: Document identifier
            chunk_index: Chunk index within document
            feedback_type: Type of feedback ('upvote', 'downvote', 'flag')
        """
        key = f"{document_id}:{chunk_index}"
        button_info = self._buttons.get(key)

        if button_info:
            current = button_info.get("current_feedback")

            # Toggle off if clicking same button
            if current == feedback_type:
                new_feedback = None
            else:
                new_feedback = feedback_type

            # Update button states
            self._update_button_states(key, new_feedback)

            # Call callback
            if self._on_feedback:
                self._on_feedback(document_id, chunk_index, new_feedback or "remove")

    def _update_button_states(self, key: str, new_feedback: Optional[str]):
        """Update button visual states.

        Args:
            key: Button key (document_id:chunk_index)
            new_feedback: New feedback state or None
        """
        button_info = self._buttons.get(key)
        if not button_info:
            return

        # Update stored state
        button_info["current_feedback"] = new_feedback

        # Update upvote button
        upvote_btn = button_info.get("upvote")
        if upvote_btn:
            style = "success" if new_feedback == "upvote" else "success-outline"
            upvote_btn.configure(bootstyle=style)

        # Update downvote button
        downvote_btn = button_info.get("downvote")
        if downvote_btn:
            style = "danger" if new_feedback == "downvote" else "danger-outline"
            downvote_btn.configure(bootstyle=style)

        # Update flag button
        flag_btn = button_info.get("flag")
        if flag_btn:
            style = "warning" if new_feedback == "flag" else "warning-outline"
            flag_btn.configure(bootstyle=style)

    def set_feedback_state(
        self,
        document_id: str,
        chunk_index: int,
        feedback_type: Optional[str]
    ):
        """Set the feedback state for a result externally.

        Args:
            document_id: Document identifier
            chunk_index: Chunk index within document
            feedback_type: Feedback type or None
        """
        key = f"{document_id}:{chunk_index}"
        self._update_button_states(key, feedback_type)

    def get_feedback_state(
        self,
        document_id: str,
        chunk_index: int
    ) -> Optional[str]:
        """Get the current feedback state for a result.

        Args:
            document_id: Document identifier
            chunk_index: Chunk index within document

        Returns:
            Current feedback type or None
        """
        key = f"{document_id}:{chunk_index}"
        button_info = self._buttons.get(key)
        if button_info:
            return button_info.get("current_feedback")
        return None

    def clear(self):
        """Clear all button references."""
        self._buttons.clear()

    def destroy(self, document_id: str = None, chunk_index: int = None):
        """Destroy button widgets.

        Args:
            document_id: Optional document to destroy. If None, destroys all.
            chunk_index: Optional chunk index. Required if document_id is provided.
        """
        if document_id and chunk_index is not None:
            key = f"{document_id}:{chunk_index}"
            button_info = self._buttons.get(key)
            if button_info:
                frame = button_info.get("frame")
                if frame and frame.winfo_exists():
                    frame.destroy()
                del self._buttons[key]
        else:
            # Destroy all
            for key, button_info in list(self._buttons.items()):
                frame = button_info.get("frame")
                if frame and frame.winfo_exists():
                    frame.destroy()
            self._buttons.clear()


class RAGFeedbackPanel(ttk.Frame):
    """A panel containing feedback buttons with feedback count display."""

    def __init__(
        self,
        parent: tk.Widget,
        document_id: str,
        chunk_index: int,
        on_feedback: Optional[Callable[[str, int, str], None]] = None,
        upvotes: int = 0,
        downvotes: int = 0,
        current_feedback: Optional[str] = None,
        **kwargs
    ):
        """Initialize the feedback panel.

        Args:
            parent: Parent widget
            document_id: Document identifier
            chunk_index: Chunk index within document
            on_feedback: Callback function(document_id, chunk_index, feedback_type)
            upvotes: Current upvote count
            downvotes: Current downvote count
            current_feedback: Current user feedback state
            **kwargs: Additional frame arguments
        """
        super().__init__(parent, **kwargs)

        self._document_id = document_id
        self._chunk_index = chunk_index
        self._on_feedback = on_feedback
        self._upvotes = upvotes
        self._downvotes = downvotes
        self._current_feedback = current_feedback

        self._create_widgets()

    def _create_widgets(self):
        """Create the panel widgets."""
        # Score display
        net_score = self._upvotes - self._downvotes
        score_color = "success" if net_score > 0 else ("danger" if net_score < 0 else "secondary")

        self._score_label = ttk.Label(
            self,
            text=f"{net_score:+d}" if net_score != 0 else "0",
            bootstyle=score_color,
            font=("TkDefaultFont", 9, "bold"),
            width=4
        )
        self._score_label.pack(side=LEFT, padx=(0, 5))

        # Upvote button
        upvote_style = "success" if self._current_feedback == "upvote" else "success-outline"
        self._upvote_btn = ttk.Button(
            self,
            text="\u25b2",
            width=3,
            bootstyle=upvote_style,
            command=lambda: self._handle_feedback("upvote")
        )
        self._upvote_btn.pack(side=LEFT, padx=1)

        # Downvote button
        downvote_style = "danger" if self._current_feedback == "downvote" else "danger-outline"
        self._downvote_btn = ttk.Button(
            self,
            text="\u25bc",
            width=3,
            bootstyle=downvote_style,
            command=lambda: self._handle_feedback("downvote")
        )
        self._downvote_btn.pack(side=LEFT, padx=1)

    def _handle_feedback(self, feedback_type: str):
        """Handle feedback button click."""
        # Toggle off if clicking same button
        if self._current_feedback == feedback_type:
            new_feedback = None
            # Revert score change
            if feedback_type == "upvote":
                self._upvotes -= 1
            else:
                self._downvotes -= 1
        else:
            # If changing from one to another, revert previous
            if self._current_feedback == "upvote":
                self._upvotes -= 1
            elif self._current_feedback == "downvote":
                self._downvotes -= 1

            new_feedback = feedback_type
            # Apply new feedback
            if feedback_type == "upvote":
                self._upvotes += 1
            else:
                self._downvotes += 1

        self._current_feedback = new_feedback
        self._update_display()

        # Call callback
        if self._on_feedback:
            self._on_feedback(
                self._document_id,
                self._chunk_index,
                new_feedback or "remove"
            )

    def _update_display(self):
        """Update the display after feedback change."""
        # Update score
        net_score = self._upvotes - self._downvotes
        score_color = "success" if net_score > 0 else ("danger" if net_score < 0 else "secondary")
        self._score_label.configure(
            text=f"{net_score:+d}" if net_score != 0 else "0",
            bootstyle=score_color
        )

        # Update button styles
        upvote_style = "success" if self._current_feedback == "upvote" else "success-outline"
        self._upvote_btn.configure(bootstyle=upvote_style)

        downvote_style = "danger" if self._current_feedback == "downvote" else "danger-outline"
        self._downvote_btn.configure(bootstyle=downvote_style)

    def set_counts(self, upvotes: int, downvotes: int):
        """Update the vote counts.

        Args:
            upvotes: New upvote count
            downvotes: New downvote count
        """
        self._upvotes = upvotes
        self._downvotes = downvotes
        self._update_display()

    def set_feedback_state(self, feedback_type: Optional[str]):
        """Set the current feedback state.

        Args:
            feedback_type: Feedback type or None
        """
        self._current_feedback = feedback_type
        self._update_display()

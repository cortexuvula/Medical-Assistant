"""
Search Autocomplete Component for RAG Tab.

Provides real-time suggestions as user types, sourcing from:
- Recent queries from conversation history
- Medical term expansions
- Common medical search patterns
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import Callable, List, Optional

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class SearchAutocomplete:
    """Autocomplete dropdown for RAG search input.

    Displays real-time suggestions based on:
    - Recent queries from conversation history
    - Medical abbreviation expansions
    - Common medical search templates
    """

    # Common medical search templates
    COMMON_QUERIES = [
        "What medications treat",
        "What are the symptoms of",
        "What causes",
        "How is diagnosed",
        "What are the side effects of",
        "Treatment options for",
        "Differential diagnosis for",
        "Lab values for",
        "Contraindications for",
        "Drug interactions with",
    ]

    # Minimum characters before showing suggestions
    MIN_CHARS = 2

    # Maximum suggestions to display
    MAX_SUGGESTIONS = 8

    def __init__(
        self,
        parent: tk.Widget,
        input_widget: tk.Entry,
        get_recent_queries: Optional[Callable[[], List[str]]] = None,
        get_medical_terms: Optional[Callable[[str], List[str]]] = None,
        on_select: Optional[Callable[[str], None]] = None
    ):
        """Initialize the autocomplete component.

        Args:
            parent: Parent widget for the dropdown
            input_widget: The entry widget to attach autocomplete to
            get_recent_queries: Callback to get recent queries from history
            get_medical_terms: Callback to get medical term expansions
            on_select: Callback when a suggestion is selected
        """
        self.parent = parent
        self.input_widget = input_widget
        self.get_recent_queries = get_recent_queries
        self.get_medical_terms = get_medical_terms
        self.on_select = on_select

        # Create dropdown listbox (hidden initially)
        self._create_dropdown()

        # Bind input events
        self._bind_events()

        # Debounce timer
        self._debounce_id: Optional[str] = None
        self._debounce_delay = 150  # ms

        # Track if dropdown is visible
        self._visible: bool = False

        # Current selection index
        self._selection_index: int = -1

    def _create_dropdown(self) -> None:
        """Create the dropdown listbox widget."""
        # Create toplevel window for dropdown (so it can float)
        self.dropdown_window = tk.Toplevel(self.parent)
        self.dropdown_window.withdraw()  # Hide initially
        self.dropdown_window.overrideredirect(True)  # No window decorations
        self.dropdown_window.attributes('-topmost', True)  # Always on top

        # Create listbox frame with border
        frame = ttk.Frame(self.dropdown_window, borderwidth=1, relief="solid")
        frame.pack(fill=tk.BOTH, expand=True)

        # Create scrollbar
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create listbox
        self.listbox = tk.Listbox(
            frame,
            height=min(8, self.MAX_SUGGESTIONS),
            selectmode=tk.SINGLE,
            yscrollcommand=scrollbar.set,
            font=("Arial", 10),
            activestyle="none",
            highlightthickness=0,
            borderwidth=0,
            selectbackground="#0078D4",
            selectforeground="white"
        )
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        # Bind listbox events
        self.listbox.bind("<ButtonRelease-1>", self._on_click)
        self.listbox.bind("<Motion>", self._on_mouse_move)
        self.listbox.bind("<Leave>", self._on_mouse_leave)

        # Bind window close to hide dropdown
        self.dropdown_window.bind("<FocusOut>", self._on_focus_out)

    def _bind_events(self) -> None:
        """Bind keyboard and focus events to input widget."""
        self.input_widget.bind("<KeyRelease>", self._on_key_release)
        self.input_widget.bind("<Up>", self._on_arrow_up)
        self.input_widget.bind("<Down>", self._on_arrow_down)
        self.input_widget.bind("<Return>", self._on_enter)
        self.input_widget.bind("<Escape>", self._on_escape)
        self.input_widget.bind("<FocusOut>", self._on_input_focus_out)

    def _on_key_release(self, event: tk.Event) -> None:
        """Handle key release - fetch and show suggestions with debounce."""
        # Ignore navigation keys
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return

        # Cancel previous debounce timer
        if self._debounce_id:
            self.parent.after_cancel(self._debounce_id)

        # Schedule suggestion update
        self._debounce_id = self.parent.after(
            self._debounce_delay,
            self._update_suggestions
        )

    def _update_suggestions(self) -> None:
        """Update suggestions based on current input."""
        text = self.input_widget.get().strip()

        if len(text) < self.MIN_CHARS:
            self._hide_dropdown()
            return

        suggestions = self._get_suggestions(text)

        if suggestions:
            self._show_dropdown(suggestions)
        else:
            self._hide_dropdown()

    def _get_suggestions(self, prefix: str) -> List[str]:
        """Get suggestions from multiple sources.

        Args:
            prefix: Current text in input

        Returns:
            List of suggestion strings
        """
        suggestions = []
        prefix_lower = prefix.lower()
        seen = set()

        def add_unique(suggestion: str):
            """Add suggestion if not already added."""
            if suggestion.lower() not in seen:
                seen.add(suggestion.lower())
                suggestions.append(suggestion)

        # 1. Recent queries from conversation history (highest priority)
        if self.get_recent_queries:
            try:
                recent = self.get_recent_queries()
                for query in recent:
                    if prefix_lower in query.lower():
                        add_unique(query)
                        if len(suggestions) >= self.MAX_SUGGESTIONS:
                            return suggestions
            except Exception as e:
                logger.debug(f"Error getting recent queries: {e}")

        # 2. Medical term expansions
        if self.get_medical_terms:
            try:
                terms = self.get_medical_terms(prefix)
                for term in terms:
                    add_unique(term)
                    if len(suggestions) >= self.MAX_SUGGESTIONS:
                        return suggestions
            except Exception as e:
                logger.debug(f"Error getting medical terms: {e}")

        # 3. Common search templates
        for template in self.COMMON_QUERIES:
            if template.lower().startswith(prefix_lower):
                add_unique(template)
                if len(suggestions) >= self.MAX_SUGGESTIONS:
                    return suggestions

        # 4. Fuzzy match templates that contain the prefix
        for template in self.COMMON_QUERIES:
            if prefix_lower in template.lower() and template not in suggestions:
                add_unique(template)
                if len(suggestions) >= self.MAX_SUGGESTIONS:
                    return suggestions

        return suggestions[:self.MAX_SUGGESTIONS]

    def _show_dropdown(self, suggestions: List[str]) -> None:
        """Show the dropdown with suggestions.

        Args:
            suggestions: List of suggestion strings
        """
        # Clear existing items
        self.listbox.delete(0, tk.END)

        # Add new suggestions
        for suggestion in suggestions:
            self.listbox.insert(tk.END, suggestion)

        # Position dropdown below input widget
        self._position_dropdown()

        # Show dropdown
        self.dropdown_window.deiconify()
        self._visible = True
        self._selection_index = -1

        # Adjust height based on items
        num_items = min(len(suggestions), 8)
        self.listbox.config(height=num_items)

    def _position_dropdown(self) -> None:
        """Position dropdown below the input widget."""
        try:
            # Get input widget position
            x = self.input_widget.winfo_rootx()
            y = self.input_widget.winfo_rooty() + self.input_widget.winfo_height()
            width = self.input_widget.winfo_width()

            # Set dropdown position and size
            self.dropdown_window.geometry(f"{width}x{self.listbox.winfo_reqheight()}+{x}+{y}")
        except tk.TclError as e:
            logger.debug(f"Error positioning dropdown: {e}")

    def _hide_dropdown(self) -> None:
        """Hide the dropdown."""
        self.dropdown_window.withdraw()
        self._visible = False
        self._selection_index = -1

    def _on_arrow_up(self, event: tk.Event) -> str:
        """Handle up arrow key."""
        if not self._visible:
            return

        if self._selection_index > 0:
            self._selection_index -= 1
            self._highlight_selection()
        elif self._selection_index == -1:
            self._selection_index = self.listbox.size() - 1
            self._highlight_selection()

        return "break"  # Prevent default behavior

    def _on_arrow_down(self, event: tk.Event) -> str:
        """Handle down arrow key."""
        if not self._visible:
            return

        if self._selection_index < self.listbox.size() - 1:
            self._selection_index += 1
            self._highlight_selection()

        return "break"  # Prevent default behavior

    def _highlight_selection(self) -> None:
        """Highlight the current selection."""
        self.listbox.selection_clear(0, tk.END)
        if 0 <= self._selection_index < self.listbox.size():
            self.listbox.selection_set(self._selection_index)
            self.listbox.see(self._selection_index)

    def _on_enter(self, event: tk.Event) -> Optional[str]:
        """Handle Enter key."""
        if self._visible and 0 <= self._selection_index < self.listbox.size():
            self._select_current()
            return "break"  # Prevent default behavior

    def _on_escape(self, event: tk.Event) -> Optional[str]:
        """Handle Escape key."""
        if self._visible:
            self._hide_dropdown()
            return "break"

    def _on_click(self, event: tk.Event) -> None:
        """Handle click on listbox item."""
        self._select_current()

    def _on_mouse_move(self, event: tk.Event) -> None:
        """Handle mouse movement over listbox."""
        index = self.listbox.nearest(event.y)
        if index >= 0:
            self._selection_index = index
            self._highlight_selection()

    def _on_mouse_leave(self, event: tk.Event) -> None:
        """Handle mouse leaving listbox."""
        pass  # Keep current selection

    def _select_current(self) -> None:
        """Select the current highlighted item."""
        if not self._visible:
            return

        selection = self.listbox.curselection()
        if selection:
            selected_text = self.listbox.get(selection[0])
            self._apply_selection(selected_text)
        elif 0 <= self._selection_index < self.listbox.size():
            selected_text = self.listbox.get(self._selection_index)
            self._apply_selection(selected_text)

    def _apply_selection(self, text: str) -> None:
        """Apply the selected suggestion to input.

        Args:
            text: Selected suggestion text
        """
        # Clear and set input value
        self.input_widget.delete(0, tk.END)
        self.input_widget.insert(0, text)

        # Hide dropdown
        self._hide_dropdown()

        # Call callback if provided
        if self.on_select:
            try:
                self.on_select(text)
            except Exception as e:
                logger.error(f"Error in on_select callback: {e}")

        # Set focus back to input
        self.input_widget.focus_set()

    def _on_focus_out(self, event: tk.Event) -> None:
        """Handle focus leaving dropdown window."""
        # Check if focus went to input widget
        try:
            if self.parent.focus_get() != self.input_widget:
                self._hide_dropdown()
        except tk.TclError:
            self._hide_dropdown()

    def _on_input_focus_out(self, event: tk.Event) -> None:
        """Handle focus leaving input widget."""
        # Delay hide to allow click on dropdown
        self.parent.after(150, self._check_hide)

    def _check_hide(self) -> None:
        """Check if dropdown should be hidden."""
        try:
            focused = self.parent.focus_get()
            if focused != self.input_widget and focused != self.listbox:
                self._hide_dropdown()
        except tk.TclError:
            self._hide_dropdown()

    def destroy(self) -> None:
        """Clean up resources."""
        if self._debounce_id:
            try:
                self.parent.after_cancel(self._debounce_id)
            except tk.TclError:
                pass

        try:
            self.dropdown_window.destroy()
        except tk.TclError:
            pass


def get_medical_term_suggestions(prefix: str) -> List[str]:
    """Get medical term suggestions based on prefix.

    This function uses the MEDICAL_ABBREVIATIONS from query_expander.

    Args:
        prefix: Text prefix to match

    Returns:
        List of matching medical terms
    """
    try:
        from rag.query_expander import MEDICAL_ABBREVIATIONS, MEDICAL_SYNONYMS

        suggestions = []
        prefix_lower = prefix.lower()

        # Check abbreviations
        for abbr, expansions in MEDICAL_ABBREVIATIONS.items():
            if abbr.startswith(prefix_lower):
                # Add the expansion, not just abbreviation
                for exp in expansions[:2]:
                    suggestions.append(f"{exp} ({abbr.upper()})")

            # Also check if prefix matches expansions
            for exp in expansions:
                if exp.lower().startswith(prefix_lower):
                    suggestions.append(f"{exp} ({abbr.upper()})")

        # Check synonyms
        for term, synonyms in MEDICAL_SYNONYMS.items():
            if term.lower().startswith(prefix_lower):
                suggestions.append(term)

        return suggestions[:10]  # Limit results

    except ImportError:
        logger.debug("query_expander not available for suggestions")
        return []
    except Exception as e:
        logger.debug(f"Error getting medical suggestions: {e}")
        return []

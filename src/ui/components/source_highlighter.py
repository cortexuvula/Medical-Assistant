"""
Source Highlighter Component for RAG Tab.

Provides visual source attribution in RAG responses by:
- Highlighting text segments from different sources with colors
- Showing tooltips with source details on hover
- Displaying a source legend at the bottom of responses
"""

import tkinter as tk
import ttkbootstrap as ttk
from dataclasses import dataclass, field
from typing import Optional

from utils.structured_logging import get_logger

logger = get_logger(__name__)


@dataclass
class SourceAttribution:
    """Tracks which source contributed to response text."""
    source_index: int  # Index in sources list (for color assignment)
    document_id: str
    document_name: str
    chunk_index: int
    chunk_text: str
    page_number: Optional[int]
    score: float
    response_spans: list[tuple[int, int]] = field(default_factory=list)  # (start, end) char positions

    @property
    def color_key(self) -> str:
        """Get the key for color assignment."""
        return f"{self.document_id}:{self.chunk_index}"


class SourceHighlighter:
    """Highlights text segments with source attribution."""

    # Color palette for different sources (light backgrounds)
    SOURCE_COLORS = [
        {"bg": "#E3F2FD", "fg": "#1565C0"},  # Light blue
        {"bg": "#E8F5E9", "fg": "#2E7D32"},  # Light green
        {"bg": "#FFF3E0", "fg": "#E65100"},  # Light orange
        {"bg": "#F3E5F5", "fg": "#7B1FA2"},  # Light purple
        {"bg": "#FFEBEE", "fg": "#C62828"},  # Light red
        {"bg": "#E0F7FA", "fg": "#00838F"},  # Light cyan
        {"bg": "#FFF8E1", "fg": "#F57F17"},  # Light amber
        {"bg": "#F1F8E9", "fg": "#558B2F"},  # Light lime
    ]

    # Dark theme colors
    DARK_SOURCE_COLORS = [
        {"bg": "#1A365D", "fg": "#90CDF4"},  # Dark blue
        {"bg": "#1C4532", "fg": "#9AE6B4"},  # Dark green
        {"bg": "#5D4037", "fg": "#FFCC80"},  # Dark orange/brown
        {"bg": "#4A235A", "fg": "#D7BDE2"},  # Dark purple
        {"bg": "#5D1A1A", "fg": "#FFAB91"},  # Dark red
        {"bg": "#014D4E", "fg": "#80DEEA"},  # Dark cyan
        {"bg": "#4D4000", "fg": "#FFE082"},  # Dark amber
        {"bg": "#33691E", "fg": "#C5E1A5"},  # Dark lime
    ]

    def __init__(self, text_widget: tk.Text, dark_theme: bool = False):
        """Initialize the source highlighter.

        Args:
            text_widget: Text widget to apply highlighting to
            dark_theme: Whether to use dark theme colors
        """
        self.text_widget = text_widget
        self.dark_theme = dark_theme
        self._source_tags = {}  # color_key -> tag name
        self._source_colors = {}  # color_key -> color dict
        self._color_index = 0
        self._attributions = []  # List of SourceAttribution
        self._tooltip = None
        self._active_tag = None

        self._create_base_tags()

    def _create_base_tags(self):
        """Create base text tags for highlighting."""
        # Create tags for each color
        colors = self.DARK_SOURCE_COLORS if self.dark_theme else self.SOURCE_COLORS

        for i, color in enumerate(colors):
            tag_name = f"source_{i}"
            self.text_widget.tag_configure(
                tag_name,
                background=color["bg"],
                foreground=color.get("fg_text", color["fg"]) if self.dark_theme else None
            )
            # Bind hover events
            self.text_widget.tag_bind(tag_name, "<Enter>", lambda e, t=tag_name: self._on_tag_enter(e, t))
            self.text_widget.tag_bind(tag_name, "<Leave>", lambda e: self._on_tag_leave(e))
            self.text_widget.tag_bind(tag_name, "<Button-1>", lambda e, t=tag_name: self._on_tag_click(e, t))

    def _get_or_create_tag(self, color_key: str) -> str:
        """Get or create a tag for a source.

        Args:
            color_key: Unique key for the source

        Returns:
            Tag name
        """
        if color_key not in self._source_tags:
            tag_index = self._color_index % len(self.SOURCE_COLORS)
            tag_name = f"source_{tag_index}"
            self._source_tags[color_key] = tag_name

            colors = self.DARK_SOURCE_COLORS if self.dark_theme else self.SOURCE_COLORS
            self._source_colors[color_key] = colors[tag_index]
            self._color_index += 1

        return self._source_tags[color_key]

    def set_theme(self, dark: bool):
        """Update theme colors.

        Args:
            dark: Whether to use dark theme
        """
        self.dark_theme = dark

        # Update existing tags
        colors = self.DARK_SOURCE_COLORS if dark else self.SOURCE_COLORS

        for i in range(len(colors)):
            tag_name = f"source_{i}"
            self.text_widget.tag_configure(
                tag_name,
                background=colors[i]["bg"],
                foreground=colors[i].get("fg_text", colors[i]["fg"]) if dark else None
            )

        # Update stored colors
        for color_key in self._source_colors:
            tag_index = int(self._source_tags[color_key].split("_")[1])
            self._source_colors[color_key] = colors[tag_index]

    def highlight_sources(self, text: str, sources: list[SourceAttribution]):
        """Apply source highlighting to text.

        Finds matching text segments and highlights them.

        Args:
            text: Full response text
            sources: List of source attributions with chunk_text
        """
        self._attributions = sources

        for source in sources:
            tag_name = self._get_or_create_tag(source.color_key)

            # Find occurrences of chunk text in response
            chunk_text = source.chunk_text

            # Find significant phrases from chunk (not single words)
            phrases = self._extract_significant_phrases(chunk_text)

            for phrase in phrases:
                # Find all occurrences in text widget
                start_idx = "1.0"
                while True:
                    start_idx = self.text_widget.search(
                        phrase,
                        start_idx,
                        stopindex=tk.END,
                        nocase=True
                    )
                    if not start_idx:
                        break

                    end_idx = f"{start_idx}+{len(phrase)}c"
                    self.text_widget.tag_add(tag_name, start_idx, end_idx)

                    # Store span
                    try:
                        start_pos = self.text_widget.count("1.0", start_idx)[0]
                        end_pos = start_pos + len(phrase)
                        source.response_spans.append((start_pos, end_pos))
                    except Exception:
                        pass

                    # Move past this occurrence
                    start_idx = end_idx

    def _extract_significant_phrases(self, text: str, min_length: int = 5, max_phrases: int = 5) -> list[str]:
        """Extract significant phrases from chunk text.

        Args:
            text: Chunk text
            min_length: Minimum phrase length in words
            max_length: Maximum number of phrases to extract

        Returns:
            List of significant phrases
        """
        import re

        phrases = []

        # Split into sentences
        sentences = re.split(r'[.!?]', text)

        for sentence in sentences:
            sentence = sentence.strip()
            words = sentence.split()

            # Take phrases of min_length words
            if len(words) >= min_length:
                # Take first min_length words as phrase
                phrase = " ".join(words[:min_length])
                if len(phrase) > 20 and phrase not in phrases:
                    phrases.append(phrase)

                    if len(phrases) >= max_phrases:
                        return phrases

        # Also check for multi-word terms
        # Medical terms often have specific patterns
        medical_patterns = [
            r'\b(?:type\s+\d+\s+diabetes|blood\s+pressure|heart\s+rate)\b',
            r'\b(?:myocardial\s+infarction|chest\s+pain|shortness\s+of\s+breath)\b',
            r'\b(?:mg|mg/dL|mmol/L)\b',
        ]

        for pattern in medical_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if match not in phrases:
                    phrases.append(match)
                    if len(phrases) >= max_phrases:
                        return phrases

        return phrases[:max_phrases]

    def _on_tag_enter(self, event, tag_name: str):
        """Handle mouse entering a highlighted region.

        Args:
            event: Tkinter event
            tag_name: Name of the tag being entered
        """
        self._active_tag = tag_name
        self._show_tooltip(event)

    def _on_tag_leave(self, event):
        """Handle mouse leaving a highlighted region."""
        self._active_tag = None
        self._hide_tooltip()

    def _on_tag_click(self, event, tag_name: str):
        """Handle click on a highlighted region.

        Args:
            event: Tkinter event
            tag_name: Name of the tag clicked
        """
        # Find the source for this tag
        for color_key, stored_tag in self._source_tags.items():
            if stored_tag == tag_name:
                # Find the attribution
                for attr in self._attributions:
                    if attr.color_key == color_key:
                        self._show_source_details(attr)
                        break
                break

    def _show_tooltip(self, event):
        """Show tooltip with source info.

        Args:
            event: Mouse event
        """
        if not self._active_tag:
            return

        # Find source info for this tag
        source_info = None
        for color_key, stored_tag in self._source_tags.items():
            if stored_tag == self._active_tag:
                for attr in self._attributions:
                    if attr.color_key == color_key:
                        source_info = attr
                        break
                break

        if not source_info:
            return

        # Create tooltip window
        if self._tooltip:
            self._tooltip.destroy()

        self._tooltip = tk.Toplevel(self.text_widget)
        self._tooltip.wm_overrideredirect(True)

        # Position near cursor
        x = event.x_root + 10
        y = event.y_root + 10
        self._tooltip.wm_geometry(f"+{x}+{y}")

        # Tooltip content
        frame = ttk.Frame(self._tooltip, borderwidth=1, relief="solid")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text=f"Source: {source_info.document_name}",
            font=("Arial", 9, "bold")
        ).pack(anchor="w", padx=5, pady=2)

        if source_info.page_number:
            ttk.Label(
                frame,
                text=f"Page: {source_info.page_number}",
                font=("Arial", 9)
            ).pack(anchor="w", padx=5)

        ttk.Label(
            frame,
            text=f"Relevance: {source_info.score:.1%}",
            font=("Arial", 9)
        ).pack(anchor="w", padx=5, pady=2)

    def _hide_tooltip(self):
        """Hide the tooltip."""
        if self._tooltip:
            self._tooltip.destroy()
            self._tooltip = None

    def _show_source_details(self, source: SourceAttribution):
        """Show detailed source information dialog.

        Args:
            source: Source attribution to show details for
        """
        dialog = tk.Toplevel(self.text_widget)
        dialog.title(f"Source: {source.document_name}")
        dialog.geometry("500x400")

        # Header
        header_frame = ttk.Frame(dialog)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text=source.document_name,
            font=("Arial", 12, "bold")
        ).pack(anchor="w")

        info_text = f"Chunk {source.chunk_index + 1}"
        if source.page_number:
            info_text += f" | Page {source.page_number}"
        info_text += f" | Relevance: {source.score:.1%}"

        ttk.Label(
            header_frame,
            text=info_text,
            font=("Arial", 9),
            foreground="gray"
        ).pack(anchor="w")

        # Chunk text
        text_frame = ttk.LabelFrame(dialog, text="Source Content", padding=10)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        text_widget = tk.Text(text_frame, wrap=tk.WORD, font=("Arial", 10))
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert("1.0", source.chunk_text)
        text_widget.config(state=tk.DISABLED)

        # Scrollbar
        scrollbar = ttk.Scrollbar(text_widget, command=text_widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.config(yscrollcommand=scrollbar.set)

        # Close button
        ttk.Button(
            dialog,
            text="Close",
            command=dialog.destroy
        ).pack(pady=10)

    def clear(self):
        """Clear all highlighting."""
        for i in range(len(self.SOURCE_COLORS)):
            tag_name = f"source_{i}"
            self.text_widget.tag_remove(tag_name, "1.0", tk.END)

        self._source_tags.clear()
        self._source_colors.clear()
        self._color_index = 0
        self._attributions.clear()


class SourceLegend:
    """Displays a legend showing source color mapping."""

    def __init__(self, parent: tk.Widget):
        """Initialize source legend.

        Args:
            parent: Parent widget
        """
        self.parent = parent
        self._items = []  # List of (color_key, document_name, score)
        self._create_widgets()

    def _create_widgets(self):
        """Create legend widgets."""
        self.frame = ttk.LabelFrame(self.parent, text="Sources")

        self.items_frame = ttk.Frame(self.frame)
        self.items_frame.pack(fill=tk.X)

    def show(self):
        """Show the legend."""
        self.frame.pack(fill=tk.X, padx=5, pady=5)

    def hide(self):
        """Hide the legend."""
        self.frame.pack_forget()

    def update(self, sources: list[SourceAttribution], colors: dict[str, dict]):
        """Update legend with sources.

        Args:
            sources: List of source attributions
            colors: Mapping of color_key to color dict
        """
        # Clear existing items
        for widget in self.items_frame.winfo_children():
            widget.destroy()

        # Group by document
        docs = {}
        for source in sources:
            key = source.document_name
            if key not in docs:
                docs[key] = {
                    "color_key": source.color_key,
                    "score": source.score,
                    "count": 0
                }
            docs[key]["count"] += 1
            docs[key]["score"] = max(docs[key]["score"], source.score)

        # Create legend items
        for doc_name, info in docs.items():
            item_frame = ttk.Frame(self.items_frame)
            item_frame.pack(fill=tk.X, pady=1)

            # Color swatch
            color = colors.get(info["color_key"], {"bg": "#cccccc"})
            swatch = tk.Canvas(
                item_frame,
                width=16,
                height=16,
                bg=color["bg"],
                highlightthickness=1,
                highlightbackground="gray"
            )
            swatch.pack(side=tk.LEFT, padx=2)

            # Document name (truncated)
            name_display = doc_name if len(doc_name) <= 30 else doc_name[:27] + "..."
            ttk.Label(
                item_frame,
                text=name_display,
                font=("Arial", 9)
            ).pack(side=tk.LEFT, padx=5)

            # Score
            ttk.Label(
                item_frame,
                text=f"{info['score']:.0%}",
                font=("Arial", 9),
                foreground="gray"
            ).pack(side=tk.RIGHT, padx=5)

            # Count
            if info["count"] > 1:
                ttk.Label(
                    item_frame,
                    text=f"({info['count']} refs)",
                    font=("Arial", 8),
                    foreground="gray"
                ).pack(side=tk.RIGHT)

    def clear(self):
        """Clear the legend."""
        for widget in self.items_frame.winfo_children():
            widget.destroy()


def create_source_attributions(search_results: list) -> list[SourceAttribution]:
    """Create source attributions from search results.

    Args:
        search_results: List of HybridSearchResult or similar

    Returns:
        List of SourceAttribution objects
    """
    attributions = []

    for i, result in enumerate(search_results):
        attribution = SourceAttribution(
            source_index=i,
            document_id=getattr(result, 'document_id', ''),
            document_name=getattr(result, 'document_filename', 'Unknown'),
            chunk_index=getattr(result, 'chunk_index', 0),
            chunk_text=getattr(result, 'chunk_text', ''),
            page_number=result.metadata.get('page_number') if getattr(result, 'metadata', None) else None,
            score=getattr(result, 'combined_score', 0.0)
        )
        attributions.append(attribution)

    return attributions

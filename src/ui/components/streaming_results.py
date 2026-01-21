"""
Streaming Results Display Component for RAG Tab.

Displays search results progressively as they arrive from different
search phases (vector, BM25, graph) with animated transitions.
"""

import tkinter as tk
import ttkbootstrap as ttk
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class SearchPhase(str, Enum):
    """Search phases for progressive result display."""
    INITIALIZING = "initializing"
    EMBEDDING = "embedding"
    VECTOR = "vector"
    BM25 = "bm25"
    GRAPH = "graph"
    MERGING = "merging"
    GENERATING = "generating"
    COMPLETE = "complete"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class ProgressState:
    """Current progress state for streaming display."""
    phase: SearchPhase = SearchPhase.INITIALIZING
    message: str = "Initializing search..."
    progress_percent: float = 0.0
    results_count: int = 0
    processing_time_ms: float = 0.0


@dataclass
class PartialResult:
    """A partial result from a search phase."""
    document_filename: str
    chunk_text: str
    score: float
    source_phase: str  # "vector", "bm25", "graph"
    document_id: str = ""
    chunk_index: int = 0
    metadata: dict = field(default_factory=dict)


class StreamingProgressBar:
    """Animated progress bar for search phases."""

    # Phase progress percentages
    PHASE_PROGRESS = {
        SearchPhase.INITIALIZING: 5,
        SearchPhase.EMBEDDING: 15,
        SearchPhase.VECTOR: 40,
        SearchPhase.BM25: 55,
        SearchPhase.GRAPH: 70,
        SearchPhase.MERGING: 85,
        SearchPhase.GENERATING: 95,
        SearchPhase.COMPLETE: 100,
        SearchPhase.ERROR: 0,
        SearchPhase.CANCELLED: 0,
    }

    # Phase descriptions
    PHASE_MESSAGES = {
        SearchPhase.INITIALIZING: "Initializing search...",
        SearchPhase.EMBEDDING: "Generating query embedding...",
        SearchPhase.VECTOR: "Searching vector database...",
        SearchPhase.BM25: "Searching keywords...",
        SearchPhase.GRAPH: "Searching knowledge graph...",
        SearchPhase.MERGING: "Merging and ranking results...",
        SearchPhase.GENERATING: "Generating response...",
        SearchPhase.COMPLETE: "Search complete",
        SearchPhase.ERROR: "Search failed",
        SearchPhase.CANCELLED: "Search cancelled",
    }

    def __init__(self, parent: tk.Widget):
        """Initialize progress bar.

        Args:
            parent: Parent widget to contain progress bar
        """
        self.parent = parent
        self._create_widgets()
        self._current_phase = SearchPhase.INITIALIZING
        self._animation_id = None

    def _create_widgets(self):
        """Create progress bar widgets."""
        self.frame = ttk.Frame(self.parent)

        # Progress bar
        self.progressbar = ttk.Progressbar(
            self.frame,
            mode='determinate',
            length=300,
            bootstyle="info-striped"
        )
        self.progressbar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        # Status label
        self.status_label = ttk.Label(
            self.frame,
            text="Ready",
            font=("Arial", 9),
            foreground="gray"
        )
        self.status_label.pack(side=tk.LEFT)

        # Cancel button
        self.cancel_btn = ttk.Button(
            self.frame,
            text="Cancel",
            bootstyle="danger-link",
            width=8
        )
        self.cancel_btn.pack(side=tk.RIGHT, padx=(10, 0))

        # Initially hidden
        self.frame.pack_forget()

    def show(self):
        """Show the progress bar."""
        self.frame.pack(fill=tk.X, padx=5, pady=5)
        self._start_animation()

    def hide(self):
        """Hide the progress bar."""
        self._stop_animation()
        self.frame.pack_forget()
        self._current_phase = SearchPhase.INITIALIZING
        self.progressbar['value'] = 0

    def update_phase(self, phase: SearchPhase, message: str = None):
        """Update progress to a new phase.

        Args:
            phase: Current search phase
            message: Optional custom message
        """
        self._current_phase = phase
        progress = self.PHASE_PROGRESS.get(phase, 0)
        display_message = message or self.PHASE_MESSAGES.get(phase, "Processing...")

        # Animate progress
        self._animate_to(progress)

        # Update label
        self.status_label.config(text=display_message)

        # Change style based on phase
        if phase == SearchPhase.ERROR:
            self.progressbar.config(bootstyle="danger-striped")
        elif phase == SearchPhase.CANCELLED:
            self.progressbar.config(bootstyle="warning-striped")
        elif phase == SearchPhase.COMPLETE:
            self.progressbar.config(bootstyle="success")
        else:
            self.progressbar.config(bootstyle="info-striped")

    def _animate_to(self, target: float):
        """Animate progress bar to target value.

        Args:
            target: Target progress value (0-100)
        """
        current = self.progressbar['value']
        step = (target - current) / 10  # Smooth animation

        def animate():
            nonlocal current
            if abs(current - target) > 1:
                current += step
                self.progressbar['value'] = current
                self.parent.after(50, animate)
            else:
                self.progressbar['value'] = target

        animate()

    def _start_animation(self):
        """Start striped animation for indeterminate phases."""
        pass  # Striped animation is built into ttkbootstrap

    def _stop_animation(self):
        """Stop striped animation."""
        if self._animation_id:
            try:
                self.parent.after_cancel(self._animation_id)
            except Exception:
                pass
            self._animation_id = None

    def set_cancel_callback(self, callback: Callable):
        """Set callback for cancel button.

        Args:
            callback: Function to call when cancel is clicked
        """
        self.cancel_btn.config(command=callback)


class StreamingResultsPanel:
    """Displays search results progressively as they arrive."""

    def __init__(
        self,
        parent: tk.Widget,
        on_result_click: Optional[Callable[[PartialResult], None]] = None
    ):
        """Initialize streaming results panel.

        Args:
            parent: Parent widget
            on_result_click: Callback when a result is clicked
        """
        self.parent = parent
        self.on_result_click = on_result_click
        self._sections = {}  # Section name -> frame
        self._results = {}  # Section name -> list of results
        self._collapsed = {}  # Section name -> collapsed state

        self._create_widgets()

    def _create_widgets(self):
        """Create the results panel widgets."""
        # Main container with scrollbar
        self.container = ttk.Frame(self.parent)

        # Canvas for scrolling
        self.canvas = tk.Canvas(self.container, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(
            self.container,
            orient=tk.VERTICAL,
            command=self.canvas.yview
        )
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.scrollable_frame,
            anchor="nw"
        )

        # Resize canvas window to match canvas width
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Pack widgets
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bind mousewheel
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _on_canvas_resize(self, event):
        """Handle canvas resize to adjust scrollable frame width."""
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        """Handle mousewheel scrolling."""
        if event.num == 4:  # Linux scroll up
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:  # Linux scroll down
            self.canvas.yview_scroll(1, "units")
        else:
            # Windows/Mac
            delta = int(-1 * (event.delta / 120))
            self.canvas.yview_scroll(delta, "units")

    def show(self):
        """Show the results panel."""
        self.container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def hide(self):
        """Hide the results panel."""
        self.container.pack_forget()

    def clear(self):
        """Clear all results."""
        for section_frame in self._sections.values():
            section_frame.destroy()
        self._sections.clear()
        self._results.clear()
        self._collapsed.clear()

    def add_section(self, section_name: str, title: str, icon: str = ""):
        """Add a new collapsible section.

        Args:
            section_name: Internal section identifier
            title: Display title for section
            icon: Optional emoji icon
        """
        if section_name in self._sections:
            return

        # Create section frame
        section_frame = ttk.LabelFrame(
            self.scrollable_frame,
            text=f"{icon} {title}" if icon else title,
            bootstyle="secondary"
        )
        section_frame.pack(fill=tk.X, padx=2, pady=2)

        # Header with collapse toggle
        header = ttk.Frame(section_frame)
        header.pack(fill=tk.X, padx=5, pady=2)

        # Result count label
        count_label = ttk.Label(
            header,
            text="0 results",
            font=("Arial", 9),
            foreground="gray"
        )
        count_label.pack(side=tk.LEFT)

        # Loading indicator
        loading_label = ttk.Label(
            header,
            text="Searching...",
            font=("Arial", 9, "italic"),
            foreground="gray"
        )
        loading_label.pack(side=tk.RIGHT)

        # Results container
        results_container = ttk.Frame(section_frame)
        results_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self._sections[section_name] = {
            "frame": section_frame,
            "header": header,
            "count_label": count_label,
            "loading_label": loading_label,
            "results_container": results_container
        }
        self._results[section_name] = []
        self._collapsed[section_name] = False

    def add_result(self, section_name: str, result: PartialResult):
        """Add a result to a section with animation.

        Args:
            section_name: Section to add result to
            result: The result to add
        """
        if section_name not in self._sections:
            return

        section = self._sections[section_name]
        container = section["results_container"]

        # Create result card
        card = self._create_result_card(container, result)
        card.pack(fill=tk.X, pady=2)

        # Store result
        self._results[section_name].append(result)

        # Update count
        count = len(self._results[section_name])
        section["count_label"].config(text=f"{count} result{'s' if count != 1 else ''}")

        # Scroll to show new result
        self.canvas.update_idletasks()
        self.canvas.yview_moveto(1.0)

    def _create_result_card(self, parent: tk.Widget, result: PartialResult) -> ttk.Frame:
        """Create a result card widget.

        Args:
            parent: Parent widget
            result: Result data

        Returns:
            Result card frame
        """
        card = ttk.Frame(parent, borderwidth=1, relief="solid")

        # Header with filename and score
        header = ttk.Frame(card)
        header.pack(fill=tk.X, padx=5, pady=2)

        filename_label = ttk.Label(
            header,
            text=result.document_filename,
            font=("Arial", 9, "bold"),
            cursor="hand2"
        )
        filename_label.pack(side=tk.LEFT)

        score_label = ttk.Label(
            header,
            text=f"{result.score:.1%}",
            font=("Arial", 9),
            foreground="green" if result.score > 0.6 else "orange" if result.score > 0.4 else "gray"
        )
        score_label.pack(side=tk.RIGHT)

        source_label = ttk.Label(
            header,
            text=f"[{result.source_phase}]",
            font=("Arial", 8),
            foreground="gray"
        )
        source_label.pack(side=tk.RIGHT, padx=(0, 10))

        # Preview text
        preview = result.chunk_text[:200] + "..." if len(result.chunk_text) > 200 else result.chunk_text
        preview_label = ttk.Label(
            card,
            text=preview,
            font=("Arial", 9),
            wraplength=400,
            justify=tk.LEFT
        )
        preview_label.pack(fill=tk.X, padx=5, pady=(0, 5))

        # Bind click event
        if self.on_result_click:
            for widget in [card, filename_label, preview_label]:
                widget.bind("<Button-1>", lambda e, r=result: self.on_result_click(r))
                widget.config(cursor="hand2")

        return card

    def complete_section(self, section_name: str):
        """Mark a section as complete.

        Args:
            section_name: Section to mark complete
        """
        if section_name not in self._sections:
            return

        section = self._sections[section_name]
        section["loading_label"].config(text="Done", foreground="green")

    def error_section(self, section_name: str, error_message: str):
        """Mark a section as having an error.

        Args:
            section_name: Section with error
            error_message: Error message to display
        """
        if section_name not in self._sections:
            return

        section = self._sections[section_name]
        section["loading_label"].config(
            text=f"Error: {error_message}",
            foreground="red"
        )

    def finalize(self, merged_results: list):
        """Replace partial results with final merged results.

        Args:
            merged_results: Final merged and ranked results
        """
        # Clear sections and show final results
        self.clear()

        # Create single "Results" section
        self.add_section("final", "Search Results", "")
        section = self._sections["final"]
        section["loading_label"].config(text="", foreground="gray")

        for result in merged_results:
            # Convert HybridSearchResult to PartialResult
            if hasattr(result, 'chunk_text'):
                partial = PartialResult(
                    document_filename=getattr(result, 'document_filename', 'Unknown'),
                    chunk_text=result.chunk_text,
                    score=getattr(result, 'combined_score', 0.0),
                    source_phase="merged",
                    document_id=getattr(result, 'document_id', ''),
                    chunk_index=getattr(result, 'chunk_index', 0)
                )
                self.add_result("final", partial)

        count = len(merged_results)
        section["count_label"].config(text=f"{count} result{'s' if count != 1 else ''}")


class StreamingResultsController:
    """Controller for coordinating streaming results display."""

    def __init__(
        self,
        parent: tk.Widget,
        text_widget: tk.Text
    ):
        """Initialize controller.

        Args:
            parent: Parent widget
            text_widget: Text widget for displaying final response
        """
        self.parent = parent
        self.text_widget = text_widget

        # Create progress bar
        self.progress_bar = StreamingProgressBar(parent)

        # Create results panel (initially hidden)
        self.results_panel = StreamingResultsPanel(parent)

        # State
        self._is_active = False

    def start_search(self, cancel_callback: Callable = None):
        """Start a new search, showing progress indicators.

        Args:
            cancel_callback: Callback when cancel is requested
        """
        self._is_active = True

        # Show progress bar
        self.progress_bar.show()
        if cancel_callback:
            self.progress_bar.set_cancel_callback(cancel_callback)

        # Initialize sections
        self.results_panel.clear()
        self.results_panel.add_section("vector", "Vector Search", "")
        self.results_panel.add_section("bm25", "Keyword Search", "")
        self.results_panel.add_section("graph", "Knowledge Graph", "")

        # Update phase
        self.progress_bar.update_phase(SearchPhase.INITIALIZING)

    def update_phase(self, phase: SearchPhase, message: str = None):
        """Update current search phase.

        Args:
            phase: Current phase
            message: Optional status message
        """
        if not self._is_active:
            return

        self.progress_bar.update_phase(phase, message)

    def add_vector_results(self, results: list):
        """Add results from vector search.

        Args:
            results: List of VectorSearchResult or similar
        """
        if not self._is_active:
            return

        for result in results:
            partial = PartialResult(
                document_filename=result.metadata.get('filename', 'Unknown') if result.metadata else 'Unknown',
                chunk_text=result.chunk_text,
                score=result.similarity_score,
                source_phase="vector",
                document_id=result.document_id,
                chunk_index=result.chunk_index
            )
            self.results_panel.add_result("vector", partial)

        self.results_panel.complete_section("vector")

    def add_bm25_results(self, results: list):
        """Add results from BM25 search.

        Args:
            results: List of BM25 search results
        """
        if not self._is_active:
            return

        for result in results:
            partial = PartialResult(
                document_filename=result.metadata.get('filename', 'Unknown') if hasattr(result, 'metadata') and result.metadata else 'Unknown',
                chunk_text=getattr(result, 'chunk_text', ''),
                score=getattr(result, 'bm25_score', 0.0),
                source_phase="bm25",
                document_id=getattr(result, 'document_id', ''),
                chunk_index=getattr(result, 'chunk_index', 0)
            )
            self.results_panel.add_result("bm25", partial)

        self.results_panel.complete_section("bm25")

    def add_graph_results(self, results: list):
        """Add results from graph search.

        Args:
            results: List of graph search results
        """
        if not self._is_active:
            return

        for result in results:
            partial = PartialResult(
                document_filename=getattr(result, 'source_document_id', 'Knowledge Graph'),
                chunk_text=getattr(result, 'fact', str(result)),
                score=getattr(result, 'relevance_score', 0.5),
                source_phase="graph"
            )
            self.results_panel.add_result("graph", partial)

        self.results_panel.complete_section("graph")

    def finalize(self, merged_results: list, processing_time_ms: float = 0):
        """Finalize search with merged results.

        Args:
            merged_results: Final ranked results
            processing_time_ms: Total processing time
        """
        if not self._is_active:
            return

        self.progress_bar.update_phase(
            SearchPhase.COMPLETE,
            f"Found {len(merged_results)} results in {processing_time_ms:.0f}ms"
        )

        # Hide progress after delay
        self.parent.after(2000, self.progress_bar.hide)

        self._is_active = False

    def error(self, message: str):
        """Handle search error.

        Args:
            message: Error message
        """
        self.progress_bar.update_phase(SearchPhase.ERROR, message)
        self.parent.after(3000, self.progress_bar.hide)
        self._is_active = False

    def cancel(self):
        """Handle search cancellation."""
        self.progress_bar.update_phase(SearchPhase.CANCELLED)
        self.parent.after(1500, self.progress_bar.hide)
        self._is_active = False

    def reset(self):
        """Reset to initial state."""
        self.progress_bar.hide()
        self.results_panel.clear()
        self._is_active = False

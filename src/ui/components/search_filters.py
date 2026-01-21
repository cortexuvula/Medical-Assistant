"""
Search Filters Panel for RAG Tab.

Provides a collapsible panel for visual filter selection including:
- Document type checkboxes
- Date range picker
- Entity type filter
- Score threshold slider
"""

import tkinter as tk
import ttkbootstrap as ttk
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Callable, Optional

from utils.structured_logging import get_logger

logger = get_logger(__name__)


@dataclass
class SearchFilters:
    """Current search filter settings."""
    document_types: list[str]  # ["pdf", "docx", "txt", "image"]
    date_start: Optional[datetime]
    date_end: Optional[datetime]
    entity_types: list[str]  # ["medication", "condition", etc.]
    min_score: float  # 0.0 - 1.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "document_types": self.document_types,
            "date_start": self.date_start.isoformat() if self.date_start else None,
            "date_end": self.date_end.isoformat() if self.date_end else None,
            "entity_types": self.entity_types,
            "min_score": self.min_score
        }

    def has_filters(self) -> bool:
        """Check if any filters are active."""
        return bool(
            self.document_types or
            self.date_start or
            self.date_end or
            self.entity_types or
            self.min_score > 0
        )

    def build_query_suffix(self) -> str:
        """Build query suffix from active filters.

        Returns:
            String to append to query (e.g., "type:pdf date:last-month")
        """
        parts = []

        # Document types
        for doc_type in self.document_types:
            parts.append(f"type:{doc_type}")

        # Date range
        if self.date_start and self.date_end:
            # Check for common patterns
            now = datetime.now()
            if self.date_start.date() == now.date():
                parts.append("date:today")
            elif self.date_start >= now - timedelta(days=7):
                parts.append("date:last-week")
            elif self.date_start >= now - timedelta(days=30):
                parts.append("date:last-month")
            elif self.date_start.year == now.year:
                parts.append("date:this-year")
            else:
                parts.append(f"date:{self.date_start.strftime('%Y-%m-%d')}")

        # Entity types
        for entity_type in self.entity_types:
            parts.append(f"entity:{entity_type}:*")

        # Score threshold
        if self.min_score > 0:
            parts.append(f"score:>{self.min_score:.1f}")

        return " ".join(parts)


class SearchFiltersPanel:
    """Collapsible filter panel for RAG search."""

    # Available document types
    DOCUMENT_TYPES = [
        ("PDF", "pdf"),
        ("Word", "docx"),
        ("Text", "txt"),
        ("Image", "image"),
    ]

    # Available entity types
    ENTITY_TYPES = [
        ("All", ""),
        ("Medication", "medication"),
        ("Condition", "condition"),
        ("Symptom", "symptom"),
        ("Procedure", "procedure"),
        ("Lab Test", "lab_test"),
        ("Anatomy", "anatomy"),
    ]

    # Date range presets
    DATE_PRESETS = [
        ("Any time", None, None),
        ("Today", lambda: datetime.now().replace(hour=0, minute=0, second=0), lambda: datetime.now()),
        ("Last 7 days", lambda: datetime.now() - timedelta(days=7), lambda: datetime.now()),
        ("Last 30 days", lambda: datetime.now() - timedelta(days=30), lambda: datetime.now()),
        ("This year", lambda: datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0), lambda: datetime.now()),
        ("Custom", None, None),
    ]

    def __init__(
        self,
        parent: tk.Widget,
        on_filters_changed: Optional[Callable[[SearchFilters], None]] = None
    ):
        """Initialize the filters panel.

        Args:
            parent: Parent widget
            on_filters_changed: Callback when filters change
        """
        self.parent = parent
        self.on_filters_changed = on_filters_changed

        # State variables
        self._is_expanded = False
        self._doc_type_vars = {}
        self._entity_type_var = tk.StringVar(value="")
        self._date_preset_var = tk.StringVar(value="Any time")
        self._score_var = tk.DoubleVar(value=0.0)
        self._custom_date_start = None
        self._custom_date_end = None

        self._create_widgets()

    def _create_widgets(self):
        """Create the filter panel widgets."""
        # Main container
        self.container = ttk.Frame(self.parent)

        # Toggle button
        self.toggle_frame = ttk.Frame(self.container)
        self.toggle_frame.pack(fill=tk.X)

        self.toggle_btn = ttk.Button(
            self.toggle_frame,
            text="Filters",
            bootstyle="info-outline",
            command=self._toggle_panel
        )
        self.toggle_btn.pack(side=tk.LEFT, padx=2)

        # Active filters indicator
        self.active_label = ttk.Label(
            self.toggle_frame,
            text="",
            font=("Arial", 9),
            foreground="gray"
        )
        self.active_label.pack(side=tk.LEFT, padx=5)

        # Clear button
        self.clear_btn = ttk.Button(
            self.toggle_frame,
            text="Clear",
            bootstyle="danger-link",
            command=self._clear_filters
        )
        self.clear_btn.pack(side=tk.RIGHT, padx=2)

        # Collapsible panel
        self.panel = ttk.Frame(self.container, borderwidth=1, relief="groove")

        # Document types section
        self._create_doc_type_section()

        # Date range section
        self._create_date_section()

        # Entity type section
        self._create_entity_section()

        # Score threshold section
        self._create_score_section()

        # Apply button
        apply_btn = ttk.Button(
            self.panel,
            text="Apply Filters",
            bootstyle="success",
            command=self._apply_filters
        )
        apply_btn.pack(fill=tk.X, padx=10, pady=10)

    def _create_doc_type_section(self):
        """Create document type checkboxes."""
        frame = ttk.LabelFrame(self.panel, text="Document Types", padding=5)
        frame.pack(fill=tk.X, padx=10, pady=5)

        for label, doc_type in self.DOCUMENT_TYPES:
            var = tk.BooleanVar(value=False)
            self._doc_type_vars[doc_type] = var

            cb = ttk.Checkbutton(
                frame,
                text=label,
                variable=var,
                bootstyle="info"
            )
            cb.pack(side=tk.LEFT, padx=5)

    def _create_date_section(self):
        """Create date range section."""
        frame = ttk.LabelFrame(self.panel, text="Date Range", padding=5)
        frame.pack(fill=tk.X, padx=10, pady=5)

        # Preset dropdown
        preset_combo = ttk.Combobox(
            frame,
            textvariable=self._date_preset_var,
            values=[p[0] for p in self.DATE_PRESETS],
            state="readonly",
            width=15
        )
        preset_combo.pack(side=tk.LEFT, padx=5)
        preset_combo.bind("<<ComboboxSelected>>", self._on_date_preset_change)

        # Custom date entries (initially hidden)
        self.custom_date_frame = ttk.Frame(frame)

        ttk.Label(self.custom_date_frame, text="From:").pack(side=tk.LEFT)
        self.start_entry = ttk.Entry(self.custom_date_frame, width=12)
        self.start_entry.pack(side=tk.LEFT, padx=2)
        self.start_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

        ttk.Label(self.custom_date_frame, text="To:").pack(side=tk.LEFT, padx=(10, 0))
        self.end_entry = ttk.Entry(self.custom_date_frame, width=12)
        self.end_entry.pack(side=tk.LEFT, padx=2)
        self.end_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

    def _create_entity_section(self):
        """Create entity type filter."""
        frame = ttk.LabelFrame(self.panel, text="Entity Type", padding=5)
        frame.pack(fill=tk.X, padx=10, pady=5)

        combo = ttk.Combobox(
            frame,
            textvariable=self._entity_type_var,
            values=[e[0] for e in self.ENTITY_TYPES],
            state="readonly",
            width=15
        )
        combo.pack(side=tk.LEFT, padx=5)
        combo.current(0)

    def _create_score_section(self):
        """Create score threshold slider."""
        frame = ttk.LabelFrame(self.panel, text="Minimum Score", padding=5)
        frame.pack(fill=tk.X, padx=10, pady=5)

        # Label showing current value
        self.score_label = ttk.Label(frame, text="0%")
        self.score_label.pack(side=tk.LEFT, padx=5)

        # Slider
        slider = ttk.Scale(
            frame,
            from_=0,
            to=100,
            variable=self._score_var,
            orient=tk.HORIZONTAL,
            command=self._on_score_change,
            length=150
        )
        slider.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

    def _toggle_panel(self):
        """Toggle the filter panel visibility."""
        self._is_expanded = not self._is_expanded

        if self._is_expanded:
            self.panel.pack(fill=tk.X, padx=5, pady=5)
            self.toggle_btn.config(text="Filters")
        else:
            self.panel.pack_forget()
            self.toggle_btn.config(text="Filters")

    def _on_date_preset_change(self, event):
        """Handle date preset selection."""
        preset = self._date_preset_var.get()

        if preset == "Custom":
            self.custom_date_frame.pack(side=tk.LEFT, padx=10)
        else:
            self.custom_date_frame.pack_forget()

    def _on_score_change(self, value):
        """Handle score slider change."""
        score = int(float(value))
        self.score_label.config(text=f"{score}%")

    def _apply_filters(self):
        """Apply current filter settings."""
        filters = self.get_filters()

        # Update active label
        active_count = 0
        if filters.document_types:
            active_count += 1
        if filters.date_start or filters.date_end:
            active_count += 1
        if filters.entity_types:
            active_count += 1
        if filters.min_score > 0:
            active_count += 1

        if active_count > 0:
            self.active_label.config(text=f"({active_count} active)")
        else:
            self.active_label.config(text="")

        # Call callback
        if self.on_filters_changed:
            try:
                self.on_filters_changed(filters)
            except Exception as e:
                logger.error(f"Error in filters callback: {e}")

    def _clear_filters(self):
        """Clear all filters."""
        # Reset document types
        for var in self._doc_type_vars.values():
            var.set(False)

        # Reset date
        self._date_preset_var.set("Any time")
        self.custom_date_frame.pack_forget()

        # Reset entity type
        self._entity_type_var.set("")

        # Reset score
        self._score_var.set(0)
        self.score_label.config(text="0%")

        # Clear active label
        self.active_label.config(text="")

        # Apply cleared filters
        if self.on_filters_changed:
            self.on_filters_changed(self.get_filters())

    def get_filters(self) -> SearchFilters:
        """Get current filter settings.

        Returns:
            SearchFilters with current settings
        """
        # Document types
        doc_types = [
            doc_type for doc_type, var in self._doc_type_vars.items()
            if var.get()
        ]

        # Date range
        date_start = None
        date_end = None
        preset = self._date_preset_var.get()

        for preset_name, start_fn, end_fn in self.DATE_PRESETS:
            if preset_name == preset:
                if start_fn and end_fn:
                    date_start = start_fn()
                    date_end = end_fn()
                elif preset_name == "Custom":
                    # Parse custom dates
                    try:
                        date_start = datetime.strptime(
                            self.start_entry.get(), "%Y-%m-%d"
                        )
                        date_end = datetime.strptime(
                            self.end_entry.get(), "%Y-%m-%d"
                        ).replace(hour=23, minute=59, second=59)
                    except ValueError:
                        pass
                break

        # Entity types
        entity_types = []
        entity_selection = self._entity_type_var.get()
        for label, entity_type in self.ENTITY_TYPES:
            if label == entity_selection and entity_type:
                entity_types.append(entity_type)
                break

        # Score threshold
        min_score = self._score_var.get() / 100.0

        return SearchFilters(
            document_types=doc_types,
            date_start=date_start,
            date_end=date_end,
            entity_types=entity_types,
            min_score=min_score
        )

    def show(self):
        """Show the filter panel container."""
        self.container.pack(fill=tk.X, padx=5, pady=2)

    def hide(self):
        """Hide the filter panel container."""
        self.container.pack_forget()

    def set_filters(self, filters: SearchFilters):
        """Set filter values programmatically.

        Args:
            filters: SearchFilters to apply
        """
        # Set document types
        for doc_type in self.DOCUMENT_TYPES:
            _, type_key = doc_type
            if type_key in self._doc_type_vars:
                self._doc_type_vars[type_key].set(type_key in filters.document_types)

        # Set date (simplified - just set to custom if dates provided)
        if filters.date_start and filters.date_end:
            self._date_preset_var.set("Custom")
            self.custom_date_frame.pack(side=tk.LEFT, padx=10)
            self.start_entry.delete(0, tk.END)
            self.start_entry.insert(0, filters.date_start.strftime("%Y-%m-%d"))
            self.end_entry.delete(0, tk.END)
            self.end_entry.insert(0, filters.date_end.strftime("%Y-%m-%d"))
        else:
            self._date_preset_var.set("Any time")
            self.custom_date_frame.pack_forget()

        # Set entity types
        if filters.entity_types:
            for label, entity_type in self.ENTITY_TYPES:
                if entity_type == filters.entity_types[0]:
                    self._entity_type_var.set(label)
                    break
        else:
            self._entity_type_var.set("All")

        # Set score threshold
        self._score_var.set(filters.min_score * 100)
        self.score_label.config(text=f"{int(filters.min_score * 100)}%")


class CompactFiltersBar:
    """Compact horizontal filters bar for RAG tab."""

    def __init__(
        self,
        parent: tk.Widget,
        on_filters_changed: Optional[Callable[[SearchFilters], None]] = None
    ):
        """Initialize compact filters bar.

        Args:
            parent: Parent widget
            on_filters_changed: Callback when filters change
        """
        self.parent = parent
        self.on_filters_changed = on_filters_changed

        # State
        self._doc_type_vars = {}
        self._date_var = tk.StringVar(value="Any")
        self._entity_var = tk.StringVar(value="All")

        self._create_widgets()

    def _create_widgets(self):
        """Create compact filter widgets."""
        self.frame = ttk.Frame(self.parent)

        # Document type chips
        type_frame = ttk.Frame(self.frame)
        type_frame.pack(side=tk.LEFT, padx=5)

        for label, doc_type in [("PDF", "pdf"), ("DOCX", "docx"), ("TXT", "txt")]:
            var = tk.BooleanVar(value=False)
            self._doc_type_vars[doc_type] = var

            btn = ttk.Checkbutton(
                type_frame,
                text=label,
                variable=var,
                bootstyle="info-outline-toolbutton",
                command=self._on_change
            )
            btn.pack(side=tk.LEFT, padx=1)

        # Separator
        ttk.Separator(self.frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Date dropdown
        ttk.Label(self.frame, text="Date:").pack(side=tk.LEFT)
        date_combo = ttk.Combobox(
            self.frame,
            textvariable=self._date_var,
            values=["Any", "Today", "This Week", "This Month", "This Year"],
            state="readonly",
            width=10
        )
        date_combo.pack(side=tk.LEFT, padx=5)
        date_combo.bind("<<ComboboxSelected>>", lambda e: self._on_change())

        # Separator
        ttk.Separator(self.frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Entity dropdown
        ttk.Label(self.frame, text="Type:").pack(side=tk.LEFT)
        entity_combo = ttk.Combobox(
            self.frame,
            textvariable=self._entity_var,
            values=["All", "Medication", "Condition", "Symptom", "Procedure"],
            state="readonly",
            width=12
        )
        entity_combo.pack(side=tk.LEFT, padx=5)
        entity_combo.bind("<<ComboboxSelected>>", lambda e: self._on_change())

        # Clear button
        clear_btn = ttk.Button(
            self.frame,
            text="Clear",
            bootstyle="secondary-link",
            command=self._clear
        )
        clear_btn.pack(side=tk.RIGHT, padx=5)

    def _on_change(self):
        """Handle filter change."""
        if self.on_filters_changed:
            self.on_filters_changed(self.get_filters())

    def _clear(self):
        """Clear all filters."""
        for var in self._doc_type_vars.values():
            var.set(False)
        self._date_var.set("Any")
        self._entity_var.set("All")
        self._on_change()

    def get_filters(self) -> SearchFilters:
        """Get current filters."""
        # Document types
        doc_types = [dt for dt, var in self._doc_type_vars.items() if var.get()]

        # Date range
        date_map = {
            "Today": (
                datetime.now().replace(hour=0, minute=0, second=0),
                datetime.now()
            ),
            "This Week": (
                datetime.now() - timedelta(days=datetime.now().weekday()),
                datetime.now()
            ),
            "This Month": (
                datetime.now().replace(day=1, hour=0, minute=0, second=0),
                datetime.now()
            ),
            "This Year": (
                datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0),
                datetime.now()
            ),
        }
        date_start, date_end = date_map.get(self._date_var.get(), (None, None))

        # Entity types
        entity_map = {
            "Medication": "medication",
            "Condition": "condition",
            "Symptom": "symptom",
            "Procedure": "procedure",
        }
        entity_types = []
        if self._entity_var.get() in entity_map:
            entity_types.append(entity_map[self._entity_var.get()])

        return SearchFilters(
            document_types=doc_types,
            date_start=date_start,
            date_end=date_end,
            entity_types=entity_types,
            min_score=0.0
        )

    def show(self):
        """Show the filters bar."""
        self.frame.pack(fill=tk.X, padx=5, pady=2)

    def hide(self):
        """Hide the filters bar."""
        self.frame.pack_forget()

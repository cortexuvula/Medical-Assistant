"""
Visual Components Module

Provides styled visual components with consistent look and feel,
including cards, separators, badges, and section headers.
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import Optional, Tuple
from enum import Enum

from ui.ui_constants import Colors, Fonts, Spacing
from ui.theme_observer import ThemeAwareMixin, register_for_theme_updates


class CardStyle(Enum):
    """Card styling options."""
    DEFAULT = "default"
    ELEVATED = "elevated"
    OUTLINED = "outlined"
    FLAT = "flat"


class Card(ttk.Frame, ThemeAwareMixin):
    """A styled card component for grouping content.

    Cards provide visual separation and hierarchy for content groups.
    They support different styles and theme-aware coloring.

    Usage:
        card = Card(parent, title="Settings", style=CardStyle.ELEVATED)
        ttk.Label(card.content, text="Content here").pack()
    """

    def __init__(
        self,
        parent: tk.Widget,
        title: str = "",
        style: CardStyle = CardStyle.DEFAULT,
        padding: int = None,
        **kwargs
    ):
        """Initialize the card.

        Args:
            parent: Parent widget
            title: Optional card title
            style: Card style (DEFAULT, ELEVATED, OUTLINED, FLAT)
            padding: Content padding (default: Spacing.MD)
            **kwargs: Additional frame arguments
        """
        super().__init__(parent, **kwargs)

        self._title = title
        self._style = style
        self._padding = padding or Spacing.MD
        self._is_dark = False

        self._create_widgets()
        self.init_theme_aware()

    def _create_widgets(self) -> None:
        """Create card widgets."""
        # Header (if title provided)
        if self._title:
            self.header = ttk.Frame(self)
            self.header.pack(fill="x", padx=self._padding, pady=(self._padding, 0))

            self.title_label = ttk.Label(
                self.header,
                text=self._title,
                font=Fonts.get_font(Fonts.SIZE_LG, Fonts.WEIGHT_BOLD)
            )
            self.title_label.pack(side="left")

            # Separator
            self.separator = ttk.Separator(self, orient="horizontal")
            self.separator.pack(fill="x", padx=self._padding, pady=(Spacing.SM, 0))

        # Content area
        self.content = ttk.Frame(self, padding=self._padding)
        self.content.pack(fill="both", expand=True)

    def update_theme(self, is_dark: bool) -> None:
        """Update card appearance for theme change."""
        self._is_dark = is_dark
        self._apply_style()

    def _apply_style(self) -> None:
        """Apply the current style to the card."""
        colors = Colors.get_theme_colors(self._is_dark)

        if self._style == CardStyle.OUTLINED:
            # Border with transparent background
            self.configure(
                borderwidth=1,
                relief="solid"
            )
        elif self._style == CardStyle.ELEVATED:
            # Raised appearance
            self.configure(
                borderwidth=1,
                relief="raised"
            )
        elif self._style == CardStyle.FLAT:
            # No border
            self.configure(
                borderwidth=0,
                relief="flat"
            )
        else:
            # Default - subtle border
            self.configure(
                borderwidth=1,
                relief="groove"
            )


class SectionHeader(ttk.Frame):
    """A styled section header with title and optional subtitle.

    Usage:
        header = SectionHeader(parent, "Documents", "Generate medical documents")
        header.pack(fill="x")
    """

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        subtitle: str = "",
        icon: str = "",
        **kwargs
    ):
        """Initialize the section header.

        Args:
            parent: Parent widget
            title: Main title text
            subtitle: Optional subtitle text
            icon: Optional icon/emoji
            **kwargs: Additional frame arguments
        """
        super().__init__(parent, **kwargs)

        self._create_widgets(title, subtitle, icon)

    def _create_widgets(self, title: str, subtitle: str, icon: str) -> None:
        """Create header widgets."""
        # Icon (if provided)
        if icon:
            icon_label = ttk.Label(
                self,
                text=icon,
                font=Fonts.get_font(Fonts.SIZE_HEADER)
            )
            icon_label.pack(side="left", padx=(0, Spacing.SM))

        # Text container
        text_frame = ttk.Frame(self)
        text_frame.pack(side="left", fill="x", expand=True)

        # Title
        title_label = ttk.Label(
            text_frame,
            text=title,
            font=Fonts.get_font(Fonts.SIZE_XL, Fonts.WEIGHT_BOLD)
        )
        title_label.pack(anchor="w")

        # Subtitle
        if subtitle:
            subtitle_label = ttk.Label(
                text_frame,
                text=subtitle,
                font=Fonts.get_font(Fonts.SIZE_SM),
                foreground=Colors.LIGHT_FG_MUTED
            )
            subtitle_label.pack(anchor="w")


class Badge(ttk.Label):
    """A styled badge for showing status or counts.

    Usage:
        badge = Badge(parent, "New", style="success")
        badge.pack()

        count_badge = Badge(parent, "5", style="primary")
    """

    STYLES = {
        "primary": (Colors.PRIMARY, "#ffffff"),
        "secondary": (Colors.SECONDARY, "#ffffff"),
        "success": (Colors.SUCCESS, "#ffffff"),
        "danger": (Colors.DANGER, "#ffffff"),
        "warning": (Colors.WARNING, "#000000"),
        "info": (Colors.INFO, "#ffffff"),
    }

    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        style: str = "primary",
        **kwargs
    ):
        """Initialize the badge.

        Args:
            parent: Parent widget
            text: Badge text
            style: Badge style (primary, secondary, success, danger, warning, info)
            **kwargs: Additional label arguments
        """
        bg_color, fg_color = self.STYLES.get(style, self.STYLES["primary"])

        super().__init__(
            parent,
            text=f" {text} ",
            background=bg_color,
            foreground=fg_color,
            font=Fonts.get_font(Fonts.SIZE_XS, Fonts.WEIGHT_BOLD),
            **kwargs
        )


class Divider(ttk.Frame):
    """A styled divider/separator with optional label.

    Usage:
        # Simple divider
        Divider(parent).pack(fill="x")

        # Divider with label
        Divider(parent, text="OR").pack(fill="x")
    """

    def __init__(
        self,
        parent: tk.Widget,
        text: str = "",
        orientation: str = "horizontal",
        **kwargs
    ):
        """Initialize the divider.

        Args:
            parent: Parent widget
            text: Optional text label
            orientation: "horizontal" or "vertical"
            **kwargs: Additional frame arguments
        """
        super().__init__(parent, **kwargs)

        if text:
            # Divider with centered text
            left_sep = ttk.Separator(self, orient=orientation)
            left_sep.pack(side="left", fill="x", expand=True)

            label = ttk.Label(
                self,
                text=f"  {text}  ",
                font=Fonts.get_font(Fonts.SIZE_SM),
                foreground=Colors.LIGHT_FG_MUTED
            )
            label.pack(side="left")

            right_sep = ttk.Separator(self, orient=orientation)
            right_sep.pack(side="left", fill="x", expand=True)
        else:
            # Simple separator
            sep = ttk.Separator(self, orient=orientation)
            if orientation == "horizontal":
                sep.pack(fill="x", expand=True)
            else:
                sep.pack(fill="y", expand=True)


class IconButton(ttk.Button):
    """A button with an icon and optional text.

    Usage:
        btn = IconButton(parent, icon="📁", text="Open", command=open_file)
        btn.pack()
    """

    def __init__(
        self,
        parent: tk.Widget,
        icon: str,
        text: str = "",
        command: Optional[callable] = None,
        tooltip: str = "",
        **kwargs
    ):
        """Initialize the icon button.

        Args:
            parent: Parent widget
            icon: Icon character/emoji
            text: Optional button text
            command: Button command
            tooltip: Tooltip text
            **kwargs: Additional button arguments
        """
        display_text = f"{icon} {text}" if text else icon

        super().__init__(
            parent,
            text=display_text,
            command=command,
            **kwargs
        )

        if tooltip:
            from ui.tooltip import ToolTip
            ToolTip(self, tooltip)


class InfoPanel(ttk.Frame, ThemeAwareMixin):
    """An information panel for displaying key-value pairs.

    Usage:
        panel = InfoPanel(parent)
        panel.add_row("Status", "Active")
        panel.add_row("Duration", "5:30")
        panel.pack(fill="x")
    """

    def __init__(
        self,
        parent: tk.Widget,
        title: str = "",
        columns: int = 2,
        **kwargs
    ):
        """Initialize the info panel.

        Args:
            parent: Parent widget
            title: Optional panel title
            columns: Number of columns (for layout)
            **kwargs: Additional frame arguments
        """
        super().__init__(parent, padding=Spacing.MD, **kwargs)

        self._columns = columns
        self._current_row = 0
        self._items: dict = {}

        if title:
            title_label = ttk.Label(
                self,
                text=title,
                font=Fonts.get_font(Fonts.SIZE_MD, Fonts.WEIGHT_BOLD)
            )
            title_label.grid(row=0, column=0, columnspan=columns * 2, sticky="w", pady=(0, Spacing.SM))
            self._current_row = 1

        self.init_theme_aware()

    def add_row(
        self,
        label: str,
        value: str,
        value_style: str = "normal"
    ) -> Tuple[ttk.Label, ttk.Label]:
        """Add a label-value row to the panel.

        Args:
            label: Row label
            value: Row value
            value_style: Value style ("normal", "bold", "muted")

        Returns:
            Tuple of (label_widget, value_widget)
        """
        col = (len(self._items) % self._columns) * 2

        # Label
        label_widget = ttk.Label(
            self,
            text=f"{label}:",
            font=Fonts.get_font(Fonts.SIZE_SM),
            foreground=Colors.LIGHT_FG_MUTED
        )
        label_widget.grid(
            row=self._current_row,
            column=col,
            sticky="e",
            padx=(0, Spacing.SM),
            pady=Spacing.XS
        )

        # Value
        font = Fonts.get_font(Fonts.SIZE_SM)
        if value_style == "bold":
            font = Fonts.get_font(Fonts.SIZE_SM, Fonts.WEIGHT_BOLD)

        value_widget = ttk.Label(
            self,
            text=value,
            font=font
        )
        value_widget.grid(
            row=self._current_row,
            column=col + 1,
            sticky="w",
            pady=Spacing.XS
        )

        self._items[label] = (label_widget, value_widget)

        # Move to next row if we've filled all columns
        if len(self._items) % self._columns == 0:
            self._current_row += 1

        return label_widget, value_widget

    def update_value(self, label: str, value: str) -> None:
        """Update the value for a label.

        Args:
            label: Row label
            value: New value
        """
        if label in self._items:
            self._items[label][1].configure(text=value)

    def update_theme(self, is_dark: bool) -> None:
        """Update panel for theme change."""
        colors = Colors.get_theme_colors(is_dark)
        for label, value in self._items.values():
            label.configure(foreground=colors["fg_muted"])


class ProgressCard(Card):
    """A card with a progress indicator for ongoing operations.

    Usage:
        card = ProgressCard(parent, title="Processing", max_value=100)
        card.update_progress(50, "Processing item 50/100")
        card.pack(fill="x")
    """

    def __init__(
        self,
        parent: tk.Widget,
        title: str = "Progress",
        max_value: int = 100,
        show_percentage: bool = True,
        **kwargs
    ):
        """Initialize the progress card.

        Args:
            parent: Parent widget
            title: Card title
            max_value: Maximum progress value
            show_percentage: Whether to show percentage text
            **kwargs: Additional card arguments
        """
        super().__init__(parent, title=title, **kwargs)

        self._max_value = max_value
        self._current_value = 0
        self._show_percentage = show_percentage

        self._create_progress_widgets()

    def _create_progress_widgets(self) -> None:
        """Create progress widgets."""
        # Progress bar
        self.progress_bar = ttk.Progressbar(
            self.content,
            mode="determinate",
            maximum=self._max_value
        )
        self.progress_bar.pack(fill="x", pady=(0, Spacing.SM))

        # Status frame
        status_frame = ttk.Frame(self.content)
        status_frame.pack(fill="x")

        # Status label
        self.status_label = ttk.Label(
            status_frame,
            text="",
            font=Fonts.get_font(Fonts.SIZE_SM)
        )
        self.status_label.pack(side="left")

        # Percentage label
        if self._show_percentage:
            self.percentage_label = ttk.Label(
                status_frame,
                text="0%",
                font=Fonts.get_font(Fonts.SIZE_SM, Fonts.WEIGHT_BOLD)
            )
            self.percentage_label.pack(side="right")

    def update_progress(self, value: int, status: str = "") -> None:
        """Update the progress value and status.

        Args:
            value: Current progress value
            status: Status message
        """
        self._current_value = min(value, self._max_value)
        self.progress_bar["value"] = self._current_value

        if status:
            self.status_label.configure(text=status)

        if self._show_percentage:
            percentage = int((self._current_value / self._max_value) * 100)
            self.percentage_label.configure(text=f"{percentage}%")

    def reset(self) -> None:
        """Reset the progress card."""
        self._current_value = 0
        self.progress_bar["value"] = 0
        self.status_label.configure(text="")
        if self._show_percentage:
            self.percentage_label.configure(text="0%")


class EmptyState(ttk.Frame):
    """A styled empty state component for when there's no content.

    Usage:
        empty = EmptyState(
            parent,
            icon="📁",
            title="No recordings",
            message="Start recording to see your recordings here",
            action_text="Start Recording",
            action_command=start_recording
        )
        empty.pack(expand=True)
    """

    def __init__(
        self,
        parent: tk.Widget,
        icon: str = "📭",
        title: str = "No items",
        message: str = "",
        action_text: str = "",
        action_command: Optional[callable] = None,
        **kwargs
    ):
        """Initialize the empty state.

        Args:
            parent: Parent widget
            icon: Large icon/emoji
            title: Title text
            message: Description message
            action_text: Optional action button text
            action_command: Optional action button command
            **kwargs: Additional frame arguments
        """
        super().__init__(parent, **kwargs)

        self._create_widgets(icon, title, message, action_text, action_command)

    def _create_widgets(
        self,
        icon: str,
        title: str,
        message: str,
        action_text: str,
        action_command: Optional[callable]
    ) -> None:
        """Create empty state widgets."""
        # Center container
        center = ttk.Frame(self)
        center.place(relx=0.5, rely=0.5, anchor="center")

        # Icon
        icon_label = ttk.Label(
            center,
            text=icon,
            font=Fonts.get_font(48)
        )
        icon_label.pack()

        # Title
        title_label = ttk.Label(
            center,
            text=title,
            font=Fonts.get_font(Fonts.SIZE_XL, Fonts.WEIGHT_BOLD)
        )
        title_label.pack(pady=(Spacing.MD, Spacing.XS))

        # Message
        if message:
            message_label = ttk.Label(
                center,
                text=message,
                font=Fonts.get_font(Fonts.SIZE_MD),
                foreground=Colors.LIGHT_FG_MUTED,
                wraplength=300,
                justify="center"
            )
            message_label.pack()

        # Action button
        if action_text and action_command:
            action_btn = ttk.Button(
                center,
                text=action_text,
                command=action_command,
                bootstyle="primary"
            )
            action_btn.pack(pady=(Spacing.LG, 0))

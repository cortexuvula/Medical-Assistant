"""
UI Constants Module

Centralized constants for colors, fonts, spacing, and button styles.
This module ensures consistent styling across the entire application.
"""

from enum import Enum
from typing import Tuple


# =============================================================================
# COLOR PALETTE
# =============================================================================

class Colors:
    """Centralized color constants for the application."""

    # Primary colors (from Bootstrap/ttkbootstrap)
    PRIMARY = "#0d6efd"      # Blue
    SECONDARY = "#6c757d"    # Gray
    SUCCESS = "#28a745"      # Green
    DANGER = "#dc3545"       # Red
    WARNING = "#ffc107"      # Yellow/Amber
    INFO = "#17a2b8"         # Cyan/Light Blue
    DARK = "#343a40"         # Dark Gray

    # Status colors (for status indicators)
    STATUS_SUCCESS = "#28a745"
    STATUS_INFO = "#17a2b8"
    STATUS_WARNING = "#ffc107"
    STATUS_ERROR = "#dc3545"
    STATUS_IDLE = "#888888"
    STATUS_PROCESSING = "#f39c12"  # Orange

    # Recording status
    RECORDING_READY = "#27ae60"    # Slightly different green
    RECORDING_ACTIVE = "#dc3545"   # Red
    RECORDING_PAUSED = "#f39c12"   # Orange

    # Content status (for treeview items)
    CONTENT_COMPLETE = "#27ae60"   # Green
    CONTENT_PARTIAL = "#3498db"    # Blue
    CONTENT_NONE = "#888888"       # Gray
    CONTENT_FAILED = "#e74c3c"     # Red
    CONTENT_PROCESSING = "#f39c12" # Orange

    # Light theme colors
    LIGHT_BG = "#ffffff"
    LIGHT_BG_SECONDARY = "#f8f9fa"
    LIGHT_BG_TERTIARY = "#e9ecef"
    LIGHT_FG = "#212529"
    LIGHT_FG_MUTED = "#6c757d"
    LIGHT_BORDER = "#dee2e6"

    # Dark theme colors
    DARK_BG = "#212529"
    DARK_BG_SECONDARY = "#343a40"
    DARK_BG_TERTIARY = "#495057"
    DARK_FG = "#f8f9fa"
    DARK_FG_MUTED = "#adb5bd"
    DARK_BORDER = "#495057"

    # Hover colors
    HOVER_LIGHT = "#e3f2fd"
    HOVER_DARK = "#3d4852"

    # Tooltip
    TOOLTIP_BG = "#ffffe0"
    TOOLTIP_FG = "#000000"

    @classmethod
    def get_theme_colors(cls, is_dark: bool) -> dict:
        """Get color set for current theme.

        Args:
            is_dark: Whether dark theme is active

        Returns:
            Dict with bg, bg_secondary, fg, fg_muted, border keys
        """
        if is_dark:
            return {
                "bg": cls.DARK_BG,
                "bg_secondary": cls.DARK_BG_SECONDARY,
                "bg_tertiary": cls.DARK_BG_TERTIARY,
                "fg": cls.DARK_FG,
                "fg_muted": cls.DARK_FG_MUTED,
                "border": cls.DARK_BORDER,
                "hover": cls.HOVER_DARK,
            }
        else:
            return {
                "bg": cls.LIGHT_BG,
                "bg_secondary": cls.LIGHT_BG_SECONDARY,
                "bg_tertiary": cls.LIGHT_BG_TERTIARY,
                "fg": cls.LIGHT_FG,
                "fg_muted": cls.LIGHT_FG_MUTED,
                "border": cls.LIGHT_BORDER,
                "hover": cls.HOVER_LIGHT,
            }


# =============================================================================
# FONT SYSTEM
# =============================================================================

class Fonts:
    """Centralized font constants and utilities."""

    # Primary font family with fallbacks
    FAMILY = ("Segoe UI", "Arial", "Helvetica", "sans-serif")

    # Font sizes (base sizes before scaling)
    SIZE_XS = 8
    SIZE_SM = 9
    SIZE_MD = 10
    SIZE_LG = 11
    SIZE_XL = 12
    SIZE_XXL = 14
    SIZE_TITLE = 16
    SIZE_HEADER = 20

    # Font weights
    WEIGHT_NORMAL = "normal"
    WEIGHT_BOLD = "bold"

    @classmethod
    def get_font(
        cls,
        size: int = None,
        weight: str = None,
        scale_func=None
    ) -> Tuple[str, int, str]:
        """Get a font tuple for tkinter widgets.

        Args:
            size: Font size (default: SIZE_MD)
            weight: Font weight (default: WEIGHT_NORMAL)
            scale_func: Optional function to scale the size (e.g., ui_scaler.scale_font_size)

        Returns:
            Tuple of (family, size, weight) for tkinter
        """
        if size is None:
            size = cls.SIZE_MD
        if weight is None:
            weight = cls.WEIGHT_NORMAL

        # Apply scaling if provided
        if scale_func:
            size = scale_func(size)

        # Return first font in family (tkinter uses single font name)
        return (cls.FAMILY[0], size, weight)

    @classmethod
    def get_family_string(cls) -> str:
        """Get font family as comma-separated string for CSS-like usage."""
        return ", ".join(cls.FAMILY)


# =============================================================================
# SPACING SYSTEM
# =============================================================================

class Spacing:
    """Centralized spacing constants."""

    # Base spacing values
    NONE = 0
    XS = 2
    SM = 5
    MD = 10
    LG = 15
    XL = 20
    XXL = 30

    # Common padding combinations
    PADDING_NONE = (0, 0)
    PADDING_XS = (2, 2)
    PADDING_SM = (5, 5)
    PADDING_MD = (10, 10)
    PADDING_LG = (15, 15)
    PADDING_XL = (20, 20)

    # Asymmetric padding (horizontal, vertical)
    PADDING_BUTTON = (10, 5)
    PADDING_DIALOG = (20, 15)
    PADDING_FRAME = (10, 5)
    PADDING_STATUS_BAR = (10, 5)


# =============================================================================
# BUTTON STYLES
# =============================================================================

class ButtonStyle(Enum):
    """Button style types for consistent styling."""

    # Primary actions
    PRIMARY = "primary"
    PRIMARY_OUTLINE = "primary-outline"

    # Success/positive actions
    SUCCESS = "success"
    SUCCESS_OUTLINE = "success-outline"

    # Danger/destructive actions
    DANGER = "danger"
    DANGER_OUTLINE = "danger-outline"

    # Warning/caution actions
    WARNING = "warning"
    WARNING_OUTLINE = "warning-outline"

    # Info/neutral actions
    INFO = "info"
    INFO_OUTLINE = "info-outline"

    # Secondary/muted actions
    SECONDARY = "secondary"
    SECONDARY_OUTLINE = "secondary-outline"

    # Dark style
    DARK = "dark"
    DARK_OUTLINE = "dark-outline"


class ButtonConfig:
    """Button configuration constants and utilities."""

    # Standard button widths
    WIDTH_XS = 6
    WIDTH_SM = 10
    WIDTH_MD = 15
    WIDTH_LG = 20
    WIDTH_XL = 25

    # Style mappings for action types
    ACTION_STYLES = {
        # Primary actions
        "primary": ButtonStyle.PRIMARY_OUTLINE,
        "submit": ButtonStyle.PRIMARY_OUTLINE,
        "save": ButtonStyle.PRIMARY_OUTLINE,
        "send": ButtonStyle.PRIMARY_OUTLINE,

        # Success/positive actions
        "start": ButtonStyle.SUCCESS_OUTLINE,
        "record": ButtonStyle.SUCCESS_OUTLINE,
        "process": ButtonStyle.SUCCESS_OUTLINE,
        "generate": ButtonStyle.SUCCESS_OUTLINE,
        "create": ButtonStyle.SUCCESS_OUTLINE,

        # Destructive actions
        "delete": ButtonStyle.DANGER_OUTLINE,
        "clear": ButtonStyle.DANGER_OUTLINE,
        "cancel": ButtonStyle.DANGER_OUTLINE,
        "remove": ButtonStyle.DANGER_OUTLINE,

        # Warning/caution actions
        "pause": ButtonStyle.WARNING_OUTLINE,
        "stop": ButtonStyle.WARNING_OUTLINE,
        "reprocess": ButtonStyle.WARNING_OUTLINE,

        # Info/tool actions
        "info": ButtonStyle.INFO_OUTLINE,
        "export": ButtonStyle.INFO_OUTLINE,
        "view": ButtonStyle.INFO_OUTLINE,
        "tools": ButtonStyle.INFO_OUTLINE,

        # Secondary/muted actions
        "secondary": ButtonStyle.SECONDARY_OUTLINE,
        "clear_field": ButtonStyle.SECONDARY_OUTLINE,
        "reset": ButtonStyle.SECONDARY_OUTLINE,

        # Dark/advanced actions
        "advanced": ButtonStyle.DARK_OUTLINE,
        "workflow": ButtonStyle.DARK_OUTLINE,
    }

    @classmethod
    def get_style_for_action(cls, action: str) -> str:
        """Get the appropriate button style for an action type.

        Args:
            action: Action type (e.g., 'delete', 'save', 'start')

        Returns:
            Button style string for ttkbootstrap bootstyle
        """
        style = cls.ACTION_STYLES.get(action.lower(), ButtonStyle.SECONDARY_OUTLINE)
        return style.value

    @classmethod
    def get_hover_style(cls, style: str) -> str:
        """Get the hover style (solid version) for an outline style.

        Args:
            style: Current button style (e.g., 'primary-outline')

        Returns:
            Solid version of the style for hover effect
        """
        if "-outline" in style:
            return style.replace("-outline", "")
        return style


# =============================================================================
# ICON CONSTANTS
# =============================================================================

class Icons:
    """Unicode icons/emojis for UI elements."""

    # Status icons
    SUCCESS = "✓"
    ERROR = "✗"
    WARNING = "⚠"
    INFO = "ℹ"
    PROCESSING = "🔄"

    # Action icons
    PLAY = "▶"
    PAUSE = "⏸"
    STOP = "⏹"
    RECORD = "⏺"

    # Navigation
    REFRESH = "⟳"
    EXPAND = "▼"
    COLLAPSE = "▲"
    MENU = "☰"

    # Theme
    SUN = "☀️"
    MOON = "🌙"

    # Content status
    CHECK = "✓"
    DASH = "—"
    CROSS = "❌"
    SPINNER = "🔄"

    # Sidebar Navigation Icons (simple text-based)
    NAV_RECORD = "●"
    NAV_SOAP = "◎"
    NAV_REFERRAL = "□"
    NAV_LETTER = "✉"
    NAV_CHAT = "◉"
    NAV_RAG = "◈"
    NAV_RECORDINGS = "▤"
    NAV_ADVANCED_ANALYSIS = "◇"
    NAV_SETTINGS = "⚙"

    # Sidebar Tool Icons (simple text-based)
    TOOL_TRANSLATION = "⊕"
    TOOL_MEDICATION = "◆"
    TOOL_DIAGNOSTIC = "⊛"
    TOOL_WORKFLOW = "⊞"
    TOOL_DATA = "⊟"
    TOOL_REFINE = "✎"
    TOOL_IMPROVE = "★"
    TOOL_ANALYTICS = "⊙"
    TOOL_ADMIN = "⊠"
    TOOL_FEEDBACK = "✦"
    TOOL_RSVP = "◉"

    # File operation icons
    FILE_NEW = "○"
    FILE_SAVE = "◇"
    FILE_LOAD = "◁"
    FILE_EXPORT = "▷"

    # Sidebar Toggle
    SIDEBAR_COLLAPSE = "◂"
    SIDEBAR_EXPAND = "▸"
    SECTION_OPEN = "▾"
    SECTION_CLOSED = "▸"


# =============================================================================
# DIALOG CONSTANTS
# =============================================================================

class DialogConfig:
    """Dialog configuration constants."""

    # Default dialog sizes (width, height)
    SIZE_SM = (400, 300)
    SIZE_MD = (600, 450)
    SIZE_LG = (800, 600)
    SIZE_XL = (950, 700)

    # Size limits as screen percentage
    MAX_WIDTH_PERCENT = 0.9
    MAX_HEIGHT_PERCENT = 0.9

    @classmethod
    def get_centered_geometry(
        cls,
        screen_width: int,
        screen_height: int,
        dialog_width: int,
        dialog_height: int
    ) -> str:
        """Calculate centered dialog geometry string.

        Args:
            screen_width: Screen width in pixels
            screen_height: Screen height in pixels
            dialog_width: Desired dialog width
            dialog_height: Desired dialog height

        Returns:
            Geometry string for tkinter (e.g., "800x600+100+50")
        """
        # Apply max size limits
        max_width = int(screen_width * cls.MAX_WIDTH_PERCENT)
        max_height = int(screen_height * cls.MAX_HEIGHT_PERCENT)

        final_width = min(dialog_width, max_width)
        final_height = min(dialog_height, max_height)

        # Calculate centered position
        x = (screen_width - final_width) // 2
        y = (screen_height - final_height) // 2

        return f"{final_width}x{final_height}+{x}+{y}"


# =============================================================================
# ANIMATION CONSTANTS
# =============================================================================

class Animation:
    """Animation timing constants."""

    # Delays in milliseconds
    TOOLTIP_DELAY = 500
    STATUS_CLEAR_DELAY = 8000
    PULSE_INTERVAL = 100
    SPINNER_INTERVAL = 80

    # Transition durations
    HOVER_TRANSITION = 150
    FADE_DURATION = 200


# =============================================================================
# SIDEBAR CONSTANTS
# =============================================================================

class SidebarConfig:
    """Sidebar navigation configuration constants."""

    # Dimensions
    WIDTH_EXPANDED = 200
    WIDTH_COLLAPSED = 50
    ITEM_HEIGHT = 40
    SECTION_HEADER_HEIGHT = 30
    ICON_SIZE = 20

    # Padding
    ITEM_PADDING_X = 12
    ITEM_PADDING_Y = 8
    SECTION_PADDING = 5

    # Navigation items configuration
    NAV_ITEMS = [
        {"id": "record", "label": "Record", "icon": "NAV_RECORD"},
        {"id": "soap", "label": "SOAP Note", "icon": "NAV_SOAP"},
        {"id": "referral", "label": "Referral", "icon": "NAV_REFERRAL"},
        {"id": "letter", "label": "Letter", "icon": "NAV_LETTER"},
        {"id": "chat", "label": "Chat", "icon": "NAV_CHAT"},
        {"id": "rag", "label": "RAG", "icon": "NAV_RAG"},
        {"id": "recordings", "label": "Recordings", "icon": "NAV_RECORDINGS"},
        {"id": "advanced_analysis", "label": "Analysis", "icon": "NAV_ADVANCED_ANALYSIS"},
    ]

    # File operation items
    FILE_ITEMS = [
        {"id": "new_session", "label": "New Session", "icon": "FILE_NEW"},
        {"id": "save", "label": "Save", "icon": "FILE_SAVE"},
        {"id": "load_audio", "label": "Load Audio", "icon": "FILE_LOAD"},
        {"id": "export_pdf", "label": "Export PDF", "icon": "FILE_EXPORT"},
    ]

    # Generate items - for creating documents
    GENERATE_ITEMS = [
        {"id": "gen_soap", "label": "Generate SOAP", "icon": "NAV_SOAP"},
        {"id": "gen_referral", "label": "Generate Referral", "icon": "NAV_REFERRAL"},
        {"id": "gen_letter", "label": "Generate Letter", "icon": "NAV_LETTER"},
    ]

    # Tool items configuration - labels match actual functionality
    TOOL_ITEMS = [
        {"id": "refine", "label": "Refine Text", "icon": "TOOL_REFINE"},
        {"id": "improve", "label": "Improve Text", "icon": "TOOL_IMPROVE"},
        {"id": "medication", "label": "Medication", "icon": "TOOL_MEDICATION"},
        {"id": "diagnostic", "label": "Diagnostic", "icon": "TOOL_DIAGNOSTIC"},
        {"id": "workflow", "label": "Workflow", "icon": "TOOL_WORKFLOW"},
        {"id": "translation", "label": "Translation", "icon": "TOOL_TRANSLATION"},
        {"id": "data_extraction", "label": "Data Extract", "icon": "TOOL_DATA"},
        {"id": "rsvp_reader", "label": "RSVP Reader", "icon": "TOOL_RSVP"},
    ]

    @classmethod
    def get_nav_items(cls) -> list:
        """Get navigation items with resolved icon references."""
        return [
            {**item, "icon": getattr(Icons, item["icon"])}
            for item in cls.NAV_ITEMS
        ]

    @classmethod
    def get_file_items(cls) -> list:
        """Get file items with resolved icon references."""
        return [
            {**item, "icon": getattr(Icons, item["icon"])}
            for item in cls.FILE_ITEMS
        ]

    @classmethod
    def get_generate_items(cls) -> list:
        """Get generate items with resolved icon references."""
        return [
            {**item, "icon": getattr(Icons, item["icon"])}
            for item in cls.GENERATE_ITEMS
        ]

    @classmethod
    def get_tool_items(cls) -> list:
        """Get tool items with resolved icon references."""
        return [
            {**item, "icon": getattr(Icons, item["icon"])}
            for item in cls.TOOL_ITEMS
        ]

    # Colors for sidebar (extends theme colors)
    @classmethod
    def get_sidebar_colors(cls, is_dark: bool) -> dict:
        """Get sidebar-specific colors for current theme."""
        if is_dark:
            return {
                "bg": "#1a1d21",
                "bg_hover": "#2d3138",
                "bg_active": "#0d6efd",
                "fg": "#f8f9fa",
                "fg_active": "#ffffff",
                "fg_muted": "#adb5bd",
                "border": "#343a40",
                "section_bg": "#212529",
            }
        else:
            return {
                "bg": "#f8f9fa",
                "bg_hover": "#e9ecef",
                "bg_active": "#0d6efd",
                "fg": "#212529",
                "fg_active": "#ffffff",
                "fg_muted": "#6c757d",
                "border": "#dee2e6",
                "section_bg": "#ffffff",
            }

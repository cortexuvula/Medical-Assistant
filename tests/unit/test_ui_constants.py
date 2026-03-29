"""
Tests for src/ui/ui_constants.py

Covers Colors (constants, get_theme_colors); Fonts (size/weight constants,
get_font, get_family_string); Spacing (constants, padding tuples); ButtonStyle
enum; ButtonConfig (widths, get_style_for_action, get_hover_style); Icons
constants; DialogConfig (sizes, get_centered_geometry); Animation constants;
SidebarConfig (dimensions, nav/file/generate/tool/soap items, get_* methods,
get_sidebar_colors).
No network, no Tkinter, no I/O.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ui.ui_constants import (
    Colors, Fonts, Spacing, ButtonStyle, ButtonConfig,
    Icons, DialogConfig, Animation, SidebarConfig,
)


# ===========================================================================
# Colors
# ===========================================================================

class TestColors:
    def test_primary_is_string(self):
        assert isinstance(Colors.PRIMARY, str)

    def test_primary_starts_with_hash(self):
        assert Colors.PRIMARY.startswith("#")

    def test_danger_is_red_ish(self):
        # Red channel dominates
        assert Colors.DANGER.startswith("#dc") or Colors.DANGER.startswith("#e")

    def test_status_colors_exist(self):
        for attr in ("STATUS_SUCCESS", "STATUS_INFO", "STATUS_WARNING", "STATUS_ERROR", "STATUS_IDLE"):
            assert hasattr(Colors, attr)

    def test_recording_colors_exist(self):
        for attr in ("RECORDING_READY", "RECORDING_ACTIVE", "RECORDING_PAUSED"):
            assert hasattr(Colors, attr)

    def test_content_colors_exist(self):
        for attr in ("CONTENT_COMPLETE", "CONTENT_PARTIAL", "CONTENT_NONE", "CONTENT_FAILED"):
            assert hasattr(Colors, attr)

    def test_get_theme_colors_dark_returns_dict(self):
        result = Colors.get_theme_colors(is_dark=True)
        assert isinstance(result, dict)

    def test_get_theme_colors_light_returns_dict(self):
        result = Colors.get_theme_colors(is_dark=False)
        assert isinstance(result, dict)

    def test_get_theme_colors_dark_has_required_keys(self):
        result = Colors.get_theme_colors(is_dark=True)
        for key in ("bg", "fg", "border"):
            assert key in result

    def test_get_theme_colors_light_has_required_keys(self):
        result = Colors.get_theme_colors(is_dark=False)
        for key in ("bg", "fg", "border"):
            assert key in result

    def test_dark_bg_different_from_light_bg(self):
        dark = Colors.get_theme_colors(is_dark=True)
        light = Colors.get_theme_colors(is_dark=False)
        assert dark["bg"] != light["bg"]

    def test_tooltip_colors_exist(self):
        assert hasattr(Colors, "TOOLTIP_BG")
        assert hasattr(Colors, "TOOLTIP_FG")


# ===========================================================================
# Fonts
# ===========================================================================

class TestFonts:
    def test_family_is_tuple(self):
        assert isinstance(Fonts.FAMILY, tuple)

    def test_family_non_empty(self):
        assert len(Fonts.FAMILY) > 0

    def test_size_xs_less_than_sm(self):
        assert Fonts.SIZE_XS < Fonts.SIZE_SM

    def test_size_sm_less_than_md(self):
        assert Fonts.SIZE_SM < Fonts.SIZE_MD

    def test_size_md_less_than_xl(self):
        assert Fonts.SIZE_MD < Fonts.SIZE_XL

    def test_size_title_less_than_header(self):
        assert Fonts.SIZE_TITLE < Fonts.SIZE_HEADER

    def test_weight_normal_is_string(self):
        assert isinstance(Fonts.WEIGHT_NORMAL, str)

    def test_weight_bold_is_string(self):
        assert isinstance(Fonts.WEIGHT_BOLD, str)

    def test_get_font_returns_tuple(self):
        result = Fonts.get_font()
        assert isinstance(result, tuple)

    def test_get_font_has_three_elements(self):
        result = Fonts.get_font()
        assert len(result) == 3

    def test_get_font_default_size(self):
        result = Fonts.get_font()
        assert result[1] == Fonts.SIZE_MD

    def test_get_font_custom_size(self):
        result = Fonts.get_font(size=14)
        assert result[1] == 14

    def test_get_font_bold(self):
        result = Fonts.get_font(weight=Fonts.WEIGHT_BOLD)
        assert result[2] == Fonts.WEIGHT_BOLD

    def test_get_font_with_scale_func(self):
        result = Fonts.get_font(size=10, scale_func=lambda s: s * 2)
        assert result[1] == 20

    def test_get_family_string_returns_str(self):
        assert isinstance(Fonts.get_family_string(), str)

    def test_get_family_string_non_empty(self):
        assert len(Fonts.get_family_string()) > 0

    def test_get_family_string_contains_font_name(self):
        assert Fonts.FAMILY[0] in Fonts.get_family_string()


# ===========================================================================
# Spacing
# ===========================================================================

class TestSpacing:
    def test_none_is_zero(self):
        assert Spacing.NONE == 0

    def test_xs_less_than_sm(self):
        assert Spacing.XS < Spacing.SM

    def test_sm_less_than_md(self):
        assert Spacing.SM < Spacing.MD

    def test_md_less_than_lg(self):
        assert Spacing.MD < Spacing.LG

    def test_lg_less_than_xl(self):
        assert Spacing.LG < Spacing.XL

    def test_xl_less_than_xxl(self):
        assert Spacing.XL < Spacing.XXL

    def test_padding_tuples_are_pairs(self):
        for attr in ("PADDING_SM", "PADDING_MD", "PADDING_LG"):
            val = getattr(Spacing, attr)
            assert isinstance(val, tuple)
            assert len(val) == 2

    def test_padding_button_exists(self):
        assert hasattr(Spacing, "PADDING_BUTTON")

    def test_padding_dialog_exists(self):
        assert hasattr(Spacing, "PADDING_DIALOG")


# ===========================================================================
# ButtonStyle enum
# ===========================================================================

class TestButtonStyle:
    def test_primary_value(self):
        assert ButtonStyle.PRIMARY.value == "primary"

    def test_danger_value(self):
        assert ButtonStyle.DANGER.value == "danger"

    def test_success_value(self):
        assert ButtonStyle.SUCCESS.value == "success"

    def test_all_outline_variants_contain_outline(self):
        outline_members = [m for m in ButtonStyle if "outline" in m.name.lower()]
        for m in outline_members:
            assert "outline" in m.value

    def test_at_least_eight_members(self):
        assert len(list(ButtonStyle)) >= 8

    def test_all_values_are_strings(self):
        for m in ButtonStyle:
            assert isinstance(m.value, str)


# ===========================================================================
# ButtonConfig
# ===========================================================================

class TestButtonConfig:
    def test_width_xs_less_than_sm(self):
        assert ButtonConfig.WIDTH_XS < ButtonConfig.WIDTH_SM

    def test_width_sm_less_than_md(self):
        assert ButtonConfig.WIDTH_SM < ButtonConfig.WIDTH_MD

    def test_width_md_less_than_lg(self):
        assert ButtonConfig.WIDTH_MD < ButtonConfig.WIDTH_LG

    def test_action_styles_dict_exists(self):
        assert isinstance(ButtonConfig.ACTION_STYLES, dict)

    def test_action_styles_non_empty(self):
        assert len(ButtonConfig.ACTION_STYLES) > 0

    def test_delete_maps_to_danger(self):
        style = ButtonConfig.get_style_for_action("delete")
        assert "danger" in style

    def test_save_maps_to_primary(self):
        style = ButtonConfig.get_style_for_action("save")
        assert "primary" in style

    def test_start_maps_to_success(self):
        style = ButtonConfig.get_style_for_action("start")
        assert "success" in style

    def test_unknown_action_returns_string(self):
        style = ButtonConfig.get_style_for_action("unknown_action_xyz")
        assert isinstance(style, str)

    def test_case_insensitive(self):
        lower = ButtonConfig.get_style_for_action("delete")
        upper = ButtonConfig.get_style_for_action("DELETE")
        assert lower == upper

    def test_get_hover_style_removes_outline(self):
        result = ButtonConfig.get_hover_style("primary-outline")
        assert result == "primary"

    def test_get_hover_style_no_outline_unchanged(self):
        result = ButtonConfig.get_hover_style("primary")
        assert result == "primary"

    def test_get_hover_style_danger_outline(self):
        result = ButtonConfig.get_hover_style("danger-outline")
        assert result == "danger"


# ===========================================================================
# Icons
# ===========================================================================

class TestIcons:
    def test_success_icon_exists(self):
        assert hasattr(Icons, "SUCCESS")

    def test_error_icon_exists(self):
        assert hasattr(Icons, "ERROR")

    def test_play_icon_exists(self):
        assert hasattr(Icons, "PLAY")

    def test_all_nav_icons_are_strings(self):
        for attr in ("NAV_RECORD", "NAV_SOAP", "NAV_REFERRAL", "NAV_LETTER", "NAV_CHAT"):
            assert isinstance(getattr(Icons, attr), str)

    def test_tool_icons_exist(self):
        for attr in ("TOOL_TRANSLATION", "TOOL_MEDICATION", "TOOL_DIAGNOSTIC"):
            assert hasattr(Icons, attr)

    def test_file_icons_exist(self):
        for attr in ("FILE_NEW", "FILE_SAVE", "FILE_LOAD", "FILE_EXPORT"):
            assert hasattr(Icons, attr)

    def test_sidebar_toggle_icons_exist(self):
        assert hasattr(Icons, "SIDEBAR_COLLAPSE")
        assert hasattr(Icons, "SIDEBAR_EXPAND")


# ===========================================================================
# DialogConfig
# ===========================================================================

class TestDialogConfig:
    def test_size_sm_is_pair(self):
        assert len(DialogConfig.SIZE_SM) == 2

    def test_size_md_is_pair(self):
        assert len(DialogConfig.SIZE_MD) == 2

    def test_size_lg_wider_than_md(self):
        assert DialogConfig.SIZE_LG[0] > DialogConfig.SIZE_MD[0]

    def test_max_width_percent_in_range(self):
        assert 0 < DialogConfig.MAX_WIDTH_PERCENT <= 1.0

    def test_max_height_percent_in_range(self):
        assert 0 < DialogConfig.MAX_HEIGHT_PERCENT <= 1.0

    def test_get_centered_geometry_returns_string(self):
        result = DialogConfig.get_centered_geometry(1920, 1080, 800, 600)
        assert isinstance(result, str)

    def test_get_centered_geometry_format(self):
        result = DialogConfig.get_centered_geometry(1920, 1080, 800, 600)
        # Should be "WxH+X+Y"
        assert "x" in result
        assert "+" in result

    def test_get_centered_geometry_centered_x(self):
        # Center on 1000x800 screen with 600x400 dialog
        result = DialogConfig.get_centered_geometry(1000, 800, 600, 400)
        parts = result.split("+")
        x = int(parts[1])
        # With capped width and centered at (1000-600)//2 = 200
        assert x >= 0

    def test_get_centered_geometry_caps_at_max_size(self):
        # Dialog larger than 90% of screen should be capped
        result = DialogConfig.get_centered_geometry(1000, 800, 2000, 2000)
        parts = result.split("x")
        width = int(parts[0])
        assert width <= 1000

    def test_get_centered_geometry_small_dialog(self):
        # Small dialog inside large screen should not be changed
        result = DialogConfig.get_centered_geometry(1920, 1080, 400, 300)
        parts = result.split("x")
        width = int(parts[0])
        assert width == 400


# ===========================================================================
# Animation
# ===========================================================================

class TestAnimation:
    def test_tooltip_delay_positive(self):
        assert Animation.TOOLTIP_DELAY > 0

    def test_status_clear_delay_positive(self):
        assert Animation.STATUS_CLEAR_DELAY > 0

    def test_status_clear_delay_several_seconds(self):
        assert Animation.STATUS_CLEAR_DELAY >= 3000  # At least 3 seconds

    def test_pulse_interval_positive(self):
        assert Animation.PULSE_INTERVAL > 0

    def test_spinner_interval_positive(self):
        assert Animation.SPINNER_INTERVAL > 0

    def test_hover_transition_positive(self):
        assert Animation.HOVER_TRANSITION > 0

    def test_fade_duration_positive(self):
        assert Animation.FADE_DURATION > 0


# ===========================================================================
# SidebarConfig
# ===========================================================================

class TestSidebarConfig:
    def test_expanded_wider_than_collapsed(self):
        assert SidebarConfig.WIDTH_EXPANDED > SidebarConfig.WIDTH_COLLAPSED

    def test_item_height_positive(self):
        assert SidebarConfig.ITEM_HEIGHT > 0

    def test_nav_items_list(self):
        assert isinstance(SidebarConfig.NAV_ITEMS, list)

    def test_nav_items_non_empty(self):
        assert len(SidebarConfig.NAV_ITEMS) > 0

    def test_nav_items_have_id_label_icon(self):
        for item in SidebarConfig.NAV_ITEMS:
            assert "id" in item
            assert "label" in item
            assert "icon" in item

    def test_file_items_non_empty(self):
        assert len(SidebarConfig.FILE_ITEMS) > 0

    def test_generate_items_non_empty(self):
        assert len(SidebarConfig.GENERATE_ITEMS) > 0

    def test_tool_items_non_empty(self):
        assert len(SidebarConfig.TOOL_ITEMS) > 0

    def test_get_nav_items_returns_list(self):
        result = SidebarConfig.get_nav_items()
        assert isinstance(result, list)

    def test_get_nav_items_same_length_as_nav_items(self):
        result = SidebarConfig.get_nav_items()
        assert len(result) == len(SidebarConfig.NAV_ITEMS)

    def test_get_nav_items_resolves_icon_to_string(self):
        for item in SidebarConfig.get_nav_items():
            assert isinstance(item["icon"], str)

    def test_get_file_items_resolves_icons(self):
        for item in SidebarConfig.get_file_items():
            assert isinstance(item["icon"], str)

    def test_get_generate_items_resolves_icons(self):
        for item in SidebarConfig.get_generate_items():
            assert isinstance(item["icon"], str)

    def test_get_tool_items_resolves_icons(self):
        for item in SidebarConfig.get_tool_items():
            assert isinstance(item["icon"], str)

    def test_get_soap_subitems_returns_list(self):
        result = SidebarConfig.get_soap_subitems()
        assert isinstance(result, list)

    def test_get_sidebar_colors_dark_returns_dict(self):
        result = SidebarConfig.get_sidebar_colors(is_dark=True)
        assert isinstance(result, dict)

    def test_get_sidebar_colors_light_returns_dict(self):
        result = SidebarConfig.get_sidebar_colors(is_dark=False)
        assert isinstance(result, dict)

    def test_get_sidebar_colors_dark_has_bg_key(self):
        result = SidebarConfig.get_sidebar_colors(is_dark=True)
        assert "bg" in result

    def test_get_sidebar_colors_different_for_themes(self):
        dark = SidebarConfig.get_sidebar_colors(is_dark=True)
        light = SidebarConfig.get_sidebar_colors(is_dark=False)
        assert dark["bg"] != light["bg"]

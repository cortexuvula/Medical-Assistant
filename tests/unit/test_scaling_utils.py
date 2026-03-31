"""
Tests for src/ui/scaling_utils.py

Covers UIScaler pure logic (no tkinter initialization):
- Default property values before initialization
- _determine_screen_category for each category
- scale_dimension and scale_font_size
- get_window_size, get_minimum_window_size, get_dialog_size
- get_button_width, get_padding, get_column_weights
- scale_factor and screen_category properties
No network, no Tkinter, no real display.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ui.scaling_utils import UIScaler


# ---------------------------------------------------------------------------
# Helpers — build a UIScaler with specific state without needing tkinter
# ---------------------------------------------------------------------------

def _scaler(scale_factor=None, category=None, width=None, height=None, dpi=None):
    """Create a UIScaler and set its private state directly."""
    s = UIScaler()
    s._scale_factor = scale_factor
    s._screen_category = category
    s._screen_width = width
    s._screen_height = height
    s._dpi = dpi
    return s


# ===========================================================================
# Defaults (no initialization)
# ===========================================================================

class TestDefaults:
    def test_scale_factor_none_initially(self):
        s = UIScaler()
        assert s._scale_factor is None

    def test_screen_category_none_initially(self):
        s = UIScaler()
        assert s._screen_category is None

    def test_screen_width_none_initially(self):
        s = UIScaler()
        assert s._screen_width is None

    def test_screen_height_none_initially(self):
        s = UIScaler()
        assert s._screen_height is None

    def test_base_dpi_is_96(self):
        assert UIScaler.BASE_DPI == 96

    def test_category_constants_exist(self):
        assert UIScaler.ULTRAWIDE == "ultrawide"
        assert UIScaler.HIGH_DPI == "high_dpi"
        assert UIScaler.STANDARD == "standard"
        assert UIScaler.SMALL == "small"


# ===========================================================================
# Properties
# ===========================================================================

class TestProperties:
    def test_scale_factor_property_none_returns_1(self):
        s = _scaler()
        assert s.scale_factor == 1.0

    def test_scale_factor_property_returns_set_value(self):
        s = _scaler(scale_factor=1.5)
        assert s.scale_factor == 1.5

    def test_screen_category_property_none_returns_standard(self):
        s = _scaler()
        assert s.screen_category == UIScaler.STANDARD

    def test_screen_category_property_returns_set_value(self):
        s = _scaler(category=UIScaler.ULTRAWIDE)
        assert s.screen_category == UIScaler.ULTRAWIDE

    def test_screen_width_property(self):
        s = _scaler(width=1920)
        assert s.screen_width == 1920

    def test_screen_height_property(self):
        s = _scaler(height=1080)
        assert s.screen_height == 1080


# ===========================================================================
# _determine_screen_category
# ===========================================================================

class TestDetermineScreenCategory:
    def test_no_dimensions_returns_standard(self):
        s = _scaler()
        assert s._determine_screen_category() == UIScaler.STANDARD

    def test_ultrawide_aspect_ratio(self):
        # 3440x1440 has aspect ratio ~2.39 > 2.1
        s = _scaler(width=3440, height=1440, dpi=96)
        assert s._determine_screen_category() == UIScaler.ULTRAWIDE

    def test_high_dpi_from_dpi_value(self):
        # 1920x1080 with DPI > 120
        s = _scaler(width=1920, height=1080, dpi=144)
        assert s._determine_screen_category() == UIScaler.HIGH_DPI

    def test_high_dpi_from_pixel_count(self):
        # 2560x1440 = 3,686,400 pixels > 3,000,000, normal aspect
        s = _scaler(width=2560, height=1440, dpi=96)
        assert s._determine_screen_category() == UIScaler.HIGH_DPI

    def test_small_screen_width(self):
        # 1280x800 — width < 1400 → small
        s = _scaler(width=1280, height=800, dpi=96)
        assert s._determine_screen_category() == UIScaler.SMALL

    def test_small_screen_height(self):
        # 1440x768 — height < 900 → small
        s = _scaler(width=1440, height=768, dpi=96)
        assert s._determine_screen_category() == UIScaler.SMALL

    def test_standard_screen(self):
        # 1920x1080 with 96 DPI — normal
        s = _scaler(width=1920, height=1080, dpi=96)
        assert s._determine_screen_category() == UIScaler.STANDARD


# ===========================================================================
# scale_dimension
# ===========================================================================

class TestScaleDimension:
    def test_no_scale_factor_returns_original(self):
        s = _scaler()
        assert s.scale_dimension(100) == 100

    def test_scale_1x(self):
        s = _scaler(scale_factor=1.0)
        assert s.scale_dimension(100) == 100

    def test_scale_2x(self):
        s = _scaler(scale_factor=2.0)
        assert s.scale_dimension(100) == 200

    def test_scale_1_5x(self):
        s = _scaler(scale_factor=1.5)
        assert s.scale_dimension(100) == 150

    def test_returns_int(self):
        s = _scaler(scale_factor=1.5)
        assert isinstance(s.scale_dimension(100), int)

    def test_zero_dimension(self):
        s = _scaler(scale_factor=2.0)
        assert s.scale_dimension(0) == 0


# ===========================================================================
# scale_font_size
# ===========================================================================

class TestScaleFontSize:
    def test_no_scale_factor_returns_original(self):
        s = _scaler()
        assert s.scale_font_size(12) == 12

    def test_scale_1x_no_category(self):
        s = _scaler(scale_factor=1.0, category=UIScaler.STANDARD)
        assert s.scale_font_size(12) == 12

    def test_scale_2x_standard(self):
        s = _scaler(scale_factor=2.0, category=UIScaler.STANDARD)
        assert s.scale_font_size(10) == 20

    def test_small_screen_reduces_size(self):
        standard = _scaler(scale_factor=1.0, category=UIScaler.STANDARD)
        small = _scaler(scale_factor=1.0, category=UIScaler.SMALL)
        assert small.scale_font_size(12) < standard.scale_font_size(12)

    def test_ultrawide_increases_size(self):
        standard = _scaler(scale_factor=1.0, category=UIScaler.STANDARD)
        ultrawide = _scaler(scale_factor=1.0, category=UIScaler.ULTRAWIDE)
        assert ultrawide.scale_font_size(12) > standard.scale_font_size(12)

    def test_minimum_font_size_8(self):
        # Very small scale should still return at least 8
        s = _scaler(scale_factor=0.1, category=UIScaler.SMALL)
        assert s.scale_font_size(12) >= 8

    def test_returns_int(self):
        s = _scaler(scale_factor=1.5, category=UIScaler.STANDARD)
        assert isinstance(s.scale_font_size(10), int)


# ===========================================================================
# get_window_size
# ===========================================================================

class TestGetWindowSize:
    def test_no_dimensions_returns_fallback(self):
        s = _scaler()
        w, h = s.get_window_size()
        assert w == 1400
        assert h == 900

    def test_standard_screen_defaults(self):
        s = _scaler(width=1920, height=1080, category=UIScaler.STANDARD)
        w, h = s.get_window_size(width_percent=0.8, height_percent=0.85)
        assert w == int(1920 * 0.8)
        assert h == int(1080 * 0.85)

    def test_max_width_constraint(self):
        s = _scaler(width=1920, height=1080, category=UIScaler.STANDARD)
        w, h = s.get_window_size(max_width=1200)
        assert w <= 1200

    def test_max_height_constraint(self):
        s = _scaler(width=1920, height=1080, category=UIScaler.STANDARD)
        w, h = s.get_window_size(max_height=700)
        assert h <= 700

    def test_ultrawide_limits_width_percent(self):
        s = _scaler(width=3440, height=1440, category=UIScaler.ULTRAWIDE)
        w, h = s.get_window_size(width_percent=0.8)
        # ultrawide limits to 0.6
        assert w <= int(3440 * 0.6) + 1  # +1 for int truncation

    def test_returns_tuple_of_ints(self):
        s = _scaler(width=1920, height=1080, category=UIScaler.STANDARD)
        result = s.get_window_size()
        assert isinstance(result, tuple)
        assert isinstance(result[0], int)
        assert isinstance(result[1], int)


# ===========================================================================
# get_minimum_window_size
# ===========================================================================

class TestGetMinimumWindowSize:
    def test_no_dimensions_returns_fallback(self):
        s = _scaler()
        w, h = s.get_minimum_window_size()
        assert w == 1000
        assert h == 700

    def test_minimum_width_at_least_800(self):
        s = _scaler(width=1920, height=1080, category=UIScaler.STANDARD)
        w, h = s.get_minimum_window_size()
        assert w >= 800

    def test_minimum_height_at_least_600(self):
        s = _scaler(width=1920, height=1080, category=UIScaler.STANDARD)
        w, h = s.get_minimum_window_size()
        assert h >= 600

    def test_returns_tuple(self):
        s = _scaler(width=1920, height=1080, category=UIScaler.STANDARD)
        assert isinstance(s.get_minimum_window_size(), tuple)


# ===========================================================================
# get_dialog_size
# ===========================================================================

class TestGetDialogSize:
    def test_returns_tuple(self):
        s = _scaler(scale_factor=1.0, width=1920, height=1080, category=UIScaler.STANDARD)
        assert isinstance(s.get_dialog_size(800, 600), tuple)

    def test_scale_1x_no_constraints(self):
        s = _scaler(scale_factor=1.0, width=1920, height=1080, category=UIScaler.STANDARD)
        w, h = s.get_dialog_size(800, 600)
        assert w == 800
        assert h == 600

    def test_min_width_applied(self):
        s = _scaler(scale_factor=1.0, width=1920, height=1080)
        w, h = s.get_dialog_size(100, 100, min_width=400)
        assert w >= 400

    def test_min_height_applied(self):
        s = _scaler(scale_factor=1.0, width=1920, height=1080)
        w, h = s.get_dialog_size(100, 100, min_height=300)
        assert h >= 300

    def test_screen_percent_constraints_applied(self):
        s = _scaler(scale_factor=1.0, width=1000, height=800)
        w, h = s.get_dialog_size(2000, 2000, max_width_percent=0.9, max_height_percent=0.9)
        assert w <= 900
        assert h <= 720


# ===========================================================================
# get_button_width
# ===========================================================================

class TestGetButtonWidth:
    def test_returns_int(self):
        s = _scaler(scale_factor=1.0, category=UIScaler.STANDARD)
        assert isinstance(s.get_button_width(), int)

    def test_small_screen_reduces_width(self):
        standard = _scaler(scale_factor=1.0, category=UIScaler.STANDARD)
        small = _scaler(scale_factor=1.0, category=UIScaler.SMALL)
        assert small.get_button_width() < standard.get_button_width()

    def test_ultrawide_increases_width(self):
        standard = _scaler(scale_factor=1.0, category=UIScaler.STANDARD)
        ultrawide = _scaler(scale_factor=1.0, category=UIScaler.ULTRAWIDE)
        assert ultrawide.get_button_width() > standard.get_button_width()


# ===========================================================================
# get_padding
# ===========================================================================

class TestGetPadding:
    def test_returns_int(self):
        s = _scaler(scale_factor=1.0, category=UIScaler.STANDARD)
        assert isinstance(s.get_padding(), int)

    def test_small_screen_reduces_padding(self):
        standard = _scaler(scale_factor=1.0, category=UIScaler.STANDARD)
        small = _scaler(scale_factor=1.0, category=UIScaler.SMALL)
        assert small.get_padding() < standard.get_padding()

    def test_ultrawide_increases_padding(self):
        standard = _scaler(scale_factor=1.0, category=UIScaler.STANDARD)
        ultrawide = _scaler(scale_factor=1.0, category=UIScaler.ULTRAWIDE)
        assert ultrawide.get_padding() > standard.get_padding()


# ===========================================================================
# get_column_weights
# ===========================================================================

class TestGetColumnWeights:
    def test_returns_tuple(self):
        s = _scaler(category=UIScaler.STANDARD)
        assert isinstance(s.get_column_weights(), tuple)

    def test_standard_weights(self):
        s = _scaler(category=UIScaler.STANDARD)
        assert s.get_column_weights() == (1, 2)

    def test_ultrawide_weights(self):
        s = _scaler(category=UIScaler.ULTRAWIDE)
        assert s.get_column_weights() == (1, 3)

    def test_high_dpi_weights(self):
        s = _scaler(category=UIScaler.HIGH_DPI)
        # Not ultrawide → standard weights
        assert s.get_column_weights() == (1, 2)

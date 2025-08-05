"""
DPI-aware scaling utilities for responsive UI design.
Handles different screen resolutions and DPI settings.
"""

import tkinter as tk
import platform
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class UIScaler:
    """Handles DPI-aware scaling and responsive sizing for the UI."""
    
    # Base DPI for scaling calculations (standard DPI)
    BASE_DPI = 96
    
    # Screen size categories
    ULTRAWIDE = "ultrawide"
    HIGH_DPI = "high_dpi"
    STANDARD = "standard"
    SMALL = "small"
    
    def __init__(self):
        """Initialize the UI scaler."""
        self._scale_factor = None
        self._screen_category = None
        self._screen_width = None
        self._screen_height = None
        self._dpi = None
        
    def initialize(self, root: tk.Tk):
        """
        Initialize scaling based on the root window.
        
        Args:
            root: The root tkinter window
        """
        try:
            # Get screen dimensions
            self._screen_width = root.winfo_screenwidth()
            self._screen_height = root.winfo_screenheight()
            
            # Get DPI
            self._dpi = self._get_dpi(root)
            
            # Calculate scale factor
            self._scale_factor = self._dpi / self.BASE_DPI
            
            # Determine screen category
            self._screen_category = self._determine_screen_category()
            
            logger.info(f"UI Scaler initialized: Screen {self._screen_width}x{self._screen_height}, "
                       f"DPI: {self._dpi}, Scale factor: {self._scale_factor:.2f}, "
                       f"Category: {self._screen_category}")
                       
        except Exception as e:
            logger.error(f"Error initializing UI scaler: {e}")
            # Fallback to no scaling
            self._scale_factor = 1.0
            self._screen_category = self.STANDARD
    
    def _get_dpi(self, root: tk.Tk) -> float:
        """
        Get the DPI of the current display.
        
        Args:
            root: The root tkinter window
            
        Returns:
            The DPI value
        """
        try:
            if platform.system() == "Windows":
                # Windows DPI awareness
                root.tk.call('tk', 'scaling')
                dpi = root.winfo_fpixels('1i')
            else:
                # Linux/Mac
                dpi = root.winfo_fpixels('1i')
                
            # Sanity check
            if dpi < 50 or dpi > 300:
                logger.warning(f"Unusual DPI detected: {dpi}, using default")
                dpi = self.BASE_DPI
                
            return float(dpi)
        except Exception as e:
            logger.error(f"Error getting DPI: {e}")
            return float(self.BASE_DPI)
    
    def _determine_screen_category(self) -> str:
        """
        Determine the screen category based on resolution and aspect ratio.
        
        Returns:
            Screen category string
        """
        if not self._screen_width or not self._screen_height:
            return self.STANDARD
            
        aspect_ratio = self._screen_width / self._screen_height
        total_pixels = self._screen_width * self._screen_height
        
        # Ultrawide detection (aspect ratio > 2.1)
        if aspect_ratio > 2.1:
            return self.ULTRAWIDE
        
        # High DPI detection (high resolution with normal aspect ratio)
        elif self._dpi > 120 or total_pixels > 3_000_000:
            return self.HIGH_DPI
        
        # Small screen detection
        elif self._screen_width < 1400 or self._screen_height < 900:
            return self.SMALL
        
        # Standard screen
        else:
            return self.STANDARD
    
    def scale_dimension(self, dimension: int) -> int:
        """
        Scale a dimension based on DPI.
        
        Args:
            dimension: The dimension to scale
            
        Returns:
            Scaled dimension
        """
        if self._scale_factor is None:
            return dimension
        return int(dimension * self._scale_factor)
    
    def scale_font_size(self, base_size: int) -> int:
        """
        Scale a font size based on DPI and screen category.
        
        Args:
            base_size: The base font size
            
        Returns:
            Scaled font size
        """
        if self._scale_factor is None:
            return base_size
            
        # Apply DPI scaling
        scaled_size = int(base_size * self._scale_factor)
        
        # Additional adjustments based on screen category
        if self._screen_category == self.SMALL:
            scaled_size = int(scaled_size * 0.9)  # Slightly smaller for small screens
        elif self._screen_category == self.ULTRAWIDE:
            scaled_size = int(scaled_size * 1.1)  # Slightly larger for ultrawide
            
        # Ensure minimum readable size
        return max(scaled_size, 8)
    
    def get_window_size(self, width_percent: float = 0.8, 
                       height_percent: float = 0.85,
                       max_width: Optional[int] = None,
                       max_height: Optional[int] = None) -> Tuple[int, int]:
        """
        Calculate appropriate window size based on screen dimensions.
        
        Args:
            width_percent: Percentage of screen width to use
            height_percent: Percentage of screen height to use
            max_width: Maximum width constraint
            max_height: Maximum height constraint
            
        Returns:
            Tuple of (width, height)
        """
        if not self._screen_width or not self._screen_height:
            # Fallback dimensions
            return (1400, 900)
        
        # Adjust percentages based on screen category
        if self._screen_category == self.ULTRAWIDE:
            width_percent = min(width_percent, 0.6)  # Don't use full width on ultrawide
        elif self._screen_category == self.SMALL:
            width_percent = min(width_percent, 0.95)  # Use more space on small screens
            height_percent = min(height_percent, 0.95)
        
        # Calculate dimensions
        width = int(self._screen_width * width_percent)
        height = int(self._screen_height * height_percent)
        
        # Apply maximum constraints if provided
        if max_width:
            width = min(width, max_width)
        if max_height:
            height = min(height, max_height)
        
        return (width, height)
    
    def get_minimum_window_size(self) -> Tuple[int, int]:
        """
        Calculate minimum window size based on screen dimensions.
        
        Returns:
            Tuple of (min_width, min_height)
        """
        if not self._screen_width or not self._screen_height:
            # Fallback dimensions
            return (1000, 700)
        
        # Base minimum percentages
        min_width_percent = 0.5
        min_height_percent = 0.6
        
        # Adjust based on screen category
        if self._screen_category == self.SMALL:
            # Allow smaller minimum for small screens
            min_width_percent = 0.7
            min_height_percent = 0.7
        elif self._screen_category == self.ULTRAWIDE:
            # Smaller width percentage for ultrawide
            min_width_percent = 0.3
        
        min_width = int(self._screen_width * min_width_percent)
        min_height = int(self._screen_height * min_height_percent)
        
        # Ensure absolute minimums for usability
        min_width = max(min_width, 800)
        min_height = max(min_height, 600)
        
        return (min_width, min_height)
    
    def get_dialog_size(self, base_width: int, base_height: int,
                       min_width: Optional[int] = None,
                       min_height: Optional[int] = None,
                       max_width_percent: float = 0.9,
                       max_height_percent: float = 0.9) -> Tuple[int, int]:
        """
        Calculate appropriate dialog size with constraints.
        
        Args:
            base_width: Base width for the dialog
            base_height: Base height for the dialog
            min_width: Minimum width constraint
            min_height: Minimum height constraint
            max_width_percent: Maximum percentage of screen width
            max_height_percent: Maximum percentage of screen height
            
        Returns:
            Tuple of (width, height)
        """
        # Scale base dimensions
        width = self.scale_dimension(base_width)
        height = self.scale_dimension(base_height)
        
        # Apply screen percentage constraints
        if self._screen_width and self._screen_height:
            max_width = int(self._screen_width * max_width_percent)
            max_height = int(self._screen_height * max_height_percent)
            
            width = min(width, max_width)
            height = min(height, max_height)
        
        # Apply minimum constraints
        if min_width:
            width = max(width, self.scale_dimension(min_width))
        if min_height:
            height = max(height, self.scale_dimension(min_height))
        
        return (width, height)
    
    def get_button_width(self, base_width: int = 20) -> int:
        """
        Calculate appropriate button width based on screen size.
        
        Args:
            base_width: Base button width
            
        Returns:
            Scaled button width
        """
        # Scale based on DPI
        width = self.scale_dimension(base_width)
        
        # Adjust based on screen category
        if self._screen_category == self.SMALL:
            width = int(width * 0.8)
        elif self._screen_category == self.ULTRAWIDE:
            width = int(width * 1.2)
        
        return width
    
    def get_padding(self, base_padding: int = 10) -> int:
        """
        Calculate appropriate padding based on screen size.
        
        Args:
            base_padding: Base padding value
            
        Returns:
            Scaled padding
        """
        # Scale based on DPI
        padding = self.scale_dimension(base_padding)
        
        # Adjust based on screen category
        if self._screen_category == self.SMALL:
            padding = int(padding * 0.7)
        elif self._screen_category == self.ULTRAWIDE:
            padding = int(padding * 1.2)
        
        return padding
    
    def get_column_weights(self) -> Tuple[int, int]:
        """
        Get column weights for the main UI based on screen type.
        
        Returns:
            Tuple of (left_weight, right_weight)
        """
        if self._screen_category == self.ULTRAWIDE:
            # More space for right column on ultrawide
            return (1, 3)
        else:
            # Standard distribution
            return (1, 2)
    
    @property
    def scale_factor(self) -> float:
        """Get the current scale factor."""
        return self._scale_factor or 1.0
    
    @property
    def screen_category(self) -> str:
        """Get the screen category."""
        return self._screen_category or self.STANDARD
    
    @property
    def screen_width(self) -> Optional[int]:
        """Get the screen width."""
        return self._screen_width
    
    @property
    def screen_height(self) -> Optional[int]:
        """Get the screen height."""
        return self._screen_height


# Global scaler instance
ui_scaler = UIScaler()
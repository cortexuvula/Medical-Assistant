#!/usr/bin/env python3
"""
Medical Assistant Application Entry Point

This file serves as the main entry point for the Medical Assistant application.
It sets up the Python path and imports the actual main function from the core module.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

# Import and run the main function
from core.main import main

if __name__ == "__main__":
    main()
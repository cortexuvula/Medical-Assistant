#!/usr/bin/env python3
"""
Run tkinter/ttkbootstrap UI tests for Medical Assistant.

This script provides convenient ways to run the UI tests with proper
environment setup, including headless mode support on Linux.
"""
import sys
import os
import subprocess
import platform
import argparse
from pathlib import Path


def check_dependencies():
    """Check if required dependencies are installed."""
    missing = []
    
    try:
        import tkinter
    except ImportError:
        missing.append("tkinter")
    
    try:
        import ttkbootstrap
    except ImportError:
        missing.append("ttkbootstrap")
    
    try:
        import pytest
    except ImportError:
        missing.append("pytest")
    
    if missing:
        print(f"ERROR: Missing dependencies: {', '.join(missing)}")
        print("\nPlease install with:")
        print(f"  pip install {' '.join(missing)}")
        return False
    
    return True


def setup_display_linux():
    """Set up virtual display for headless Linux testing."""
    if not platform.system() == "Linux":
        return True
    
    # Check if display is already set
    if os.environ.get('DISPLAY'):
        return True
    
    # Try to use Xvfb
    try:
        # Check if Xvfb is installed
        result = subprocess.run(['which', 'xvfb-run'], capture_output=True)
        if result.returncode != 0:
            print("WARNING: Xvfb not found. UI tests may fail in headless mode.")
            print("Install with: sudo apt-get install xvfb")
            return False
        
        return True
    except Exception:
        return False


def run_tests(args):
    """Run the tkinter UI tests."""
    # Build pytest command
    cmd = [sys.executable, "-m", "pytest"]
    
    # Add test paths
    test_dir = Path(__file__).parent / "unit"
    tkinter_tests = [
        test_dir / "test_tkinter_ui_basic.py",
        test_dir / "test_tkinter_ui_medical_assistant.py",
        test_dir / "test_tkinter_workflow_tabs.py",
        test_dir / "test_tkinter_chat_and_editors.py"
    ]
    
    # Add only existing test files
    for test_file in tkinter_tests:
        if test_file.exists():
            cmd.append(str(test_file))
    
    # Add verbosity
    if args.verbose:
        cmd.append("-vv")
    else:
        cmd.append("-v")
    
    # Add coverage if requested
    if args.coverage:
        cmd.extend(["--cov=.", "--cov-report=term-missing"])
    
    # Add any additional pytest args
    if args.pytest_args:
        cmd.extend(args.pytest_args)
    
    # Run tests
    if args.headless and platform.system() == "Linux":
        # Use xvfb-run for headless mode
        final_cmd = ["xvfb-run", "-a"] + cmd
    else:
        final_cmd = cmd
    
    print("Running tkinter UI tests...")
    print(f"Command: {' '.join(final_cmd)}")
    print("-" * 60)
    
    return subprocess.call(final_cmd)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Medical Assistant tkinter UI tests"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose test output"
    )
    
    parser.add_argument(
        "-c", "--coverage",
        action="store_true",
        help="Run with coverage reporting"
    )
    
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode (Linux only)"
    )
    
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="Additional arguments to pass to pytest"
    )
    
    args = parser.parse_args()
    
    # Print environment info
    print("Medical Assistant Tkinter UI Test Runner")
    print("=" * 60)
    print(f"Platform: {platform.system()}")
    print(f"Python: {sys.version.split()[0]}")
    
    # Check dependencies
    if not check_dependencies():
        return 1
    
    # Setup display for Linux
    if args.headless and platform.system() == "Linux":
        if not setup_display_linux():
            print("\nWARNING: Headless mode setup failed")
            print("Tests may fail without a display")
    
    # Check if test files exist
    test_dir = Path(__file__).parent / "unit"
    tkinter_test_files = list(test_dir.glob("test_tkinter_*.py"))
    
    if not tkinter_test_files:
        print(f"\nERROR: No tkinter UI test files found in {test_dir}")
        return 1
    
    print(f"\nFound {len(tkinter_test_files)} tkinter test files")
    print()
    
    # Run tests
    return run_tests(args)


if __name__ == "__main__":
    sys.exit(main())
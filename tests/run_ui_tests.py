#!/usr/bin/env python
"""
UI Test Runner for Medical Assistant

This script helps run UI tests with proper display configuration.
UI tests require a display (real or virtual) to run properly.
"""
import sys
import os
import subprocess
import platform


def check_display():
    """Check if a display is available."""
    if platform.system() == "Linux":
        display = os.environ.get('DISPLAY')
        if not display:
            print("No display found. Setting up virtual display...")
            return False
    return True


def setup_virtual_display():
    """Set up Xvfb virtual display for headless testing."""
    if platform.system() != "Linux":
        return True
    
    try:
        # Check if Xvfb is installed
        subprocess.run(['which', 'Xvfb'], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("Xvfb not installed. Install with: sudo apt-get install xvfb")
        return False
    
    # Start Xvfb
    os.environ['DISPLAY'] = ':99'
    xvfb_process = subprocess.Popen([
        'Xvfb', ':99', '-screen', '0', '1024x768x24', '-ac'
    ])
    
    import time
    time.sleep(2)  # Give Xvfb time to start
    
    return xvfb_process


def run_ui_tests():
    """Run the UI tests."""
    # Check for PyQt5
    try:
        import PyQt5
    except ImportError:
        print("PyQt5 not installed. Install with: pip install PyQt5")
        return 1
    
    # Check for pytest-qt
    try:
        import pytest_qt
    except ImportError:
        print("pytest-qt not installed. Install with: pip install pytest-qt")
        return 1
    
    # Set up display if needed
    xvfb_process = None
    if not check_display():
        xvfb_process = setup_virtual_display()
        if not xvfb_process:
            return 1
    
    # Run tests
    test_args = [
        'python', '-m', 'pytest',
        'tests/unit/test_ui_basic.py',
        'tests/unit/test_ui_medical_assistant.py',
        '-v',
        '-m', 'ui',  # Run only UI tests
        '--tb=short'
    ]
    
    # Add any additional arguments passed to the script
    test_args.extend(sys.argv[1:])
    
    try:
        result = subprocess.run(test_args)
        return result.returncode
    finally:
        # Clean up Xvfb if we started it
        if xvfb_process:
            xvfb_process.terminate()
            xvfb_process.wait()


def main():
    """Main entry point."""
    print("Medical Assistant UI Test Runner")
    print("-" * 40)
    
    # Platform-specific instructions
    if platform.system() == "Windows":
        print("Running on Windows - display should work normally")
    elif platform.system() == "Darwin":  # macOS
        print("Running on macOS - display should work normally")
    elif platform.system() == "Linux":
        print("Running on Linux - may use virtual display if needed")
    
    print()
    
    # Run tests
    exit_code = run_ui_tests()
    
    if exit_code == 0:
        print("\nAll UI tests passed!")
    else:
        print(f"\nUI tests failed with exit code: {exit_code}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
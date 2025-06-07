#!/usr/bin/env python3
"""
Run all STT provider tests.

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py test_base.py       # Run specific test file
    python run_tests.py -v                 # Run with verbose output
    python run_tests.py -k "test_transcribe"  # Run tests matching pattern
"""

import sys
import os
import pytest

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
sys.path.insert(0, project_root)

def main():
    """Run STT provider tests."""
    # Default arguments
    args = [
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
        "--color=yes",  # Colored output
    ]
    
    # Add coverage if pytest-cov is available
    try:
        import pytest_cov
        args.extend([
            "--cov=stt_providers",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
        ])
    except ImportError:
        print("Note: Install pytest-cov for coverage reports")
    
    # Add any command line arguments
    if len(sys.argv) > 1:
        args.extend(sys.argv[1:])
    else:
        # If no arguments, run all tests in this directory
        args.append(os.path.dirname(__file__))
    
    # Run tests
    exit_code = pytest.main(args)
    
    # Print summary
    if exit_code == 0:
        print("\n✅ All STT provider tests passed!")
    else:
        print(f"\n❌ Tests failed with exit code: {exit_code}")
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main())
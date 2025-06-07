#!/usr/bin/env python
"""Run tkinter/ttkbootstrap UI tests separately to avoid import conflicts."""
import sys
import subprocess
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Run Medical Assistant tkinter UI tests"
    )
    
    parser.add_argument(
        '-v', '--verbose', 
        action='count', 
        default=1,
        help='Increase verbosity'
    )
    
    parser.add_argument(
        '--cov',
        action='store_true',
        help='Run with coverage'
    )
    
    parser.add_argument(
        'test',
        nargs='?',
        help='Specific test file or test to run'
    )
    
    args = parser.parse_args()
    
    # Base test files
    tkinter_tests = [
        'tests/unit/test_tkinter_ui_basic.py',
        'tests/unit/test_tkinter_ui_medical_assistant.py',
        'tests/unit/test_tkinter_workflow_tabs.py',
        'tests/unit/test_tkinter_chat_and_editors.py'
    ]
    
    # Build command
    cmd = [sys.executable, '-m', 'pytest']
    
    # Add specific test or all tkinter tests
    if args.test:
        cmd.append(args.test)
    else:
        cmd.extend(tkinter_tests)
    
    # Add verbosity
    if args.verbose:
        cmd.append('-' + 'v' * args.verbose)
    
    # Add coverage
    if args.cov:
        cmd.extend(['--cov=.', '--cov-report=term-missing'])
    
    # Add other options
    cmd.extend(['--tb=short', '-p', 'no:warnings'])
    
    print(f"Running tkinter UI tests...")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 60)
    
    # Run tests
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("\n✅ All tkinter UI tests passed!")
    else:
        print(f"\n❌ Some tests failed (exit code: {result.returncode})")
    
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
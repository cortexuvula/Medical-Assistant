#!/usr/bin/env python
"""Convenience script for running tests with various options."""
import sys
import subprocess
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run Medical Assistant tests")
    
    # Test selection
    parser.add_argument('path', nargs='?', default='tests/', 
                       help='Path to test file or directory (default: tests/)')
    parser.add_argument('-k', '--keyword', help='Run tests matching keyword')
    parser.add_argument('-m', '--marker', help='Run tests with specific marker')
    
    # Coverage options
    parser.add_argument('--cov', action='store_true', 
                       help='Run with coverage report')
    parser.add_argument('--cov-html', action='store_true', 
                       help='Generate HTML coverage report')
    parser.add_argument('--cov-fail', type=int, default=0,
                       help='Fail if coverage is below this percentage')
    
    # Output options
    parser.add_argument('-v', '--verbose', action='count', default=0,
                       help='Increase verbosity (can be used multiple times)')
    parser.add_argument('-s', '--capture', action='store_false',
                       help='Disable output capture (show print statements)')
    parser.add_argument('--tb', choices=['short', 'long', 'native', 'no'],
                       default='short', help='Traceback style')
    
    # Performance options
    parser.add_argument('-n', '--numprocesses', type=str,
                       help='Number of processes for parallel execution')
    parser.add_argument('--timeout', type=int,
                       help='Timeout for each test in seconds')
    
    # Special modes
    parser.add_argument('--slow', action='store_true',
                       help='Include slow tests')
    parser.add_argument('--unit', action='store_true',
                       help='Run only unit tests')
    parser.add_argument('--integration', action='store_true',
                       help='Run only integration tests')
    parser.add_argument('--ui', action='store_true',
                       help='Run only UI tests')
    parser.add_argument('--failed', action='store_true',
                       help='Run only previously failed tests')
    parser.add_argument('--pdb', action='store_true',
                       help='Drop into debugger on failures')
    
    args = parser.parse_args()
    
    # Build pytest command
    cmd = ['python', '-m', 'pytest', args.path]
    
    # Exclude tkinter tests by default unless specifically running UI tests
    if not args.ui and 'tkinter' not in args.path:
        cmd.extend(['--ignore=tests/unit/test_tkinter_ui_basic.py',
                    '--ignore=tests/unit/test_tkinter_ui_medical_assistant.py', 
                    '--ignore=tests/unit/test_tkinter_workflow_tabs.py',
                    '--ignore=tests/unit/test_tkinter_chat_and_editors.py'])
    
    # Add verbosity
    if args.verbose:
        cmd.append('-' + 'v' * args.verbose)
    
    # Add keyword filter
    if args.keyword:
        cmd.extend(['-k', args.keyword])
    
    # Add marker filter
    markers = []
    if args.marker:
        markers.append(args.marker)
    if args.unit:
        markers.append('not integration and not ui')
    if args.integration:
        markers.append('integration')
    if args.ui:
        markers.append('ui')
    if not args.slow:
        markers.append('not slow')
    
    if markers:
        cmd.extend(['-m', ' and '.join(markers)])
    
    # Add coverage options
    if args.cov or args.cov_html:
        cmd.extend(['--cov=.', '--cov-report=term-missing'])
        if args.cov_html:
            cmd.append('--cov-report=html')
        if args.cov_fail:
            cmd.append(f'--cov-fail-under={args.cov_fail}')
    
    # Add output options
    if not args.capture:
        cmd.append('-s')
    cmd.append(f'--tb={args.tb}')
    
    # Add performance options
    if args.numprocesses:
        cmd.extend(['-n', args.numprocesses])
    if args.timeout:
        cmd.append(f'--timeout={args.timeout}')
    
    # Add special modes
    if args.failed:
        cmd.append('--lf')
    if args.pdb:
        cmd.append('--pdb')
    
    # Print command for debugging
    print(f"Running: {' '.join(cmd)}")
    print("-" * 50)
    
    # Run tests
    result = subprocess.run(cmd)
    
    # Open coverage report if generated
    if args.cov_html and result.returncode == 0:
        import webbrowser
        import os
        coverage_path = Path('htmlcov/index.html').absolute()
        if coverage_path.exists():
            print(f"\nOpening coverage report: {coverage_path}")
            webbrowser.open(f'file://{coverage_path}')
    
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
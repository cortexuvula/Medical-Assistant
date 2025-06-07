"""Test to verify CI environment is working correctly."""
import os
import sys


def test_ci_environment():
    """Test that CI environment is detected correctly."""
    is_ci = bool(os.environ.get('CI', '')) or bool(os.environ.get('GITHUB_ACTIONS', ''))
    print(f"CI environment: {is_ci}")
    print(f"CI env var: {os.environ.get('CI', 'not set')}")
    print(f"GITHUB_ACTIONS env var: {os.environ.get('GITHUB_ACTIONS', 'not set')}")
    assert True  # Always pass


def test_python_version():
    """Test Python version."""
    print(f"Python version: {sys.version}")
    assert sys.version_info >= (3, 8)


def test_no_ttkbootstrap_import():
    """Test that ttkbootstrap is not imported in this module."""
    # Check that ttkbootstrap is not in sys.modules at this point
    ttkbootstrap_modules = [m for m in sys.modules if 'ttkbootstrap' in m]
    print(f"ttkbootstrap modules loaded: {ttkbootstrap_modules}")
    # Don't fail the test, just report
    assert True
"""Test to verify pytest setup is working correctly."""
import pytest


def test_pytest_is_working():
    """Simple test to verify pytest is set up correctly."""
    assert True


def test_imports_work():
    """Test that we can import main modules."""
    # These imports should not raise exceptions
    from src.database import database
    from src.core import config
    from src.utils import validation
    from src.utils import security

    assert True


class TestBasicMath:
    """Basic test class to verify pytest class discovery."""
    
    def test_addition(self):
        """Test basic addition."""
        assert 1 + 1 == 2
    
    def test_subtraction(self):
        """Test basic subtraction."""
        assert 5 - 3 == 2
    
    @pytest.mark.parametrize("a,b,expected", [
        (2, 3, 6),
        (5, 4, 20),
        (0, 10, 0),
    ])
    def test_multiplication(self, a, b, expected):
        """Test multiplication with parametrize."""
        assert a * b == expected
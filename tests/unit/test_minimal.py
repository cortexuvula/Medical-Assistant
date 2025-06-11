#!/usr/bin/env python3
"""
Minimal test to verify basic service layer functionality without UI dependencies
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing Medical Assistant Service Layer (Minimal)")
print("=" * 50)

# Test 1: Check if service modules exist
print("\n1. Checking service modules...")
modules_to_check = [
    ("infrastructure", "Infrastructure"),
    ("services", "Services"),
    ("repositories", "Repositories"),
    ("models", "Models")
]

all_exist = True
for module_name, description in modules_to_check:
    module_path = os.path.join(os.path.dirname(__file__), module_name)
    if os.path.exists(module_path):
        print(f"   ✓ {description} module exists")
    else:
        print(f"   ✗ {description} module missing")
        all_exist = False

if not all_exist:
    print("\nError: Not all required modules are present.")
    sys.exit(1)

# Test 2: Try importing base modules (no external dependencies)
print("\n2. Testing basic imports...")
try:
    from services.base_service import BaseService, ServiceResult
    print("   ✓ Base service imports work")
except ImportError as e:
    print(f"   ✗ Failed to import base service: {e}")
    sys.exit(1)

try:
    from repositories.base_repository import BaseRepository
    print("   ✓ Base repository imports work")
except ImportError as e:
    print(f"   ✗ Failed to import base repository: {e}")
    sys.exit(1)

try:
    from models.recording import Recording
    print("   ✓ Model imports work")
except ImportError as e:
    print(f"   ✗ Failed to import models: {e}")
    sys.exit(1)

try:
    from infrastructure.di.container import DIContainer
    print("   ✓ DI container imports work")
except ImportError as e:
    print(f"   ✗ Failed to import DI container: {e}")
    sys.exit(1)

# Test 3: Test ServiceResult functionality
print("\n3. Testing ServiceResult...")
success_result = ServiceResult.ok("test data")
fail_result = ServiceResult.fail("test error", "TEST_ERROR")

assert success_result.success == True
assert success_result.data == "test data"
assert fail_result.success == False
assert fail_result.error == "test error"
assert fail_result.error_code == "TEST_ERROR"
print("   ✓ ServiceResult works correctly")

# Test 4: Test Recording model
print("\n4. Testing Recording model...")
recording = Recording(
    filename="test.wav",
    transcript="Test transcript"
)
assert recording.filename == "test.wav"
assert recording.transcript == "Test transcript"
assert recording.timestamp is not None
print("   ✓ Recording model works correctly")

# Test 5: Test DI Container
print("\n5. Testing DI Container...")
container = DIContainer()

# Register a simple service
class TestService:
    def __init__(self):
        self.name = "TestService"

container.register_singleton(TestService, TestService)
service = container.resolve(TestService)
assert service.name == "TestService"
print("   ✓ DI Container works correctly")

print("\n" + "=" * 50)
print("✅ All basic tests passed!")
print("\nThe service layer infrastructure is correctly installed.")
print("\nTo use the full application, you need to install dependencies:")
print("  1. Install pip: sudo apt install python3-pip")
print("  2. Run: ./install_dependencies.sh")
print("  3. Then run: python3 main_v2.py")
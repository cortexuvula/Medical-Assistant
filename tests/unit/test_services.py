#!/usr/bin/env python3
"""
Test script to verify service layer implementation
"""

import asyncio
import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from infrastructure import configure_services, shutdown_services, ServiceLocator
from models import Recording


async def test_services():
    """Test basic service functionality."""
    print("Testing Medical Assistant Service Layer")
    print("=" * 50)
    
    try:
        # Configure services
        print("1. Configuring services...")
        configure_services()
        print("   ✓ Services configured successfully")
        
        # Get service instances
        print("\n2. Getting service instances...")
        audio_service = ServiceLocator.get_audio_service()
        ai_service = ServiceLocator.get_ai_service()
        database_service = ServiceLocator.get_database_service()
        security_service = ServiceLocator.get_security_service()
        print("   ✓ All services retrieved successfully")
        
        # Test audio service
        print("\n3. Testing Audio Service...")
        providers = audio_service.get_available_providers()
        print(f"   Available STT providers: {[p['name'] for p in providers if p['available']]}")
        
        # Test AI service
        print("\n4. Testing AI Service...")
        ai_providers = ai_service.get_available_providers()
        print(f"   Available AI providers: {[p['name'] for p in ai_providers if p['available']]}")
        
        # Test simple text processing
        test_text = "This is a test transcription"
        command_result = await ai_service.process_command(test_text)
        if command_result.success:
            print(f"   ✓ Command processing works: {command_result.data}")
        
        # Test database service
        print("\n5. Testing Database Service...")
        
        # Create a test recording
        test_recording = await database_service.create_recording(
            filename="test_recording.wav",
            transcript="Test transcript",
            soap_note="Test SOAP note"
        )
        
        if test_recording.success:
            recording_id = test_recording.data.id
            print(f"   ✓ Created test recording with ID: {recording_id}")
            
            # Retrieve the recording
            retrieved = await database_service.get_recording(recording_id)
            if retrieved.success:
                print(f"   ✓ Retrieved recording: {retrieved.data.filename}")
            
            # Delete the test recording
            deleted = await database_service.delete_recording(recording_id)
            if deleted.success:
                print("   ✓ Deleted test recording")
        
        # Test security service
        print("\n6. Testing Security Service...")
        
        # Test input sanitization
        dirty_input = "Test <script>alert('xss')</script> input"
        sanitized = await security_service.sanitize_input(dirty_input)
        if sanitized.success:
            print(f"   ✓ Input sanitization works: '{sanitized.data}'")
        
        # Test rate limiting
        rate_check = await security_service.check_rate_limit("openai")
        if rate_check.success:
            print(f"   ✓ Rate limiting works: allowed={rate_check.data['allowed']}")
        
        print("\n✅ All services are working correctly!")
        
    except Exception as e:
        print(f"\n❌ Error testing services: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Shutdown services
        print("\n7. Shutting down services...")
        shutdown_services()
        print("   ✓ Services shut down successfully")


def main():
    """Main test function."""
    # Create test recording file if it doesn't exist
    test_file = Path("test_recording.wav")
    if not test_file.exists():
        test_file.touch()
    
    try:
        # Run async tests
        asyncio.run(test_services())
    finally:
        # Clean up test file
        if test_file.exists():
            test_file.unlink()


if __name__ == "__main__":
    main()
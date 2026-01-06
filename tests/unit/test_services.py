#!/usr/bin/env python3
"""
Tests for application services and managers.

These tests verify that the application's manager classes and service-like
components work correctly.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest


class TestAgentManager:
    """Test the AgentManager singleton."""

    def test_agent_manager_import(self):
        """Test AgentManager can be imported."""
        from managers.agent_manager import AgentManager
        assert AgentManager is not None

    def test_agent_manager_singleton(self):
        """Test AgentManager follows singleton pattern."""
        from managers.agent_manager import agent_manager
        assert agent_manager is not None


class TestAPIKeyManager:
    """Test the API Key Manager."""

    def test_api_key_manager_import(self):
        """Test APIKeyManager can be imported."""
        from managers.api_key_manager import APIKeyManager
        assert APIKeyManager is not None

    def test_api_key_manager_providers(self):
        """Test APIKeyManager knows about providers."""
        from managers.api_key_manager import APIKeyManager

        manager = APIKeyManager()
        # Should have provider keys configuration
        assert hasattr(manager, 'PROVIDER_KEYS')
        assert len(manager.PROVIDER_KEYS) > 0


class TestSettingsManager:
    """Test settings management."""

    def test_settings_load(self):
        """Test settings can be loaded."""
        from settings.settings import SETTINGS, load_settings

        settings = load_settings()
        assert settings is not None
        assert isinstance(settings, dict)

    def test_settings_has_required_keys(self):
        """Test settings contains required configuration keys."""
        from settings.settings import SETTINGS

        # Check for some expected keys
        expected_keys = ['theme', 'soap_note']
        for key in expected_keys:
            assert key in SETTINGS, f"Missing settings key: {key}"


@pytest.mark.requires_audio
class TestAudioStateManager:
    """Test the AudioStateManager."""

    @pytest.fixture(autouse=True)
    def check_dependencies(self):
        """Skip tests if audio dependencies are missing."""
        pytest.importorskip("pydub")
        pytest.importorskip("numpy")

    def test_audio_state_manager_creation(self):
        """Test AudioStateManager can be created."""
        from audio.audio_state_manager import AudioStateManager

        manager = AudioStateManager()
        assert manager is not None

    def test_audio_state_manager_initial_state(self):
        """Test AudioStateManager starts in IDLE state."""
        from audio.audio_state_manager import AudioStateManager, RecordingState

        manager = AudioStateManager()
        assert manager.get_state() == RecordingState.IDLE

    def test_audio_state_manager_state_transitions(self):
        """Test AudioStateManager handles state transitions."""
        from audio.audio_state_manager import AudioStateManager, RecordingState

        manager = AudioStateManager()

        # Start recording
        manager.start_recording()
        assert manager.get_state() == RecordingState.RECORDING

        # Pause
        manager.pause_recording()
        assert manager.get_state() == RecordingState.PAUSED

        # Resume
        manager.resume_recording()
        assert manager.get_state() == RecordingState.RECORDING

        # Stop
        manager.stop_recording()
        assert manager.get_state() == RecordingState.PROCESSING

    def test_audio_state_manager_invalid_transitions(self):
        """Test AudioStateManager rejects invalid state transitions."""
        from audio.audio_state_manager import AudioStateManager

        manager = AudioStateManager()

        # Can't pause when not recording
        with pytest.raises(RuntimeError):
            manager.pause_recording()

        # Can't resume when not paused
        with pytest.raises(RuntimeError):
            manager.resume_recording()

    def test_audio_state_manager_clear(self):
        """Test AudioStateManager can be cleared."""
        from audio.audio_state_manager import AudioStateManager, RecordingState

        manager = AudioStateManager()
        manager.start_recording()
        manager.clear_all()

        assert manager.get_state() == RecordingState.IDLE
        assert not manager.has_audio()


class TestDocumentGenerators:
    """Test document generator functions."""

    @pytest.mark.requires_audio
    def test_document_generators_import(self):
        """Test document generators can be imported."""
        pytest.importorskip("pydub")
        pytest.importorskip("numpy")
        from processing.document_generators import (
            create_soap_note,
            create_referral,
            create_letter,
        )
        assert callable(create_soap_note)
        assert callable(create_referral)
        assert callable(create_letter)


class TestAgentModels:
    """Test agent data models."""

    def test_agent_config_model(self):
        """Test AgentConfig model."""
        from ai.agents.models import AgentConfig

        config = AgentConfig(
            name="TestAgent",
            description="A test agent",
            system_prompt="You are a test agent.",
        )

        assert config.name == "TestAgent"
        assert config.description == "A test agent"

    def test_agent_task_model(self):
        """Test AgentTask model."""
        from ai.agents.models import AgentTask

        task = AgentTask(
            task_description="Generate synopsis",
            input_data={"text": "test input"},
        )

        assert task.task_description == "Generate synopsis"
        assert task.input_data["text"] == "test input"

    def test_agent_response_model(self):
        """Test AgentResponse model."""
        from ai.agents.models import AgentResponse

        response = AgentResponse(
            success=True,
            result="Test result",
        )

        assert response.success is True
        assert response.result == "Test result"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

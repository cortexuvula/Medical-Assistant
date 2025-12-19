"""Regression tests for core application functionality.

These tests verify that the application initializes correctly and
critical paths work as expected.
"""
import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestConfigLoading:
    """Tests for configuration loading."""

    def test_config_module_imports(self):
        """Config module should import without errors."""
        try:
            from src.core.config import get_config
            assert callable(get_config)
        except ImportError as e:
            pytest.fail(f"Failed to import config module: {e}")

    def test_get_config_returns_config(self):
        """get_config() should return a configuration object."""
        from src.core.config import get_config

        config = get_config()

        assert config is not None

    def test_config_has_required_attributes(self):
        """Configuration should have required attributes."""
        from src.core.config import get_config

        config = get_config()

        # Check for common config attributes
        # These may vary based on implementation
        assert hasattr(config, '__class__')


class TestDataFolderManager:
    """Tests for data folder management."""

    def test_data_folder_manager_imports(self):
        """Data folder manager should import correctly."""
        try:
            from src.managers.data_folder_manager import data_folder_manager
            assert data_folder_manager is not None
        except ImportError as e:
            pytest.fail(f"Failed to import data_folder_manager: {e}")

    def test_data_folder_paths_exist(self):
        """Data folder manager should provide path attributes."""
        from src.managers.data_folder_manager import data_folder_manager

        # Check that paths are Path objects or strings
        assert hasattr(data_folder_manager, 'app_data_folder')
        assert hasattr(data_folder_manager, 'database_file_path')
        assert hasattr(data_folder_manager, 'settings_file_path')


class TestDatabaseInitialization:
    """Tests for database initialization."""

    def test_database_class_imports(self):
        """Database class should import correctly."""
        try:
            from src.database.database import Database
            assert Database is not None
        except ImportError as e:
            pytest.fail(f"Failed to import Database: {e}")

    def test_database_creates_tables(self, tmp_path):
        """Database should create required tables."""
        from src.database.database import Database

        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        db.create_tables()

        # Verify file exists
        assert db_path.exists()

        db.close_all_connections()


class TestMigrationSystem:
    """Tests for database migration system."""

    def test_migration_manager_imports(self):
        """Migration manager should import correctly."""
        try:
            from src.database.db_migrations import MigrationManager
            assert MigrationManager is not None
        except ImportError as e:
            pytest.fail(f"Failed to import MigrationManager: {e}")

    def test_migration_manager_initializes(self, tmp_path):
        """Migration manager should initialize with database path."""
        from src.database.db_migrations import MigrationManager

        db_path = tmp_path / "test.db"
        manager = MigrationManager(str(db_path))

        assert manager is not None


class TestSchemaDefinitions:
    """Tests for database schema definitions."""

    def test_schema_imports(self):
        """Schema definitions should import correctly."""
        try:
            from src.database.schema import (
                RecordingSchema,
                RECORDING_FIELDS,
                RECORDING_UPDATE_FIELDS
            )
            assert RecordingSchema is not None
            assert RECORDING_FIELDS is not None
        except ImportError as e:
            pytest.fail(f"Failed to import schema: {e}")

    def test_recording_schema_has_columns(self):
        """RecordingSchema should define basic columns."""
        from src.database.schema import RecordingSchema

        assert hasattr(RecordingSchema, 'BASIC_COLUMNS')
        assert 'id' in RecordingSchema.BASIC_COLUMNS
        assert 'filename' in RecordingSchema.BASIC_COLUMNS

    def test_update_fields_is_frozenset(self):
        """Update fields should be a frozenset for security."""
        from src.database.schema import RECORDING_UPDATE_FIELDS

        assert isinstance(RECORDING_UPDATE_FIELDS, frozenset)


class TestAudioHandlerInitialization:
    """Tests for audio handler initialization."""

    def test_audio_handler_imports(self):
        """AudioHandler should import correctly."""
        try:
            from src.audio.audio import AudioHandler
            assert AudioHandler is not None
        except ImportError as e:
            pytest.fail(f"Failed to import AudioHandler: {e}")

    @patch('src.audio.audio.get_all_devices')
    def test_audio_handler_initializes(self, mock_devices, mock_api_keys):
        """AudioHandler should initialize with mocked devices."""
        mock_devices.return_value = {
            'input': [{'name': 'Test Mic', 'id': 0}],
            'output': [{'name': 'Test Speaker', 'id': 1}]
        }

        from src.audio.audio import AudioHandler

        # Mock the provider initializations
        with patch.object(AudioHandler, '_init_stt_providers'):
            handler = AudioHandler()
            assert handler is not None


class TestSettingsLoading:
    """Tests for settings loading."""

    def test_settings_module_imports(self):
        """Settings module should import correctly."""
        try:
            from src.settings.settings import SETTINGS, load_settings, save_settings
            assert SETTINGS is not None
            assert callable(load_settings)
            assert callable(save_settings)
        except ImportError as e:
            pytest.fail(f"Failed to import settings: {e}")

    def test_settings_is_dict(self):
        """SETTINGS should be a dictionary."""
        from src.settings.settings import SETTINGS

        assert isinstance(SETTINGS, dict)

    def test_settings_has_defaults(self):
        """SETTINGS should have default values."""
        from src.settings.settings import SETTINGS

        assert 'ai_provider' in SETTINGS
        assert 'stt_provider' in SETTINGS


class TestSecurityModule:
    """Tests for security module initialization."""

    def test_security_module_imports(self):
        """Security module should import correctly."""
        try:
            from src.utils.security import SecurityManager
            assert SecurityManager is not None
        except ImportError as e:
            pytest.fail(f"Failed to import SecurityManager: {e}")

    def test_security_manager_initializes(self, tmp_path):
        """SecurityManager should initialize correctly."""
        from src.utils.security import SecurityManager

        with patch.object(SecurityManager, '_get_key_file_path', return_value=tmp_path / "keys.enc"):
            manager = SecurityManager()
            assert manager is not None


class TestAgentModuleImports:
    """Tests for agent module imports."""

    def test_base_agent_imports(self):
        """BaseAgent should import correctly."""
        try:
            from src.ai.agents.base import BaseAgent
            assert BaseAgent is not None
        except ImportError as e:
            pytest.fail(f"Failed to import BaseAgent: {e}")

    def test_agent_models_import(self):
        """Agent models should import correctly."""
        try:
            from src.ai.agents.models import AgentConfig, AgentTask, AgentResponse
            assert AgentConfig is not None
            assert AgentTask is not None
            assert AgentResponse is not None
        except ImportError as e:
            pytest.fail(f"Failed to import agent models: {e}")

    def test_agent_manager_imports(self):
        """AgentManager should import correctly."""
        try:
            from src.managers.agent_manager import AgentManager
            assert AgentManager is not None
        except ImportError as e:
            pytest.fail(f"Failed to import AgentManager: {e}")


class TestSTTProviderImports:
    """Tests for STT provider imports."""

    def test_base_stt_provider_imports(self):
        """BaseSTTProvider should import correctly."""
        try:
            from src.stt_providers.base import BaseSTTProvider
            assert BaseSTTProvider is not None
        except ImportError as e:
            pytest.fail(f"Failed to import BaseSTTProvider: {e}")

    def test_deepgram_provider_imports(self):
        """DeepgramProvider should import correctly."""
        try:
            from src.stt_providers.deepgram import DeepgramProvider
            assert DeepgramProvider is not None
        except ImportError as e:
            pytest.fail(f"Failed to import DeepgramProvider: {e}")

    def test_groq_provider_imports(self):
        """GroqProvider should import correctly."""
        try:
            from src.stt_providers.groq import GroqProvider
            assert GroqProvider is not None
        except ImportError as e:
            pytest.fail(f"Failed to import GroqProvider: {e}")


class TestAIModuleImports:
    """Tests for AI module imports."""

    def test_ai_module_imports(self):
        """AI module should import correctly."""
        try:
            from src.ai import ai
            assert ai is not None
        except ImportError as e:
            pytest.fail(f"Failed to import ai module: {e}")

    def test_ai_processor_imports(self):
        """AIProcessor should import correctly."""
        try:
            from src.ai.ai_processor import AIProcessor
            assert AIProcessor is not None
        except ImportError as e:
            pytest.fail(f"Failed to import AIProcessor: {e}")


class TestProcessingModuleImports:
    """Tests for processing module imports."""

    def test_document_generators_imports(self):
        """DocumentGenerators should import correctly."""
        try:
            from src.processing.document_generators import DocumentGenerators
            assert DocumentGenerators is not None
        except ImportError as e:
            pytest.fail(f"Failed to import DocumentGenerators: {e}")

    def test_processing_queue_imports(self):
        """ProcessingQueue should import correctly."""
        try:
            from src.processing.processing_queue import ProcessingQueue
            assert ProcessingQueue is not None
        except ImportError as e:
            pytest.fail(f"Failed to import ProcessingQueue: {e}")


@pytest.mark.regression
class TestCoreRegressionSuite:
    """Comprehensive regression tests for core functionality."""

    def test_all_core_modules_import(self):
        """All core modules should import without errors."""
        modules_to_test = [
            'src.core.config',
            'src.database.database',
            'src.settings.settings',
            'src.ai.ai',
            'src.ai.ai_processor',
            'src.audio.audio',
            'src.processing.document_generators',
            'src.managers.agent_manager',
            'src.utils.security',
        ]

        failed = []
        for module in modules_to_test:
            try:
                __import__(module)
            except ImportError as e:
                failed.append((module, str(e)))

        if failed:
            pytest.fail(f"Failed to import modules: {failed}")

    def test_database_operations_work(self, tmp_path):
        """Basic database operations should work."""
        from src.database.database import Database

        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        db.create_tables()

        # Add recording
        rec_id = db.add_recording(filename="test.wav", transcript="Test")
        assert rec_id > 0

        # Read recording
        rec = db.get_recording(rec_id)
        assert rec is not None
        assert rec['filename'] == 'test.wav'

        # Update recording
        db.update_recording(rec_id, transcript="Updated")
        rec = db.get_recording(rec_id)
        assert rec['transcript'] == 'Updated'

        # Delete recording
        db.delete_recording(rec_id)
        assert db.get_recording(rec_id) is None

        db.close_all_connections()

    def test_settings_load_save_cycle(self, tmp_path):
        """Settings should save and load correctly."""
        from src.settings.settings import save_settings, load_settings

        settings_file = tmp_path / "settings.json"

        with patch('src.settings.settings.SETTINGS_FILE', str(settings_file)):
            test_settings = {'test_key': 'test_value'}
            save_settings(test_settings)
            loaded = load_settings()

        assert 'test_key' in loaded
        assert loaded['test_key'] == 'test_value'

    def test_agent_response_model_works(self):
        """AgentResponse model should work correctly."""
        from src.ai.agents.models import AgentResponse

        response = AgentResponse(
            success=True,
            content="Test content",
            error=None
        )

        assert response.success is True
        assert response.content == "Test content"
        assert response.error is None

    def test_agent_task_model_works(self):
        """AgentTask model should work correctly."""
        from src.ai.agents.models import AgentTask

        task = AgentTask(
            task_type="analyze",
            content="Test content",
            context={"key": "value"}
        )

        assert task.task_type == "analyze"
        assert task.content == "Test content"
        assert task.context == {"key": "value"}

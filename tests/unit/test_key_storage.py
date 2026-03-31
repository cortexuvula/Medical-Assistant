"""
Comprehensive tests for src/utils/security/key_storage.py

Tests SecureKeyStorage — Fernet encryption with PBKDF2 key derivation for API keys.
"""

import os
import json
import base64
import threading
import pytest
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock, mock_open, call

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MASTER_KEY = "test_master_key_for_unit_tests_12345"


def _make_storage(tmp_path, master_key=MASTER_KEY, key_file=None):
    """Create a SecureKeyStorage instance wired to tmp_path."""
    with patch("utils.security.key_storage.get_config") as mock_cfg:
        mock_cfg.return_value.storage.base_folder = str(tmp_path)
        with patch.dict(os.environ, {"MEDICAL_ASSISTANT_MASTER_KEY": master_key}):
            from utils.security.key_storage import SecureKeyStorage
            if key_file is None:
                storage = SecureKeyStorage()
            else:
                storage = SecureKeyStorage(key_file=key_file)
    return storage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def storage(tmp_path):
    """Standard storage fixture backed by tmp_path."""
    return _make_storage(tmp_path)


@pytest.fixture(autouse=True)
def _reset_legacy_logged():
    """Reset the class-level _LEGACY_MIGRATION_LOGGED flag between tests."""
    from utils.security.key_storage import SecureKeyStorage
    original = SecureKeyStorage._LEGACY_MIGRATION_LOGGED
    yield
    SecureKeyStorage._LEGACY_MIGRATION_LOGGED = original


# ===========================================================================
# TestSecureKeyStorageInit
# ===========================================================================

class TestSecureKeyStorageInit:
    def test_creates_key_directory(self, tmp_path):
        """Storage __init__ must create the .keys sub-directory."""
        storage = _make_storage(tmp_path)
        assert storage.key_file.parent.is_dir()

    def test_creates_salt_file_on_first_run(self, tmp_path):
        """A salt.bin file must exist after first init."""
        storage = _make_storage(tmp_path)
        assert storage.salt_file.exists()

    def test_custom_key_file_path(self, tmp_path):
        """Passing a custom key_file path is respected."""
        custom = tmp_path / "custom" / "my_keys.enc"
        storage = _make_storage(tmp_path, key_file=custom)
        assert storage.key_file == custom
        assert custom.parent.is_dir()

    def test_uses_env_master_key_when_set(self, tmp_path):
        """When MEDICAL_ASSISTANT_MASTER_KEY is set, _get_machine_id is NOT called."""
        with patch("utils.security.key_storage.get_config") as mock_cfg:
            mock_cfg.return_value.storage.base_folder = str(tmp_path)
            with patch.dict(os.environ, {"MEDICAL_ASSISTANT_MASTER_KEY": "env_key_abc"}):
                with patch(
                    "utils.security.key_storage.SecureKeyStorage._get_machine_id"
                ) as mock_mid:
                    from utils.security.key_storage import SecureKeyStorage
                    SecureKeyStorage()
                    mock_mid.assert_not_called()


# ===========================================================================
# TestGetOrCreateSalt
# ===========================================================================

class TestGetOrCreateSalt:
    def test_creates_new_salt_when_no_file(self, tmp_path):
        """No salt.bin → a 32-byte salt is generated and saved."""
        storage = _make_storage(tmp_path)
        assert storage.salt_file.exists()
        assert len(storage._salt) == 32

    def test_reads_existing_valid_salt(self, tmp_path):
        """If salt.bin already has ≥32 bytes, it is reused."""
        storage = _make_storage(tmp_path)
        original_salt = storage._salt
        # Second instance reads the same file
        storage2 = _make_storage(tmp_path, key_file=storage.key_file)
        assert storage2._salt == original_salt

    def test_regenerates_salt_when_too_short(self, tmp_path):
        """A salt.bin with fewer than SALT_LENGTH bytes causes regeneration."""
        storage = _make_storage(tmp_path)
        # Overwrite with a short salt
        storage.salt_file.write_bytes(b"short")
        storage2 = _make_storage(tmp_path, key_file=storage.key_file)
        assert len(storage2._salt) == 32
        # The new salt must have been saved (file grows to 32 bytes)
        assert len(storage2.salt_file.read_bytes()) == 32

    def test_regenerates_salt_on_read_error(self, tmp_path):
        """An IOError reading salt.bin causes _get_or_create_salt to attempt regeneration.

        When the read fails AND the subsequent save also fails (e.g. no space),
        a ConfigurationError is raised — this proves the read-error branch was hit.
        """
        from utils.exceptions import ConfigurationError

        storage = _make_storage(tmp_path)

        # Patch exists() so the code tries to read, then make the read fail,
        # and also make _save_salt fail so we can observe the error propagation.
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", side_effect=OSError("read fail")):
                with pytest.raises(ConfigurationError):
                    # read fails → tries to save new salt → save fails too
                    storage._get_or_create_salt()

    def test_regenerates_salt_on_read_error_saves_new(self, tmp_path):
        """After a failed read, a new salt is generated and written."""
        storage = _make_storage(tmp_path)
        salt_file = storage.salt_file
        # Write a valid salt first
        salt_file.write_bytes(b"x" * 32)
        # Corrupt it with fewer bytes
        salt_file.write_bytes(b"bad")
        # New instance should regenerate
        storage2 = _make_storage(tmp_path, key_file=storage.key_file)
        new_salt = salt_file.read_bytes()
        assert len(new_salt) == 32
        assert new_salt != b"bad"


# ===========================================================================
# TestSaveSalt
# ===========================================================================

class TestSaveSalt:
    def test_save_salt_writes_bytes(self, tmp_path):
        """_save_salt writes the exact bytes to salt_file."""
        storage = _make_storage(tmp_path)
        test_salt = b"A" * 32
        storage._save_salt(test_salt)
        assert storage.salt_file.read_bytes() == test_salt

    def test_save_salt_sets_posix_permissions(self, tmp_path):
        """On POSIX, _save_salt calls os.chmod with 0o600."""
        storage = _make_storage(tmp_path)
        with patch("os.name", "posix"):
            with patch("os.chmod") as mock_chmod:
                storage._save_salt(b"S" * 32)
                mock_chmod.assert_called_once_with(storage.salt_file, 0o600)

    def test_save_salt_raises_on_failure(self, tmp_path):
        """An OSError in _save_salt bubbles up as ConfigurationError."""
        from utils.exceptions import ConfigurationError

        storage = _make_storage(tmp_path)
        with patch("builtins.open", side_effect=OSError("no space")):
            with pytest.raises(ConfigurationError):
                storage._save_salt(b"X" * 32)


# ===========================================================================
# TestGetLegacySalt
# ===========================================================================

class TestGetLegacySalt:
    def test_legacy_salt_is_correct_bytes(self):
        """_get_legacy_salt must return the expected static bytes."""
        from utils.security.key_storage import SecureKeyStorage

        salt = SecureKeyStorage._get_legacy_salt()
        assert salt == b"medical_assistant_salt_v1"

    def test_legacy_salt_logs_warning_first_time(self):
        """The first call to _get_legacy_salt emits a warning via logger."""
        from utils.security.key_storage import SecureKeyStorage

        SecureKeyStorage._LEGACY_MIGRATION_LOGGED = False

        with patch("utils.security.key_storage.logger") as mock_logger:
            SecureKeyStorage._get_legacy_salt()
            mock_logger.warning.assert_called_once()

    def test_legacy_salt_logs_warning_only_once(self):
        """Subsequent calls do NOT emit additional warnings."""
        from utils.security.key_storage import SecureKeyStorage

        SecureKeyStorage._LEGACY_MIGRATION_LOGGED = False

        with patch("utils.security.key_storage.logger") as mock_logger:
            SecureKeyStorage._get_legacy_salt()
            SecureKeyStorage._get_legacy_salt()
            assert mock_logger.warning.call_count == 1


# ===========================================================================
# TestCreateCipher
# ===========================================================================

class TestCreateCipher:
    def test_create_cipher_returns_fernet(self, storage):
        """_create_cipher must return a Fernet instance."""
        from cryptography.fernet import Fernet

        cipher = storage._create_cipher("password", b"s" * 32)
        assert isinstance(cipher, Fernet)

    def test_same_password_salt_gives_same_key(self, storage):
        """Calling _create_cipher twice with the same args yields the same key (same encrypt/decrypt)."""
        password = "stable_password"
        salt = b"stable_salt_bytes" + b"\x00" * 15  # 32 bytes

        cipher1 = storage._create_cipher(password, salt)
        cipher2 = storage._create_cipher(password, salt)

        plaintext = b"test_data_abc"
        encrypted = cipher1.encrypt(plaintext)
        decrypted = cipher2.decrypt(encrypted)
        assert decrypted == plaintext


# ===========================================================================
# TestStoreAndGetKey
# ===========================================================================

class TestStoreAndGetKey:
    def test_store_key_encrypts_and_saves(self, storage):
        """store_key should write an encrypted entry to the JSON file."""
        storage.store_key("openai", "sk-abc123")
        assert storage.key_file.exists()
        raw = json.loads(storage.key_file.read_text())
        assert "openai" in raw
        assert "encrypted_key" in raw["openai"]
        # The stored value must not be the plaintext
        assert raw["openai"]["encrypted_key"] != "sk-abc123"

    def test_get_key_decrypts_correctly(self, storage):
        """get_key must return the original plaintext after store_key."""
        storage.store_key("anthropic", "claude_key_xyz")
        result = storage.get_key("anthropic")
        assert result == "claude_key_xyz"

    def test_get_key_not_found_returns_none(self, storage):
        """get_key for an unknown provider must return None."""
        assert storage.get_key("nonexistent_provider") is None

    def test_get_key_decrypt_failure_returns_none(self, storage):
        """If the stored data cannot be decrypted, get_key returns None (no raise)."""
        # Write corrupted encrypted_key entry
        storage._save_keys({
            "bad_provider": {
                "encrypted_key": base64.b64encode(b"totally_not_fernet").decode(),
                "stored_at": datetime.now().isoformat(),
                "key_hash": "abcd1234",
            }
        })
        result = storage.get_key("bad_provider")
        assert result is None

    def test_store_key_overwrites_existing(self, storage):
        """Calling store_key twice for the same provider replaces the value."""
        storage.store_key("openai", "old_key")
        storage.store_key("openai", "new_key")
        assert storage.get_key("openai") == "new_key"

    def test_store_key_stores_key_hash(self, storage):
        """store_key persists a key_hash (first 8 hex chars of sha256)."""
        import hashlib

        api_key = "test_api_key_999"
        storage.store_key("groq", api_key)
        raw = json.loads(storage.key_file.read_text())
        expected_hash = hashlib.sha256(api_key.encode()).hexdigest()[:8]
        assert raw["groq"]["key_hash"] == expected_hash


# ===========================================================================
# TestRemoveKey
# ===========================================================================

class TestRemoveKey:
    def test_remove_key_returns_true_when_found(self, storage):
        """remove_key returns True when the provider exists."""
        storage.store_key("deepgram", "dg_key")
        assert storage.remove_key("deepgram") is True

    def test_remove_key_returns_false_when_not_found(self, storage):
        """remove_key returns False when the provider does not exist."""
        assert storage.remove_key("phantom_provider") is False

    def test_remove_key_deletes_from_file(self, storage):
        """After remove_key, the provider must not appear in the JSON file."""
        storage.store_key("elevenlabs", "el_key")
        storage.remove_key("elevenlabs")
        raw = json.loads(storage.key_file.read_text())
        assert "elevenlabs" not in raw


# ===========================================================================
# TestListProviders
# ===========================================================================

class TestListProviders:
    def test_list_providers_empty(self, storage):
        """An empty store returns an empty dict from list_providers."""
        assert storage.list_providers() == {}

    def test_list_providers_returns_metadata(self, storage):
        """list_providers returns stored_at and key_hash for each provider."""
        storage.store_key("openai", "sk-test")
        providers = storage.list_providers()
        assert "openai" in providers
        assert "stored_at" in providers["openai"]
        assert "key_hash" in providers["openai"]

    def test_list_providers_excludes_metadata_entry(self, storage):
        """The internal _metadata entry must NOT appear in list_providers output."""
        storage.store_key("openai", "sk-test")
        providers = storage.list_providers()
        assert "_metadata" not in providers

    def test_list_providers_all_stored_keys(self, storage):
        """All stored providers appear in list_providers."""
        for name in ("openai", "anthropic", "groq"):
            storage.store_key(name, f"key_{name}")
        providers = storage.list_providers()
        assert set(providers.keys()) == {"openai", "anthropic", "groq"}

    def test_list_providers_no_encrypted_key_in_output(self, storage):
        """list_providers must NOT expose encrypted_key values."""
        storage.store_key("openai", "sk-secret")
        providers = storage.list_providers()
        for meta in providers.values():
            assert "encrypted_key" not in meta


# ===========================================================================
# TestLoadAndSaveKeys
# ===========================================================================

class TestLoadAndSaveKeys:
    def test_load_keys_returns_empty_when_no_file(self, tmp_path):
        """_load_keys returns {} when the key file does not exist."""
        storage = _make_storage(tmp_path)
        # Ensure there's no key file
        if storage.key_file.exists():
            storage.key_file.unlink()
        result = storage._load_keys()
        assert result == {}

    def test_load_keys_returns_empty_on_json_error(self, tmp_path):
        """_load_keys returns {} on malformed JSON without raising."""
        storage = _make_storage(tmp_path)
        storage.key_file.write_text("NOT VALID JSON {{{{")
        result = storage._load_keys()
        assert result == {}

    def test_save_keys_writes_json(self, storage):
        """_save_keys writes a valid JSON dict to key_file."""
        data = {"_metadata": {"salt_version": 2}, "provider_x": {"key": "val"}}
        storage._save_keys(data)
        loaded = json.loads(storage.key_file.read_text())
        assert loaded == data

    def test_save_keys_raises_config_error_on_failure(self, storage):
        """An OSError in _save_keys raises ConfigurationError."""
        from utils.exceptions import ConfigurationError

        with patch("builtins.open", side_effect=OSError("permission denied")):
            with pytest.raises(ConfigurationError):
                storage._save_keys({"_metadata": {}})

    def test_save_keys_sets_posix_permissions(self, tmp_path):
        """On POSIX, _save_keys calls os.chmod with 0o600 on the key file."""
        storage = _make_storage(tmp_path)
        with patch("os.name", "posix"):
            with patch("os.chmod") as mock_chmod:
                storage._save_keys({"_metadata": {"salt_version": 2}})
                mock_chmod.assert_called_once_with(storage.key_file, 0o600)


# ===========================================================================
# TestMigrateLegacyKeys
# ===========================================================================

class TestMigrateLegacyKeys:
    def _make_legacy_store(self, tmp_path, master_key, providers):
        """Helper: build a key file at salt_version 1 with given providers."""
        # First create a storage to get the legacy cipher
        from utils.security.key_storage import SecureKeyStorage

        legacy_salt = SecureKeyStorage._get_legacy_salt()

        # We need a bare cipher — create one without full init to avoid recursion
        with patch("utils.security.key_storage.get_config") as mock_cfg:
            mock_cfg.return_value.storage.base_folder = str(tmp_path)
            with patch.dict(os.environ, {"MEDICAL_ASSISTANT_MASTER_KEY": master_key}):
                storage = SecureKeyStorage()

        legacy_cipher = storage._create_cipher(master_key, legacy_salt)

        keys = {"_metadata": {"salt_version": 1}}
        for provider, api_key in providers.items():
            encrypted = legacy_cipher.encrypt(api_key.encode())
            import hashlib
            keys[provider] = {
                "encrypted_key": base64.b64encode(encrypted).decode(),
                "stored_at": datetime.now().isoformat(),
                "key_hash": hashlib.sha256(api_key.encode()).hexdigest()[:8],
            }

        storage.key_file.write_text(json.dumps(keys))
        return storage

    def test_migration_skipped_when_already_at_version_2(self, tmp_path):
        """If salt_version is already 2, no migration is attempted."""
        storage = _make_storage(tmp_path)
        # Write version 2 metadata
        storage._save_keys({"_metadata": {"salt_version": 2}})

        with patch.object(storage, "_get_legacy_salt") as mock_ls:
            storage._migrate_legacy_keys_if_needed(MASTER_KEY)
            mock_ls.assert_not_called()

    def test_migration_skipped_when_no_keys(self, tmp_path):
        """Empty store (only metadata) just bumps the version, no key re-encryption."""
        storage = _make_storage(tmp_path)
        # Save only metadata at version 1
        storage._save_keys({"_metadata": {"salt_version": 1}})

        with patch.object(storage.__class__, "_get_legacy_salt", wraps=storage._get_legacy_salt):
            storage._migrate_legacy_keys_if_needed(MASTER_KEY)

        raw = json.loads(storage.key_file.read_text())
        assert raw["_metadata"]["salt_version"] == 2

    def test_migration_updates_metadata_version(self, tmp_path):
        """After migration, the key file metadata reflects salt_version == 2."""
        storage = self._make_legacy_store(tmp_path, MASTER_KEY, {"openai": "sk-test"})
        # Reload — migration should run automatically
        storage2 = _make_storage(tmp_path, master_key=MASTER_KEY, key_file=storage.key_file)
        raw = json.loads(storage2.key_file.read_text())
        assert raw["_metadata"]["salt_version"] == 2

    def test_successful_migration_re_encrypts_keys(self, tmp_path):
        """After migration, the key is readable via the new cipher."""
        from utils.security.key_storage import SecureKeyStorage

        # Build a legacy key file
        legacy_salt = SecureKeyStorage._get_legacy_salt()

        with patch("utils.security.key_storage.get_config") as mock_cfg:
            mock_cfg.return_value.storage.base_folder = str(tmp_path)
            with patch.dict(os.environ, {"MEDICAL_ASSISTANT_MASTER_KEY": MASTER_KEY}):
                storage1 = SecureKeyStorage()

        legacy_cipher = storage1._create_cipher(MASTER_KEY, legacy_salt)
        encrypted = legacy_cipher.encrypt(b"my_api_key_value")

        import hashlib
        legacy_keys = {
            "_metadata": {"salt_version": 1},
            "openai": {
                "encrypted_key": base64.b64encode(encrypted).decode(),
                "stored_at": datetime.now().isoformat(),
                "key_hash": hashlib.sha256(b"my_api_key_value").hexdigest()[:8],
            }
        }
        storage1.key_file.write_text(json.dumps(legacy_keys))

        # Now create a fresh storage — migration should fire
        with patch("utils.security.key_storage.get_config") as mock_cfg:
            mock_cfg.return_value.storage.base_folder = str(tmp_path)
            with patch.dict(os.environ, {"MEDICAL_ASSISTANT_MASTER_KEY": MASTER_KEY}):
                storage2 = SecureKeyStorage(key_file=storage1.key_file)

        result = storage2.get_key("openai")
        assert result == "my_api_key_value"

    def test_migration_tracks_failures(self, tmp_path):
        """Providers that fail decryption are tracked in _migration_failures.

        The migration code catches (ValueError, TypeError, KeyError).
        We trigger a KeyError by omitting the 'encrypted_key' field so the
        dict lookup `data["encrypted_key"]` raises KeyError.
        """
        from utils.security.key_storage import SecureKeyStorage

        with patch("utils.security.key_storage.get_config") as mock_cfg:
            mock_cfg.return_value.storage.base_folder = str(tmp_path)
            with patch.dict(os.environ, {"MEDICAL_ASSISTANT_MASTER_KEY": MASTER_KEY}):
                storage1 = SecureKeyStorage()

        # Build a version-1 key file where the provider entry is malformed
        # (missing 'encrypted_key' key → KeyError during migration)
        legacy_keys = {
            "_metadata": {"salt_version": 1},
            "broken_provider": {
                # deliberately omitting 'encrypted_key' to trigger KeyError
                "stored_at": datetime.now().isoformat(),
                "key_hash": "deadbeef",
            }
        }
        storage1.key_file.write_text(json.dumps(legacy_keys))

        # Reload — migration runs, KeyError is caught, provider added to failures
        with patch("utils.security.key_storage.get_config") as mock_cfg:
            mock_cfg.return_value.storage.base_folder = str(tmp_path)
            with patch.dict(os.environ, {"MEDICAL_ASSISTANT_MASTER_KEY": MASTER_KEY}):
                storage2 = SecureKeyStorage(key_file=storage1.key_file)

        failures = storage2.get_migration_failures()
        assert "broken_provider" in failures

    def test_migration_handles_file_error(self, tmp_path):
        """A file I/O error during migration is caught; failures set to ['all']."""
        from utils.security.key_storage import SecureKeyStorage

        with patch("utils.security.key_storage.get_config") as mock_cfg:
            mock_cfg.return_value.storage.base_folder = str(tmp_path)
            with patch.dict(os.environ, {"MEDICAL_ASSISTANT_MASTER_KEY": MASTER_KEY}):
                storage = SecureKeyStorage()

        # Write a version-1 file with one provider
        legacy_salt = SecureKeyStorage._get_legacy_salt()
        legacy_cipher = storage._create_cipher(MASTER_KEY, legacy_salt)
        encrypted = legacy_cipher.encrypt(b"some_key")
        legacy_keys = {
            "_metadata": {"salt_version": 1},
            "provider_x": {
                "encrypted_key": base64.b64encode(encrypted).decode(),
                "stored_at": datetime.now().isoformat(),
                "key_hash": "abc12345",
            }
        }
        storage.key_file.write_text(json.dumps(legacy_keys))

        # Make _save_keys raise IOError
        with patch("utils.security.key_storage.get_config") as mock_cfg:
            mock_cfg.return_value.storage.base_folder = str(tmp_path)
            with patch.dict(os.environ, {"MEDICAL_ASSISTANT_MASTER_KEY": MASTER_KEY}):
                with patch.object(SecureKeyStorage, "_save_keys", side_effect=OSError("disk full")):
                    storage2 = SecureKeyStorage(key_file=storage.key_file)

        assert storage2._migration_failures == ["all"]

    def test_get_migration_failures_empty(self, storage):
        """get_migration_failures returns [] when no failures occurred."""
        assert storage.get_migration_failures() == []

    def test_get_migration_failures_with_failures(self, storage):
        """get_migration_failures returns the list set during migration."""
        storage._migration_failures = ["openai", "anthropic"]
        assert storage.get_migration_failures() == ["openai", "anthropic"]


# ===========================================================================
# TestUpdateMetadataVersion
# ===========================================================================

class TestUpdateMetadataVersion:
    def test_update_metadata_version_sets_version_2(self, storage):
        """_update_metadata_version saves salt_version == 2 in the key file."""
        keys: dict = {}
        storage._update_metadata_version(keys)
        raw = json.loads(storage.key_file.read_text())
        assert raw["_metadata"]["salt_version"] == 2

    def test_update_metadata_version_preserves_other_entries(self, storage):
        """_update_metadata_version keeps existing provider entries intact."""
        storage.store_key("openai", "sk-preserve")
        keys = storage._load_keys()
        storage._update_metadata_version(keys)
        loaded = storage._load_keys()
        assert "openai" in loaded


# ===========================================================================
# TestGetMachineId
# ===========================================================================

class TestGetMachineId:
    def _machine_id_storage(self, tmp_path):
        """Create a storage instance that actually calls _get_machine_id."""
        # We must NOT set MEDICAL_ASSISTANT_MASTER_KEY
        env_without_key = {k: v for k, v in os.environ.items() if k != "MEDICAL_ASSISTANT_MASTER_KEY"}
        with patch("utils.security.key_storage.get_config") as mock_cfg:
            mock_cfg.return_value.storage.base_folder = str(tmp_path)
            with patch.dict(os.environ, env_without_key, clear=True):
                from utils.security.key_storage import SecureKeyStorage
                storage = SecureKeyStorage()
        return storage

    def test_machine_id_returns_hex_string(self, tmp_path):
        """_get_machine_id must return a non-empty hex string."""
        storage = _make_storage(tmp_path)
        machine_id = storage._get_machine_id()
        assert isinstance(machine_id, str)
        assert len(machine_id) > 0
        # Must be valid hex
        int(machine_id, 16)

    def test_machine_id_is_consistent(self, tmp_path):
        """Two consecutive calls to _get_machine_id must return the same value."""
        storage = _make_storage(tmp_path)
        id1 = storage._get_machine_id()
        id2 = storage._get_machine_id()
        assert id1 == id2

    def test_machine_id_uses_fallback_when_no_sources(self, tmp_path):
        """When all platform sources fail, the fallback sources still produce a valid ID."""
        storage = _make_storage(tmp_path)

        with patch("builtins.open", side_effect=OSError("no machine-id")):
            with patch("subprocess.run", side_effect=OSError("no findmnt")):
                machine_id = storage._get_machine_id()
                assert isinstance(machine_id, str)
                assert len(machine_id) == 64  # SHA-256 hex digest

    def test_machine_id_length_is_64_chars(self, tmp_path):
        """The machine ID must be exactly 64 hex characters (SHA-256)."""
        storage = _make_storage(tmp_path)
        machine_id = storage._get_machine_id()
        assert len(machine_id) == 64

    def test_machine_id_used_when_env_not_set(self, tmp_path):
        """Without MEDICAL_ASSISTANT_MASTER_KEY, _get_machine_id is used as master key."""
        with patch("utils.security.key_storage.get_config") as mock_cfg:
            mock_cfg.return_value.storage.base_folder = str(tmp_path)
            # Remove the env var
            env = {k: v for k, v in os.environ.items() if k != "MEDICAL_ASSISTANT_MASTER_KEY"}
            with patch.dict(os.environ, env, clear=True):
                with patch.object(
                    __import__("utils.security.key_storage", fromlist=["SecureKeyStorage"]).SecureKeyStorage,
                    "_get_machine_id",
                    return_value="a" * 64,
                ) as mock_mid:
                    from utils.security.key_storage import SecureKeyStorage
                    s = SecureKeyStorage()
                    mock_mid.assert_called_once()


# ===========================================================================
# TestThreadSafety
# ===========================================================================

class TestThreadSafety:
    def test_store_and_get_from_multiple_threads(self, tmp_path):
        """Concurrent store+get from multiple threads must not raise."""
        storage = _make_storage(tmp_path)
        errors = []

        def worker(i):
            try:
                storage.store_key(f"provider_{i}", f"key_{i}")
                val = storage.get_key(f"provider_{i}")
                assert val == f"key_{i}", f"Got {val!r} for provider_{i}"
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"

    def test_concurrent_stores_dont_corrupt_data(self, tmp_path):
        """After many concurrent writes, all stored keys are retrievable."""
        storage = _make_storage(tmp_path)
        n = 15
        errors = []

        def store_worker(i):
            try:
                storage.store_key(f"concurrent_{i}", f"value_{i}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=store_worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"

        # All stored providers must be retrievable
        providers = storage.list_providers()
        for i in range(n):
            assert f"concurrent_{i}" in providers, f"concurrent_{i} missing from providers"
            val = storage.get_key(f"concurrent_{i}")
            assert val == f"value_{i}", f"Expected value_{i}, got {val!r}"


# ===========================================================================
# Additional edge-case tests
# ===========================================================================

class TestEdgeCases:
    def test_store_and_get_empty_string_key(self, storage):
        """An empty string API key round-trips correctly."""
        storage.store_key("empty_provider", "")
        assert storage.get_key("empty_provider") == ""

    def test_store_and_get_unicode_key(self, storage):
        """A unicode API key (non-ASCII) round-trips correctly."""
        unicode_key = "api-key-日本語-テスト-αβγ"
        storage.store_key("unicode_provider", unicode_key)
        assert storage.get_key("unicode_provider") == unicode_key

    def test_store_and_get_very_long_key(self, storage):
        """A very long API key (1024 chars) round-trips correctly."""
        long_key = "A" * 1024
        storage.store_key("long_provider", long_key)
        assert storage.get_key("long_provider") == long_key

    def test_list_providers_after_remove(self, storage):
        """After removing a provider, it no longer appears in list_providers."""
        storage.store_key("openai", "sk-test")
        storage.store_key("groq", "groq-test")
        storage.remove_key("openai")
        providers = storage.list_providers()
        assert "openai" not in providers
        assert "groq" in providers

    def test_multiple_providers_independent(self, storage):
        """Storing multiple providers doesn't overwrite each other."""
        storage.store_key("a", "key_a")
        storage.store_key("b", "key_b")
        storage.store_key("c", "key_c")
        assert storage.get_key("a") == "key_a"
        assert storage.get_key("b") == "key_b"
        assert storage.get_key("c") == "key_c"

    def test_stored_at_is_iso_format(self, storage):
        """The stored_at field should be parseable as an ISO datetime."""
        storage.store_key("ts_provider", "ts_key")
        providers = storage.list_providers()
        stored_at = providers["ts_provider"]["stored_at"]
        # Should not raise
        parsed = datetime.fromisoformat(stored_at)
        assert parsed is not None

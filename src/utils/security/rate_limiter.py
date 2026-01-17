"""
Rate Limiter Module

Provides persistent rate limiting for API calls with sliding window algorithm.
"""

import os
import json
import time
import threading
from pathlib import Path
from typing import Dict, Optional, Any, Tuple, List
from threading import Lock
from utils.structured_logging import get_logger

from core.config import get_config

logger = get_logger(__name__)
from utils.constants import (
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_OLLAMA,
    STT_DEEPGRAM, STT_GROQ, STT_ELEVENLABS
)


class RateLimiter:
    """Persistent rate limiter for API calls with sliding window algorithm.

    This implementation provides:
    - Persistence across application restarts via JSON file storage
    - Sliding window rate limiting with configurable time windows
    - Automatic cleanup of expired entries
    - Thread-safe operations with per-key locking
    - Graceful degradation if persistence fails
    - Memory-bounded lock management with time-based expiry

    The sliding window algorithm uses timestamps to track calls within a
    rolling time window, providing more accurate rate limiting than fixed
    windows.
    """

    # File save interval in seconds (avoid excessive disk writes)
    SAVE_INTERVAL = 30

    # Maximum age of rate limit data to keep (in seconds)
    MAX_DATA_AGE = 3600  # 1 hour

    # Lock management constants
    MAX_LOCKS = 100  # Maximum number of locks to keep
    LOCK_EXPIRY_SECONDS = 3600  # Remove locks unused for 1 hour
    LOCK_CLEANUP_INTERVAL = 300  # Run cleanup every 5 minutes

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize rate limiter with persistent storage.

        Args:
            storage_path: Path to rate limit data file (default: config/.rate_limits.json)
        """
        # Using module-level logger
        self._global_lock = Lock()
        # Changed from defaultdict to regular dict with timestamps
        # Format: {key: (Lock, last_access_time)}
        self._key_locks: Dict[str, Tuple[Lock, float]] = {}
        self._last_save_time = 0.0
        self._last_lock_cleanup = 0.0

        # In-memory cache of rate limit data
        # Format: {key: {"calls": [timestamp, ...], "window_seconds": int}}
        self._limits: Dict[str, Dict[str, Any]] = {}

        # Set up storage path
        if storage_path is None:
            config = get_config()
            storage_path = Path(config.storage.base_folder) / ".keys" / ".rate_limits.json"
        self.storage_path = storage_path

        # Default rate limits per provider (calls per time window)
        # Format: (calls, window_seconds)
        self.default_limits: Dict[str, Tuple[int, int]] = {
            PROVIDER_OPENAI: (60, 60),       # 60 calls per minute
            STT_GROQ: (30, 60),              # 30 calls per minute
            STT_DEEPGRAM: (100, 60),         # 100 calls per minute
            STT_ELEVENLABS: (50, 60),        # 50 calls per minute
            PROVIDER_ANTHROPIC: (60, 60),    # 60 calls per minute
            PROVIDER_OLLAMA: (1000, 60),     # Local, so higher limit
        }

        # Load persisted data on startup
        self._load_from_disk()

    def _get_key_lock(self, key: str) -> Lock:
        """Get or create a lock for a specific key.

        Thread-safe method that manages lock lifecycle with time-based expiry.

        Args:
            key: The rate limit key

        Returns:
            Lock for the key
        """
        now = time.time()

        with self._global_lock:
            # Run periodic lock cleanup
            if now - self._last_lock_cleanup > self.LOCK_CLEANUP_INTERVAL:
                self._cleanup_expired_locks(now)
                self._last_lock_cleanup = now

            if key in self._key_locks:
                # Update last access time
                lock, _ = self._key_locks[key]
                self._key_locks[key] = (lock, now)
                return lock
            else:
                # Create new lock
                lock = Lock()
                self._key_locks[key] = (lock, now)
                return lock

    def _cleanup_expired_locks(self, now: float) -> None:
        """Remove locks that haven't been used recently.

        Must be called with _global_lock held.

        Args:
            now: Current timestamp
        """
        # Find locks that have expired (not used for LOCK_EXPIRY_SECONDS)
        expired_keys = []
        for key, (lock, last_access) in list(self._key_locks.items()):
            if now - last_access > self.LOCK_EXPIRY_SECONDS:
                # Only remove if the lock is not currently held
                if lock.acquire(blocking=False):
                    lock.release()
                    expired_keys.append(key)

        # Remove expired locks
        for key in expired_keys:
            del self._key_locks[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired locks")

        # Safety limit: if still over MAX_LOCKS, remove oldest
        if len(self._key_locks) > self.MAX_LOCKS:
            # Sort by last access time and remove oldest
            provider_keys = set(self.default_limits.keys())
            sorted_locks = sorted(
                [(k, v[1]) for k, v in self._key_locks.items() if k not in provider_keys],
                key=lambda x: x[1]  # Sort by last access time
            )
            # Remove oldest locks until under limit
            remove_count = len(self._key_locks) - self.MAX_LOCKS
            for key, _ in sorted_locks[:remove_count]:
                if key in self._key_locks:
                    lock, _ = self._key_locks[key]
                    if lock.acquire(blocking=False):
                        lock.release()
                        del self._key_locks[key]

            logger.debug(f"Removed {remove_count} locks to stay under MAX_LOCKS")

    def _load_from_disk(self) -> None:
        """Load rate limit data from disk."""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)

                now = time.time()

                # Load and validate data
                for key, limit_data in data.items():
                    if isinstance(limit_data, dict) and "calls" in limit_data:
                        # Filter out expired calls
                        window = limit_data.get("window_seconds", 60)
                        valid_calls = [
                            ts for ts in limit_data["calls"]
                            if now - ts < window
                        ]

                        # Only keep if there are valid calls
                        if valid_calls:
                            self._limits[key] = {
                                "calls": valid_calls,
                                "window_seconds": window
                            }

                logger.debug(f"Loaded rate limit data for {len(self._limits)} keys")

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid rate limit data file, starting fresh: {e}")
            self._limits = {}
        except Exception as e:
            logger.warning(f"Could not load rate limit data: {e}")
            self._limits = {}

    def _save_to_disk(self, force: bool = False) -> None:
        """Save rate limit data to disk asynchronously.

        This method schedules a save operation in a background thread to avoid
        blocking API calls. The save is rate-limited by SAVE_INTERVAL.

        Args:
            force: If True, save immediately; otherwise respect SAVE_INTERVAL
        """
        now = time.time()

        # Respect save interval unless forced
        if not force and now - self._last_save_time < self.SAVE_INTERVAL:
            return

        # Update timestamp immediately to prevent multiple concurrent saves
        self._last_save_time = now

        # Take a snapshot of data for async save (quick operation under lock)
        with self._global_lock:
            data_snapshot = {k: dict(v) for k, v in self._limits.items()}

        # Schedule async save in background thread
        def _do_save():
            try:
                # Ensure directory exists
                self.storage_path.parent.mkdir(parents=True, exist_ok=True)

                # Cleanup old data from snapshot
                cutoff = time.time() - self.MAX_DATA_AGE
                cleaned_data = {}
                for key, limit_data in data_snapshot.items():
                    calls = limit_data.get("calls", [])
                    window = limit_data.get("window_seconds", 60)
                    if calls and max(calls) > cutoff:
                        # Keep only calls within window
                        window_start = time.time() - window
                        limit_data["calls"] = [ts for ts in calls if ts > window_start]
                        cleaned_data[key] = limit_data

                # Write to disk (no lock needed - working with snapshot)
                with open(self.storage_path, 'w') as f:
                    json.dump(cleaned_data, f)

                # Set file permissions (Unix-like systems)
                if os.name == 'posix':
                    os.chmod(self.storage_path, 0o600)

                logger.debug(f"Saved rate limit data for {len(cleaned_data)} keys")

            except Exception as e:
                logger.warning(f"Could not save rate limit data: {e}")

        # Run save in background thread to avoid blocking
        save_thread = threading.Thread(target=_do_save, daemon=True)
        save_thread.start()

    def _cleanup_expired_data(self) -> None:
        """Remove expired entries from rate limit data and stale locks."""
        now = time.time()
        keys_to_remove = []

        for key, limit_data in self._limits.items():
            window = limit_data.get("window_seconds", 60)
            calls = limit_data.get("calls", [])

            # Filter out expired calls
            valid_calls = [ts for ts in calls if now - ts < window]

            if valid_calls:
                limit_data["calls"] = valid_calls
            else:
                keys_to_remove.append(key)

        # Remove empty entries
        for key in keys_to_remove:
            del self._limits[key]

        # Clean up stale locks (locks for keys that no longer have data)
        self._cleanup_stale_locks(keys_to_remove)

    def _cleanup_stale_locks(self, removed_keys: List[str]) -> None:
        """Remove locks for keys that have been removed from rate limit data.

        This is called during data cleanup to remove locks for keys that
        no longer have rate limit data.

        Args:
            removed_keys: List of keys that were removed from rate limit data
        """
        with self._global_lock:
            # Remove locks for explicitly removed keys
            for key in removed_keys:
                if key in self._key_locks:
                    # Only remove if the lock is not currently held
                    lock, _ = self._key_locks[key]
                    if lock.acquire(blocking=False):
                        lock.release()
                        del self._key_locks[key]

            # Also clean up locks for keys without active rate limit data
            active_keys = set(self._limits.keys())
            stale_lock_keys = [
                k for k in list(self._key_locks.keys())
                if k not in active_keys
            ]

            for key in stale_lock_keys:
                if key in self._key_locks:
                    lock, _ = self._key_locks[key]
                    if lock.acquire(blocking=False):
                        lock.release()
                        del self._key_locks[key]

            # Note: MAX_LOCKS enforcement is now handled in _cleanup_expired_locks()

    def check_rate_limit(self, provider: str, identifier: Optional[str] = None) -> Tuple[bool, Optional[float]]:
        """Check if a request is within rate limits using sliding window.

        Args:
            provider: API provider name
            identifier: Optional identifier for more granular limiting

        Returns:
            Tuple of (is_allowed, wait_time_seconds)
        """
        key = f"{provider}:{identifier}" if identifier else provider
        key_lock = self._get_key_lock(key)

        with key_lock:
            now = time.time()

            # Get rate limit configuration for provider
            limit_config = self.default_limits.get(provider, (60, 60))
            max_calls, window_seconds = limit_config

            # Initialize limit data if not exists
            if key not in self._limits:
                self._limits[key] = {
                    "calls": [],
                    "window_seconds": window_seconds
                }

            limit_data = self._limits[key]
            calls = limit_data["calls"]

            # Sliding window: remove calls outside the current window
            window_start = now - window_seconds
            valid_calls = [ts for ts in calls if ts > window_start]
            limit_data["calls"] = valid_calls

            # Check if we're at the limit
            if len(valid_calls) >= max_calls:
                # Calculate wait time until oldest call expires
                if valid_calls:
                    oldest_call = min(valid_calls)
                    wait_time = window_seconds - (now - oldest_call)
                    if wait_time > 0:
                        return False, wait_time

                # All calls have expired, reset
                limit_data["calls"] = []

            # Record this call
            limit_data["calls"].append(now)

            # Trigger async save
            self._save_to_disk()

            return True, None

    def set_limit(self, provider: str, calls_per_window: int, window_seconds: int = 60) -> None:
        """Set custom rate limit for a provider.

        Args:
            provider: API provider name
            calls_per_window: Maximum calls per time window
            window_seconds: Time window in seconds (default: 60)
        """
        self.default_limits[provider] = (calls_per_window, window_seconds)
        logger.info(f"Set rate limit for {provider}: {calls_per_window} calls/{window_seconds}s")

    def get_usage_stats(self, provider: str, identifier: Optional[str] = None) -> Dict[str, Any]:
        """Get usage statistics for a provider.

        Args:
            provider: API provider name
            identifier: Optional identifier for more granular stats

        Returns:
            Usage statistics
        """
        key = f"{provider}:{identifier}" if identifier else provider
        key_lock = self._get_key_lock(key)

        with key_lock:
            now = time.time()

            # Get rate limit configuration
            limit_config = self.default_limits.get(provider, (60, 60))
            max_calls, window_seconds = limit_config

            if key not in self._limits:
                return {
                    "provider": provider,
                    "identifier": identifier,
                    "calls_in_window": 0,
                    "rate_limit": max_calls,
                    "window_seconds": window_seconds,
                    "available": max_calls,
                    "utilization": 0.0,
                    "reset_in_seconds": None
                }

            limit_data = self._limits[key]
            calls = limit_data["calls"]

            # Filter to current window
            window_start = now - window_seconds
            valid_calls = [ts for ts in calls if ts > window_start]

            # Calculate reset time
            reset_in = None
            if valid_calls:
                oldest_call = min(valid_calls)
                reset_in = window_seconds - (now - oldest_call)
                if reset_in < 0:
                    reset_in = 0

            return {
                "provider": provider,
                "identifier": identifier,
                "calls_in_window": len(valid_calls),
                "rate_limit": max_calls,
                "window_seconds": window_seconds,
                "available": max(0, max_calls - len(valid_calls)),
                "utilization": len(valid_calls) / max_calls if max_calls > 0 else 0,
                "reset_in_seconds": reset_in
            }

    def reset_provider(self, provider: str, identifier: Optional[str] = None) -> None:
        """Reset rate limit data for a provider.

        Args:
            provider: API provider name
            identifier: Optional identifier for more granular reset
        """
        key = f"{provider}:{identifier}" if identifier else provider
        key_lock = self._get_key_lock(key)

        with key_lock:
            if key in self._limits:
                del self._limits[key]
                self._save_to_disk(force=True)
                logger.info(f"Reset rate limit data for {key}")

    def reset_all(self) -> None:
        """Reset all rate limit data."""
        with self._global_lock:
            self._limits = {}
            self._save_to_disk(force=True)
            logger.info("Reset all rate limit data")

    def flush(self) -> None:
        """Force save current state to disk."""
        self._save_to_disk(force=True)


__all__ = ["RateLimiter"]

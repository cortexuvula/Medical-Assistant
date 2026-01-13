"""
Singleton HTTP client manager with connection pooling.

Provides persistent connections per provider with configurable pool sizes.
This eliminates the 100-500ms overhead of creating new connections for each API call.
"""

import httpx
import requests
import threading
import time
import atexit
import logging
from typing import Dict, Optional
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)

# Check if HTTP/2 support is available
try:
    import h2  # noqa: F401
    HTTP2_AVAILABLE = True
except ImportError:
    HTTP2_AVAILABLE = False
    logger.debug("h2 package not installed, HTTP/2 disabled. Install with: pip install httpx[http2]")


class HTTPClientManager:
    """Thread-safe singleton for managing HTTP client pools."""

    _instance: Optional["HTTPClientManager"] = None
    _lock = threading.Lock()

    # Pool configuration per provider
    POOL_CONFIG = {
        "openai": {"max_connections": 10, "max_keepalive": 5},
        "anthropic": {"max_connections": 10, "max_keepalive": 5},
        "ollama": {"max_connections": 3, "max_keepalive": 2},
        "gemini": {"max_connections": 5, "max_keepalive": 3},
        "elevenlabs": {"max_connections": 5, "max_keepalive": 3},
        "deepgram": {"max_connections": 5, "max_keepalive": 3},
        "groq": {"max_connections": 5, "max_keepalive": 3},
        "rag": {"max_connections": 3, "max_keepalive": 2},
    }

    # Default timeouts per provider (connect, read)
    PROVIDER_TIMEOUTS = {
        "openai": (5.0, 60.0),
        "anthropic": (5.0, 60.0),
        "ollama": (5.0, 120.0),  # Local, may be slower
        "gemini": (5.0, 60.0),
        "elevenlabs": (5.0, 90.0),  # TTS can be slower
        "deepgram": (5.0, 120.0),  # Long audio transcription
        "groq": (5.0, 60.0),
        "rag": (5.0, 30.0),
    }

    def __init__(self):
        """Initialize client manager. Use get_instance() instead of direct instantiation."""
        self._httpx_clients: Dict[str, httpx.Client] = {}
        self._requests_sessions: Dict[str, requests.Session] = {}
        self._client_lock = threading.Lock()
        self._shutdown = False

        # Register cleanup on exit
        atexit.register(self.shutdown)

    @classmethod
    def get_instance(cls) -> "HTTPClientManager":
        """Get or create the singleton instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_httpx_client(
        self,
        provider: str,
        timeout: Optional[float] = None,
        custom_limits: Optional[httpx.Limits] = None,
    ) -> httpx.Client:
        """
        Get or create an httpx client for a provider.

        Args:
            provider: Provider name (e.g., "openai", "anthropic")
            timeout: Optional custom timeout (uses provider default if not specified)
            custom_limits: Optional custom connection limits

        Returns:
            Configured httpx.Client with connection pooling
        """
        if self._shutdown:
            raise RuntimeError("HTTPClientManager has been shut down")

        with self._client_lock:
            if provider not in self._httpx_clients:
                config = self.POOL_CONFIG.get(provider, {"max_connections": 5, "max_keepalive": 3})
                default_timeout = self.PROVIDER_TIMEOUTS.get(provider, (5.0, 60.0))

                limits = custom_limits or httpx.Limits(
                    max_connections=config["max_connections"],
                    max_keepalive_connections=config["max_keepalive"],
                    keepalive_expiry=30.0,  # Keep connections alive for 30 seconds
                )

                connect_timeout, read_timeout = default_timeout
                if timeout:
                    read_timeout = timeout

                self._httpx_clients[provider] = httpx.Client(
                    limits=limits,
                    timeout=httpx.Timeout(
                        connect=connect_timeout,
                        read=read_timeout,
                        write=30.0,
                        pool=5.0,
                    ),
                    http2=HTTP2_AVAILABLE,  # Enable HTTP/2 if h2 package is installed
                )

            return self._httpx_clients[provider]

    def get_requests_session(
        self,
        provider: str,
        timeout: Optional[float] = None,
    ) -> requests.Session:
        """
        Get or create a requests session for a provider.

        Args:
            provider: Provider name (e.g., "ollama", "elevenlabs")
            timeout: Optional custom timeout

        Returns:
            Configured requests.Session with connection pooling
        """
        if self._shutdown:
            raise RuntimeError("HTTPClientManager has been shut down")

        with self._client_lock:
            if provider not in self._requests_sessions:
                config = self.POOL_CONFIG.get(provider, {"max_connections": 5})

                session = requests.Session()

                # Configure retry strategy for transient errors
                retry_strategy = Retry(
                    total=3,
                    backoff_factor=0.5,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"],
                )

                # Configure connection pool adapter
                adapter = HTTPAdapter(
                    pool_connections=config["max_connections"],
                    pool_maxsize=config["max_connections"],
                    max_retries=retry_strategy,
                    pool_block=False,
                )

                session.mount("http://", adapter)
                session.mount("https://", adapter)

                self._requests_sessions[provider] = session

            return self._requests_sessions[provider]

    def get_timeout(self, provider: str) -> tuple:
        """Get the default (connect, read) timeout tuple for a provider."""
        return self.PROVIDER_TIMEOUTS.get(provider, (5.0, 60.0))

    def close_provider(self, provider: str) -> None:
        """Close connections for a specific provider."""
        with self._client_lock:
            if provider in self._httpx_clients:
                try:
                    self._httpx_clients[provider].close()
                except Exception:
                    pass
                del self._httpx_clients[provider]

            if provider in self._requests_sessions:
                try:
                    self._requests_sessions[provider].close()
                except Exception:
                    pass
                del self._requests_sessions[provider]

    def shutdown(self) -> None:
        """Close all clients and sessions. Called automatically on exit."""
        if self._shutdown:
            return

        self._shutdown = True

        with self._client_lock:
            # Close all httpx clients
            for provider, client in list(self._httpx_clients.items()):
                try:
                    client.close()
                except Exception:
                    pass
            self._httpx_clients.clear()

            # Close all requests sessions
            for provider, session in list(self._requests_sessions.items()):
                try:
                    session.close()
                except Exception:
                    pass
            self._requests_sessions.clear()

    def get_stats(self) -> Dict[str, Dict]:
        """Get statistics about active connections (for debugging)."""
        stats = {
            "httpx_clients": list(self._httpx_clients.keys()),
            "requests_sessions": list(self._requests_sessions.keys()),
        }
        return stats


# Convenience function for getting the singleton
def get_http_client_manager() -> HTTPClientManager:
    """Get the HTTPClientManager singleton instance."""
    return HTTPClientManager.get_instance()

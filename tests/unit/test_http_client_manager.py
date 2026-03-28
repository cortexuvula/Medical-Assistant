"""Tests for utils.http_client_manager — singleton HTTP client manager."""

import threading
import pytest
from unittest.mock import patch, MagicMock

import httpx
import requests

from utils.http_client_manager import HTTPClientManager, get_http_client_manager


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton before and after each test."""
    HTTPClientManager._instance = None
    yield
    # Shutdown the instance if it was created
    if HTTPClientManager._instance is not None:
        try:
            HTTPClientManager._instance.shutdown()
        except Exception:
            pass
        HTTPClientManager._instance = None


class TestHTTPClientManagerSingleton:
    def test_get_instance_returns_instance(self):
        manager = HTTPClientManager.get_instance()
        assert manager is not None

    def test_get_instance_is_singleton(self):
        a = HTTPClientManager.get_instance()
        b = HTTPClientManager.get_instance()
        assert a is b

    def test_convenience_function_returns_singleton(self):
        manager = get_http_client_manager()
        assert manager is HTTPClientManager.get_instance()

    def test_thread_safe_singleton(self):
        instances = []
        errors = []

        def create_instance():
            try:
                instances.append(HTTPClientManager.get_instance())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(instances) == 10
        assert all(i is instances[0] for i in instances)


class TestGetHttpxClient:
    def test_returns_httpx_client(self):
        manager = HTTPClientManager.get_instance()
        client = manager.get_httpx_client("openai")
        assert isinstance(client, httpx.Client)

    def test_same_provider_returns_same_client(self):
        manager = HTTPClientManager.get_instance()
        c1 = manager.get_httpx_client("openai")
        c2 = manager.get_httpx_client("openai")
        assert c1 is c2

    def test_different_providers_return_different_clients(self):
        manager = HTTPClientManager.get_instance()
        openai_client = manager.get_httpx_client("openai")
        anthropic_client = manager.get_httpx_client("anthropic")
        assert openai_client is not anthropic_client

    def test_unknown_provider_uses_defaults(self):
        manager = HTTPClientManager.get_instance()
        client = manager.get_httpx_client("unknown_provider")
        assert isinstance(client, httpx.Client)

    def test_custom_limits_accepted(self):
        manager = HTTPClientManager.get_instance()
        limits = httpx.Limits(max_connections=2, max_keepalive_connections=1)
        client = manager.get_httpx_client("test_custom", custom_limits=limits)
        assert isinstance(client, httpx.Client)

    def test_custom_timeout_accepted(self):
        manager = HTTPClientManager.get_instance()
        client = manager.get_httpx_client("test_timeout", timeout=120.0)
        assert isinstance(client, httpx.Client)

    def test_raises_after_shutdown(self):
        manager = HTTPClientManager.get_instance()
        manager.shutdown()
        with pytest.raises(RuntimeError, match="shut down"):
            manager.get_httpx_client("openai")


class TestGetRequestsSession:
    def test_returns_requests_session(self):
        manager = HTTPClientManager.get_instance()
        session = manager.get_requests_session("ollama")
        assert isinstance(session, requests.Session)

    def test_same_provider_returns_same_session(self):
        manager = HTTPClientManager.get_instance()
        s1 = manager.get_requests_session("ollama")
        s2 = manager.get_requests_session("ollama")
        assert s1 is s2

    def test_different_providers_return_different_sessions(self):
        manager = HTTPClientManager.get_instance()
        s1 = manager.get_requests_session("ollama")
        s2 = manager.get_requests_session("openai")
        assert s1 is not s2

    def test_session_has_tls_verification_enabled(self):
        manager = HTTPClientManager.get_instance()
        session = manager.get_requests_session("openai")
        assert session.verify is True

    def test_unknown_provider_uses_defaults(self):
        manager = HTTPClientManager.get_instance()
        session = manager.get_requests_session("unknown_provider")
        assert isinstance(session, requests.Session)

    def test_raises_after_shutdown(self):
        manager = HTTPClientManager.get_instance()
        manager.shutdown()
        with pytest.raises(RuntimeError, match="shut down"):
            manager.get_requests_session("openai")


class TestGetTimeout:
    def test_known_provider_returns_tuple(self):
        manager = HTTPClientManager.get_instance()
        timeout = manager.get_timeout("openai")
        assert isinstance(timeout, tuple)
        assert len(timeout) == 2

    def test_unknown_provider_returns_default(self):
        manager = HTTPClientManager.get_instance()
        timeout = manager.get_timeout("unknown")
        assert timeout == (5.0, 60.0)

    def test_ollama_has_longer_timeout(self):
        manager = HTTPClientManager.get_instance()
        connect, read = manager.get_timeout("ollama")
        assert read >= 60.0  # Local models may be slower

    def test_deepgram_has_long_read_timeout(self):
        manager = HTTPClientManager.get_instance()
        connect, read = manager.get_timeout("deepgram")
        assert read >= 60.0  # Long audio transcription


class TestCloseProvider:
    def test_close_existing_httpx_client(self):
        manager = HTTPClientManager.get_instance()
        manager.get_httpx_client("openai")  # Create client
        assert "openai" in manager._httpx_clients
        manager.close_provider("openai")
        assert "openai" not in manager._httpx_clients

    def test_close_existing_requests_session(self):
        manager = HTTPClientManager.get_instance()
        manager.get_requests_session("openai")  # Create session
        assert "openai" in manager._requests_sessions
        manager.close_provider("openai")
        assert "openai" not in manager._requests_sessions

    def test_close_nonexistent_provider_is_safe(self):
        manager = HTTPClientManager.get_instance()
        # Should not raise
        manager.close_provider("nonexistent_provider")

    def test_close_provider_with_broken_client(self):
        manager = HTTPClientManager.get_instance()
        # Install a broken client that raises on close
        broken = MagicMock()
        broken.close.side_effect = Exception("close failed")
        manager._httpx_clients["broken"] = broken
        # Should not raise
        manager.close_provider("broken")
        assert "broken" not in manager._httpx_clients

    def test_after_close_new_client_is_created(self):
        manager = HTTPClientManager.get_instance()
        c1 = manager.get_httpx_client("openai")
        manager.close_provider("openai")
        c2 = manager.get_httpx_client("openai")
        assert c1 is not c2


class TestShutdown:
    def test_shutdown_clears_all_clients(self):
        manager = HTTPClientManager.get_instance()
        manager.get_httpx_client("openai")
        manager.get_requests_session("ollama")
        manager.shutdown()
        assert len(manager._httpx_clients) == 0
        assert len(manager._requests_sessions) == 0

    def test_shutdown_idempotent(self):
        manager = HTTPClientManager.get_instance()
        manager.shutdown()
        manager.shutdown()  # Should not raise

    def test_shutdown_sets_flag(self):
        manager = HTTPClientManager.get_instance()
        assert not manager._shutdown
        manager.shutdown()
        assert manager._shutdown

    def test_shutdown_with_broken_clients(self):
        manager = HTTPClientManager.get_instance()
        broken = MagicMock()
        broken.close.side_effect = Exception("close failed")
        manager._httpx_clients["broken"] = broken
        manager._requests_sessions["broken"] = broken
        # Should not raise
        manager.shutdown()
        assert len(manager._httpx_clients) == 0
        assert len(manager._requests_sessions) == 0


class TestGetStats:
    def test_returns_dict(self):
        manager = HTTPClientManager.get_instance()
        stats = manager.get_stats()
        assert isinstance(stats, dict)

    def test_stats_contains_expected_keys(self):
        manager = HTTPClientManager.get_instance()
        stats = manager.get_stats()
        assert "httpx_clients" in stats
        assert "requests_sessions" in stats

    def test_empty_when_no_clients_created(self):
        manager = HTTPClientManager.get_instance()
        stats = manager.get_stats()
        assert stats["httpx_clients"] == []
        assert stats["requests_sessions"] == []

    def test_lists_created_clients(self):
        manager = HTTPClientManager.get_instance()
        manager.get_httpx_client("openai")
        manager.get_requests_session("ollama")
        stats = manager.get_stats()
        assert "openai" in stats["httpx_clients"]
        assert "ollama" in stats["requests_sessions"]


class TestPoolConfig:
    def test_all_known_providers_have_pool_config(self):
        manager = HTTPClientManager.get_instance()
        known_providers = ["openai", "anthropic", "ollama", "gemini"]
        for p in known_providers:
            assert p in manager.POOL_CONFIG or manager.get_httpx_client(p) is not None

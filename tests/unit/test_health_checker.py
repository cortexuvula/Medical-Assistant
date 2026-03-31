"""Unit tests for utils.health_checker — unified health monitoring."""

import unittest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from utils.health_checker import (
    ServiceStatus,
    ServiceCategory,
    ServiceHealthResult,
    HealthReport,
    UnifiedHealthChecker,
    get_health_checker,
    check_service,
    is_service_healthy,
)
import utils.health_checker as health_module


class TestServiceStatus(unittest.TestCase):

    def test_healthy_value(self):
        assert ServiceStatus.HEALTHY.value == "healthy"

    def test_degraded_value(self):
        assert ServiceStatus.DEGRADED.value == "degraded"

    def test_unhealthy_value(self):
        assert ServiceStatus.UNHEALTHY.value == "unhealthy"

    def test_disabled_value(self):
        assert ServiceStatus.DISABLED.value == "disabled"

    def test_unknown_value(self):
        assert ServiceStatus.UNKNOWN.value == "unknown"


class TestServiceCategory(unittest.TestCase):

    def test_rag_value(self):
        assert ServiceCategory.RAG.value == "rag"

    def test_database_value(self):
        assert ServiceCategory.DATABASE.value == "database"


class TestServiceHealthResult(unittest.TestCase):

    def test_basic_creation(self):
        result = ServiceHealthResult(
            service_name="db",
            category=ServiceCategory.DATABASE,
            status=ServiceStatus.HEALTHY,
        )
        assert result.service_name == "db"
        assert result.status == ServiceStatus.HEALTHY

    def test_is_healthy_for_healthy(self):
        result = ServiceHealthResult(
            service_name="db",
            category=ServiceCategory.DATABASE,
            status=ServiceStatus.HEALTHY,
        )
        assert result.is_healthy() is True

    def test_is_healthy_for_degraded(self):
        result = ServiceHealthResult(
            service_name="db",
            category=ServiceCategory.DATABASE,
            status=ServiceStatus.DEGRADED,
        )
        assert result.is_healthy() is True

    def test_is_healthy_for_unhealthy(self):
        result = ServiceHealthResult(
            service_name="db",
            category=ServiceCategory.DATABASE,
            status=ServiceStatus.UNHEALTHY,
        )
        assert result.is_healthy() is False

    def test_is_healthy_for_disabled(self):
        result = ServiceHealthResult(
            service_name="db",
            category=ServiceCategory.DATABASE,
            status=ServiceStatus.DISABLED,
        )
        assert result.is_healthy() is False

    def test_defaults(self):
        result = ServiceHealthResult(
            service_name="db",
            category=ServiceCategory.DATABASE,
            status=ServiceStatus.UNKNOWN,
        )
        assert result.latency_ms == 0.0
        assert result.error_message is None
        assert result.details == {}


class TestHealthReport(unittest.TestCase):

    def _make_result(self, name, category, status):
        return ServiceHealthResult(
            service_name=name,
            category=category,
            status=status,
        )

    def test_healthy_services(self):
        report = HealthReport(
            overall_status=ServiceStatus.HEALTHY,
            services={
                "db": self._make_result("db", ServiceCategory.DATABASE, ServiceStatus.HEALTHY),
                "neo4j": self._make_result("neo4j", ServiceCategory.RAG, ServiceStatus.UNHEALTHY),
            },
        )
        assert "db" in report.healthy_services
        assert "neo4j" not in report.healthy_services

    def test_unhealthy_services(self):
        report = HealthReport(
            overall_status=ServiceStatus.DEGRADED,
            services={
                "db": self._make_result("db", ServiceCategory.DATABASE, ServiceStatus.HEALTHY),
                "neo4j": self._make_result("neo4j", ServiceCategory.RAG, ServiceStatus.UNHEALTHY),
            },
        )
        assert "neo4j" in report.unhealthy_services

    def test_degraded_services(self):
        report = HealthReport(
            overall_status=ServiceStatus.DEGRADED,
            services={
                "stt": self._make_result("stt", ServiceCategory.STT_PROVIDER, ServiceStatus.DEGRADED),
            },
        )
        assert "stt" in report.degraded_services

    def test_can_operate_without_db(self):
        report = HealthReport(
            overall_status=ServiceStatus.DEGRADED,
            services={
                "neo4j": self._make_result("neo4j", ServiceCategory.RAG, ServiceStatus.UNHEALTHY),
            },
        )
        assert report.can_operate is True

    def test_cannot_operate_with_unhealthy_db(self):
        report = HealthReport(
            overall_status=ServiceStatus.UNHEALTHY,
            services={
                "database": self._make_result("database", ServiceCategory.DATABASE, ServiceStatus.UNHEALTHY),
            },
        )
        assert report.can_operate is False

    def test_can_operate_with_healthy_db(self):
        report = HealthReport(
            overall_status=ServiceStatus.HEALTHY,
            services={
                "database": self._make_result("database", ServiceCategory.DATABASE, ServiceStatus.HEALTHY),
            },
        )
        assert report.can_operate is True

    def test_to_dict(self):
        report = HealthReport(
            overall_status=ServiceStatus.HEALTHY,
            services={
                "db": self._make_result("db", ServiceCategory.DATABASE, ServiceStatus.HEALTHY),
            },
        )
        d = report.to_dict()
        assert d["overall_status"] == "healthy"
        assert "db" in d["services"]
        assert d["summary"]["healthy"] == 1
        assert d["summary"]["total"] == 1
        assert d["can_operate"] is True

    def test_to_dict_timestamp(self):
        report = HealthReport(
            overall_status=ServiceStatus.HEALTHY,
            services={},
        )
        d = report.to_dict()
        assert "timestamp" in d


class TestUnifiedHealthChecker(unittest.TestCase):

    def setUp(self):
        UnifiedHealthChecker._instance = None
        UnifiedHealthChecker._initialized = False
        health_module._health_checker = None

    def tearDown(self):
        UnifiedHealthChecker._instance = None
        UnifiedHealthChecker._initialized = False
        health_module._health_checker = None

    def _make_checker(self, checks=None):
        checker = UnifiedHealthChecker.__new__(UnifiedHealthChecker)
        checker._initialized = False
        checker._cache_ttl = 30
        checker._cache = {}
        checker._cache_times = {}
        import threading
        checker._cache_lock = threading.Lock()
        checker._checks = {}
        checker._initialized = True
        UnifiedHealthChecker._instance = checker
        if checks:
            for name, func in checks.items():
                checker.register(name, func)
        return checker

    def test_singleton_returns_same_instance(self):
        c1 = self._make_checker()
        UnifiedHealthChecker._instance = c1
        c2 = UnifiedHealthChecker.__new__(UnifiedHealthChecker)
        assert c1 is c2

    def test_register_and_check(self):
        checker = self._make_checker()
        mock_result = ServiceHealthResult(
            service_name="test",
            category=ServiceCategory.EXTERNAL,
            status=ServiceStatus.HEALTHY,
        )
        checker.register("test", lambda: mock_result)
        result = checker.check("test", force=True)
        assert result.status == ServiceStatus.HEALTHY

    def test_check_unregistered_returns_none(self):
        checker = self._make_checker()
        assert checker.check("nonexistent") is None

    def test_unregister(self):
        checker = self._make_checker()
        checker.register("test", lambda: None)
        checker.unregister("test")
        assert checker.check("test") is None

    def test_cache_returns_cached_result(self):
        call_count = {"n": 0}

        def counting_check():
            call_count["n"] += 1
            return ServiceHealthResult(
                service_name="test",
                category=ServiceCategory.EXTERNAL,
                status=ServiceStatus.HEALTHY,
            )

        checker = self._make_checker({"test": counting_check})
        checker.check("test", force=True)
        checker.check("test")  # should use cache
        assert call_count["n"] == 1

    def test_force_bypasses_cache(self):
        call_count = {"n": 0}

        def counting_check():
            call_count["n"] += 1
            return ServiceHealthResult(
                service_name="test",
                category=ServiceCategory.EXTERNAL,
                status=ServiceStatus.HEALTHY,
            )

        checker = self._make_checker({"test": counting_check})
        checker.check("test", force=True)
        checker.check("test", force=True)
        assert call_count["n"] == 2

    def test_check_handles_exception_in_check_func(self):
        def failing_check():
            raise RuntimeError("boom")

        checker = self._make_checker({"test": failing_check})
        result = checker.check("test", force=True)
        assert result.status == ServiceStatus.UNHEALTHY
        assert "boom" in result.error_message

    def test_check_all(self):
        healthy = ServiceHealthResult(
            service_name="db", category=ServiceCategory.DATABASE, status=ServiceStatus.HEALTHY,
        )
        checker = self._make_checker({"db": lambda: healthy})
        report = checker.check_all(force=True)
        assert isinstance(report, HealthReport)
        assert "db" in report.services

    def test_check_category(self):
        db_result = ServiceHealthResult(
            service_name="db", category=ServiceCategory.DATABASE, status=ServiceStatus.HEALTHY,
        )
        rag_result = ServiceHealthResult(
            service_name="neo4j", category=ServiceCategory.RAG, status=ServiceStatus.HEALTHY,
        )
        checker = self._make_checker({
            "db": lambda: db_result,
            "neo4j": lambda: rag_result,
        })
        results = checker.check_category(ServiceCategory.DATABASE, force=True)
        assert "db" in results
        assert "neo4j" not in results

    def test_calculate_overall_status_empty(self):
        checker = self._make_checker()
        assert checker._calculate_overall_status({}) == ServiceStatus.UNKNOWN

    def test_calculate_overall_status_all_healthy(self):
        checker = self._make_checker()
        results = {
            "svc1": ServiceHealthResult(
                service_name="svc1", category=ServiceCategory.EXTERNAL, status=ServiceStatus.HEALTHY,
            ),
        }
        assert checker._calculate_overall_status(results) == ServiceStatus.HEALTHY

    def test_calculate_overall_status_critical_unhealthy(self):
        checker = self._make_checker()
        results = {
            "database": ServiceHealthResult(
                service_name="database", category=ServiceCategory.DATABASE, status=ServiceStatus.UNHEALTHY,
            ),
        }
        assert checker._calculate_overall_status(results) == ServiceStatus.UNHEALTHY

    def test_calculate_overall_status_degraded(self):
        checker = self._make_checker()
        results = {
            "svc1": ServiceHealthResult(
                service_name="svc1", category=ServiceCategory.EXTERNAL, status=ServiceStatus.HEALTHY,
            ),
            "svc2": ServiceHealthResult(
                service_name="svc2", category=ServiceCategory.RAG, status=ServiceStatus.UNHEALTHY,
            ),
        }
        status = checker._calculate_overall_status(results)
        assert status == ServiceStatus.DEGRADED

    def test_get_cache_stats(self):
        checker = self._make_checker()
        stats = checker.get_cache_stats()
        assert "cached_services" in stats
        assert "cache_ttl" in stats

    def test_clear_cache(self):
        healthy = ServiceHealthResult(
            service_name="db", category=ServiceCategory.DATABASE, status=ServiceStatus.HEALTHY,
        )
        checker = self._make_checker({"db": lambda: healthy})
        checker.check("db", force=True)
        checker.clear_cache()
        stats = checker.get_cache_stats()
        assert len(stats["cached_services"]) == 0


class TestModuleFunctions(unittest.TestCase):

    def setUp(self):
        UnifiedHealthChecker._instance = None
        UnifiedHealthChecker._initialized = False
        health_module._health_checker = None

    def tearDown(self):
        UnifiedHealthChecker._instance = None
        UnifiedHealthChecker._initialized = False
        health_module._health_checker = None

    def test_get_health_checker_returns_instance(self):
        checker = get_health_checker()
        assert isinstance(checker, UnifiedHealthChecker)

    def test_get_health_checker_singleton(self):
        c1 = get_health_checker()
        c2 = get_health_checker()
        assert c1 is c2

    def test_check_service_unregistered(self):
        checker = get_health_checker()
        result = checker.check("nonexistent_service_xyz")
        assert result is None

    def test_is_service_healthy_returns_false_for_unknown(self):
        assert is_service_healthy("nonexistent_service_xyz") is False


class TestCheckDatabase(unittest.TestCase):
    """Tests for the _check_database() health check function."""

    @patch("database.database.get_session", create=True)
    def test_healthy_path(self, mock_get_session):
        """Healthy DB: session.execute succeeds."""
        from utils.health_checker import _check_database

        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = _check_database()
        assert result.status == ServiceStatus.HEALTHY
        assert result.service_name == "database"
        assert result.category == ServiceCategory.DATABASE

    @patch("database.database.get_session", create=True)
    def test_unhealthy_path(self, mock_get_session):
        """DB failure: get_session raises."""
        from utils.health_checker import _check_database

        mock_get_session.side_effect = Exception("Connection refused")

        result = _check_database()
        assert result.status == ServiceStatus.UNHEALTHY
        assert result.service_name == "database"
        assert "Connection refused" in result.error_message

    @patch("database.database.get_session", create=True)
    def test_latency_positive(self, mock_get_session):
        """Latency should be a positive number."""
        from utils.health_checker import _check_database

        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = _check_database()
        assert result.latency_ms >= 0

    @patch("database.database.get_session", create=True)
    def test_category_is_database(self, mock_get_session):
        """Service category must be DATABASE."""
        from utils.health_checker import _check_database

        mock_get_session.side_effect = Exception("err")
        result = _check_database()
        assert result.category == ServiceCategory.DATABASE

    @patch("database.database.get_session", create=True)
    def test_unhealthy_latency_positive(self, mock_get_session):
        """Even on error, latency should be a positive number."""
        from utils.health_checker import _check_database

        mock_get_session.side_effect = Exception("err")
        result = _check_database()
        assert result.latency_ms >= 0


class TestCheckNeo4j(unittest.TestCase):
    """Tests for the _check_neo4j() health check function."""

    @patch("rag.health_manager.get_health_manager")
    def test_healthy(self, mock_get_hm):
        from utils.health_checker import _check_neo4j

        mock_health = Mock()
        mock_health.healthy = True
        mock_health.latency_ms = 5.0
        mock_health.error_message = None
        mock_health.circuit_state = "closed"
        mock_get_hm.return_value.check_neo4j.return_value = mock_health

        result = _check_neo4j()
        assert result.status == ServiceStatus.HEALTHY
        assert result.service_name == "neo4j"

    @patch("rag.health_manager.get_health_manager")
    def test_unhealthy(self, mock_get_hm):
        from utils.health_checker import _check_neo4j

        mock_health = Mock()
        mock_health.healthy = False
        mock_health.latency_ms = 10.0
        mock_health.error_message = "neo4j down"
        mock_health.circuit_state = "open"
        mock_get_hm.return_value.check_neo4j.return_value = mock_health

        result = _check_neo4j()
        assert result.status == ServiceStatus.UNHEALTHY

    @patch("rag.health_manager.get_health_manager", side_effect=ImportError("no rag"))
    def test_import_error_disabled(self, mock_get_hm):
        from utils.health_checker import _check_neo4j

        result = _check_neo4j()
        assert result.status == ServiceStatus.DISABLED
        assert "RAG module not available" in result.error_message

    @patch("rag.health_manager.get_health_manager")
    def test_general_exception(self, mock_get_hm):
        from utils.health_checker import _check_neo4j

        mock_get_hm.side_effect = RuntimeError("unexpected")
        result = _check_neo4j()
        assert result.status == ServiceStatus.UNHEALTHY
        assert "unexpected" in result.error_message


class TestCheckNeon(unittest.TestCase):
    """Tests for the _check_neon() health check function."""

    @patch("rag.health_manager.get_health_manager")
    def test_healthy(self, mock_get_hm):
        from utils.health_checker import _check_neon

        mock_health = Mock()
        mock_health.healthy = True
        mock_health.latency_ms = 3.0
        mock_health.error_message = None
        mock_health.circuit_state = "closed"
        mock_get_hm.return_value.check_neon.return_value = mock_health

        result = _check_neon()
        assert result.status == ServiceStatus.HEALTHY
        assert result.service_name == "neon"

    @patch("rag.health_manager.get_health_manager")
    def test_unhealthy(self, mock_get_hm):
        from utils.health_checker import _check_neon

        mock_health = Mock()
        mock_health.healthy = False
        mock_health.latency_ms = 20.0
        mock_health.error_message = "neon timeout"
        mock_health.circuit_state = "open"
        mock_get_hm.return_value.check_neon.return_value = mock_health

        result = _check_neon()
        assert result.status == ServiceStatus.UNHEALTHY

    @patch("rag.health_manager.get_health_manager", side_effect=ImportError("no rag"))
    def test_import_error_disabled(self, mock_get_hm):
        from utils.health_checker import _check_neon

        result = _check_neon()
        assert result.status == ServiceStatus.DISABLED
        assert "RAG module not available" in result.error_message

    @patch("rag.health_manager.get_health_manager")
    def test_general_exception(self, mock_get_hm):
        from utils.health_checker import _check_neon

        mock_get_hm.side_effect = RuntimeError("oops")
        result = _check_neon()
        assert result.status == ServiceStatus.UNHEALTHY
        assert "oops" in result.error_message


class TestCheckEmbedding(unittest.TestCase):
    """Tests for the _check_embedding() health check function."""

    @patch("rag.health_manager.get_health_manager")
    def test_healthy(self, mock_get_hm):
        from utils.health_checker import _check_embedding

        mock_health = Mock()
        mock_health.healthy = True
        mock_health.latency_ms = 15.0
        mock_health.error_message = None
        mock_health.circuit_state = "closed"
        mock_get_hm.return_value.check_openai.return_value = mock_health

        result = _check_embedding()
        assert result.status == ServiceStatus.HEALTHY
        assert result.service_name == "embedding"

    @patch("rag.health_manager.get_health_manager")
    def test_unhealthy(self, mock_get_hm):
        from utils.health_checker import _check_embedding

        mock_health = Mock()
        mock_health.healthy = False
        mock_health.latency_ms = 50.0
        mock_health.error_message = "openai key invalid"
        mock_health.circuit_state = "open"
        mock_get_hm.return_value.check_openai.return_value = mock_health

        result = _check_embedding()
        assert result.status == ServiceStatus.UNHEALTHY

    @patch("rag.health_manager.get_health_manager", side_effect=ImportError("no rag"))
    def test_import_error_disabled(self, mock_get_hm):
        from utils.health_checker import _check_embedding

        result = _check_embedding()
        assert result.status == ServiceStatus.DISABLED
        assert "RAG module not available" in result.error_message

    @patch("rag.health_manager.get_health_manager")
    def test_general_exception(self, mock_get_hm):
        from utils.health_checker import _check_embedding

        mock_get_hm.side_effect = RuntimeError("embed fail")
        result = _check_embedding()
        assert result.status == ServiceStatus.UNHEALTHY
        assert "embed fail" in result.error_message


class TestCheckSttProvider(unittest.TestCase):
    """Tests for the _check_stt_provider() health check function.

    The function body does:
        from settings.settings_manager import settings_manager
        from stt_providers.factory import get_stt_provider
    Since stt_providers.factory does not exist in this codebase, we inject
    a mock module into sys.modules before calling _check_stt_provider().
    """

    def _run_with_mocks(self, settings_get_return, provider_obj, factory_side_effect=None):
        """Helper to run _check_stt_provider with properly injected mocks."""
        import sys
        from utils.health_checker import _check_stt_provider

        mock_settings_mgr = Mock()
        mock_settings_mgr.get.return_value = settings_get_return

        mock_factory = MagicMock()
        if factory_side_effect:
            mock_factory.get_stt_provider.side_effect = factory_side_effect
        else:
            mock_factory.get_stt_provider.return_value = provider_obj

        # Save ALL modules that we touch
        _sentinel = object()
        old_factory = sys.modules.get("stt_providers.factory", _sentinel)
        old_sm = sys.modules.get("settings.settings_manager", _sentinel)
        try:
            sys.modules["stt_providers.factory"] = mock_factory
            mock_sm_module = MagicMock()
            mock_sm_module.settings_manager = mock_settings_mgr
            sys.modules["settings.settings_manager"] = mock_sm_module
            return _check_stt_provider()
        finally:
            # Restore original state exactly
            if old_factory is _sentinel:
                sys.modules.pop("stt_providers.factory", None)
            else:
                sys.modules["stt_providers.factory"] = old_factory
            if old_sm is _sentinel:
                sys.modules.pop("settings.settings_manager", None)
            else:
                sys.modules["settings.settings_manager"] = old_sm

    def test_provider_none_disabled(self):
        result = self._run_with_mocks("deepgram", None)
        assert result.status == ServiceStatus.DISABLED

    def test_provider_test_connection_true(self):
        mock_provider = Mock()
        mock_provider.test_connection.return_value = True
        result = self._run_with_mocks("deepgram", mock_provider)
        assert result.status == ServiceStatus.HEALTHY

    def test_provider_test_connection_false(self):
        mock_provider = Mock()
        mock_provider.test_connection.return_value = False
        result = self._run_with_mocks("deepgram", mock_provider)
        assert result.status == ServiceStatus.UNHEALTHY

    def test_provider_no_test_connection(self):
        mock_provider = Mock(spec=[])  # no attributes
        result = self._run_with_mocks("deepgram", mock_provider)
        assert result.status == ServiceStatus.UNKNOWN
        assert "No test_connection method" in result.error_message

    def test_import_error_disabled(self):
        """When the import fails, status should be DISABLED."""
        from utils.health_checker import _check_stt_provider
        import sys

        _sentinel = object()
        old_factory = sys.modules.get("stt_providers.factory", _sentinel)
        old_sm = sys.modules.get("settings.settings_manager", _sentinel)
        try:
            # Inject a settings_manager mock so that import succeeds
            mock_sm_module = MagicMock()
            mock_sm_module.settings_manager = Mock()
            mock_sm_module.settings_manager.get.return_value = "deepgram"
            sys.modules["settings.settings_manager"] = mock_sm_module

            # Remove factory module so the import fails
            sys.modules.pop("stt_providers.factory", None)
            result = _check_stt_provider()
            assert result.status == ServiceStatus.DISABLED
        finally:
            if old_factory is _sentinel:
                sys.modules.pop("stt_providers.factory", None)
            else:
                sys.modules["stt_providers.factory"] = old_factory
            if old_sm is _sentinel:
                sys.modules.pop("settings.settings_manager", None)
            else:
                sys.modules["settings.settings_manager"] = old_sm

    def test_general_exception(self):
        result = self._run_with_mocks("deepgram", None,
                                      factory_side_effect=RuntimeError("provider crash"))
        assert result.status == ServiceStatus.UNHEALTHY
        assert "provider crash" in result.error_message

    def test_service_name_includes_provider(self):
        mock_provider = Mock()
        mock_provider.test_connection.return_value = True
        result = self._run_with_mocks("groq_stt", mock_provider)
        assert "groq_stt" in result.service_name


class TestStartupDiagnostics(unittest.TestCase):
    """Tests for run_startup_diagnostics()."""

    def setUp(self):
        UnifiedHealthChecker._instance = None
        UnifiedHealthChecker._initialized = False
        health_module._health_checker = None

    def tearDown(self):
        UnifiedHealthChecker._instance = None
        UnifiedHealthChecker._initialized = False
        health_module._health_checker = None

    def _make_checker(self, checks=None):
        checker = UnifiedHealthChecker.__new__(UnifiedHealthChecker)
        checker._initialized = False
        checker._cache_ttl = 30
        checker._cache = {}
        checker._cache_times = {}
        import threading
        checker._cache_lock = threading.Lock()
        checker._checks = {}
        checker._initialized = True
        UnifiedHealthChecker._instance = checker
        if checks:
            for name, func in checks.items():
                checker.register(name, func)
        return checker

    def test_returns_health_report(self):
        from utils.health_checker import run_startup_diagnostics

        healthy = ServiceHealthResult(
            service_name="db", category=ServiceCategory.DATABASE, status=ServiceStatus.HEALTHY,
        )
        checker = self._make_checker({"db": lambda: healthy})
        health_module._health_checker = checker

        report = run_startup_diagnostics(log_results=False)
        assert isinstance(report, HealthReport)

    @patch("utils.health_checker.logger")
    def test_logs_unhealthy_services(self, mock_logger):
        from utils.health_checker import run_startup_diagnostics

        unhealthy = ServiceHealthResult(
            service_name="neo4j", category=ServiceCategory.RAG,
            status=ServiceStatus.UNHEALTHY, error_message="down",
        )
        checker = self._make_checker({"neo4j": lambda: unhealthy})
        health_module._health_checker = checker

        run_startup_diagnostics(log_results=True)
        assert mock_logger.warning.called

    @patch("utils.health_checker.logger")
    def test_logs_degraded_services(self, mock_logger):
        from utils.health_checker import run_startup_diagnostics

        degraded = ServiceHealthResult(
            service_name="stt", category=ServiceCategory.STT_PROVIDER,
            status=ServiceStatus.DEGRADED, error_message="slow",
        )
        checker = self._make_checker({"stt": lambda: degraded})
        health_module._health_checker = checker

        run_startup_diagnostics(log_results=True)
        # Info is called for degraded services and for the summary
        assert mock_logger.info.called

    @patch("utils.health_checker.logger")
    def test_logs_critical_error_when_cannot_operate(self, mock_logger):
        from utils.health_checker import run_startup_diagnostics

        unhealthy_db = ServiceHealthResult(
            service_name="database", category=ServiceCategory.DATABASE,
            status=ServiceStatus.UNHEALTHY, error_message="db crashed",
        )
        checker = self._make_checker({"database": lambda: unhealthy_db})
        health_module._health_checker = checker

        report = run_startup_diagnostics(log_results=True)
        assert report.can_operate is False
        assert mock_logger.error.called


class TestOverallStatusEdgeCases(unittest.TestCase):
    """Edge case tests for _calculate_overall_status."""

    def setUp(self):
        UnifiedHealthChecker._instance = None
        UnifiedHealthChecker._initialized = False
        health_module._health_checker = None

    def tearDown(self):
        UnifiedHealthChecker._instance = None
        UnifiedHealthChecker._initialized = False
        health_module._health_checker = None

    def _make_checker(self):
        checker = UnifiedHealthChecker.__new__(UnifiedHealthChecker)
        checker._initialized = False
        checker._cache_ttl = 30
        checker._cache = {}
        checker._cache_times = {}
        import threading
        checker._cache_lock = threading.Lock()
        checker._checks = {}
        checker._initialized = True
        UnifiedHealthChecker._instance = checker
        return checker

    def _result(self, name, category, status):
        return ServiceHealthResult(
            service_name=name, category=category, status=status,
        )

    def test_all_disabled_returns_healthy(self):
        """All DISABLED services: no healthy/unhealthy/degraded counts → HEALTHY."""
        checker = self._make_checker()
        results = {
            "neo4j": self._result("neo4j", ServiceCategory.RAG, ServiceStatus.DISABLED),
            "neon": self._result("neon", ServiceCategory.RAG, ServiceStatus.DISABLED),
        }
        # All disabled => no unhealthy, no degraded, no healthy => 0/0 → HEALTHY branch
        status = checker._calculate_overall_status(results)
        assert status == ServiceStatus.HEALTHY

    def test_healthy_and_disabled_returns_healthy(self):
        """Healthy + Disabled should be HEALTHY."""
        checker = self._make_checker()
        results = {
            "database": self._result("database", ServiceCategory.DATABASE, ServiceStatus.HEALTHY),
            "neo4j": self._result("neo4j", ServiceCategory.RAG, ServiceStatus.DISABLED),
        }
        status = checker._calculate_overall_status(results)
        assert status == ServiceStatus.HEALTHY

    def test_critical_db_unhealthy_overrides(self):
        """Database unhealthy should return UNHEALTHY regardless of others."""
        checker = self._make_checker()
        results = {
            "database": self._result("database", ServiceCategory.DATABASE, ServiceStatus.UNHEALTHY),
            "neo4j": self._result("neo4j", ServiceCategory.RAG, ServiceStatus.HEALTHY),
        }
        status = checker._calculate_overall_status(results)
        assert status == ServiceStatus.UNHEALTHY

    def test_majority_unhealthy(self):
        """If more than half of services are unhealthy, overall is UNHEALTHY."""
        checker = self._make_checker()
        results = {
            "svc1": self._result("svc1", ServiceCategory.EXTERNAL, ServiceStatus.UNHEALTHY),
            "svc2": self._result("svc2", ServiceCategory.EXTERNAL, ServiceStatus.UNHEALTHY),
            "svc3": self._result("svc3", ServiceCategory.EXTERNAL, ServiceStatus.HEALTHY),
        }
        status = checker._calculate_overall_status(results)
        assert status == ServiceStatus.UNHEALTHY

    def test_single_non_critical_unhealthy_is_degraded(self):
        """A single non-critical unhealthy among healthy → DEGRADED."""
        checker = self._make_checker()
        results = {
            "svc1": self._result("svc1", ServiceCategory.EXTERNAL, ServiceStatus.HEALTHY),
            "svc2": self._result("svc2", ServiceCategory.RAG, ServiceStatus.UNHEALTHY),
            "svc3": self._result("svc3", ServiceCategory.EXTERNAL, ServiceStatus.HEALTHY),
        }
        status = checker._calculate_overall_status(results)
        assert status == ServiceStatus.DEGRADED


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

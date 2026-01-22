"""
Unified Health Check API

Provides centralized health monitoring for all application services.
Aggregates health checks from RAG, STT providers, database, and AI providers.

Features:
- Singleton pattern for consistent state across application
- Cached health results with configurable TTL
- Startup diagnostics with detailed reporting
- Category-based service organization
- Graceful degradation reporting

Usage:
    from utils.health_checker import get_health_checker, run_startup_diagnostics

    # At startup
    report = run_startup_diagnostics()
    if not report.can_operate:
        logger.warning("Limited functionality due to unavailable services")

    # During operation
    checker = get_health_checker()
    report = checker.check_all()
    print(f"Overall status: {report.overall_status}")
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Callable, Any

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================

class ServiceStatus(Enum):
    """Health status for a service."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class ServiceCategory(Enum):
    """Category of service for organization."""
    RAG = "rag"
    AI_PROVIDER = "ai_provider"
    STT_PROVIDER = "stt_provider"
    TTS_PROVIDER = "tts_provider"
    DATABASE = "database"
    EXTERNAL = "external"


@dataclass
class ServiceHealthResult:
    """Health check result for a single service."""
    service_name: str
    category: ServiceCategory
    status: ServiceStatus
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    last_check: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)

    def is_healthy(self) -> bool:
        """Check if service is operational."""
        return self.status in (ServiceStatus.HEALTHY, ServiceStatus.DEGRADED)


@dataclass
class HealthReport:
    """Aggregated health report for all services."""
    overall_status: ServiceStatus
    services: Dict[str, ServiceHealthResult]
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def healthy_services(self) -> List[str]:
        """List of healthy service names."""
        return [name for name, result in self.services.items()
                if result.status == ServiceStatus.HEALTHY]

    @property
    def unhealthy_services(self) -> List[str]:
        """List of unhealthy service names."""
        return [name for name, result in self.services.items()
                if result.status == ServiceStatus.UNHEALTHY]

    @property
    def degraded_services(self) -> List[str]:
        """List of degraded service names."""
        return [name for name, result in self.services.items()
                if result.status == ServiceStatus.DEGRADED]

    @property
    def can_operate(self) -> bool:
        """Check if application can operate with basic functionality.

        Returns True if database is available (core functionality).
        """
        db_result = self.services.get("database")
        if db_result and db_result.status == ServiceStatus.UNHEALTHY:
            return False
        return True

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "overall_status": self.overall_status.value,
            "timestamp": self.timestamp.isoformat(),
            "can_operate": self.can_operate,
            "services": {
                name: {
                    "status": result.status.value,
                    "category": result.category.value,
                    "latency_ms": result.latency_ms,
                    "error_message": result.error_message,
                }
                for name, result in self.services.items()
            },
            "summary": {
                "healthy": len(self.healthy_services),
                "unhealthy": len(self.unhealthy_services),
                "degraded": len(self.degraded_services),
                "total": len(self.services),
            }
        }


# =============================================================================
# Health Check Functions
# =============================================================================

def _check_database() -> ServiceHealthResult:
    """Check database connectivity and health."""
    start_time = time.perf_counter()
    try:
        from database.database import get_session

        with get_session() as session:
            # Simple query to verify connectivity
            session.execute("SELECT 1")

        latency = (time.perf_counter() - start_time) * 1000
        return ServiceHealthResult(
            service_name="database",
            category=ServiceCategory.DATABASE,
            status=ServiceStatus.HEALTHY,
            latency_ms=latency,
        )
    except Exception as e:
        latency = (time.perf_counter() - start_time) * 1000
        return ServiceHealthResult(
            service_name="database",
            category=ServiceCategory.DATABASE,
            status=ServiceStatus.UNHEALTHY,
            latency_ms=latency,
            error_message=str(e),
        )


def _check_neo4j() -> ServiceHealthResult:
    """Check Neo4j knowledge graph connectivity."""
    start_time = time.perf_counter()
    try:
        from rag.health_manager import get_health_manager

        health_mgr = get_health_manager()
        health = health_mgr.check_neo4j()

        latency = (time.perf_counter() - start_time) * 1000
        status = ServiceStatus.HEALTHY if health.healthy else ServiceStatus.UNHEALTHY

        return ServiceHealthResult(
            service_name="neo4j",
            category=ServiceCategory.RAG,
            status=status,
            latency_ms=health.latency_ms if health.latency_ms else latency,
            error_message=health.error_message,
            details={"circuit_state": health.circuit_state},
        )
    except ImportError:
        return ServiceHealthResult(
            service_name="neo4j",
            category=ServiceCategory.RAG,
            status=ServiceStatus.DISABLED,
            error_message="RAG module not available",
        )
    except Exception as e:
        latency = (time.perf_counter() - start_time) * 1000
        return ServiceHealthResult(
            service_name="neo4j",
            category=ServiceCategory.RAG,
            status=ServiceStatus.UNHEALTHY,
            latency_ms=latency,
            error_message=str(e),
        )


def _check_neon() -> ServiceHealthResult:
    """Check Neon PostgreSQL vector store connectivity."""
    start_time = time.perf_counter()
    try:
        from rag.health_manager import get_health_manager

        health_mgr = get_health_manager()
        health = health_mgr.check_neon()

        latency = (time.perf_counter() - start_time) * 1000
        status = ServiceStatus.HEALTHY if health.healthy else ServiceStatus.UNHEALTHY

        return ServiceHealthResult(
            service_name="neon",
            category=ServiceCategory.RAG,
            status=status,
            latency_ms=health.latency_ms if health.latency_ms else latency,
            error_message=health.error_message,
            details={"circuit_state": health.circuit_state},
        )
    except ImportError:
        return ServiceHealthResult(
            service_name="neon",
            category=ServiceCategory.RAG,
            status=ServiceStatus.DISABLED,
            error_message="RAG module not available",
        )
    except Exception as e:
        latency = (time.perf_counter() - start_time) * 1000
        return ServiceHealthResult(
            service_name="neon",
            category=ServiceCategory.RAG,
            status=ServiceStatus.UNHEALTHY,
            latency_ms=latency,
            error_message=str(e),
        )


def _check_embedding() -> ServiceHealthResult:
    """Check embedding service (OpenAI) connectivity."""
    start_time = time.perf_counter()
    try:
        from rag.health_manager import get_health_manager

        health_mgr = get_health_manager()
        health = health_mgr.check_openai()

        latency = (time.perf_counter() - start_time) * 1000
        status = ServiceStatus.HEALTHY if health.healthy else ServiceStatus.UNHEALTHY

        return ServiceHealthResult(
            service_name="embedding",
            category=ServiceCategory.RAG,
            status=status,
            latency_ms=health.latency_ms if health.latency_ms else latency,
            error_message=health.error_message,
            details={"circuit_state": health.circuit_state},
        )
    except ImportError:
        return ServiceHealthResult(
            service_name="embedding",
            category=ServiceCategory.RAG,
            status=ServiceStatus.DISABLED,
            error_message="RAG module not available",
        )
    except Exception as e:
        latency = (time.perf_counter() - start_time) * 1000
        return ServiceHealthResult(
            service_name="embedding",
            category=ServiceCategory.RAG,
            status=ServiceStatus.UNHEALTHY,
            latency_ms=latency,
            error_message=str(e),
        )


def _check_stt_provider() -> ServiceHealthResult:
    """Check configured STT provider connectivity."""
    start_time = time.perf_counter()
    try:
        from settings.settings import SETTINGS
        from stt_providers.factory import get_stt_provider

        provider_name = SETTINGS.get("stt_provider", "groq")
        provider = get_stt_provider(provider_name)

        if provider is None:
            return ServiceHealthResult(
                service_name=f"stt_{provider_name}",
                category=ServiceCategory.STT_PROVIDER,
                status=ServiceStatus.DISABLED,
                error_message=f"Provider '{provider_name}' not configured",
            )

        # Try test_connection if available
        if hasattr(provider, "test_connection"):
            is_healthy = provider.test_connection()
            latency = (time.perf_counter() - start_time) * 1000

            return ServiceHealthResult(
                service_name=f"stt_{provider_name}",
                category=ServiceCategory.STT_PROVIDER,
                status=ServiceStatus.HEALTHY if is_healthy else ServiceStatus.UNHEALTHY,
                latency_ms=latency,
            )

        # Provider exists but no test method
        latency = (time.perf_counter() - start_time) * 1000
        return ServiceHealthResult(
            service_name=f"stt_{provider_name}",
            category=ServiceCategory.STT_PROVIDER,
            status=ServiceStatus.UNKNOWN,
            latency_ms=latency,
            error_message="No test_connection method",
        )

    except ImportError as e:
        return ServiceHealthResult(
            service_name="stt",
            category=ServiceCategory.STT_PROVIDER,
            status=ServiceStatus.DISABLED,
            error_message=f"STT module not available: {e}",
        )
    except Exception as e:
        latency = (time.perf_counter() - start_time) * 1000
        return ServiceHealthResult(
            service_name="stt",
            category=ServiceCategory.STT_PROVIDER,
            status=ServiceStatus.UNHEALTHY,
            latency_ms=latency,
            error_message=str(e),
        )


# =============================================================================
# Unified Health Checker
# =============================================================================

class UnifiedHealthChecker:
    """
    Aggregates health checks from all application services.

    Thread-safe singleton that caches health results and provides
    unified reporting across all service categories.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, cache_ttl: int = 30):
        """Initialize health checker.

        Args:
            cache_ttl: Time-to-live for cached health results in seconds
        """
        if self._initialized:
            return

        self._cache_ttl = cache_ttl
        self._cache: Dict[str, ServiceHealthResult] = {}
        self._cache_times: Dict[str, float] = {}
        self._cache_lock = threading.Lock()
        self._checks: Dict[str, Callable[[], ServiceHealthResult]] = {}

        # Register default health checks
        self._register_default_checks()
        self._initialized = True

    def _register_default_checks(self):
        """Register default health check functions."""
        self.register("database", _check_database)
        self.register("neo4j", _check_neo4j)
        self.register("neon", _check_neon)
        self.register("embedding", _check_embedding)
        self.register("stt", _check_stt_provider)

    def register(self, name: str, check_func: Callable[[], ServiceHealthResult]):
        """Register a health check function.

        Args:
            name: Service name
            check_func: Function that returns ServiceHealthResult
        """
        self._checks[name] = check_func

    def unregister(self, name: str):
        """Remove a health check.

        Args:
            name: Service name to remove
        """
        self._checks.pop(name, None)
        with self._cache_lock:
            self._cache.pop(name, None)
            self._cache_times.pop(name, None)

    def check(self, name: str, force: bool = False) -> Optional[ServiceHealthResult]:
        """Check health of a specific service.

        Args:
            name: Service name
            force: Bypass cache and force fresh check

        Returns:
            ServiceHealthResult or None if service not registered
        """
        if name not in self._checks:
            return None

        current_time = time.time()

        # Check cache
        if not force:
            with self._cache_lock:
                if name in self._cache:
                    cache_age = current_time - self._cache_times.get(name, 0)
                    if cache_age < self._cache_ttl:
                        return self._cache[name]

        # Run health check
        try:
            result = self._checks[name]()
        except Exception as e:
            result = ServiceHealthResult(
                service_name=name,
                category=ServiceCategory.EXTERNAL,
                status=ServiceStatus.UNHEALTHY,
                error_message=f"Health check failed: {e}",
            )

        # Update cache
        with self._cache_lock:
            self._cache[name] = result
            self._cache_times[name] = current_time

        return result

    def check_all(self, force: bool = False) -> HealthReport:
        """Check health of all registered services.

        Args:
            force: Bypass cache and force fresh checks

        Returns:
            HealthReport with all service results
        """
        results: Dict[str, ServiceHealthResult] = {}

        for name in self._checks:
            result = self.check(name, force=force)
            if result:
                results[name] = result

        # Determine overall status
        overall = self._calculate_overall_status(results)

        return HealthReport(
            overall_status=overall,
            services=results,
        )

    def check_category(
        self, category: ServiceCategory, force: bool = False
    ) -> Dict[str, ServiceHealthResult]:
        """Check health of services in a specific category.

        Args:
            category: ServiceCategory to check
            force: Bypass cache

        Returns:
            Dict of service name to health result
        """
        results = {}

        for name in self._checks:
            result = self.check(name, force=force)
            if result and result.category == category:
                results[name] = result

        return results

    def _calculate_overall_status(
        self, results: Dict[str, ServiceHealthResult]
    ) -> ServiceStatus:
        """Calculate overall status from individual results."""
        if not results:
            return ServiceStatus.UNKNOWN

        statuses = [r.status for r in results.values()]

        # If any critical service is unhealthy, overall is unhealthy
        critical_services = {"database"}
        for name in critical_services:
            if name in results and results[name].status == ServiceStatus.UNHEALTHY:
                return ServiceStatus.UNHEALTHY

        # Count status types
        unhealthy_count = sum(1 for s in statuses if s == ServiceStatus.UNHEALTHY)
        degraded_count = sum(1 for s in statuses if s == ServiceStatus.DEGRADED)
        healthy_count = sum(1 for s in statuses if s == ServiceStatus.HEALTHY)

        # Determine overall
        total = len(statuses)
        if unhealthy_count == 0 and degraded_count == 0:
            return ServiceStatus.HEALTHY
        elif unhealthy_count > total / 2:
            return ServiceStatus.UNHEALTHY
        else:
            return ServiceStatus.DEGRADED

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache statistics
        """
        with self._cache_lock:
            current_time = time.time()
            return {
                "cached_services": list(self._cache.keys()),
                "cache_ttl": self._cache_ttl,
                "cache_ages": {
                    name: current_time - t
                    for name, t in self._cache_times.items()
                },
            }

    def clear_cache(self):
        """Clear all cached health results."""
        with self._cache_lock:
            self._cache.clear()
            self._cache_times.clear()


# =============================================================================
# Module-Level Functions
# =============================================================================

_health_checker: Optional[UnifiedHealthChecker] = None
_health_checker_lock = threading.Lock()


def get_health_checker() -> UnifiedHealthChecker:
    """Get the singleton health checker instance.

    Returns:
        UnifiedHealthChecker instance
    """
    global _health_checker
    if _health_checker is None:
        with _health_checker_lock:
            if _health_checker is None:
                _health_checker = UnifiedHealthChecker()
    return _health_checker


def run_startup_diagnostics(log_results: bool = True) -> HealthReport:
    """Run comprehensive health checks at application startup.

    Performs fresh health checks on all services and logs results.

    Args:
        log_results: Whether to log the results

    Returns:
        HealthReport with all results
    """
    checker = get_health_checker()
    report = checker.check_all(force=True)

    if log_results:
        # Log summary
        logger.info(
            f"Startup diagnostics complete: {report.overall_status.value} "
            f"({len(report.healthy_services)} healthy, "
            f"{len(report.unhealthy_services)} unhealthy, "
            f"{len(report.degraded_services)} degraded)"
        )

        # Log unhealthy services
        for name in report.unhealthy_services:
            result = report.services[name]
            logger.warning(
                f"Service '{name}' is unhealthy: {result.error_message or 'Unknown error'}"
            )

        # Log degraded services
        for name in report.degraded_services:
            result = report.services[name]
            logger.info(f"Service '{name}' is degraded: {result.error_message or ''}")

        if not report.can_operate:
            logger.error(
                "Critical services unavailable - application may have limited functionality"
            )

    return report


def check_service(name: str) -> Optional[ServiceHealthResult]:
    """Quick check of a single service.

    Args:
        name: Service name

    Returns:
        ServiceHealthResult or None
    """
    return get_health_checker().check(name)


def is_service_healthy(name: str) -> bool:
    """Check if a service is healthy.

    Args:
        name: Service name

    Returns:
        True if service is healthy or degraded
    """
    result = check_service(name)
    return result is not None and result.is_healthy()

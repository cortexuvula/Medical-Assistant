"""
Environment Variable Schema

Documents all environment variables used by the application
and provides startup validation with warnings for missing recommended vars.
"""

from dataclasses import dataclass
from typing import Optional
import os

from utils.constants import DEFAULT_OLLAMA_URL, DEFAULT_NEO4J_BOLT_URL
from utils.structured_logging import get_logger

logger = get_logger(__name__)


@dataclass
class EnvVar:
    """Describes a single environment variable used by the application."""

    name: str
    description: str
    required: bool = False
    default: Optional[str] = None
    category: str = "general"
    sensitive: bool = False  # If True, don't log the value


# ---------------------------------------------------------------------------
# Complete catalog of environment variables referenced throughout the codebase
# ---------------------------------------------------------------------------

ENV_SCHEMA: list[EnvVar] = [
    # ── Environment / App Configuration ────────────────────────────────
    EnvVar(
        name="MEDICAL_ASSISTANT_ENV",
        description="Application environment mode (development, production, testing)",
        default="production",
        category="app_config",
    ),
    EnvVar(
        name="MEDICAL_ASSISTANT_LOG_LEVEL",
        description="Override log level (DEBUG, INFO, WARNING, ERROR)",
        default="",
        category="app_config",
    ),
    EnvVar(
        name="MEDICAL_ASSISTANT_MASTER_KEY",
        description="Optional master encryption key for API key storage (overrides machine-derived key)",
        category="app_config",
        sensitive=True,
    ),
    EnvVar(
        name="MEDICAL_ASSISTANT_STORAGE",
        description="Override default storage folder for recordings and exports",
        category="app_config",
    ),
    EnvVar(
        name="RECOGNITION_LANGUAGE",
        description="Speech recognition language code (e.g. en-US, es-ES, fr-FR)",
        default="en-US",
        category="app_config",
    ),
    EnvVar(
        name="GC_DISABLE_GAME_CONTROLLER_DISCOVERY",
        description="Suppress macOS game controller discovery (set to 1)",
        default="1",
        category="app_config",
    ),

    # ── AI Provider API Keys ───────────────────────────────────────────
    EnvVar(
        name="OPENAI_API_KEY",
        description="OpenAI API key (https://platform.openai.com/api-keys)",
        category="ai_provider",
        sensitive=True,
    ),
    EnvVar(
        name="ANTHROPIC_API_KEY",
        description="Anthropic Claude API key (https://console.anthropic.com/)",
        category="ai_provider",
        sensitive=True,
    ),
    EnvVar(
        name="GEMINI_API_KEY",
        description="Google Gemini API key (https://aistudio.google.com/app/apikey)",
        category="ai_provider",
        sensitive=True,
    ),
    EnvVar(
        name="GROK_API_KEY",
        description="Grok (xAI) API key (https://console.x.ai/)",
        category="ai_provider",
        sensitive=True,
    ),
    EnvVar(
        name="PERPLEXITY_API_KEY",
        description="Perplexity API key (https://www.perplexity.ai/settings/api)",
        category="ai_provider",
        sensitive=True,
    ),

    # ── Local Model Configuration ──────────────────────────────────────
    EnvVar(
        name="OLLAMA_API_URL",
        description="Ollama server URL for local LLM inference",
        default=DEFAULT_OLLAMA_URL,
        category="ai_provider",
    ),
    EnvVar(
        name="OLLAMA_HOST",
        description="Ollama host URL (alternative to OLLAMA_API_URL)",
        default=DEFAULT_OLLAMA_URL,
        category="ai_provider",
    ),

    # ── STT Provider API Keys ──────────────────────────────────────────
    EnvVar(
        name="GROQ_API_KEY",
        description="Groq API key for Whisper STT (https://console.groq.com/keys)",
        category="stt_provider",
        sensitive=True,
    ),
    EnvVar(
        name="DEEPGRAM_API_KEY",
        description="Deepgram API key for Nova-2 Medical STT (https://console.deepgram.com/)",
        category="stt_provider",
        sensitive=True,
    ),
    EnvVar(
        name="ELEVENLABS_API_KEY",
        description="ElevenLabs API key for STT and TTS (https://elevenlabs.io/app/settings/api-keys)",
        category="stt_provider",
        sensitive=True,
    ),

    # ── RAG / Vector Database ──────────────────────────────────────────
    EnvVar(
        name="NEON_DATABASE_URL",
        description="Neon PostgreSQL connection URL for RAG vector storage (pgvector)",
        category="database",
        sensitive=True,
    ),

    # ── Knowledge Graph (Neo4j) ────────────────────────────────────────
    EnvVar(
        name="NEO4J_URI",
        description="Neo4j database URI for knowledge graph (e.g. bolt://localhost:7687)",
        category="database",
    ),
    EnvVar(
        name="NEO4J_USER",
        description="Neo4j database username",
        default="neo4j",
        category="database",
    ),
    EnvVar(
        name="NEO4J_PASSWORD",
        description="Neo4j database password",
        category="database",
        sensitive=True,
    ),

    # ── Clinical Guidelines Database ───────────────────────────────────
    EnvVar(
        name="CLINICAL_GUIDELINES_DATABASE_URL",
        description="Neon PostgreSQL URL for clinical guidelines (separate from patient data)",
        category="database",
        sensitive=True,
    ),
    EnvVar(
        name="CLINICAL_GUIDELINES_NEO4J_URI",
        description="Neo4j URI for clinical guidelines knowledge graph",
        category="database",
    ),
    EnvVar(
        name="CLINICAL_GUIDELINES_NEO4J_USER",
        description="Neo4j username for clinical guidelines",
        default="neo4j",
        category="database",
    ),
    EnvVar(
        name="CLINICAL_GUIDELINES_NEO4J_PASSWORD",
        description="Neo4j password for clinical guidelines",
        category="database",
        sensitive=True,
    ),

    # ── OCR ────────────────────────────────────────────────────────────
    EnvVar(
        name="AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT",
        description="Azure Document Intelligence endpoint URL for OCR",
        category="ocr",
    ),
    EnvVar(
        name="AZURE_DOCUMENT_INTELLIGENCE_KEY",
        description="Azure Document Intelligence API key",
        category="ocr",
        sensitive=True,
    ),

    # ── Monitoring ─────────────────────────────────────────────────────
    EnvVar(
        name="SENTRY_DSN",
        description="Sentry DSN for error monitoring and performance tracking",
        category="monitoring",
        sensitive=True,
    ),

    # ── Embedding Cache ────────────────────────────────────────────────
    EnvVar(
        name="REDIS_URL",
        description="Redis connection URL for embedding cache (e.g. redis://localhost:6379)",
        category="cache",
    ),
    EnvVar(
        name="REDIS_PREFIX",
        description="Redis key prefix for embedding cache",
        default="medassist:embedding:",
        category="cache",
    ),
    EnvVar(
        name="EMBEDDING_CACHE_BACKEND",
        description="Embedding cache backend (sqlite, redis, fallback, auto)",
        default="auto",
        category="cache",
    ),
    EnvVar(
        name="EMBEDDING_CACHE_FALLBACK",
        description="Enable fallback from Redis to SQLite (true/false)",
        default="true",
        category="cache",
    ),
    EnvVar(
        name="EMBEDDING_CACHE_MAX_ENTRIES",
        description="Maximum number of cached embeddings",
        default="10000",
        category="cache",
    ),
    EnvVar(
        name="EMBEDDING_CACHE_MAX_AGE_DAYS",
        description="Maximum age in days for cached embeddings",
        default="30",
        category="cache",
    ),
    EnvVar(
        name="EMBEDDING_CACHE_RETRY_SECONDS",
        description="Seconds to wait before retrying failed cache backend",
        default="60",
        category="cache",
    ),

    # ── Debug ──────────────────────────────────────────────────────────
    EnvVar(
        name="CHAT_DEBUG_ENABLED",
        description="Enable chat debug logging (set to 'true' to activate)",
        default="",
        category="debug",
    ),
]


def validate_environment() -> list[str]:
    """Validate environment variables at startup.

    Checks all variables in ENV_SCHEMA against the current environment.
    Logs a summary grouped by category and returns a list of warning
    messages for any required variables that are missing.

    This function intentionally never blocks startup -- it only logs and warns.
    """
    warnings: list[str] = []
    set_vars: list[str] = []
    unset_optional: list[str] = []

    for var in ENV_SCHEMA:
        value = os.getenv(var.name)
        if var.required and not value and not var.default:
            msg = f"Required env var {var.name} is not set: {var.description}"
            warnings.append(msg)
            logger.warning(msg)
        elif value:
            # Variable is set -- log it (redact sensitive values)
            display = "****" if var.sensitive else value
            set_vars.append(f"{var.name}={display}")
        elif not var.default:
            unset_optional.append(var.name)
            logger.debug(f"Optional env var {var.name} not set: {var.description}")

    # Summary log
    if set_vars:
        logger.info(
            f"Environment: {len(set_vars)} variable(s) configured: "
            + ", ".join(set_vars)
        )
    if unset_optional:
        logger.debug(
            f"Environment: {len(unset_optional)} optional variable(s) not set: "
            + ", ".join(unset_optional)
        )

    return warnings

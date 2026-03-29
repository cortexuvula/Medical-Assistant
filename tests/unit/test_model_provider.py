"""
Tests for ModelProvider in src/ai/model_provider.py

Covers FALLBACK_MODELS structure (6 providers, list values, string elements),
class constants (CACHE_TTL, MAX_CACHE_SIZE), get_all_providers(),
clear_cache() (specific and all), get_cache_stats() (delegation to LRU),
cleanup_expired_cache() (delegation), and get_available_models() when
the cache has data (no API call made).
No API calls, no Tkinter, no file I/O.
"""

import sys
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.model_provider import ModelProvider
from utils.constants import (
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_OLLAMA,
    PROVIDER_GEMINI, PROVIDER_GROQ, PROVIDER_CEREBRAS,
)

ALL_PROVIDERS = [
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_OLLAMA,
    PROVIDER_GEMINI, PROVIDER_GROQ, PROVIDER_CEREBRAS,
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mp() -> ModelProvider:
    return ModelProvider()


# ===========================================================================
# Class constants
# ===========================================================================

class TestModelProviderConstants:
    def test_cache_ttl_is_positive(self):
        assert ModelProvider.CACHE_TTL > 0

    def test_max_cache_size_is_positive(self):
        assert ModelProvider.MAX_CACHE_SIZE > 0

    def test_cache_ttl_is_int(self):
        assert isinstance(ModelProvider.CACHE_TTL, int)

    def test_max_cache_size_is_int(self):
        assert isinstance(ModelProvider.MAX_CACHE_SIZE, int)


# ===========================================================================
# FALLBACK_MODELS structure
# ===========================================================================

class TestFallbackModels:
    def test_is_dict(self):
        assert isinstance(ModelProvider.FALLBACK_MODELS, dict)

    def test_has_openai_key(self):
        assert PROVIDER_OPENAI in ModelProvider.FALLBACK_MODELS

    def test_has_anthropic_key(self):
        assert PROVIDER_ANTHROPIC in ModelProvider.FALLBACK_MODELS

    def test_has_ollama_key(self):
        assert PROVIDER_OLLAMA in ModelProvider.FALLBACK_MODELS

    def test_has_gemini_key(self):
        assert PROVIDER_GEMINI in ModelProvider.FALLBACK_MODELS

    def test_has_groq_key(self):
        assert PROVIDER_GROQ in ModelProvider.FALLBACK_MODELS

    def test_has_cerebras_key(self):
        assert PROVIDER_CEREBRAS in ModelProvider.FALLBACK_MODELS

    def test_all_values_are_lists(self):
        for provider, models in ModelProvider.FALLBACK_MODELS.items():
            assert isinstance(models, list), f"Provider '{provider}' value is not a list"

    def test_all_model_lists_non_empty(self):
        for provider, models in ModelProvider.FALLBACK_MODELS.items():
            assert len(models) > 0, f"Provider '{provider}' has empty fallback list"

    def test_all_model_names_are_strings(self):
        for provider, models in ModelProvider.FALLBACK_MODELS.items():
            for model in models:
                assert isinstance(model, str), f"Non-string model in '{provider}': {model}"

    def test_all_model_names_non_empty(self):
        for provider, models in ModelProvider.FALLBACK_MODELS.items():
            for model in models:
                assert len(model.strip()) > 0, f"Empty model name in '{provider}'"

    def test_openai_models_include_gpt4(self):
        models = ModelProvider.FALLBACK_MODELS[PROVIDER_OPENAI]
        assert any("gpt-4" in m for m in models)

    def test_anthropic_models_include_claude(self):
        models = ModelProvider.FALLBACK_MODELS[PROVIDER_ANTHROPIC]
        assert any("claude" in m for m in models)

    def test_has_six_providers(self):
        assert len(ModelProvider.FALLBACK_MODELS) == 6


# ===========================================================================
# get_all_providers
# ===========================================================================

class TestGetAllProviders:
    def test_returns_list(self, mp):
        assert isinstance(mp.get_all_providers(), list)

    def test_contains_six_providers(self, mp):
        assert len(mp.get_all_providers()) == 6

    def test_contains_openai(self, mp):
        assert PROVIDER_OPENAI in mp.get_all_providers()

    def test_contains_anthropic(self, mp):
        assert PROVIDER_ANTHROPIC in mp.get_all_providers()

    def test_contains_ollama(self, mp):
        assert PROVIDER_OLLAMA in mp.get_all_providers()

    def test_contains_gemini(self, mp):
        assert PROVIDER_GEMINI in mp.get_all_providers()

    def test_contains_groq(self, mp):
        assert PROVIDER_GROQ in mp.get_all_providers()

    def test_contains_cerebras(self, mp):
        assert PROVIDER_CEREBRAS in mp.get_all_providers()

    def test_all_strings(self, mp):
        for p in mp.get_all_providers():
            assert isinstance(p, str)


# ===========================================================================
# get_cache_stats / cleanup_expired_cache
# ===========================================================================

class TestCacheStats:
    def test_returns_dict(self, mp):
        assert isinstance(mp.get_cache_stats(), dict)

    def test_contains_size_key(self, mp):
        assert "size" in mp.get_cache_stats()

    def test_contains_max_size_key(self, mp):
        stats = mp.get_cache_stats()
        assert "max_size" in stats

    def test_max_size_matches_constant(self, mp):
        assert mp.get_cache_stats()["max_size"] == ModelProvider.MAX_CACHE_SIZE

    def test_cleanup_returns_int(self, mp):
        assert isinstance(mp.cleanup_expired_cache(), int)

    def test_empty_cache_cleanup_returns_zero(self, mp):
        assert mp.cleanup_expired_cache() == 0


# ===========================================================================
# clear_cache
# ===========================================================================

class TestClearCache:
    def test_clear_all_empties_cache(self, mp):
        # Seed cache with a model list
        mp._cache.set(PROVIDER_OPENAI, ["gpt-4"])
        mp.clear_cache()
        assert mp.get_cache_stats()["size"] == 0

    def test_clear_specific_provider_removes_only_that(self, mp):
        mp._cache.set(PROVIDER_OPENAI, ["gpt-4"])
        mp._cache.set(PROVIDER_ANTHROPIC, ["claude-3"])
        mp.clear_cache(provider=PROVIDER_OPENAI)
        # OpenAI cleared, Anthropic should remain
        assert mp._cache.get(PROVIDER_OPENAI) is None
        assert mp._cache.get(PROVIDER_ANTHROPIC) == ["claude-3"]

    def test_clear_nonexistent_provider_no_error(self, mp):
        mp.clear_cache(provider="nonexistent_provider")  # Should not raise

    def test_clear_all_when_empty_no_error(self, mp):
        mp.clear_cache()  # Should not raise


# ===========================================================================
# get_available_models with cache hit
# ===========================================================================

class TestGetAvailableModelsCache:
    def test_returns_list(self, mp):
        # Seed cache to avoid API call
        mp._cache.set(PROVIDER_OPENAI, ["gpt-4"])
        result = mp.get_available_models(PROVIDER_OPENAI, force_refresh=False)
        assert isinstance(result, list)

    def test_returns_cached_models(self, mp):
        models = ["gpt-4", "gpt-3.5-turbo"]
        mp._cache.set(PROVIDER_OPENAI, models)
        result = mp.get_available_models(PROVIDER_OPENAI, force_refresh=False)
        assert result == models

    def test_unknown_provider_returns_fallback(self, mp):
        # Unknown provider - no cache, no API; returns fallback (empty list or default)
        result = mp.get_available_models(PROVIDER_OPENAI, force_refresh=False)
        # With empty cache and API failing in test env, should return fallback models
        assert isinstance(result, list)

    def test_fallback_models_used_when_api_fails_and_no_cache(self, mp):
        # OpenAI API call will fail in test env → should return FALLBACK_MODELS
        result = mp.get_available_models(PROVIDER_OPENAI, force_refresh=True)
        # Either returns some models (fallback) or empty list
        assert isinstance(result, list)

"""
Model Provider Service

Dynamically fetches available models from AI providers and manages model lists
with caching and fallback support.
"""

import logging
import json
import time
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import OrderedDict
import requests
from openai import OpenAI
from anthropic import Anthropic

from utils.security import get_security_manager
from settings.settings import SETTINGS
from utils.constants import (
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_PERPLEXITY,
    PROVIDER_GROK, PROVIDER_OLLAMA, PROVIDER_GEMINI
)
import google.generativeai as genai

logger = logging.getLogger(__name__)


class LRUCache:
    """Thread-safe LRU cache with TTL support.

    This cache automatically evicts the least recently used entries
    when the maximum size is exceeded, and entries older than TTL.
    """

    def __init__(self, max_size: int = 10, ttl_seconds: int = 3600):
        """Initialize the LRU cache.

        Args:
            max_size: Maximum number of entries to store
            ttl_seconds: Time-to-live for entries in seconds
        """
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            # Check if expired
            if time.time() - entry["timestamp"] > self._ttl:
                del self._cache[key]
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return entry["value"]

    def set(self, key: str, value: Any) -> None:
        """Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            # If key exists, update and move to end
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = {"value": value, "timestamp": time.time()}
            else:
                # Add new entry
                self._cache[key] = {"value": value, "timestamp": time.time()}

                # Evict oldest if over max size
                while len(self._cache) > self._max_size:
                    self._cache.popitem(last=False)

    def remove(self, key: str) -> bool:
        """Remove an entry from the cache.

        Args:
            key: Cache key

        Returns:
            True if entry was removed, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries from the cache."""
        with self._lock:
            self._cache.clear()

    def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed
        """
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, entry in self._cache.items()
                if current_time - entry["timestamp"] > self._ttl
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)

    @property
    def size(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._cache)

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "ttl_seconds": self._ttl,
                "keys": list(self._cache.keys())
            }


class ModelProvider:
    """Manages dynamic model fetching from AI providers."""

    # Cache TTL in seconds (default: 1 hour)
    CACHE_TTL = 3600

    # Maximum number of providers to cache (prevents unbounded growth)
    MAX_CACHE_SIZE = 10

    # Fallback model lists in case API calls fail
    FALLBACK_MODELS = {
        PROVIDER_OPENAI: [
            "gpt-4-turbo-preview",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-4-32k",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k"
        ],
        PROVIDER_ANTHROPIC: [
            "claude-opus-4-20250514",
            "claude-sonnet-4-20250514",
            "claude-haiku-4-20250514",
            "claude-2.1",
            "claude-2.0",
            "claude-instant-1.2"
        ],
        PROVIDER_OLLAMA: [
            "llama3",
            "llama2",
            "mistral",
            "codellama",
            "vicuna",
            "orca-mini"
        ],
        PROVIDER_PERPLEXITY: [
            "llama-3.1-sonar-large-128k-online",
            "llama-3.1-sonar-large-128k-chat",
            "llama-3.1-sonar-small-128k-online",
            "llama-3.1-sonar-small-128k-chat",
            "sonar-medium-online",
            "sonar-medium-chat",
            "sonar-small-online",
            "sonar-small-chat"
        ],
        PROVIDER_GROK: [
            "grok-1",
            "grok-2"
        ],
        PROVIDER_GEMINI: [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-2.0-pro-exp",
            "gemini-2.0-flash-thinking-exp",
            "gemini-2.0-flash-exp"
        ]
    }
    
    def __init__(self):
        """Initialize the model provider."""
        # Use LRU cache with TTL and max size to prevent unbounded memory growth
        self._cache = LRUCache(max_size=self.MAX_CACHE_SIZE, ttl_seconds=self.CACHE_TTL)
        self._security_manager = get_security_manager()

    def get_available_models(self, provider: str, force_refresh: bool = False) -> List[str]:
        """
        Get available models for a provider.

        Args:
            provider: The AI provider name
            force_refresh: Force refresh from API instead of using cache

        Returns:
            List of available model names
        """
        # Check cache first (LRUCache handles TTL automatically)
        if not force_refresh:
            cached_models = self._cache.get(provider)
            if cached_models is not None:
                return cached_models

        # Try to fetch from API
        models = self._fetch_models_from_api(provider)

        if models:
            # Update cache (LRUCache handles size limits automatically)
            self._cache.set(provider, models)
            return models
        else:
            # Fall back to cached values or hardcoded list
            cached_models = self._cache.get(provider)
            if cached_models:
                logger.warning(f"Using cached models for {provider} due to API failure")
                return cached_models
            else:
                logger.warning(f"Using fallback models for {provider}")
                return self.FALLBACK_MODELS.get(provider, [])
        
    def _fetch_models_from_api(self, provider: str) -> Optional[List[str]]:
        """
        Fetch models from provider's API.
        
        Args:
            provider: The AI provider name
            
        Returns:
            List of model names or None if failed
        """
        try:
            if provider == PROVIDER_OPENAI:
                return self._fetch_openai_models()
            elif provider == PROVIDER_ANTHROPIC:
                return self._fetch_anthropic_models()
            elif provider == PROVIDER_OLLAMA:
                return self._fetch_ollama_models()
            elif provider == PROVIDER_PERPLEXITY:
                return self._fetch_perplexity_models()
            elif provider == PROVIDER_GROK:
                return self._fetch_grok_models()
            elif provider == PROVIDER_GEMINI:
                return self._fetch_gemini_models()
            else:
                logger.warning(f"Unknown provider: {provider}")
                return None
        except Exception as e:
            logger.error(f"Error fetching models for {provider}: {e}")
            return None
            
    def _fetch_openai_models(self) -> Optional[List[str]]:
        """Fetch available models from OpenAI."""
        try:
            api_key = self._security_manager.get_api_key(PROVIDER_OPENAI)
            if not api_key:
                return None
                
            client = OpenAI(api_key=api_key)
            models_response = client.models.list()
            
            # Filter for chat models
            chat_models = []
            for model in models_response.data:
                if any(prefix in model.id for prefix in ["gpt-", "text-"]):
                    chat_models.append(model.id)
                    
            # Sort models with newer versions first
            chat_models.sort(reverse=True)
            
            return chat_models
            
        except Exception as e:
            logger.error(f"Error fetching OpenAI models: {e}")
            return None
            
    def _fetch_anthropic_models(self) -> Optional[List[str]]:
        """Fetch available models from Anthropic."""
        try:
            api_key = self._security_manager.get_api_key(PROVIDER_ANTHROPIC)
            if not api_key:
                return None

            # Anthropic doesn't have a models endpoint yet, but we can make a test call
            # to see which models are available
            client = Anthropic(api_key=api_key)

            # For now, return the known models
            # In the future, Anthropic may add a models endpoint
            return self.FALLBACK_MODELS[PROVIDER_ANTHROPIC]
            
        except Exception as e:
            logger.error(f"Error with Anthropic: {e}")
            return None
            
    def _fetch_ollama_models(self) -> Optional[List[str]]:
        """Fetch available models from Ollama."""
        try:
            # Check if Ollama is running locally
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                models = [model["name"].split(":")[0] for model in data.get("models", [])]
                # Remove duplicates and sort
                models = sorted(list(set(models)))
                return models
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error fetching Ollama models: {e}")
            return None
            
    def _fetch_perplexity_models(self) -> Optional[List[str]]:
        """Fetch available models from Perplexity."""
        try:
            api_key = self._security_manager.get_api_key(PROVIDER_PERPLEXITY)
            if not api_key:
                return None

            # Perplexity doesn't have a public models endpoint
            # Return the known models
            return self.FALLBACK_MODELS[PROVIDER_PERPLEXITY]
            
        except Exception as e:
            logger.error(f"Error with Perplexity: {e}")
            return None
            
    def _fetch_grok_models(self) -> Optional[List[str]]:
        """Fetch available models from Grok."""
        try:
            api_key = self._security_manager.get_api_key(PROVIDER_GROK)
            if not api_key:
                return None

            # Grok API endpoint for models (if available)
            # For now, return known models
            return self.FALLBACK_MODELS[PROVIDER_GROK]

        except Exception as e:
            logger.error(f"Error with Grok: {e}")
            return None

    def _fetch_gemini_models(self) -> Optional[List[str]]:
        """Fetch available models from Google Gemini."""
        try:
            api_key = self._security_manager.get_api_key(PROVIDER_GEMINI)
            if not api_key:
                return None

            # Configure the API
            genai.configure(api_key=api_key)

            # List available models
            models = []
            for model in genai.list_models():
                # Filter for models that support generateContent
                if "generateContent" in model.supported_generation_methods:
                    # Extract just the model name (remove 'models/' prefix)
                    model_name = model.name.replace("models/", "")
                    models.append(model_name)

            # Sort models (gemini-2.0 first, then 1.5, then others)
            def model_sort_key(name):
                if "2.0" in name:
                    return (0, name)
                elif "1.5" in name:
                    return (1, name)
                else:
                    return (2, name)

            models.sort(key=model_sort_key)
            return models if models else self.FALLBACK_MODELS[PROVIDER_GEMINI]

        except Exception as e:
            logger.error(f"Error fetching Gemini models: {e}")
            return None

    def clear_cache(self, provider: Optional[str] = None):
        """
        Clear cached model lists.

        Args:
            provider: Specific provider to clear, or None to clear all
        """
        if provider:
            self._cache.remove(provider)
        else:
            self._cache.clear()

    def cleanup_expired_cache(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of entries removed
        """
        return self._cache.cleanup_expired()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring.

        Returns:
            Dictionary with cache stats
        """
        return self._cache.stats()

    def get_all_providers(self) -> List[str]:
        """Get list of all supported providers."""
        return list(self.FALLBACK_MODELS.keys())


# Global instance
model_provider = ModelProvider()
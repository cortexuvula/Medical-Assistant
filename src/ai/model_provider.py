"""
Model Provider Service

Dynamically fetches available models from AI providers and manages model lists
with caching and fallback support.
"""

import logging
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import requests
from openai import OpenAI
from anthropic import Anthropic

from utils.security import get_security_manager
from settings.settings import SETTINGS
from utils.constants import (
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_PERPLEXITY,
    PROVIDER_GROK, PROVIDER_OLLAMA
)

logger = logging.getLogger(__name__)


class ModelProvider:
    """Manages dynamic model fetching from AI providers."""
    
    # Cache TTL in seconds (default: 1 hour)
    CACHE_TTL = 3600
    
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
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
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
        ]
    }
    
    def __init__(self):
        """Initialize the model provider."""
        self._cache: Dict[str, Dict[str, Any]] = {}
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
        # Check cache first
        if not force_refresh and self._is_cache_valid(provider):
            return self._cache[provider]["models"]
            
        # Try to fetch from API
        models = self._fetch_models_from_api(provider)
        
        if models:
            # Update cache
            self._update_cache(provider, models)
            return models
        else:
            # Fall back to hardcoded list or cached values
            if provider in self._cache:
                logger.warning(f"Using cached models for {provider} due to API failure")
                return self._cache[provider]["models"]
            else:
                logger.warning(f"Using fallback models for {provider}")
                return self.FALLBACK_MODELS.get(provider, [])
                
    def _is_cache_valid(self, provider: str) -> bool:
        """Check if cached data is still valid."""
        if provider not in self._cache:
            return False
            
        cache_entry = self._cache[provider]
        cache_time = cache_entry.get("timestamp", 0)
        current_time = time.time()
        
        return (current_time - cache_time) < self.CACHE_TTL
        
    def _update_cache(self, provider: str, models: List[str]):
        """Update cache with new model list."""
        self._cache[provider] = {
            "models": models,
            "timestamp": time.time()
        }
        
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
            
    def clear_cache(self, provider: Optional[str] = None):
        """
        Clear cached model lists.
        
        Args:
            provider: Specific provider to clear, or None to clear all
        """
        if provider:
            self._cache.pop(provider, None)
        else:
            self._cache.clear()
            
    def get_all_providers(self) -> List[str]:
        """Get list of all supported providers."""
        return list(self.FALLBACK_MODELS.keys())


# Global instance
model_provider = ModelProvider()
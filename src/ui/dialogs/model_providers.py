"""
Model Providers Module

Functions for fetching available AI models from various providers.
"""

import os
import logging
import time
import requests
from typing import List, Dict, Tuple, Optional
from functools import lru_cache

from openai import OpenAI

# Cache TTL constant (seconds)
MODEL_CACHE_TTL_SECONDS = 3600  # 1 hour

# Cache for model lists with TTL
_model_cache: Dict[str, Tuple[float, List[str]]] = {}
_cache_ttl = MODEL_CACHE_TTL_SECONDS


def clear_model_cache(provider: str = None) -> None:
    """Clear the model cache for a specific provider or all providers.

    Args:
        provider: Specific provider to clear cache for, or None to clear all
    """
    global _model_cache
    if provider:
        cache_key = f"{provider}_models"
        if cache_key in _model_cache:
            del _model_cache[cache_key]
            logging.info(f"Cleared model cache for {provider}")
    else:
        _model_cache.clear()
        logging.info("Cleared all model caches")


def get_openai_models() -> List[str]:
    """Fetch available models from OpenAI API."""
    import openai
    try:
        # Create OpenAI client
        client = openai.OpenAI()

        # Make API call to list models
        response = client.models.list()

        # Extract GPT models from response
        models = []
        for model in response.data:
            if "gpt" in model.id.lower():
                models.append(model.id)

        # Add common models in case they're not in the API response
        common_models = [
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
            "gpt-3.5-turbo-1106",
            "gpt-3.5-turbo-0125",
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4-turbo-preview",
            "gpt-4-0125-preview",
            "gpt-4-1106-preview",
            "gpt-4-vision-preview",
            "gpt-4-32k"
        ]

        # Add any missing common models
        for model in common_models:
            if model not in models:
                models.append(model)

        # Return sorted list
        return sorted(models)
    except Exception as e:
        logging.error(f"Error fetching OpenAI models: {str(e)}")
        return get_fallback_openai_models()


def get_fallback_openai_models() -> List[str]:
    """Return a list of common OpenAI models as fallback."""
    logging.info("Using fallback set of common OpenAI models")
    return ["gpt-4o", "gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]


def get_grok_models() -> List[str]:
    """Fetch available models from Grok API."""
    try:
        # Get API key from environment
        api_key = os.getenv("GROK_API_KEY")
        if not api_key:
            logging.error("Grok API key not found in environment variables")
            return get_fallback_grok_models()

        # Make API call to get models using the OpenAI client with x.ai base URL
        try:
            # Initialize client with X.AI base URL
            client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")

            # Make API call to get models
            response = client.models.list()

            # Extract model IDs
            models = []
            for model in response.data:
                if hasattr(model, 'id'):
                    models.append(model.id)

            # Add common models that might be missing
            common_models = ["grok-1", "grok-1.5", "grok-mini"]
            for model in common_models:
                if model not in models:
                    models.append(model)

            return sorted(models)

        except Exception as api_error:
            # Fall back to direct request if OpenAI client approach fails
            logging.warning(f"OpenAI client approach failed, trying direct request: {str(api_error)}")

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            response = requests.get(
                "https://api.x.ai/v1/models",
                headers=headers
            )

            if response.status_code == 200:
                data = response.json()
                # Extract model IDs - adjust according to actual response structure
                if "data" in data:
                    models = [model.get("id") for model in data.get("data", []) if model.get("id")]
                else:
                    models = [model.get("id") for model in data if model.get("id")]

                # Add common models that might be missing
                common_models = ["grok-1", "grok-1.5", "grok-mini"]
                for model in common_models:
                    if model not in models:
                        models.append(model)
                return sorted(models)
            else:
                logging.error(f"Error fetching Grok models: {response.status_code}")
                return get_fallback_grok_models()

    except Exception as e:
        logging.error(f"Error fetching Grok models: {str(e)}")
        return get_fallback_grok_models()


def get_fallback_grok_models() -> List[str]:
    """Return fallback list of common Grok models."""
    return ["grok-1", "grok-1.5", "grok-mini"]


def get_ollama_models() -> List[str]:
    """Fetch available models from Ollama API."""
    try:
        # Make a request to the Ollama API to list models
        response = requests.get("http://localhost:11434/api/tags")

        if response.status_code == 200:
            # Parse the response as JSON
            data = response.json()

            # Extract model names from the response
            models = [model["name"] for model in data["models"]]

            # Sort models alphabetically
            models.sort()

            return models
        else:
            logging.error(f"Error fetching Ollama models: {response.status_code}")
            return []
    except Exception as e:
        logging.error(f"Error fetching Ollama models: {str(e)}")
        return []


def get_perplexity_models() -> List[str]:
    """Return a curated list of Perplexity models.

    Note: Perplexity doesn't have a direct API endpoint for listing models,
    so we use a curated list.
    """
    logging.info("Using curated list of Perplexity models")
    return [
        # Latest curated Perplexity models with context windows
        "sonar-reasoning-pro",    # 128k context
        "sonar-reasoning",        # 128k context
        "sonar-pro",              # 200k context
        "sonar",                  # 128k context
        "r1-1776"                 # 128k context
    ]


def get_fallback_perplexity_models() -> List[str]:
    """Return a list of Perplexity models."""
    logging.info("Using standard list of Perplexity models")
    return [
        "sonar-reasoning-pro",    # 128k context
        "sonar-reasoning",        # 128k context
        "sonar-pro",              # 200k context
        "sonar",                  # 128k context
        "r1-1776"                 # 128k context
    ]


def get_anthropic_models() -> List[str]:
    """Return a list of Anthropic models, fetched dynamically if possible."""
    # Check cache first
    cache_key = "anthropic_models"
    if cache_key in _model_cache:
        cached_time, cached_models = _model_cache[cache_key]
        if time.time() - cached_time < _cache_ttl:
            logging.info("Using cached Anthropic models")
            return cached_models

    try:
        # Try to fetch models dynamically from Anthropic API
        from anthropic import Anthropic
        from utils.security import get_security_manager

        security_manager = get_security_manager()
        api_key = security_manager.get_api_key("anthropic")

        if api_key:
            logging.info("Attempting to fetch Anthropic models from API")
            client = Anthropic(api_key=api_key)

            # Fetch models list from API
            models_response = client.models.list()

            # Extract model IDs from the response
            model_ids = []
            if hasattr(models_response, 'data'):
                for model in models_response.data:
                    if hasattr(model, 'id'):
                        model_ids.append(model.id)
            elif isinstance(models_response, list):
                model_ids = [model.id if hasattr(model, 'id') else str(model) for model in models_response]

            if model_ids:
                logging.info(f"Successfully fetched {len(model_ids)} Anthropic models from API")
                # Sort models with Claude 3 models first, then by version
                model_ids.sort(key=lambda x: (
                    0 if 'claude-3-opus' in x else
                    1 if 'claude-3-sonnet' in x else
                    2 if 'claude-3-haiku' in x else
                    3 if 'claude-2.1' in x else
                    4 if 'claude-2.0' in x else
                    5 if 'claude-instant' in x else
                    6
                ))
                # Cache the results
                _model_cache[cache_key] = (time.time(), model_ids)
                return model_ids
            else:
                logging.warning("No models found in API response, using fallback list")
                return get_fallback_anthropic_models()
        else:
            logging.info("No Anthropic API key available, using fallback list")
            return get_fallback_anthropic_models()

    except ImportError:
        logging.warning("Anthropic library not installed, using fallback list")
        return get_fallback_anthropic_models()
    except Exception as e:
        logging.error(f"Error fetching Anthropic models from API: {e}")
        return get_fallback_anthropic_models()


def get_fallback_anthropic_models() -> List[str]:
    """Return a fallback list of Anthropic models."""
    logging.info("Using fallback list of Anthropic models")
    return [
        "claude-3-opus-20240229",      # Most capable model
        "claude-3-sonnet-20240229",    # Balanced performance
        "claude-3-haiku-20240307",     # Fastest model
        "claude-2.1",                  # Previous generation
        "claude-2.0",                  # Legacy model
        "claude-instant-1.2"           # Fast, lightweight model
    ]


def get_gemini_models() -> List[str]:
    """Fetch available models from Google Gemini API."""
    # Check cache first
    cache_key = "gemini_models"
    if cache_key in _model_cache:
        cached_time, cached_models = _model_cache[cache_key]
        if time.time() - cached_time < _cache_ttl:
            logging.info("Using cached Gemini models")
            return cached_models

    try:
        import google.generativeai as genai
        from utils.security import get_security_manager

        security_manager = get_security_manager()
        api_key = security_manager.get_api_key("gemini")

        if not api_key:
            api_key = os.getenv("GEMINI_API_KEY")

        if api_key:
            logging.info("Attempting to fetch Gemini models from API")
            genai.configure(api_key=api_key)

            # Fetch models list from API
            models = []
            for model in genai.list_models():
                # Filter for models that support generateContent
                if "generateContent" in model.supported_generation_methods:
                    # Extract just the model name (remove 'models/' prefix)
                    model_name = model.name.replace("models/", "")
                    models.append(model_name)

            if models:
                logging.info(f"Successfully fetched {len(models)} Gemini models from API")
                # Sort models (gemini-2.0 first, then 1.5, then others)
                models.sort(key=lambda x: (
                    0 if "2.0" in x else
                    1 if "1.5-pro" in x else
                    2 if "1.5-flash" in x else
                    3 if "1.5" in x else
                    4
                ))
                # Cache the results
                _model_cache[cache_key] = (time.time(), models)
                return models
            else:
                logging.warning("No models found in API response, using fallback list")
                return get_fallback_gemini_models()
        else:
            logging.info("No Gemini API key available, using fallback list")
            return get_fallback_gemini_models()

    except ImportError:
        logging.warning("google-generativeai library not installed, using fallback list")
        return get_fallback_gemini_models()
    except Exception as e:
        logging.error(f"Error fetching Gemini models from API: {e}")
        return get_fallback_gemini_models()


def get_fallback_gemini_models() -> List[str]:
    """Return a fallback list of Google Gemini models."""
    logging.info("Using fallback list of Gemini models")
    return [
        "gemini-2.0-flash-exp",        # Latest experimental flash model
        "gemini-1.5-pro",              # Most capable Gemini 1.5 model
        "gemini-1.5-flash",            # Fast and efficient
        "gemini-1.5-flash-8b",         # Smaller, faster variant
        "gemini-pro"                   # Original Gemini Pro
    ]

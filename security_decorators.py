"""
Security decorators and utilities for Medical Assistant.
"""

import functools
import time
import logging
from typing import Callable, Any, Optional

from security import get_security_manager
from exceptions import APIError, RateLimitError


def rate_limited(provider: str, identifier_arg: Optional[str] = None):
    """Decorator to apply rate limiting to API calls.
    
    Args:
        provider: API provider name
        identifier_arg: Optional argument name to use as identifier
        
    Example:
        @rate_limited("openai")
        def call_openai_api():
            ...
        
        @rate_limited("deepgram", identifier_arg="user_id")
        def transcribe_audio(audio_file, user_id=None):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            security_manager = get_security_manager()
            
            # Get identifier if specified
            identifier = None
            if identifier_arg and identifier_arg in kwargs:
                identifier = kwargs[identifier_arg]
            
            # Check rate limit
            is_allowed, wait_time = security_manager.check_rate_limit(provider, identifier)
            
            if not is_allowed:
                raise RateLimitError(
                    f"Rate limit exceeded for {provider}. Please wait {wait_time:.1f} seconds.",
                    retry_after=int(wait_time) + 1
                )
            
            # Call the function
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def sanitize_inputs(*input_args: str, input_type: str = "prompt"):
    """Decorator to sanitize function inputs.
    
    Args:
        *input_args: Names of arguments to sanitize
        input_type: Type of sanitization to apply
        
    Example:
        @sanitize_inputs("prompt", "user_input")
        def process_text(prompt, user_input):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            security_manager = get_security_manager()
            
            # Get function signature
            import inspect
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Sanitize specified arguments
            for arg_name in input_args:
                if arg_name in bound_args.arguments:
                    original_value = bound_args.arguments[arg_name]
                    if isinstance(original_value, str):
                        sanitized_value = security_manager.sanitize_input(
                            original_value, input_type
                        )
                        bound_args.arguments[arg_name] = sanitized_value
                        
                        if original_value != sanitized_value:
                            logging.warning(
                                f"Sanitized {arg_name} in {func.__name__}"
                            )
            
            # Call function with sanitized arguments
            return func(*bound_args.args, **bound_args.kwargs)
        
        return wrapper
    return decorator


def require_api_key(provider: str):
    """Decorator to ensure API key is available before calling function.
    
    Args:
        provider: API provider name
        
    Example:
        @require_api_key("openai")
        def call_openai():
            api_key = get_api_key("openai")  # Guaranteed to exist
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            security_manager = get_security_manager()
            
            # Check if API key is available
            api_key = security_manager.get_api_key(provider)
            if not api_key:
                raise APIError(
                    f"API key for {provider} not found. "
                    f"Please set the {provider.upper()}_API_KEY environment variable "
                    "or configure it in the application."
                )
            
            # Validate the key
            is_valid, error = security_manager.validate_api_key(provider, api_key)
            if not is_valid:
                raise APIError(f"Invalid {provider} API key: {error}")
            
            # Call the function
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def log_api_call(provider: str, log_response: bool = False):
    """Decorator to log API calls for security auditing.
    
    Args:
        provider: API provider name
        log_response: Whether to log the response (be careful with sensitive data)
        
    Example:
        @log_api_call("openai")
        def call_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = logging.getLogger(f"api_audit.{provider}")
            security_manager = get_security_manager()
            
            # Log the call
            call_id = security_manager.generate_secure_token(16)
            start_time = time.time()
            
            logger.info(
                f"API call started - ID: {call_id}, "
                f"Function: {func.__name__}, "
                f"Provider: {provider}"
            )
            
            try:
                # Call the function
                result = func(*args, **kwargs)
                
                # Log success
                elapsed = time.time() - start_time
                logger.info(
                    f"API call succeeded - ID: {call_id}, "
                    f"Duration: {elapsed:.3f}s"
                )
                
                if log_response and result:
                    # Be careful not to log sensitive data
                    result_preview = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
                    logger.debug(f"Response preview - ID: {call_id}: {result_preview}")
                
                return result
                
            except Exception as e:
                # Log failure
                elapsed = time.time() - start_time
                logger.error(
                    f"API call failed - ID: {call_id}, "
                    f"Duration: {elapsed:.3f}s, "
                    f"Error: {str(e)}"
                )
                raise
        
        return wrapper
    return decorator


def secure_api_call(provider: str, rate_limit: bool = True, sanitize: bool = True):
    """Combined decorator for secure API calls.
    
    Args:
        provider: API provider name
        rate_limit: Whether to apply rate limiting
        sanitize: Whether to sanitize inputs
        
    Example:
        @secure_api_call("openai")
        def call_openai(prompt):
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Apply decorators in order
        decorated = func
        
        # Always require API key
        decorated = require_api_key(provider)(decorated)
        
        # Apply rate limiting if requested
        if rate_limit:
            decorated = rate_limited(provider)(decorated)
        
        # Apply logging
        decorated = log_api_call(provider)(decorated)
        
        # Apply input sanitization if requested
        if sanitize:
            # Try to detect prompt-like arguments
            import inspect
            sig = inspect.signature(func)
            prompt_args = []
            
            for param_name in sig.parameters:
                if any(keyword in param_name.lower() for keyword in ['prompt', 'text', 'input', 'query']):
                    prompt_args.append(param_name)
            
            if prompt_args:
                decorated = sanitize_inputs(*prompt_args, input_type="prompt")(decorated)
        
        return decorated
    
    return decorator
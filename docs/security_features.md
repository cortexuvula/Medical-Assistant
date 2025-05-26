# Security Features

The Medical Assistant implements comprehensive security measures to protect sensitive data and API operations.

## 1. API Key Encryption at Rest

### Secure Storage
- API keys are encrypted using Fernet symmetric encryption
- Keys are derived using PBKDF2 with SHA-256
- Machine-specific identifiers used for key derivation
- Encrypted keys stored in protected `.keys` directory

### Key Management
```bash
# Add an API key securely
python manage_keys.py add openai

# List stored keys (without showing actual keys)
python manage_keys.py list

# Validate a key
python manage_keys.py validate openai

# Check all keys
python manage_keys.py check

# Export keys for environment
python manage_keys.py export > .env
```

### Environment Variables
Keys can be provided via environment variables (preferred for production):
- `OPENAI_API_KEY`
- `PERPLEXITY_API_KEY`
- `GROQ_API_KEY`
- `DEEPGRAM_API_KEY`
- `ELEVENLABS_API_KEY`

## 2. Enhanced API Key Validation

### Format Validation
Each provider has specific validation rules:
- **OpenAI**: Must start with `sk-` and be 51 characters
- **Groq**: Must start with `gsk_` and be 56 characters
- **Deepgram**: Must be 32 hexadecimal characters
- **ElevenLabs**: Must be 32 hexadecimal characters
- **Perplexity**: Must start with `pplx-` and be 53 characters

### Validation Features
- Length checking
- Pattern matching
- Common mistake detection (quotes, spaces, placeholders)
- Provider-specific format validation

## 3. Rate Limiting

### Per-Provider Limits
Default rate limits (calls per minute):
- OpenAI: 60
- Perplexity: 50
- Groq: 30
- Deepgram: 100
- ElevenLabs: 50
- Ollama: 1000 (local)

### Rate Limiting Features
- Thread-safe implementation
- Per-provider and per-user limiting
- Automatic retry-after calculation
- Usage statistics tracking

### Using Rate Limiting
```python
from security_decorators import rate_limited

@rate_limited("openai")
def call_api():
    # API call here
    pass

# With user-specific limiting
@rate_limited("openai", identifier_arg="user_id")
def call_api_for_user(prompt, user_id):
    # API call here
    pass
```

## 4. Input Sanitization

### Prompt Sanitization
- Removes script injection attempts
- Filters command injection patterns
- Detects prompt injection attempts
- Enforces length limits (10,000 characters)
- Removes control characters
- Validates UTF-8 encoding

### Filename Sanitization
- Removes path traversal attempts (`../`)
- Filters invalid characters
- Prevents reserved names (CON, PRN, etc.)
- Enforces length limits
- Ensures filesystem compatibility

### Using Sanitization
```python
from security_decorators import sanitize_inputs

@sanitize_inputs("prompt", "user_input")
def process_text(prompt, user_input):
    # Inputs are automatically sanitized
    pass
```

## 5. Security Decorators

### @secure_api_call
Combines multiple security features:
```python
from security_decorators import secure_api_call

@secure_api_call("openai")
def call_openai(prompt):
    # Automatically:
    # - Validates API key exists
    # - Applies rate limiting
    # - Logs API calls
    # - Sanitizes inputs
    pass
```

### @require_api_key
Ensures API key is available:
```python
from security_decorators import require_api_key

@require_api_key("openai")
def use_openai():
    # Guaranteed to have valid API key
    pass
```

### @log_api_call
Audit logging for API calls:
```python
from security_decorators import log_api_call

@log_api_call("openai", log_response=False)
def call_api():
    # Logs call details for security auditing
    pass
```

## 6. Security Manager

Central security management:
```python
from security import get_security_manager

security_manager = get_security_manager()

# Store API key securely
success, error = security_manager.store_api_key("openai", api_key)

# Get API key (checks env and secure storage)
api_key = security_manager.get_api_key("openai")

# Validate API key
is_valid, error = security_manager.validate_api_key("openai", api_key)

# Check rate limit
is_allowed, wait_time = security_manager.check_rate_limit("openai")

# Sanitize input
clean_prompt = security_manager.sanitize_input(user_input, "prompt")

# Generate secure tokens
token = security_manager.generate_secure_token(32)

# Hash sensitive data for logging
hashed = security_manager.hash_sensitive_data(sensitive_info)
```

## 7. Best Practices

### API Key Security
1. Use environment variables in production
2. Never commit API keys to version control
3. Rotate keys regularly
4. Use the `manage_keys.py` utility for secure storage
5. Set restrictive file permissions on key storage

### Input Validation
1. Always sanitize user inputs
2. Use the `@sanitize_inputs` decorator
3. Validate file paths and names
4. Check audio file formats and sizes
5. Limit input lengths appropriately

### Rate Limiting
1. Monitor API usage with `get_usage_stats()`
2. Adjust limits based on provider guidelines
3. Implement user-specific limits when needed
4. Handle rate limit errors gracefully

### Error Handling
1. Never expose API keys in error messages
2. Log security events for auditing
3. Use generic error messages for users
4. Implement proper exception handling

## 8. Configuration

Add to your configuration:
```json
{
  "security": {
    "rate_limits": {
      "openai": 60,
      "groq": 30
    },
    "max_prompt_length": 10000,
    "enable_audit_logging": true
  }
}
```

## 9. Compliance

The security implementation helps with:
- **Data Protection**: Encrypted storage of sensitive credentials
- **Access Control**: API key validation and management
- **Audit Trail**: Comprehensive logging of API operations
- **Input Validation**: Protection against injection attacks
- **Rate Limiting**: Prevention of abuse and cost control

## 10. Troubleshooting

### Common Issues

1. **"API key not found"**
   - Check environment variables
   - Run `python manage_keys.py check`
   - Ensure key is properly formatted

2. **"Rate limit exceeded"**
   - Wait for the suggested time
   - Check usage with `get_usage_stats()`
   - Adjust rate limits if needed

3. **"Invalid API key format"**
   - Verify key matches provider format
   - Remove any quotes or spaces
   - Check for placeholder values

4. **"Prompt sanitized"**
   - Review sanitization logs
   - Check for injection patterns
   - Ensure prompts are under length limit

The security features provide comprehensive protection while maintaining ease of use and performance.
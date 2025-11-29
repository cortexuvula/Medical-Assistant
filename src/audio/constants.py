"""
Audio Constants Module

Centralized constants for audio processing to avoid magic numbers throughout the codebase.
"""

# Sample Rates (Hz)
SAMPLE_RATE_8K = 8000      # Low quality, telephony
SAMPLE_RATE_16K = 16000    # Speech recognition standard
SAMPLE_RATE_22K = 22050    # Half of CD quality
SAMPLE_RATE_44K = 44100    # CD quality
SAMPLE_RATE_48K = 48000    # Professional audio/video standard

# Default sample rate for recording (professional quality)
DEFAULT_SAMPLE_RATE = SAMPLE_RATE_48K

# Sample rate for STT processing (speech recognition optimized)
STT_SAMPLE_RATE = SAMPLE_RATE_16K

# Sample Widths (bytes)
SAMPLE_WIDTH_8BIT = 1      # 8-bit audio (256 levels)
SAMPLE_WIDTH_16BIT = 2     # 16-bit audio (65536 levels, CD quality)
SAMPLE_WIDTH_24BIT = 3     # 24-bit audio (professional)
SAMPLE_WIDTH_32BIT = 4     # 32-bit audio (floating point)

# Default sample width (16-bit is standard for most applications)
DEFAULT_SAMPLE_WIDTH = SAMPLE_WIDTH_16BIT

# Channel configurations
CHANNELS_MONO = 1
CHANNELS_STEREO = 2

# Default channel configuration (mono for voice recording)
DEFAULT_CHANNELS = CHANNELS_MONO

# Buffer Sizes (samples)
BUFFER_SIZE_SMALL = 512
BUFFER_SIZE_MEDIUM = 1024
BUFFER_SIZE_LARGE = 2048
BUFFER_SIZE_XLARGE = 4096
BUFFER_SIZE_XXLARGE = 8192

# Default buffer size for audio processing
DEFAULT_BUFFER_SIZE = BUFFER_SIZE_LARGE

# Chunk size for streaming (bytes)
DEFAULT_CHUNK_SIZE = 1024

# Timeouts and intervals (milliseconds)
RECORDING_TIMEOUT_MS = 30000      # 30 seconds
TRANSCRIPTION_TIMEOUT_MS = 60000  # 60 seconds
UI_UPDATE_INTERVAL_MS = 100       # UI refresh rate

# Timeouts (seconds)
API_TIMEOUT_SECONDS = 30
STREAM_TIMEOUT_SECONDS = 60

# Cache TTL (seconds)
MODEL_CACHE_TTL_SECONDS = 3600    # 1 hour

# Audio thresholds
SILENCE_THRESHOLD_DB = -40        # dB level considered silence
VOICE_ACTIVITY_THRESHOLD = 0.02   # Normalized amplitude threshold

# Max tokens for AI responses
DEFAULT_MAX_TOKENS = 4096

# Validation limits
MAX_PROMPT_LENGTH = 10000
MAX_INPUT_LENGTH = 100000

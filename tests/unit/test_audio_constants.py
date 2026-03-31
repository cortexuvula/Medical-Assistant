"""
Tests for src/audio/constants.py

Covers:
- Sample rate constants (values, ordering)
- Sample width constants (values, ordering)
- Channel constants
- Buffer size constants (ordering)
- Timeout values (positive, reasonable magnitudes)
- Memory limits and thresholds
No network, no Tkinter, no I/O.
"""

import sys
import importlib.util
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Load audio/constants.py directly to avoid audio/__init__.py
# importing soundcard which requires PulseAudio.
_spec = importlib.util.spec_from_file_location(
    "audio_constants",
    project_root / "src/audio/constants.py"
)
ac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ac)


# ===========================================================================
# Sample Rates
# ===========================================================================

class TestSampleRates:
    def test_sample_rate_8k_value(self):
        assert ac.SAMPLE_RATE_8K == 8000

    def test_sample_rate_16k_value(self):
        assert ac.SAMPLE_RATE_16K == 16000

    def test_sample_rate_22k_value(self):
        assert ac.SAMPLE_RATE_22K == 22050

    def test_sample_rate_44k_value(self):
        assert ac.SAMPLE_RATE_44K == 44100

    def test_sample_rate_48k_value(self):
        assert ac.SAMPLE_RATE_48K == 48000

    def test_sample_rates_increasing(self):
        rates = [ac.SAMPLE_RATE_8K, ac.SAMPLE_RATE_16K, ac.SAMPLE_RATE_22K,
                 ac.SAMPLE_RATE_44K, ac.SAMPLE_RATE_48K]
        assert rates == sorted(rates)

    def test_default_sample_rate_is_48k(self):
        assert ac.DEFAULT_SAMPLE_RATE == ac.SAMPLE_RATE_48K

    def test_stt_sample_rate_is_16k(self):
        assert ac.STT_SAMPLE_RATE == ac.SAMPLE_RATE_16K

    def test_stt_rate_less_than_default(self):
        assert ac.STT_SAMPLE_RATE < ac.DEFAULT_SAMPLE_RATE


# ===========================================================================
# Sample Widths
# ===========================================================================

class TestSampleWidths:
    def test_sample_width_8bit_is_1(self):
        assert ac.SAMPLE_WIDTH_8BIT == 1

    def test_sample_width_16bit_is_2(self):
        assert ac.SAMPLE_WIDTH_16BIT == 2

    def test_sample_width_24bit_is_3(self):
        assert ac.SAMPLE_WIDTH_24BIT == 3

    def test_sample_width_32bit_is_4(self):
        assert ac.SAMPLE_WIDTH_32BIT == 4

    def test_sample_widths_increasing(self):
        widths = [ac.SAMPLE_WIDTH_8BIT, ac.SAMPLE_WIDTH_16BIT,
                  ac.SAMPLE_WIDTH_24BIT, ac.SAMPLE_WIDTH_32BIT]
        assert widths == sorted(widths)

    def test_default_sample_width_is_16bit(self):
        assert ac.DEFAULT_SAMPLE_WIDTH == ac.SAMPLE_WIDTH_16BIT


# ===========================================================================
# Channels
# ===========================================================================

class TestChannels:
    def test_mono_is_1(self):
        assert ac.CHANNELS_MONO == 1

    def test_stereo_is_2(self):
        assert ac.CHANNELS_STEREO == 2

    def test_stereo_greater_than_mono(self):
        assert ac.CHANNELS_STEREO > ac.CHANNELS_MONO

    def test_default_channels_is_mono(self):
        assert ac.DEFAULT_CHANNELS == ac.CHANNELS_MONO


# ===========================================================================
# Buffer Sizes
# ===========================================================================

class TestBufferSizes:
    def test_buffer_small_is_512(self):
        assert ac.BUFFER_SIZE_SMALL == 512

    def test_buffer_medium_is_1024(self):
        assert ac.BUFFER_SIZE_MEDIUM == 1024

    def test_buffer_large_is_2048(self):
        assert ac.BUFFER_SIZE_LARGE == 2048

    def test_buffer_xlarge_is_4096(self):
        assert ac.BUFFER_SIZE_XLARGE == 4096

    def test_buffer_xxlarge_is_8192(self):
        assert ac.BUFFER_SIZE_XXLARGE == 8192

    def test_buffers_increasing(self):
        sizes = [ac.BUFFER_SIZE_SMALL, ac.BUFFER_SIZE_MEDIUM, ac.BUFFER_SIZE_LARGE,
                 ac.BUFFER_SIZE_XLARGE, ac.BUFFER_SIZE_XXLARGE]
        assert sizes == sorted(sizes)

    def test_default_buffer_is_large(self):
        assert ac.DEFAULT_BUFFER_SIZE == ac.BUFFER_SIZE_LARGE

    def test_default_chunk_size_positive(self):
        assert ac.DEFAULT_CHUNK_SIZE > 0


# ===========================================================================
# Timeouts and intervals
# ===========================================================================

class TestTimeouts:
    def test_recording_timeout_ms_positive(self):
        assert ac.RECORDING_TIMEOUT_MS > 0

    def test_transcription_timeout_ms_positive(self):
        assert ac.TRANSCRIPTION_TIMEOUT_MS > 0

    def test_transcription_timeout_longer_than_recording(self):
        assert ac.TRANSCRIPTION_TIMEOUT_MS >= ac.RECORDING_TIMEOUT_MS

    def test_ui_update_interval_positive(self):
        assert ac.UI_UPDATE_INTERVAL_MS > 0

    def test_api_timeout_seconds_positive(self):
        assert ac.API_TIMEOUT_SECONDS > 0

    def test_stream_timeout_seconds_positive(self):
        assert ac.STREAM_TIMEOUT_SECONDS > 0

    def test_stream_timeout_at_least_as_long_as_api(self):
        assert ac.STREAM_TIMEOUT_SECONDS >= ac.API_TIMEOUT_SECONDS

    def test_model_cache_ttl_positive(self):
        assert ac.MODEL_CACHE_TTL_SECONDS > 0

    def test_model_cache_ttl_at_least_1_hour(self):
        assert ac.MODEL_CACHE_TTL_SECONDS >= 3600


# ===========================================================================
# Audio thresholds
# ===========================================================================

class TestThresholds:
    def test_silence_threshold_negative_db(self):
        assert ac.SILENCE_THRESHOLD_DB < 0

    def test_voice_activity_threshold_positive(self):
        assert ac.VOICE_ACTIVITY_THRESHOLD > 0

    def test_voice_activity_threshold_less_than_1(self):
        # Normalized amplitude should be < 1.0
        assert ac.VOICE_ACTIVITY_THRESHOLD < 1.0


# ===========================================================================
# Token and validation limits
# ===========================================================================

class TestLimits:
    def test_default_max_tokens_positive(self):
        assert ac.DEFAULT_MAX_TOKENS > 0

    def test_max_prompt_length_positive(self):
        assert ac.MAX_PROMPT_LENGTH > 0

    def test_max_input_length_greater_than_prompt_length(self):
        assert ac.MAX_INPUT_LENGTH >= ac.MAX_PROMPT_LENGTH


# ===========================================================================
# Memory limits
# ===========================================================================

class TestMemoryLimits:
    def test_max_recording_duration_positive(self):
        assert ac.MAX_RECORDING_DURATION_MINUTES > 0

    def test_max_audio_memory_mb_positive(self):
        assert ac.MAX_AUDIO_MEMORY_MB > 0

    def test_segment_combine_threshold_positive(self):
        assert ac.SEGMENT_COMBINE_THRESHOLD > 0

    def test_bytes_per_second_48k_mono_correct(self):
        # 48000 Hz * 2 bytes per sample * 1 channel = 96000
        assert ac.BYTES_PER_SECOND_48K_MONO == 96000

    def test_bytes_per_second_positive(self):
        assert ac.BYTES_PER_SECOND_48K_MONO > 0

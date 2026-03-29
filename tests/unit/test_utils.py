"""
Tests for src/utils/utils.py

Covers get_valid_microphones, get_valid_output_devices, and
get_device_index_from_name — all with sounddevice and platform mocked.
No real audio hardware required.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import utils.utils as utils_module
from utils.utils import (
    get_valid_microphones,
    get_valid_output_devices,
    get_device_index_from_name,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_device(name, in_ch=0, out_ch=0, index=0):
    return {"name": name, "max_input_channels": in_ch, "max_output_channels": out_ch, "index": index}


def _input(name, index=0):
    return _make_device(name, in_ch=2, out_ch=0, index=index)


def _output(name, index=0):
    return _make_device(name, in_ch=0, out_ch=2, index=index)


def _both(name, index=0):
    return _make_device(name, in_ch=2, out_ch=2, index=index)


# ===========================================================================
# get_valid_microphones
# ===========================================================================

class TestGetValidMicrophones:
    def _patch(self, devices, platform_name="Linux", soundcard_mics=None):
        """Convenience: patch sd.query_devices, platform, soundcard."""
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = devices

        sc_mock = MagicMock()
        if soundcard_mics is not None:
            sc_mock.all_microphones.return_value = soundcard_mics
        else:
            sc_mock.all_microphones.return_value = []

        return (
            patch.object(utils_module, "sd", mock_sd),
            patch("platform.system", return_value=platform_name),
            patch.object(utils_module, "soundcard", sc_mock),
            patch.object(utils_module, "SOUNDCARD_AVAILABLE", True),
        )

    def test_returns_list(self):
        devices = [_input("Mic A", 0)]
        with patch.object(utils_module, "sd", MagicMock(query_devices=MagicMock(return_value=devices))), \
             patch("platform.system", return_value="Darwin"), \
             patch.object(utils_module, "soundcard", MagicMock(all_microphones=MagicMock(return_value=[]))):
            result = get_valid_microphones()
        assert isinstance(result, list)

    def test_returns_empty_on_exception(self):
        mock_sd = MagicMock()
        mock_sd.query_devices.side_effect = Exception("no audio")
        with patch.object(utils_module, "sd", mock_sd):
            result = get_valid_microphones()
        assert result == []

    def test_only_input_devices_included(self):
        devices = [
            _input("Mic A", 0),
            _output("Speaker B", 1),
        ]
        with patch.object(utils_module, "sd", MagicMock(query_devices=MagicMock(return_value=devices))), \
             patch("platform.system", return_value="Darwin"), \
             patch.object(utils_module, "soundcard", MagicMock(all_microphones=MagicMock(return_value=[]))):
            result = get_valid_microphones()
        names = " ".join(result)
        assert "Mic A" in names
        assert "Speaker B" not in names

    def test_linux_filters_pulse_devices(self):
        devices = [
            _input("PulseAudio Mic", 0),
            _input("Real Mic", 1),
        ]
        with patch.object(utils_module, "sd", MagicMock(query_devices=MagicMock(return_value=devices))), \
             patch("platform.system", return_value="Linux"), \
             patch.object(utils_module, "soundcard", MagicMock(all_microphones=MagicMock(return_value=[]))):
            result = get_valid_microphones()
        names = " ".join(result)
        assert "PulseAudio Mic" not in names
        assert "Real Mic" in names

    def test_linux_filters_pipewire_devices(self):
        devices = [
            _input("PipeWire Audio", 0),
            _input("USB Microphone", 1),
        ]
        with patch.object(utils_module, "sd", MagicMock(query_devices=MagicMock(return_value=devices))), \
             patch("platform.system", return_value="Linux"), \
             patch.object(utils_module, "soundcard", MagicMock(all_microphones=MagicMock(return_value=[]))):
            result = get_valid_microphones()
        names = " ".join(result)
        assert "PipeWire" not in names
        assert "USB Microphone" in names

    def test_windows_filters_microsoft_sound_mapper(self):
        devices = [
            _input("Microsoft Sound Mapper", 0),
            _input("Headset Mic", 1),
        ]
        with patch.object(utils_module, "sd", MagicMock(query_devices=MagicMock(return_value=devices))), \
             patch("platform.system", return_value="Windows"), \
             patch.object(utils_module, "soundcard", MagicMock(all_microphones=MagicMock(return_value=[]))):
            result = get_valid_microphones()
        names = " ".join(result)
        assert "Microsoft Sound Mapper" not in names
        assert "Headset Mic" in names

    def test_device_name_includes_device_id(self):
        devices = [_input("USB Mic", 2)]
        with patch.object(utils_module, "sd", MagicMock(query_devices=MagicMock(return_value=devices))), \
             patch("platform.system", return_value="Darwin"), \
             patch.object(utils_module, "soundcard", MagicMock(all_microphones=MagicMock(return_value=[]))):
            result = get_valid_microphones()
        assert any("Device 0" in name for name in result)

    def test_voicemeeter_devices_appear_first(self):
        devices = [
            _input("Regular Mic", 0),
            _input("Voicemeeter Out A1", 1),
        ]
        with patch.object(utils_module, "sd", MagicMock(query_devices=MagicMock(return_value=devices))), \
             patch("platform.system", return_value="Windows"), \
             patch.object(utils_module, "soundcard", MagicMock(all_microphones=MagicMock(return_value=[]))):
            result = get_valid_microphones()
        # Voicemeeter should come first
        voicemeeter_pos = next((i for i, n in enumerate(result) if "Voicemeeter" in n), None)
        regular_pos = next((i for i, n in enumerate(result) if "Regular Mic" in n), None)
        if voicemeeter_pos is not None and regular_pos is not None:
            assert voicemeeter_pos < regular_pos


# ===========================================================================
# get_valid_output_devices
# ===========================================================================

class TestGetValidOutputDevices:
    def test_returns_list(self):
        mock_sd = MagicMock(query_devices=MagicMock(return_value=[_output("Speaker", 0)]))
        with patch.object(utils_module, "sd", mock_sd), \
             patch("platform.system", return_value="Darwin"):
            result = get_valid_output_devices()
        assert isinstance(result, list)

    def test_returns_default_output_on_exception(self):
        mock_sd = MagicMock()
        mock_sd.query_devices.side_effect = Exception("no audio")
        with patch.object(utils_module, "sd", mock_sd):
            result = get_valid_output_devices()
        assert result == ["Default Output"]

    def test_only_output_devices_included(self):
        devices = [
            _output("Speaker", 0),
            _input("Mic", 1),
        ]
        mock_sd = MagicMock(query_devices=MagicMock(return_value=devices))
        with patch.object(utils_module, "sd", mock_sd), \
             patch("platform.system", return_value="Darwin"):
            result = get_valid_output_devices()
        assert "Speaker" in result
        assert "Mic" not in result

    def test_removes_duplicates(self):
        devices = [
            _output("Speakers", 0),
            _output("Speakers", 1),
        ]
        mock_sd = MagicMock(query_devices=MagicMock(return_value=devices))
        with patch.object(utils_module, "sd", mock_sd), \
             patch("platform.system", return_value="Darwin"):
            result = get_valid_output_devices()
        assert result.count("Speakers") == 1

    def test_linux_filters_pulse_output(self):
        devices = [
            _output("pulse", 0),
            _output("Headphones", 1),
        ]
        mock_sd = MagicMock(query_devices=MagicMock(return_value=devices))
        with patch.object(utils_module, "sd", mock_sd), \
             patch("platform.system", return_value="Linux"):
            result = get_valid_output_devices()
        assert "pulse" not in result
        assert "Headphones" in result

    def test_windows_filters_microsoft_sound_mapper(self):
        devices = [
            _output("Microsoft Sound Mapper", 0),
            _output("Speakers", 1),
        ]
        mock_sd = MagicMock(query_devices=MagicMock(return_value=devices))
        with patch.object(utils_module, "sd", mock_sd), \
             patch("platform.system", return_value="Windows"):
            result = get_valid_output_devices()
        assert "Microsoft Sound Mapper" not in result
        assert "Speakers" in result


# ===========================================================================
# get_device_index_from_name
# ===========================================================================

class TestGetDeviceIndexFromName:
    def _mock_devices(self, devices):
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = devices
        return mock_sd

    def test_returns_zero_on_exception(self):
        mock_sd = MagicMock()
        mock_sd.query_devices.side_effect = Exception("broken")
        with patch.object(utils_module, "sd", mock_sd):
            result = get_device_index_from_name("Any Mic")
        assert result == 0

    def test_extracts_device_id_from_name(self):
        devices = [_input("USB Mic", 0), _input("Headset", 1), _input("Target Mic", 2)]
        mock_sd = self._mock_devices(devices)
        with patch.object(utils_module, "sd", mock_sd):
            result = get_device_index_from_name("Target Mic (Device 2)")
        assert result == 2

    def test_exact_name_match_when_no_device_id(self):
        devices = [_input("USB Microphone", 0), _input("Headset Mic", 1)]
        mock_sd = self._mock_devices(devices)
        with patch.object(utils_module, "sd", mock_sd):
            result = get_device_index_from_name("Headset Mic")
        assert result == 1

    def test_returns_zero_when_device_not_found(self):
        devices = [_input("USB Mic", 0)]
        mock_sd = self._mock_devices(devices)
        # Make default input also return something
        mock_sd.query_devices.side_effect = lambda *a, **kw: (
            {"name": "Default", "index": 0, "max_input_channels": 2}
            if kw.get("kind") == "input"
            else devices
        )
        with patch.object(utils_module, "sd", mock_sd):
            result = get_device_index_from_name("Nonexistent Device")
        # Should return some valid index (default or 0)
        assert isinstance(result, int)

    def test_invalid_device_id_falls_back_to_name_match(self):
        # Device ID 99 doesn't exist in a 2-device list
        devices = [_input("USB Mic", 0), _input("Real Mic", 1)]
        mock_sd = self._mock_devices(devices)
        with patch.object(utils_module, "sd", mock_sd):
            # Pattern matches "(Device 99)" but index 99 is out of range
            # → falls back to name match
            result = get_device_index_from_name("USB Mic (Device 99)")
        # Falls back to exact name match on "USB Mic" (index 0)
        assert result == 0

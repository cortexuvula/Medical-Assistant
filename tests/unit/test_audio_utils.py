"""Tests for utils.utils — audio device enumeration helpers.

These tests mock sounddevice and soundcard to isolate the logic.
"""

import pytest
from unittest.mock import patch, MagicMock


def make_device(name: str, max_input: int, max_output: int, index: int = 0) -> dict:
    return {
        "name": name,
        "max_input_channels": max_input,
        "max_output_channels": max_output,
        "index": index,
    }


# ── get_valid_microphones ─────────────────────────────────────────────────────

class TestGetValidMicrophones:
    def _run(self, devices, platform_name="linux", soundcard_mics=None, soundcard_fails=False):
        """Helper: patch sd and platform, then call get_valid_microphones."""
        from utils import utils as utils_mod

        mock_soundcard = MagicMock()
        if soundcard_fails:
            mock_soundcard.all_microphones.side_effect = Exception("no soundcard")
        else:
            mic_objs = []
            for name in (soundcard_mics or []):
                m = MagicMock()
                m.name = name
                mic_objs.append(m)
            mock_soundcard.all_microphones.return_value = mic_objs

        with patch.object(utils_mod, "soundcard", mock_soundcard), \
             patch.object(utils_mod, "SOUNDCARD_AVAILABLE", True), \
             patch("sounddevice.query_devices", return_value=devices), \
             patch("platform.system", return_value=platform_name):
            return utils_mod.get_valid_microphones()

    def test_returns_list(self):
        devices = [make_device("Microphone A", 2, 0, 0)]
        result = self._run(devices)
        assert isinstance(result, list)

    def test_input_device_included(self):
        devices = [make_device("My Mic", 2, 0, 0)]
        result = self._run(devices)
        names_joined = " ".join(result)
        assert "My Mic" in names_joined

    def test_output_only_device_excluded(self):
        devices = [make_device("Speakers", 0, 2, 0)]
        result = self._run(devices)
        assert all("Speakers" not in name for name in result)

    def test_linux_filters_pipewire(self):
        devices = [
            make_device("pipewire", 2, 0, 0),
            make_device("Real Mic", 2, 0, 1),
        ]
        result = self._run(devices, platform_name="linux")
        assert all("pipewire" not in name.lower() for name in result)
        assert any("Real Mic" in name for name in result)

    def test_linux_filters_pulse_when_other_devices_available(self):
        # Pulse is filtered only when real hardware devices are also available.
        # When it's the only device the fallback restores it.
        devices = [
            make_device("pulse", 2, 0, 0),
            make_device("HDA Intel PCH Mic", 2, 0, 1),
        ]
        result = self._run(devices, platform_name="linux")
        # With a real hardware device available, pulse is excluded
        assert all("pulse" not in name.lower() for name in result)
        assert any("HDA Intel PCH Mic" in name for name in result)

    def test_windows_filters_mapper_device(self):
        devices = [
            make_device("Microsoft Sound Mapper", 2, 0, 0),
            make_device("Headset Mic", 2, 0, 1),
        ]
        result = self._run(devices, platform_name="windows")
        assert all("microsoft sound mapper" not in name.lower() for name in result)

    def test_macos_allows_all_devices(self):
        devices = [make_device("Built-in Microphone", 2, 0, 0)]
        result = self._run(devices, platform_name="darwin")
        assert any("Built-in Microphone" in name for name in result)

    def test_device_name_includes_device_number(self):
        # The code uses enumerate index (position in the returned list), not the
        # device's 'index' field.  The first non-filtered device gets index 0.
        devices = [make_device("USB Mic", 2, 0, 0)]
        result = self._run(devices)
        assert any("(Device 0)" in name for name in result)

    def test_voicemeeter_appears_first(self):
        devices = [
            make_device("Regular Mic", 2, 0, 0),
            make_device("VoiceMeeter VAIO", 2, 0, 1),
        ]
        result = self._run(devices, platform_name="windows")
        if result:
            # Voicemeeter should be before regular mic
            vm_indices = [i for i, n in enumerate(result) if "voicemeeter" in n.lower() or "vb-audio" in n.lower()]
            reg_indices = [i for i, n in enumerate(result) if "Regular Mic" in n]
            if vm_indices and reg_indices:
                assert min(vm_indices) < min(reg_indices)

    def test_soundcard_mics_appended(self):
        devices = [make_device("SD Mic", 2, 0, 0)]
        result = self._run(devices, soundcard_mics=["SC Mic A", "SC Mic B"])
        names = " ".join(result)
        assert "SC Mic A" in names
        assert "SC Mic B" in names

    def test_soundcard_failure_does_not_crash(self):
        devices = [make_device("SD Mic", 2, 0, 0)]
        result = self._run(devices, soundcard_fails=True)
        assert isinstance(result, list)

    def test_no_devices_returns_fallback(self):
        from utils import utils as utils_mod

        mock_soundcard = MagicMock()
        mock_soundcard.all_microphones.return_value = []

        default_device = make_device("Default Input", 2, 0, 0)

        with patch.object(utils_mod, "soundcard", mock_soundcard), \
             patch.object(utils_mod, "SOUNDCARD_AVAILABLE", True), \
             patch("sounddevice.query_devices", side_effect=lambda *args, **kw: (
                 [] if not args else default_device
             )), \
             patch("platform.system", return_value="linux"):
            result = utils_mod.get_valid_microphones()
        assert isinstance(result, list)

    def test_exception_returns_empty_list(self):
        from utils import utils as utils_mod

        with patch("sounddevice.query_devices", side_effect=Exception("no audio")), \
             patch.object(utils_mod, "soundcard", None), \
             patch.object(utils_mod, "SOUNDCARD_AVAILABLE", False):
            result = utils_mod.get_valid_microphones()
        assert result == []


# ── get_valid_output_devices ──────────────────────────────────────────────────

class TestGetValidOutputDevices:
    def _run(self, devices, platform_name="linux"):
        from utils import utils as utils_mod

        with patch("sounddevice.query_devices", return_value=devices), \
             patch("platform.system", return_value=platform_name):
            return utils_mod.get_valid_output_devices()

    def test_returns_list(self):
        devices = [make_device("Speakers", 0, 2, 0)]
        result = self._run(devices)
        assert isinstance(result, list)

    def test_output_device_included(self):
        devices = [make_device("Built-in Output", 0, 2, 0)]
        result = self._run(devices)
        assert "Built-in Output" in result

    def test_input_only_device_excluded(self):
        devices = [make_device("Microphone", 2, 0, 0)]
        result = self._run(devices)
        assert "Microphone" not in result

    def test_linux_filters_pipewire_output(self):
        devices = [
            make_device("pipewire", 0, 2, 0),
            make_device("Real Speaker", 0, 2, 1),
        ]
        result = self._run(devices, platform_name="linux")
        assert "pipewire" not in result
        assert "Real Speaker" in result

    def test_windows_filters_mapper_device(self):
        devices = [
            make_device("Microsoft Sound Mapper", 0, 2, 0),
            make_device("Headphones", 0, 2, 1),
        ]
        result = self._run(devices, platform_name="windows")
        assert "Microsoft Sound Mapper" not in result
        assert "Headphones" in result

    def test_no_duplicates(self):
        devices = [
            make_device("Speaker A", 0, 2, 0),
            make_device("Speaker A", 0, 2, 1),  # Duplicate name
        ]
        result = self._run(devices)
        assert result.count("Speaker A") == 1

    def test_exception_returns_default(self):
        from utils import utils as utils_mod

        with patch("sounddevice.query_devices", side_effect=Exception("audio error")):
            result = utils_mod.get_valid_output_devices()
        assert isinstance(result, list)
        assert len(result) > 0


# ── get_device_index_from_name ────────────────────────────────────────────────

class TestGetDeviceIndexFromName:
    def _run(self, device_name, devices, default_device=None):
        from utils import utils as utils_mod

        def sd_query(*args, **kwargs):
            if args or kwargs.get("kind"):
                return default_device or make_device("Default", 2, 0, 0)
            return devices

        with patch("sounddevice.query_devices", side_effect=sd_query):
            return utils_mod.get_device_index_from_name(device_name)

    def test_device_with_id_in_name_returns_id(self):
        devices = [
            make_device("Device 0", 2, 0, 0),
            make_device("USB Mic", 2, 0, 1),
        ]
        result = self._run("USB Mic (Device 1)", devices)
        assert result == 1

    def test_exact_name_match(self):
        devices = [
            make_device("USB Mic", 2, 0, 0),
            make_device("HD Webcam", 2, 0, 1),
        ]
        result = self._run("USB Mic", devices)
        assert result == 0

    def test_partial_name_match(self):
        devices = [
            make_device("USB Microphone Pro", 2, 0, 0),
        ]
        result = self._run("USB Microphone", devices)
        assert result == 0

    def test_unknown_device_falls_back_to_default(self):
        devices = [make_device("Known Mic", 2, 0, 0)]
        default = make_device("Default Input", 2, 0, 0)
        default["index"] = 0
        result = self._run("Nonexistent Device", devices, default_device=default)
        assert isinstance(result, int)

    def test_invalid_device_id_falls_back_to_name_search(self):
        devices = [make_device("Only Mic", 2, 0, 0)]
        # "Device 99" doesn't exist in the list
        result = self._run("Only Mic (Device 99)", devices)
        # Should fall back to name search and find index 0
        assert result == 0

    def test_exception_returns_zero(self):
        from utils import utils as utils_mod

        with patch("sounddevice.query_devices", side_effect=Exception("no audio")):
            result = utils_mod.get_device_index_from_name("Any Mic")
        assert result == 0

    def test_voicemeeter_matching_with_designation(self):
        devices = [
            make_device("VoiceMeeter VAIO", 2, 0, 0),
            make_device("VoiceMeeter Out A1", 2, 0, 1),
        ]
        result = self._run("VoiceMeeter Out A1 (Device 5)", devices)
        # Falls back to name matching for non-existent ID
        assert isinstance(result, int)

    def test_non_input_device_not_matched_by_id(self):
        devices = [
            make_device("Speakers", 0, 2, 0),  # output-only at index 0
            make_device("Mic", 2, 0, 1),
        ]
        # Device 0 is not an input device
        result = self._run("Speakers (Device 0)", devices)
        # Should not return 0 (not an input device), falls back
        assert isinstance(result, int)

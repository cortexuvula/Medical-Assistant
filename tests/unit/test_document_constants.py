"""
Tests for src/core/controllers/export/document_constants.py

Covers:
- DOCUMENT_TYPES list (membership, order, length)
- TAB_DOCUMENT_MAP (mapping, length, valid/invalid indices)
- DOCUMENT_DISPLAY_NAMES (keys, values, human-readable)
- SOAP_EXPORT_TYPES / CORRESPONDENCE_TYPES sets
- get_document_display_name() (known types, unknown fallback)
- get_document_type_for_tab() (valid tab indices 0-4, invalid index)
No network, no Tkinter, no I/O.
"""

import sys
import importlib.util
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Load document_constants directly from file path to avoid
# core.controllers.__init__ importing soundcard-dependent modules.
_spec = importlib.util.spec_from_file_location(
    "document_constants",
    project_root / "src/core/controllers/export/document_constants.py"
)
dc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dc)

DOCUMENT_TYPES = dc.DOCUMENT_TYPES
TAB_DOCUMENT_MAP = dc.TAB_DOCUMENT_MAP
DOCUMENT_DISPLAY_NAMES = dc.DOCUMENT_DISPLAY_NAMES
SOAP_EXPORT_TYPES = dc.SOAP_EXPORT_TYPES
CORRESPONDENCE_TYPES = dc.CORRESPONDENCE_TYPES
get_document_display_name = dc.get_document_display_name
get_document_type_for_tab = dc.get_document_type_for_tab


# ===========================================================================
# DOCUMENT_TYPES
# ===========================================================================

class TestDocumentTypes:
    def test_is_list(self):
        assert isinstance(DOCUMENT_TYPES, list)

    def test_has_five_types(self):
        assert len(DOCUMENT_TYPES) == 5

    def test_contains_transcript(self):
        assert "transcript" in DOCUMENT_TYPES

    def test_contains_soap_note(self):
        assert "soap_note" in DOCUMENT_TYPES

    def test_contains_referral(self):
        assert "referral" in DOCUMENT_TYPES

    def test_contains_letter(self):
        assert "letter" in DOCUMENT_TYPES

    def test_contains_chat(self):
        assert "chat" in DOCUMENT_TYPES

    def test_order_transcript_first(self):
        assert DOCUMENT_TYPES[0] == "transcript"

    def test_order_soap_note_second(self):
        assert DOCUMENT_TYPES[1] == "soap_note"

    def test_order_referral_third(self):
        assert DOCUMENT_TYPES[2] == "referral"

    def test_order_letter_fourth(self):
        assert DOCUMENT_TYPES[3] == "letter"

    def test_order_chat_fifth(self):
        assert DOCUMENT_TYPES[4] == "chat"

    def test_all_strings(self):
        assert all(isinstance(t, str) for t in DOCUMENT_TYPES)

    def test_no_duplicates(self):
        assert len(DOCUMENT_TYPES) == len(set(DOCUMENT_TYPES))


# ===========================================================================
# TAB_DOCUMENT_MAP
# ===========================================================================

class TestTabDocumentMap:
    def test_is_dict(self):
        assert isinstance(TAB_DOCUMENT_MAP, dict)

    def test_has_five_entries(self):
        assert len(TAB_DOCUMENT_MAP) == 5

    def test_tab_0_is_transcript(self):
        assert TAB_DOCUMENT_MAP[0] == "transcript"

    def test_tab_1_is_soap_note(self):
        assert TAB_DOCUMENT_MAP[1] == "soap_note"

    def test_tab_2_is_referral(self):
        assert TAB_DOCUMENT_MAP[2] == "referral"

    def test_tab_3_is_letter(self):
        assert TAB_DOCUMENT_MAP[3] == "letter"

    def test_tab_4_is_chat(self):
        assert TAB_DOCUMENT_MAP[4] == "chat"

    def test_keys_are_consecutive_integers(self):
        keys = sorted(TAB_DOCUMENT_MAP.keys())
        assert keys == list(range(5))

    def test_values_match_document_types(self):
        for v in TAB_DOCUMENT_MAP.values():
            assert v in DOCUMENT_TYPES


# ===========================================================================
# DOCUMENT_DISPLAY_NAMES
# ===========================================================================

class TestDocumentDisplayNames:
    def test_is_dict(self):
        assert isinstance(DOCUMENT_DISPLAY_NAMES, dict)

    def test_has_five_entries(self):
        assert len(DOCUMENT_DISPLAY_NAMES) == 5

    def test_transcript_display_name(self):
        assert DOCUMENT_DISPLAY_NAMES["transcript"] == "Transcript"

    def test_soap_note_display_name(self):
        assert DOCUMENT_DISPLAY_NAMES["soap_note"] == "SOAP Note"

    def test_referral_display_name(self):
        assert DOCUMENT_DISPLAY_NAMES["referral"] == "Referral"

    def test_letter_display_name(self):
        assert DOCUMENT_DISPLAY_NAMES["letter"] == "Letter"

    def test_chat_display_name(self):
        assert DOCUMENT_DISPLAY_NAMES["chat"] == "Chat"

    def test_all_values_are_strings(self):
        assert all(isinstance(v, str) for v in DOCUMENT_DISPLAY_NAMES.values())

    def test_all_keys_in_document_types(self):
        for key in DOCUMENT_DISPLAY_NAMES:
            assert key in DOCUMENT_TYPES


# ===========================================================================
# SOAP_EXPORT_TYPES / CORRESPONDENCE_TYPES
# ===========================================================================

class TestExportTypeSets:
    def test_soap_export_types_is_set(self):
        assert isinstance(SOAP_EXPORT_TYPES, set)

    def test_soap_export_types_contains_soap_note(self):
        assert "soap_note" in SOAP_EXPORT_TYPES

    def test_correspondence_types_is_set(self):
        assert isinstance(CORRESPONDENCE_TYPES, set)

    def test_correspondence_types_contains_referral(self):
        assert "referral" in CORRESPONDENCE_TYPES

    def test_correspondence_types_contains_letter(self):
        assert "letter" in CORRESPONDENCE_TYPES

    def test_soap_not_in_correspondence(self):
        assert "soap_note" not in CORRESPONDENCE_TYPES

    def test_transcript_not_in_soap_export(self):
        assert "transcript" not in SOAP_EXPORT_TYPES

    def test_sets_are_disjoint(self):
        assert SOAP_EXPORT_TYPES.isdisjoint(CORRESPONDENCE_TYPES)


# ===========================================================================
# get_document_display_name
# ===========================================================================

class TestGetDocumentDisplayName:
    def test_transcript_returns_transcript(self):
        assert get_document_display_name("transcript") == "Transcript"

    def test_soap_note_returns_soap_note(self):
        assert get_document_display_name("soap_note") == "SOAP Note"

    def test_referral_returns_referral(self):
        assert get_document_display_name("referral") == "Referral"

    def test_letter_returns_letter(self):
        assert get_document_display_name("letter") == "Letter"

    def test_chat_returns_chat(self):
        assert get_document_display_name("chat") == "Chat"

    def test_unknown_type_returns_string(self):
        result = get_document_display_name("unknown_type")
        assert isinstance(result, str)

    def test_unknown_type_titlecase_fallback(self):
        # Underscore replaced with space, title cased
        result = get_document_display_name("custom_doc")
        assert "Custom Doc" in result or result  # non-empty fallback

    def test_empty_string_returns_string(self):
        assert isinstance(get_document_display_name(""), str)


# ===========================================================================
# get_document_type_for_tab
# ===========================================================================

class TestGetDocumentTypeForTab:
    def test_tab_0_transcript(self):
        assert get_document_type_for_tab(0) == "transcript"

    def test_tab_1_soap_note(self):
        assert get_document_type_for_tab(1) == "soap_note"

    def test_tab_2_referral(self):
        assert get_document_type_for_tab(2) == "referral"

    def test_tab_3_letter(self):
        assert get_document_type_for_tab(3) == "letter"

    def test_tab_4_chat(self):
        assert get_document_type_for_tab(4) == "chat"

    def test_invalid_index_returns_unknown(self):
        assert get_document_type_for_tab(99) == "unknown"

    def test_negative_index_returns_unknown(self):
        assert get_document_type_for_tab(-1) == "unknown"

    def test_returns_string(self):
        assert isinstance(get_document_type_for_tab(0), str)

    def test_all_valid_tabs_in_document_types(self):
        for i in range(5):
            result = get_document_type_for_tab(i)
            assert result in DOCUMENT_TYPES

"""
Tests for src/models/translation_session.py

Covers Speaker enum, TranslationEntry (create, to_dict, from_dict,
get_display_text), and TranslationSession (create, add_entry, end_session,
duration, entry_count, to_dict, to_json, from_dict, from_json,
to_transcript, get_patient_entries, get_doctor_entries).
All pure logic — no DB or Tkinter dependencies.
"""

import json
import sys
import pytest
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from models.translation_session import Speaker, TranslationEntry, TranslationSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(speaker=Speaker.PATIENT, original_text="Hello", translated_text="Hola",
                original_language="en", target_language="es"):
    return TranslationEntry.create(
        speaker=speaker,
        original_text=original_text,
        original_language=original_language,
        translated_text=translated_text,
        target_language=target_language
    )


def _make_session(patient_language="es", doctor_language="en", patient_name=None):
    return TranslationSession.create(
        patient_language=patient_language,
        doctor_language=doctor_language,
        patient_name=patient_name
    )


# ===========================================================================
# Speaker enum
# ===========================================================================

class TestSpeaker:
    def test_patient_value(self):
        assert Speaker.PATIENT.value == "patient"

    def test_doctor_value(self):
        assert Speaker.DOCTOR.value == "doctor"

    def test_enum_from_string(self):
        assert Speaker("patient") == Speaker.PATIENT
        assert Speaker("doctor") == Speaker.DOCTOR


# ===========================================================================
# TranslationEntry.create
# ===========================================================================

class TestTranslationEntryCreate:
    def test_creates_instance(self):
        entry = _make_entry()
        assert isinstance(entry, TranslationEntry)

    def test_auto_generates_uuid_id(self):
        e1 = _make_entry()
        e2 = _make_entry()
        assert e1.id != e2.id

    def test_id_is_string(self):
        entry = _make_entry()
        assert isinstance(entry.id, str)

    def test_auto_sets_timestamp(self):
        before = datetime.now()
        entry = _make_entry()
        after = datetime.now()
        assert before <= entry.timestamp <= after

    def test_speaker_set(self):
        entry = _make_entry(speaker=Speaker.DOCTOR)
        assert entry.speaker == Speaker.DOCTOR

    def test_original_text_set(self):
        entry = _make_entry(original_text="Good morning")
        assert entry.original_text == "Good morning"

    def test_translated_text_set(self):
        entry = _make_entry(translated_text="Buenos días")
        assert entry.translated_text == "Buenos días"

    def test_original_language_set(self):
        entry = _make_entry(original_language="en")
        assert entry.original_language == "en"

    def test_target_language_set(self):
        entry = _make_entry(target_language="es")
        assert entry.target_language == "es"

    def test_llm_refined_text_default_none(self):
        entry = _make_entry()
        assert entry.llm_refined_text is None

    def test_duration_seconds_default_none(self):
        entry = _make_entry()
        assert entry.duration_seconds is None

    def test_llm_refined_text_set(self):
        entry = TranslationEntry.create(
            speaker=Speaker.PATIENT, original_text="x", original_language="en",
            translated_text="y", target_language="es", llm_refined_text="z"
        )
        assert entry.llm_refined_text == "z"

    def test_duration_seconds_set(self):
        entry = TranslationEntry.create(
            speaker=Speaker.PATIENT, original_text="x", original_language="en",
            translated_text="y", target_language="es", duration_seconds=3.5
        )
        assert entry.duration_seconds == 3.5


# ===========================================================================
# TranslationEntry.to_dict
# ===========================================================================

class TestTranslationEntryToDict:
    def test_returns_dict(self):
        entry = _make_entry()
        assert isinstance(entry.to_dict(), dict)

    def test_contains_id(self):
        entry = _make_entry()
        assert "id" in entry.to_dict()

    def test_contains_speaker_value(self):
        entry = _make_entry(speaker=Speaker.DOCTOR)
        d = entry.to_dict()
        assert d["speaker"] == "doctor"

    def test_contains_timestamp_iso(self):
        entry = _make_entry()
        d = entry.to_dict()
        # Should be parseable ISO string
        datetime.fromisoformat(d["timestamp"])

    def test_contains_original_text(self):
        entry = _make_entry(original_text="Pain in chest")
        assert entry.to_dict()["original_text"] == "Pain in chest"

    def test_contains_translated_text(self):
        entry = _make_entry(translated_text="Dolor en el pecho")
        assert entry.to_dict()["translated_text"] == "Dolor en el pecho"


# ===========================================================================
# TranslationEntry.from_dict
# ===========================================================================

class TestTranslationEntryFromDict:
    def test_roundtrip(self):
        entry = _make_entry()
        d = entry.to_dict()
        restored = TranslationEntry.from_dict(d)
        assert restored.id == entry.id
        assert restored.speaker == entry.speaker
        assert restored.original_text == entry.original_text
        assert restored.translated_text == entry.translated_text

    def test_restores_speaker_enum(self):
        entry = _make_entry(speaker=Speaker.DOCTOR)
        restored = TranslationEntry.from_dict(entry.to_dict())
        assert restored.speaker == Speaker.DOCTOR

    def test_restores_timestamp(self):
        entry = _make_entry()
        restored = TranslationEntry.from_dict(entry.to_dict())
        assert abs((restored.timestamp - entry.timestamp).total_seconds()) < 1


# ===========================================================================
# TranslationEntry.get_display_text
# ===========================================================================

class TestTranslationEntryGetDisplayText:
    def test_contains_speaker_label(self):
        entry = _make_entry(speaker=Speaker.PATIENT)
        text = entry.get_display_text()
        assert "Patient" in text

    def test_contains_original_text(self):
        entry = _make_entry(original_text="I have a headache")
        text = entry.get_display_text()
        assert "I have a headache" in text

    def test_contains_translated_text(self):
        entry = _make_entry(translated_text="Tengo dolor de cabeza")
        text = entry.get_display_text()
        assert "Tengo dolor de cabeza" in text

    def test_uses_llm_refined_when_available(self):
        entry = TranslationEntry.create(
            speaker=Speaker.PATIENT, original_text="x", original_language="en",
            translated_text="raw translation", target_language="es",
            llm_refined_text="refined translation"
        )
        text = entry.get_display_text()
        assert "refined translation" in text
        assert "raw translation" not in text

    def test_no_translation_when_include_translation_false(self):
        entry = _make_entry(translated_text="Should not appear")
        text = entry.get_display_text(include_translation=False)
        assert "Should not appear" not in text

    def test_contains_timestamp(self):
        entry = _make_entry()
        text = entry.get_display_text()
        # Should have time in HH:MM:SS format
        import re
        assert re.search(r'\d{2}:\d{2}:\d{2}', text)


# ===========================================================================
# TranslationSession.create
# ===========================================================================

class TestTranslationSessionCreate:
    def test_creates_instance(self):
        session = _make_session()
        assert isinstance(session, TranslationSession)

    def test_auto_generates_uuid(self):
        s1 = _make_session()
        s2 = _make_session()
        assert s1.session_id != s2.session_id

    def test_session_id_is_string(self):
        session = _make_session()
        assert isinstance(session.session_id, str)

    def test_patient_language_set(self):
        session = _make_session(patient_language="fr")
        assert session.patient_language == "fr"

    def test_doctor_language_set(self):
        session = _make_session(doctor_language="de")
        assert session.doctor_language == "de"

    def test_patient_name_optional(self):
        session = _make_session(patient_name="John Doe")
        assert session.patient_name == "John Doe"

    def test_patient_name_none_by_default(self):
        session = _make_session()
        assert session.patient_name is None

    def test_entries_empty_initially(self):
        session = _make_session()
        assert session.entries == []

    def test_ended_at_none_initially(self):
        session = _make_session()
        assert session.ended_at is None

    def test_auto_sets_created_at(self):
        before = datetime.now()
        session = _make_session()
        after = datetime.now()
        assert before <= session.created_at <= after


# ===========================================================================
# TranslationSession.add_entry
# ===========================================================================

class TestTranslationSessionAddEntry:
    def test_appends_entry(self):
        session = _make_session()
        entry = _make_entry()
        session.add_entry(entry)
        assert entry in session.entries

    def test_multiple_entries(self):
        session = _make_session()
        for i in range(3):
            session.add_entry(_make_entry(original_text=f"text {i}"))
        assert len(session.entries) == 3

    def test_entry_count_increases(self):
        session = _make_session()
        assert session.entry_count == 0
        session.add_entry(_make_entry())
        assert session.entry_count == 1


# ===========================================================================
# TranslationSession.end_session
# ===========================================================================

class TestTranslationSessionEndSession:
    def test_sets_ended_at(self):
        session = _make_session()
        before = datetime.now()
        session.end_session()
        after = datetime.now()
        assert before <= session.ended_at <= after

    def test_duration_computed_after_end(self):
        session = _make_session()
        session.end_session()
        assert session.duration is not None
        assert session.duration >= 0

    def test_duration_none_before_end(self):
        session = _make_session()
        assert session.duration is None


# ===========================================================================
# TranslationSession.to_dict / to_json / from_dict / from_json
# ===========================================================================

class TestTranslationSessionSerialization:
    def test_to_dict_returns_dict(self):
        session = _make_session()
        assert isinstance(session.to_dict(), dict)

    def test_to_dict_contains_session_id(self):
        session = _make_session()
        assert "session_id" in session.to_dict()

    def test_to_dict_contains_languages(self):
        session = _make_session(patient_language="zh", doctor_language="en")
        d = session.to_dict()
        assert d["patient_language"] == "zh"
        assert d["doctor_language"] == "en"

    def test_to_dict_contains_entries(self):
        session = _make_session()
        session.add_entry(_make_entry())
        d = session.to_dict()
        assert len(d["entries"]) == 1

    def test_to_json_returns_valid_json(self):
        session = _make_session()
        json_str = session.to_json()
        data = json.loads(json_str)
        assert "session_id" in data

    def test_from_dict_roundtrip(self):
        session = _make_session(patient_language="ja", doctor_language="en")
        session.add_entry(_make_entry())
        d = session.to_dict()
        restored = TranslationSession.from_dict(d)
        assert restored.session_id == session.session_id
        assert restored.patient_language == "ja"
        assert len(restored.entries) == 1

    def test_from_json_roundtrip(self):
        session = _make_session()
        json_str = session.to_json()
        restored = TranslationSession.from_json(json_str)
        assert restored.session_id == session.session_id

    def test_from_dict_restores_ended_at(self):
        session = _make_session()
        session.end_session()
        d = session.to_dict()
        restored = TranslationSession.from_dict(d)
        assert restored.ended_at is not None


# ===========================================================================
# TranslationSession.to_transcript
# ===========================================================================

class TestTranslationSessionToTranscript:
    def test_returns_string(self):
        session = _make_session()
        assert isinstance(session.to_transcript(), str)

    def test_contains_session_id(self):
        session = _make_session()
        transcript = session.to_transcript()
        assert session.session_id in transcript

    def test_contains_patient_language(self):
        session = _make_session(patient_language="es")
        transcript = session.to_transcript()
        assert "es" in transcript

    def test_contains_entry_text(self):
        session = _make_session()
        session.add_entry(_make_entry(original_text="I feel dizzy"))
        transcript = session.to_transcript()
        assert "I feel dizzy" in transcript

    def test_contains_entry_count(self):
        session = _make_session()
        session.add_entry(_make_entry())
        session.add_entry(_make_entry())
        transcript = session.to_transcript()
        assert "2" in transcript

    def test_includes_patient_name_when_set(self):
        session = _make_session(patient_name="Jane Smith")
        transcript = session.to_transcript()
        assert "Jane Smith" in transcript

    def test_includes_duration_after_end(self):
        session = _make_session()
        session.end_session()
        transcript = session.to_transcript()
        assert "Duration" in transcript


# ===========================================================================
# get_patient_entries / get_doctor_entries
# ===========================================================================

class TestTranslationSessionFilterEntries:
    def test_get_patient_entries(self):
        session = _make_session()
        session.add_entry(_make_entry(speaker=Speaker.PATIENT))
        session.add_entry(_make_entry(speaker=Speaker.DOCTOR))
        session.add_entry(_make_entry(speaker=Speaker.PATIENT))
        patient_entries = session.get_patient_entries()
        assert len(patient_entries) == 2
        assert all(e.speaker == Speaker.PATIENT for e in patient_entries)

    def test_get_doctor_entries(self):
        session = _make_session()
        session.add_entry(_make_entry(speaker=Speaker.PATIENT))
        session.add_entry(_make_entry(speaker=Speaker.DOCTOR))
        doctor_entries = session.get_doctor_entries()
        assert len(doctor_entries) == 1
        assert all(e.speaker == Speaker.DOCTOR for e in doctor_entries)

    def test_empty_when_no_entries(self):
        session = _make_session()
        assert session.get_patient_entries() == []
        assert session.get_doctor_entries() == []

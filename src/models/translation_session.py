"""
Translation Session Data Models

Provides data structures for tracking translation conversations between
doctors and patients, with support for persistence and export.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional
from enum import Enum


class Speaker(Enum):
    """Identifies the speaker in a translation exchange."""
    PATIENT = "patient"
    DOCTOR = "doctor"


@dataclass
class TranslationEntry:
    """A single translation exchange in a conversation.

    Represents one utterance from either the patient or doctor,
    along with its translation.
    """
    id: str
    speaker: Speaker
    timestamp: datetime
    original_text: str
    original_language: str
    translated_text: str
    target_language: str
    llm_refined_text: Optional[str] = None
    duration_seconds: Optional[float] = None

    @classmethod
    def create(
        cls,
        speaker: Speaker,
        original_text: str,
        original_language: str,
        translated_text: str,
        target_language: str,
        llm_refined_text: Optional[str] = None,
        duration_seconds: Optional[float] = None
    ) -> 'TranslationEntry':
        """Create a new TranslationEntry with auto-generated ID and timestamp."""
        return cls(
            id=str(uuid.uuid4()),
            speaker=speaker,
            timestamp=datetime.now(),
            original_text=original_text,
            original_language=original_language,
            translated_text=translated_text,
            target_language=target_language,
            llm_refined_text=llm_refined_text,
            duration_seconds=duration_seconds
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'speaker': self.speaker.value,
            'timestamp': self.timestamp.isoformat(),
            'original_text': self.original_text,
            'original_language': self.original_language,
            'translated_text': self.translated_text,
            'target_language': self.target_language,
            'llm_refined_text': self.llm_refined_text,
            'duration_seconds': self.duration_seconds
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'TranslationEntry':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            speaker=Speaker(data['speaker']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            original_text=data['original_text'],
            original_language=data['original_language'],
            translated_text=data['translated_text'],
            target_language=data['target_language'],
            llm_refined_text=data.get('llm_refined_text'),
            duration_seconds=data.get('duration_seconds')
        )

    def get_display_text(self, include_translation: bool = True) -> str:
        """Get formatted text for display."""
        time_str = self.timestamp.strftime("%H:%M:%S")
        speaker_label = self.speaker.value.title()

        text = f"[{time_str}] {speaker_label}\n"
        text += f"[{self.original_language}] {self.original_text}\n"

        if include_translation:
            display_translation = self.llm_refined_text or self.translated_text
            text += f"[{self.target_language}] {display_translation}"

        return text


@dataclass
class TranslationSession:
    """A complete translation session between doctor and patient.

    Contains all translation exchanges for a single consultation,
    with metadata for tracking and export.
    """
    session_id: str
    created_at: datetime
    patient_language: str
    doctor_language: str
    entries: List[TranslationEntry] = field(default_factory=list)
    patient_name: Optional[str] = None
    recording_id: Optional[int] = None
    notes: Optional[str] = None
    ended_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        patient_language: str,
        doctor_language: str,
        patient_name: Optional[str] = None,
        recording_id: Optional[int] = None
    ) -> 'TranslationSession':
        """Create a new TranslationSession with auto-generated ID and timestamp."""
        return cls(
            session_id=str(uuid.uuid4()),
            created_at=datetime.now(),
            patient_language=patient_language,
            doctor_language=doctor_language,
            patient_name=patient_name,
            recording_id=recording_id
        )

    def add_entry(self, entry: TranslationEntry) -> None:
        """Add a translation entry to the session."""
        self.entries.append(entry)

    def end_session(self) -> None:
        """Mark the session as ended."""
        self.ended_at = datetime.now()

    @property
    def duration(self) -> Optional[float]:
        """Get session duration in seconds."""
        if self.ended_at:
            return (self.ended_at - self.created_at).total_seconds()
        return None

    @property
    def entry_count(self) -> int:
        """Get the number of entries in the session."""
        return len(self.entries)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'session_id': self.session_id,
            'created_at': self.created_at.isoformat(),
            'patient_language': self.patient_language,
            'doctor_language': self.doctor_language,
            'entries': [entry.to_dict() for entry in self.entries],
            'patient_name': self.patient_name,
            'recording_id': self.recording_id,
            'notes': self.notes,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict) -> 'TranslationSession':
        """Create from dictionary."""
        session = cls(
            session_id=data['session_id'],
            created_at=datetime.fromisoformat(data['created_at']),
            patient_language=data['patient_language'],
            doctor_language=data['doctor_language'],
            patient_name=data.get('patient_name'),
            recording_id=data.get('recording_id'),
            notes=data.get('notes'),
            ended_at=datetime.fromisoformat(data['ended_at']) if data.get('ended_at') else None
        )
        session.entries = [
            TranslationEntry.from_dict(entry_data)
            for entry_data in data.get('entries', [])
        ]
        return session

    @classmethod
    def from_json(cls, json_str: str) -> 'TranslationSession':
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def to_transcript(self, include_both_languages: bool = True, include_timestamps: bool = True) -> str:
        """Export session as a formatted transcript.

        Args:
            include_both_languages: Include both original and translated text
            include_timestamps: Include timestamps for each entry

        Returns:
            Formatted transcript string
        """
        lines = []

        # Header
        lines.append("=" * 60)
        lines.append("TRANSLATION SESSION TRANSCRIPT")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Session ID: {self.session_id}")
        lines.append(f"Date: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Patient Language: {self.patient_language}")
        lines.append(f"Doctor Language: {self.doctor_language}")

        if self.patient_name:
            lines.append(f"Patient Name: {self.patient_name}")

        if self.recording_id:
            lines.append(f"Recording ID: {self.recording_id}")

        if self.ended_at:
            duration_mins = self.duration / 60 if self.duration else 0
            lines.append(f"Duration: {duration_mins:.1f} minutes")

        lines.append("")
        lines.append("-" * 60)
        lines.append("CONVERSATION")
        lines.append("-" * 60)
        lines.append("")

        # Entries
        for entry in self.entries:
            speaker_label = entry.speaker.value.upper()

            if include_timestamps:
                time_str = entry.timestamp.strftime("%H:%M:%S")
                lines.append(f"[{time_str}] {speaker_label}:")
            else:
                lines.append(f"{speaker_label}:")

            # Original text
            lines.append(f"  [{entry.original_language}] {entry.original_text}")

            # Translation
            if include_both_languages:
                display_translation = entry.llm_refined_text or entry.translated_text
                lines.append(f"  [{entry.target_language}] {display_translation}")

            lines.append("")

        # Footer
        lines.append("-" * 60)
        lines.append(f"Total exchanges: {self.entry_count}")

        if self.notes:
            lines.append("")
            lines.append("NOTES:")
            lines.append(self.notes)

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def get_patient_entries(self) -> List[TranslationEntry]:
        """Get all entries from the patient."""
        return [e for e in self.entries if e.speaker == Speaker.PATIENT]

    def get_doctor_entries(self) -> List[TranslationEntry]:
        """Get all entries from the doctor."""
        return [e for e in self.entries if e.speaker == Speaker.DOCTOR]

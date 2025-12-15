"""
Vocabulary Manager - Singleton manager for vocabulary corrections.

This manager handles:
- Loading/saving vocabulary settings
- Applying corrections to transcripts
- CRUD operations for vocabulary entries
- Import/export functionality
"""

import logging
import json
import csv
import threading
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from settings.settings import SETTINGS, save_settings
from utils.vocabulary_corrector import VocabularyCorrector, CorrectionResult


class VocabularyManager:
    """Manages vocabulary corrections and settings.

    This is a singleton class that provides:
    - Correction application via VocabularyCorrector
    - Settings persistence
    - CRUD operations for vocabulary entries
    - Import/export to CSV/JSON
    """

    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self):
        """Initialize the vocabulary manager."""
        self.logger = logging.getLogger(__name__)
        self.corrector = VocabularyCorrector()
        self._load_settings()

    @classmethod
    def get_instance(cls) -> 'VocabularyManager':
        """Get or create the singleton instance (thread-safe).

        Returns:
            VocabularyManager instance
        """
        if cls._instance is None:
            with cls._instance_lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = VocabularyManager()
        return cls._instance

    def _load_settings(self):
        """Load vocabulary settings from SETTINGS."""
        vocab_settings = SETTINGS.get("custom_vocabulary", {})
        self._enabled = vocab_settings.get("enabled", True)
        self._default_specialty = vocab_settings.get("default_specialty", "general")
        self._categories = vocab_settings.get("categories", [
            "doctor_names", "medication_names", "medical_terminology", "abbreviations", "general"
        ])
        self._specialties = vocab_settings.get("specialties", [
            "general", "cardiology", "orthopedics", "neurology", "pediatrics",
            "general_practice", "surgery", "psychiatry", "dermatology",
            "gastroenterology", "pulmonology", "endocrinology"
        ])
        self._corrections = vocab_settings.get("corrections", {})

    def _save_settings(self):
        """Save vocabulary settings to SETTINGS."""
        SETTINGS["custom_vocabulary"] = {
            "enabled": self._enabled,
            "default_specialty": self._default_specialty,
            "categories": self._categories,
            "specialties": self._specialties,
            "corrections": self._corrections
        }
        save_settings(SETTINGS)
        self.logger.info("Vocabulary settings saved")

    def save_settings(self):
        """Public method to save vocabulary settings.

        Call this after making changes via the dialog.
        """
        self._save_settings()

    def reload_settings(self):
        """Reload settings from SETTINGS dict.

        Call this after external changes to settings.
        """
        self._load_settings()
        self.corrector.clear_cache()
        self.logger.info("Vocabulary settings reloaded")

    @property
    def enabled(self) -> bool:
        """Check if vocabulary correction is enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        """Enable or disable vocabulary correction."""
        self._enabled = value
        self._save_settings()

    @property
    def default_specialty(self) -> str:
        """Get default specialty context."""
        return self._default_specialty

    @default_specialty.setter
    def default_specialty(self, value: str):
        """Set default specialty context."""
        self._default_specialty = value
        self._save_settings()

    @property
    def categories(self) -> List[str]:
        """Get available categories."""
        return self._categories.copy()

    @property
    def specialties(self) -> List[str]:
        """Get available specialties."""
        return self._specialties.copy()

    @property
    def corrections(self) -> Dict[str, Dict]:
        """Get all corrections (read-only copy)."""
        return self._corrections.copy()

    def correct_transcript(
        self,
        text: str,
        specialty: Optional[str] = None
    ) -> str:
        """Apply vocabulary corrections to transcript text.

        This is the main entry point for transcript correction.

        Args:
            text: Transcript text to correct
            specialty: Medical specialty context (uses default if None)

        Returns:
            Corrected transcript text
        """
        if not self._enabled:
            return text

        if not text:
            return text

        specialty = specialty or self._default_specialty

        result = self.corrector.apply_corrections(
            text,
            self._corrections,
            specialty
        )

        if result.total_replacements > 0:
            self.logger.info(
                f"Applied {result.total_replacements} vocabulary corrections "
                f"(specialty: {specialty})"
            )

        return result.corrected_text

    def correct_transcript_with_details(
        self,
        text: str,
        specialty: Optional[str] = None
    ) -> CorrectionResult:
        """Apply corrections and return detailed result.

        Args:
            text: Transcript text to correct
            specialty: Medical specialty context

        Returns:
            CorrectionResult with full details
        """
        if not self._enabled:
            return CorrectionResult(
                original_text=text,
                corrected_text=text,
                specialty_used=specialty or self._default_specialty
            )

        specialty = specialty or self._default_specialty
        return self.corrector.apply_corrections(
            text,
            self._corrections,
            specialty
        )

    # CRUD Operations

    def get_correction(self, find_text: str) -> Optional[Dict]:
        """Get a specific correction by find text.

        Args:
            find_text: The text to find

        Returns:
            Correction dict or None if not found
        """
        return self._corrections.get(find_text)

    def add_correction(
        self,
        find_text: str,
        replacement: str,
        category: str = "general",
        specialty: Optional[str] = None,
        case_sensitive: bool = False,
        priority: int = 0,
        enabled: bool = True
    ) -> bool:
        """Add a new vocabulary correction.

        Args:
            find_text: Text to find in transcripts
            replacement: Replacement text
            category: Category (doctor_names, medications, etc.)
            specialty: Medical specialty or None for all
            case_sensitive: Whether to match case
            priority: Higher priority runs first
            enabled: Whether this correction is active

        Returns:
            True if added successfully
        """
        if not find_text or not replacement:
            return False

        self._corrections[find_text] = {
            "replacement": replacement,
            "category": category,
            "specialty": specialty,
            "case_sensitive": case_sensitive,
            "priority": priority,
            "enabled": enabled
        }

        self.corrector.clear_cache()
        self._save_settings()
        return True

    def update_correction(
        self,
        original_find_text: str,
        new_find_text: str,
        replacement: str,
        category: str = "general",
        specialty: Optional[str] = None,
        case_sensitive: bool = False,
        priority: int = 0,
        enabled: bool = True
    ) -> bool:
        """Update an existing vocabulary correction.

        Args:
            original_find_text: Original find text (key)
            new_find_text: New find text (may be same as original)
            replacement: Replacement text
            category: Category
            specialty: Medical specialty or None
            case_sensitive: Whether to match case
            priority: Priority level
            enabled: Whether active

        Returns:
            True if updated successfully
        """
        if not new_find_text or not replacement:
            return False

        # Remove old entry if find text changed
        if original_find_text != new_find_text and original_find_text in self._corrections:
            del self._corrections[original_find_text]

        # Add/update entry
        self._corrections[new_find_text] = {
            "replacement": replacement,
            "category": category,
            "specialty": specialty,
            "case_sensitive": case_sensitive,
            "priority": priority,
            "enabled": enabled
        }

        self.corrector.clear_cache()
        self._save_settings()
        return True

    def delete_correction(self, find_text: str) -> bool:
        """Delete a vocabulary correction.

        Args:
            find_text: The find text to delete

        Returns:
            True if deleted, False if not found
        """
        if find_text in self._corrections:
            del self._corrections[find_text]
            self.corrector.clear_cache()
            self._save_settings()
            return True
        return False

    def get_corrections_by_category(self, category: str) -> Dict[str, Dict]:
        """Get all corrections in a category.

        Args:
            category: Category to filter by

        Returns:
            Dict of corrections in that category
        """
        return {
            k: v for k, v in self._corrections.items()
            if v.get("category") == category
        }

    def get_corrections_by_specialty(self, specialty: str) -> Dict[str, Dict]:
        """Get all corrections for a specialty (includes general).

        Args:
            specialty: Specialty to filter by

        Returns:
            Dict of corrections for that specialty
        """
        return {
            k: v for k, v in self._corrections.items()
            if v.get("specialty") in (specialty, None, "general")
        }

    # Import/Export

    def export_to_json(self, file_path: str) -> int:
        """Export corrections to JSON file.

        Args:
            file_path: Path to save JSON file

        Returns:
            Number of entries exported
        """
        try:
            export_data = {
                "version": "1.0",
                "corrections": []
            }

            for find_text, rule in self._corrections.items():
                export_data["corrections"].append({
                    "find_text": find_text,
                    "replacement": rule.get("replacement", ""),
                    "category": rule.get("category", "general"),
                    "specialty": rule.get("specialty"),
                    "case_sensitive": rule.get("case_sensitive", False),
                    "priority": rule.get("priority", 0),
                    "enabled": rule.get("enabled", True)
                })

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2)

            self.logger.info(f"Exported {len(export_data['corrections'])} corrections to {file_path}")
            return len(export_data["corrections"])

        except Exception as e:
            self.logger.error(f"Failed to export JSON: {e}")
            return 0

    def import_from_json(self, file_path: str) -> Tuple[int, List[str]]:
        """Import corrections from JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            Tuple of (count imported, list of errors)
        """
        errors = []
        count = 0

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            corrections = data.get("corrections", [])

            for item in corrections:
                find_text = item.get("find_text", "").strip()
                replacement = item.get("replacement", "").strip()

                if not find_text or not replacement:
                    errors.append(f"Skipped entry with missing find_text or replacement")
                    continue

                self._corrections[find_text] = {
                    "replacement": replacement,
                    "category": item.get("category", "general"),
                    "specialty": item.get("specialty"),
                    "case_sensitive": item.get("case_sensitive", False),
                    "priority": item.get("priority", 0),
                    "enabled": item.get("enabled", True)
                }
                count += 1

            if count > 0:
                self.corrector.clear_cache()
                self._save_settings()

            self.logger.info(f"Imported {count} corrections from {file_path}")
            return count, errors

        except Exception as e:
            self.logger.error(f"Failed to import JSON: {e}")
            errors.append(str(e))
            return count, errors

    def export_to_csv(self, file_path: str) -> int:
        """Export corrections to CSV file.

        Args:
            file_path: Path to save CSV file

        Returns:
            Number of entries exported
        """
        try:
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'find_text', 'replacement', 'category', 'specialty',
                    'case_sensitive', 'priority', 'enabled'
                ])
                writer.writeheader()

                for find_text, rule in self._corrections.items():
                    writer.writerow({
                        'find_text': find_text,
                        'replacement': rule.get("replacement", ""),
                        'category': rule.get("category", "general"),
                        'specialty': rule.get("specialty", ""),
                        'case_sensitive': str(rule.get("case_sensitive", False)).lower(),
                        'priority': rule.get("priority", 0),
                        'enabled': str(rule.get("enabled", True)).lower()
                    })

            self.logger.info(f"Exported {len(self._corrections)} corrections to {file_path}")
            return len(self._corrections)

        except Exception as e:
            self.logger.error(f"Failed to export CSV: {e}")
            return 0

    def import_from_csv(self, file_path: str) -> Tuple[int, List[str]]:
        """Import corrections from CSV file.

        Expected columns: find_text, replacement, category, specialty,
                         case_sensitive, priority, enabled

        Args:
            file_path: Path to CSV file

        Returns:
            Tuple of (count imported, list of errors)
        """
        errors = []
        count = 0

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    find_text = row.get('find_text', '').strip()
                    replacement = row.get('replacement', '').strip()

                    if not find_text or not replacement:
                        errors.append(f"Row skipped: missing find_text or replacement")
                        continue

                    # Parse boolean fields
                    case_sensitive = row.get('case_sensitive', 'false').lower() == 'true'
                    enabled = row.get('enabled', 'true').lower() != 'false'

                    # Parse priority
                    try:
                        priority = int(row.get('priority', 0))
                    except ValueError:
                        priority = 0

                    # Handle specialty
                    specialty = row.get('specialty', '').strip()
                    if specialty == '' or specialty.lower() == 'none':
                        specialty = None

                    self._corrections[find_text] = {
                        "replacement": replacement,
                        "category": row.get('category', 'general'),
                        "specialty": specialty,
                        "case_sensitive": case_sensitive,
                        "priority": priority,
                        "enabled": enabled
                    }
                    count += 1

            if count > 0:
                self.corrector.clear_cache()
                self._save_settings()

            self.logger.info(f"Imported {count} corrections from {file_path}")
            return count, errors

        except Exception as e:
            self.logger.error(f"Failed to import CSV: {e}")
            errors.append(str(e))
            return count, errors

    def get_statistics(self) -> Dict[str, Any]:
        """Get vocabulary statistics.

        Returns:
            Dict with counts by category, specialty, etc.
        """
        by_category: Dict[str, int] = {}
        by_specialty: Dict[str, int] = {}
        enabled_count = 0

        for find_text, rule in self._corrections.items():
            # Count by category
            cat = rule.get("category", "general")
            by_category[cat] = by_category.get(cat, 0) + 1

            # Count by specialty
            spec = rule.get("specialty") or "general"
            by_specialty[spec] = by_specialty.get(spec, 0) + 1

            # Count enabled
            if rule.get("enabled", True):
                enabled_count += 1

        return {
            "total": len(self._corrections),
            "enabled": enabled_count,
            "disabled": len(self._corrections) - enabled_count,
            "by_category": by_category,
            "by_specialty": by_specialty
        }

    def reset_to_defaults(self):
        """Reset corrections to default set."""
        self._corrections = _get_default_corrections()
        self.corrector.clear_cache()
        self._save_settings()
        self.logger.info("Vocabulary reset to defaults")


def _get_default_corrections() -> Dict[str, Dict]:
    """Get default vocabulary corrections.

    Returns:
        Dict of default corrections
    """
    return {
        # Common doctor name corrections
        "dr smith": {
            "replacement": "Dr. Smith",
            "category": "doctor_names",
            "specialty": None,
            "case_sensitive": False,
            "priority": 0,
            "enabled": True
        },
        "dr jones": {
            "replacement": "Dr. Jones",
            "category": "doctor_names",
            "specialty": None,
            "case_sensitive": False,
            "priority": 0,
            "enabled": True
        },

        # Common medication corrections
        "asprin": {
            "replacement": "aspirin",
            "category": "medication_names",
            "specialty": None,
            "case_sensitive": False,
            "priority": 0,
            "enabled": True
        },
        "ibuprophen": {
            "replacement": "ibuprofen",
            "category": "medication_names",
            "specialty": None,
            "case_sensitive": False,
            "priority": 0,
            "enabled": True
        },
        "tylenol": {
            "replacement": "Tylenol",
            "category": "medication_names",
            "specialty": None,
            "case_sensitive": False,
            "priority": 0,
            "enabled": True
        },
        "metforman": {
            "replacement": "metformin",
            "category": "medication_names",
            "specialty": None,
            "case_sensitive": False,
            "priority": 0,
            "enabled": True
        },

        # Common abbreviations
        "htn": {
            "replacement": "hypertension",
            "category": "abbreviations",
            "specialty": "cardiology",
            "case_sensitive": False,
            "priority": 0,
            "enabled": True
        },
        "dm": {
            "replacement": "diabetes mellitus",
            "category": "abbreviations",
            "specialty": None,
            "case_sensitive": False,
            "priority": 0,
            "enabled": True
        },
        "sob": {
            "replacement": "shortness of breath",
            "category": "abbreviations",
            "specialty": None,
            "case_sensitive": False,
            "priority": 0,
            "enabled": True
        },
        "cp": {
            "replacement": "chest pain",
            "category": "abbreviations",
            "specialty": "cardiology",
            "case_sensitive": False,
            "priority": 0,
            "enabled": True
        },

        # Medical terminology
        "atelectisis": {
            "replacement": "atelectasis",
            "category": "medical_terminology",
            "specialty": "pulmonology",
            "case_sensitive": False,
            "priority": 0,
            "enabled": True
        },
    }


# Global instance accessor
def get_vocabulary_manager() -> VocabularyManager:
    """Get the global VocabularyManager instance.

    Returns:
        VocabularyManager singleton instance
    """
    return VocabularyManager.get_instance()


# Convenience function for direct use
vocabulary_manager = VocabularyManager.get_instance()
